#!/usr/bin/env python3
from contextlib import redirect_stderr, redirect_stdout
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest import mock


GX10_DIR = Path(__file__).resolve().parents[1]
ROOT = GX10_DIR.parents[1]
BASE_SCHEMA = GX10_DIR / 'sql' / 'initialize.sql'
INCIDENT_SCHEMA = GX10_DIR / 'sql' / 'incident-v1.sql'
PACKET_SCHEMA = GX10_DIR / 'sql' / 'reasoning-v1.sql'
INFERENCE_SCHEMA = GX10_DIR / 'sql' / 'inference-v1.sql'
CONFIG = GX10_DIR / 'config' / 'reasoning-runtime-v2.json'
PROMPT = GX10_DIR / 'prompts' / 'incident-assessment-v2.txt'
OUTPUT_SCHEMA = GX10_DIR / 'prompts' / 'incident-assessment-output-v2.json'
PRODUCER_PATH = GX10_DIR / 'sbin' / 'build-result-outbox.py'
COLLECTOR_GATE = ROOT / 'components' / 'collector' / 'sbin' / 'ai-results-gate'


def canonical_json(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_caller(database):
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        return load_module('result_outbox_caller', GX10_DIR / 'sbin' / 'run-local-reasoning.py')
    finally:
        if previous is None:
            del sys.modules['runtime_config']
        else:
            sys.modules['runtime_config'] = previous


class ResultOutboxTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / 'events.sqlite3'
        self.outbox = self.root / 'outbox'
        self.outbox.mkdir(mode=0o700)
        self.ready = self.outbox / 'ready'
        self.delivered = self.outbox / 'delivered'
        self.ready.mkdir(mode=0o700)
        self.delivered.mkdir(mode=0o700)
        connection = sqlite3.connect(self.database)
        for schema in (
            BASE_SCHEMA,
            INCIDENT_SCHEMA,
            PACKET_SCHEMA,
            INFERENCE_SCHEMA,
        ):
            connection.executescript(schema.read_text(encoding='utf-8'))
        connection.execute(
            '''
            INSERT INTO source_files (remote_path,status,discovered_at)
            VALUES ('/spool/synthetic','processed','2026-08-24T08:00:00+00:00')
            '''
        )
        self.event_id = connection.execute(
            '''
            INSERT INTO recent_events (
                source_file,record_number,timestamp,timestamp_epoch_ms,
                severity,message,event_json
            ) VALUES (
                '/spool/synthetic',1,'2026-08-24T08:00:00+00:00',
                1787558400000,'warning','synthetic','{}'
            )
            '''
        ).lastrowid
        self.incident_id = 'inc-v1-synthetic'
        connection.execute(
            '''
            INSERT INTO incidents (
                incident_id,correlation_key,status,event_family,protocol,
                entity_type,entity_key,severity,first_seen,
                first_seen_epoch_ms,last_seen,last_seen_epoch_ms,
                occurrence_count,repeat_count_total,
                observation_state_changes,last_observation_state,opened_at,
                recovering_at,resolved_at,last_event_id,context_json,
                engine_version,created_at,updated_at
            ) VALUES (
                ?,'synthetic-correlation','OPEN','interface','ethernet',
                'interface','INTERFACE|router.example.invalid|Ethernet1',
                'warning','2026-08-24T08:00:00+00:00',1787558400000,
                '2026-08-24T08:05:00+00:00',1787558700000,3,4,1,
                'down','2026-08-24T08:00:00+00:00',NULL,NULL,?,'{}',
                1,'2026-08-24T08:00:00+00:00',
                '2026-08-24T08:05:00+00:00'
            )
            ''',
            (self.incident_id, self.event_id),
        )
        connection.commit()
        connection.close()
        self.caller = load_caller(self.database)
        self.producer = load_module('result_outbox', PRODUCER_PATH)
        self.collector_validate = runpy.run_path(str(COLLECTOR_GATE))[
            'validate_record'
        ]
        self.packet_id = self.add_packet(1)

    def add_packet(self, sequence):
        packet_id = f'pkt-v1-synthetic-{sequence}'
        packet = canonical_json(
            {
                'created_at': '2026-08-24T08:05:00+00:00',
                'incident': {
                    'entity_type': 'interface',
                    'entity_key': 'INTERFACE|router.example.invalid|Ethernet1',
                    'first_seen': '2026-08-24T08:00:00+00:00',
                    'incident_id': self.incident_id,
                    'last_seen': '2026-08-24T08:05:00+00:00',
                    'occurrence_count': 3,
                    'severity': 'warning',
                    'status': 'OPEN',
                },
                'packet_id': packet_id,
                'packet_version': 1,
                'policy_version': 1,
                'schema': 'gx10-incident-reasoning-packet',
                'wake': {
                    'primary_reason': 'incident_opened',
                    'priority': 90 - sequence,
                    'reasons': ['incident_opened'],
                },
            }
        )
        connection = sqlite3.connect(self.database)
        connection.execute(
            '''
            INSERT INTO reasoning_packets (
                packet_id,incident_id,policy_version,packet_version,
                primary_reason,wake_reasons_json,priority,as_of_event_id,
                as_of_evidence_sequence,as_of_transition_sequence,
                basis_repeat_count_total,basis_state_change_count,
                basis_last_seen_epoch_ms,created_at,packet_json,packet_sha256
            ) VALUES (
                ?,?,1,1,'incident_opened','["incident_opened"]',?,?,
                ?,?,4,1,1787558700000,'2026-08-24T08:05:00+00:00',?,?
            )
            ''',
            (
                packet_id,
                self.incident_id,
                90 - sequence,
                self.event_id,
                sequence,
                sequence,
                packet,
                hashlib.sha256(packet.encode()).hexdigest(),
            ),
        )
        connection.commit()
        connection.close()
        return packet_id

    def output(self, packet_id):
        return {
            'schema': 'gx10-incident-assessment',
            'schema_version': self.caller.OUTPUT_SCHEMA_VERSION,
            'packet_id': packet_id,
            'incident_id': self.incident_id,
            'disposition': 'action_required',
            'severity': 'medium',
            'confidence': 78,
            'title': 'Synthetic interface incident',
            'summary': 'The packet reports an interface-down incident.',
            'likely_causes': [
                {
                    'cause': 'Physical or administrative interface change',
                    'basis': 'The deterministic packet reports interface down.',
                    'confidence': 60,
                }
            ],
            'recommended_actions': [
                {
                    'action': 'Inspect the current interface operational state.',
                    'priority': 1,
                    'risk': 'read_only',
                },
                {
                    'action': 'Review recently approved interface configuration changes.',
                    'priority': 2,
                    'risk': 'read_only',
                }
            ],
            'tags': ['incident_opened', 'open', 'warning'],
        }

    def response(self, packet_id):
        return json.dumps(
            {
                'model': self.caller.MODEL_REFERENCE,
                'done': True,
                'message': {
                    'role': 'assistant',
                    'content': json.dumps(self.output(packet_id)),
                },
            }
        ).encode()

    def invoke_success(self, packet_id):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = self.caller.run(
                self.database,
                config_path=CONFIG,
                prompt_path=PROMPT,
                output_schema_path=OUTPUT_SCHEMA,
                transport=lambda _: self.response(packet_id),
                now=lambda: '2026-08-24T08:10:00+00:00',
            )
        self.assertEqual(result, 0)

    def final_files(self):
        return sorted(self.ready.glob('ai-result-v1-*.jsonl'))

    def test_success_maps_to_valid_complete_collector_record_and_reuses(self):
        self.invoke_success(self.packet_id)
        first = self.producer.build(
            self.database, self.ready, self.delivered
        )
        self.assertEqual(first['total'], 1)
        self.assertEqual(first['created'], 1)
        path = self.final_files()[0]
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        raw = path.read_bytes()
        self.assertLessEqual(len(raw), self.producer.MAX_FILE_BYTES)
        self.assertEqual(raw.count(b'\n'), 1)
        self.assertTrue(raw.endswith(b'\n'))
        record = json.loads(raw)
        self.assertIsNone(self.collector_validate(record))
        self.assertEqual(record['result'], self.output(self.packet_id))
        self.assertEqual(
            record['provenance']['packet_id'], self.packet_id
        )
        self.assertEqual(record['provenance']['provider'], 'ollama')
        self.assertEqual(record['provenance']['run_attempt_number'], 1)
        self.assertEqual(record['provenance']['run_diagnostics'], {})
        self.assertEqual(
            record['provenance']['run_completed_at'], record['timestamp']
        )
        self.assertEqual(record['occurrence_count'], 3)
        self.assertEqual(record['device'], 'router.example.invalid')
        self.assertNotIn(self.packet_id, path.name)
        second = self.producer.build(
            self.database, self.ready, self.delivered
        )
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['reused'], 1)
        self.assertEqual(path.read_bytes(), raw)

    def test_legacy_record_without_device_is_reused(self):
        self.invoke_success(self.packet_id)
        self.producer.build(self.database, self.ready, self.delivered)
        path = self.final_files()[0]
        legacy = json.loads(path.read_text(encoding='utf-8'))
        del legacy['device']
        legacy_data = (canonical_json(legacy) + '\n').encode('utf-8')
        path.write_bytes(legacy_data)
        path.chmod(0o640)

        state = self.producer.build(
            self.database, self.ready, self.delivered
        )

        self.assertEqual(state['created'], 0)
        self.assertEqual(state['reused'], 1)
        self.assertEqual(path.read_bytes(), legacy_data)

    def test_terminal_failure_is_not_exported(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = self.caller.run(
                self.database,
                config_path=CONFIG,
                prompt_path=PROMPT,
                output_schema_path=OUTPUT_SCHEMA,
                transport=lambda _: (_ for _ in ()).throw(
                    self.caller.InferenceFailure('INFERENCE_UNAVAILABLE')
                ),
                now=lambda: '2026-08-24T08:10:00+00:00',
            )
        self.assertEqual(result, 1)
        state = self.producer.build(
            self.database, self.ready, self.delivered
        )
        self.assertEqual(state['total'], 0)
        self.assertEqual(self.final_files(), [])

    def test_exact_delivered_file_is_reused_without_recreation(self):
        self.invoke_success(self.packet_id)
        first = self.producer.build(
            self.database, self.ready, self.delivered
        )
        self.assertEqual(first['created'], 1)
        source = self.final_files()[0]
        target = self.delivered / source.name
        os.replace(source, target)
        state = self.producer.build(
            self.database, self.ready, self.delivered
        )
        self.assertEqual(state['created'], 0)
        self.assertEqual(state['reused'], 1)
        self.assertEqual(state['ready'], 0)
        self.assertEqual(state['delivered'], 1)
        self.assertEqual(self.final_files(), [])

    def test_duplicate_ready_and_delivered_state_is_refused(self):
        self.invoke_success(self.packet_id)
        self.producer.build(
            self.database, self.ready, self.delivered
        )
        source = self.final_files()[0]
        target = self.delivered / source.name
        target.write_bytes(source.read_bytes())
        target.chmod(0o640)
        with self.assertRaisesRegex(
            self.producer.OutboxError, 'state is duplicated'
        ):
            self.producer.build(
                self.database, self.ready, self.delivered
            )

    def test_divergent_target_fails_before_other_publication(self):
        self.invoke_success(self.packet_id)
        second_packet = self.add_packet(2)
        self.invoke_success(second_packet)
        records = self.producer.load_records(self.database)
        first_name = sorted(records)[0]
        divergent = self.ready / first_name
        divergent.write_bytes(b'{}\n')
        divergent.chmod(0o640)
        with self.assertRaisesRegex(
            self.producer.OutboxError, 'target differs'
        ):
            self.producer.build(
                self.database, self.ready, self.delivered
            )
        self.assertEqual(self.final_files(), [divergent])

    def test_crash_after_one_file_is_idempotently_resumed(self):
        self.invoke_success(self.packet_id)
        second_packet = self.add_packet(2)
        self.invoke_success(second_packet)
        original = self.producer.publish
        calls = []

        def interrupted(directory, name, data):
            created = original(directory, name, data)
            calls.append(name)
            if len(calls) == 1:
                raise OSError('synthetic interruption')
            return created

        with mock.patch.object(self.producer, 'publish', interrupted):
            with self.assertRaisesRegex(OSError, 'synthetic interruption'):
                self.producer.build(
                    self.database, self.ready, self.delivered
                )
        self.assertEqual(len(self.final_files()), 1)
        resumed = self.producer.build(
            self.database, self.ready, self.delivered
        )
        self.assertEqual(resumed['total'], 2)
        self.assertEqual(resumed['reused'], 1)
        self.assertEqual(resumed['created'], 1)

    def test_strict_stale_partial_is_recovered(self):
        self.invoke_success(self.packet_id)
        partial = self.ready / (
            '.ai-result-v1-' + 'a' * 32 + '.jsonl.tmp-123-456'
        )
        partial.write_bytes(b'partial')
        partial.chmod(0o600)
        state = self.producer.build(
            self.database, self.ready, self.delivered
        )
        self.assertEqual(state['recovered'], 1)
        self.assertFalse(partial.exists())
        self.assertEqual(len(self.final_files()), 1)

    def test_unknown_outbox_entry_is_refused(self):
        self.invoke_success(self.packet_id)
        unknown = self.ready / 'unexpected.txt'
        unknown.write_text('unexpected', encoding='utf-8')
        with self.assertRaisesRegex(
            self.producer.OutboxError, 'unexpected entry'
        ):
            self.producer.build(
                self.database, self.ready, self.delivered
            )
        self.assertEqual(self.final_files(), [])

    def test_lock_contention_prevents_publication(self):
        self.invoke_success(self.packet_id)
        descriptor = os.open(
            self.outbox / self.producer.LOCK_NAME,
            os.O_RDWR | os.O_CREAT,
            0o600,
        )
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with self.assertRaisesRegex(
            self.producer.OutboxError, 'already running'
        ):
            self.producer.build(
                self.database, self.ready, self.delivered
            )
        self.assertEqual(self.final_files(), [])

    def test_tampered_result_digest_is_refused(self):
        self.invoke_success(self.packet_id)
        connection = sqlite3.connect(self.database)
        connection.execute('DROP TRIGGER reasoning_results_no_update')
        connection.execute(
            "UPDATE reasoning_results SET result_sha256=?", ('0' * 64,)
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(
            self.producer.OutboxError, 'digest differs'
        ):
            self.producer.build(
                self.database, self.ready, self.delivered
            )
        self.assertEqual(self.final_files(), [])

    def test_symlink_outbox_is_refused(self):
        link = self.outbox / 'ready-link'
        link.symlink_to(self.ready, target_is_directory=True)
        with self.assertRaisesRegex(
            self.producer.OutboxError, 'not a directory'
        ):
            self.producer.build(self.database, link, self.delivered)


if __name__ == '__main__':
    unittest.main()
