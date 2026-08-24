#!/usr/bin/env python3
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
BASE_SCHEMA = GX10_DIR / 'sql' / 'initialize.sql'
INCIDENT_SCHEMA = GX10_DIR / 'sql' / 'incident-v1.sql'
PACKET_SCHEMA = GX10_DIR / 'sql' / 'reasoning-v1.sql'
INFERENCE_SCHEMA = GX10_DIR / 'sql' / 'inference-v1.sql'
CONFIG = GX10_DIR / 'config' / 'reasoning-runtime-v2.json'
PROMPT = GX10_DIR / 'prompts' / 'incident-assessment-v2.txt'
OUTPUT_SCHEMA = GX10_DIR / 'prompts' / 'incident-assessment-output-v2.json'


def canonical_json(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def load_caller(database):
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        path = GX10_DIR / 'sbin' / 'run-local-reasoning.py'
        spec = importlib.util.spec_from_file_location('local_reasoning', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules['runtime_config']
        else:
            sys.modules['runtime_config'] = previous


class LocalReasoningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
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
            INSERT INTO source_files (remote_path, status, discovered_at)
            VALUES ('/spool/synthetic', 'processed', '2026-08-24T08:00:00+00:00')
            '''
        )
        self.event_id = connection.execute(
            '''
            INSERT INTO recent_events (
                source_file, record_number, timestamp, timestamp_epoch_ms,
                severity, message, event_json
            ) VALUES (
                '/spool/synthetic', 1, '2026-08-24T08:00:00+00:00',
                1787558400000, 'warning', 'synthetic', '{}'
            )
            '''
        ).lastrowid
        self.incident_id = 'inc-v1-synthetic'
        connection.execute(
            '''
            INSERT INTO incidents (
                incident_id, correlation_key, status, event_family, protocol,
                entity_type, entity_key, severity, first_seen,
                first_seen_epoch_ms, last_seen, last_seen_epoch_ms,
                occurrence_count, repeat_count_total,
                observation_state_changes, last_observation_state, opened_at,
                recovering_at, resolved_at, last_event_id, context_json,
                engine_version, created_at, updated_at
            ) VALUES (
                ?, 'synthetic-correlation', 'OPEN', 'interface', 'ethernet',
                'interface', 'INTERFACE|router.example.invalid|Ethernet1',
                'warning', '2026-08-24T08:00:00+00:00', 1787558400000,
                '2026-08-24T08:00:00+00:00', 1787558400000, 1, 1, 0,
                'down', '2026-08-24T08:00:00+00:00', NULL, NULL, ?, '{}',
                1, '2026-08-24T08:00:00+00:00',
                '2026-08-24T08:00:00+00:00'
            )
            ''',
            (self.incident_id, self.event_id),
        )
        connection.commit()
        connection.close()
        self.caller = load_caller(self.database)
        self.packet_id = self.add_packet(priority=90, sequence=1)

    def add_packet(self, *, priority, sequence):
        packet_id = f'pkt-v1-synthetic-{sequence}'
        packet = canonical_json(
            {
                'incident': {
                    'incident_id': self.incident_id,
                    'severity': 'warning',
                    'status': 'OPEN',
                },
                'packet_id': packet_id,
                'packet_version': 1,
                'policy_version': 1,
                'schema': 'gx10-incident-reasoning-packet',
                'wake': {
                    'primary_reason': 'incident_opened',
                    'priority': priority,
                    'reasons': ['incident_opened'],
                },
            }
        )
        connection = sqlite3.connect(self.database)
        connection.execute(
            '''
            INSERT INTO reasoning_packets (
                packet_id, incident_id, policy_version, packet_version,
                primary_reason, wake_reasons_json, priority, as_of_event_id,
                as_of_evidence_sequence, as_of_transition_sequence,
                basis_repeat_count_total, basis_state_change_count,
                basis_last_seen_epoch_ms, created_at, packet_json,
                packet_sha256
            ) VALUES (?, ?, 1, 1, 'incident_opened', '["incident_opened"]',
                      ?, ?, ?, ?, ?, 0, ?, '2026-08-24T08:00:00+00:00', ?, ?)
            ''',
            (
                packet_id,
                self.incident_id,
                priority,
                self.event_id,
                sequence,
                sequence,
                sequence,
                1787558400000 + sequence,
                packet,
                hashlib.sha256(packet.encode()).hexdigest(),
            ),
        )
        connection.commit()
        connection.close()
        return packet_id

    def output(self, packet_id=None, **changes):
        value = {
            'schema': 'gx10-incident-assessment',
            'schema_version': self.caller.OUTPUT_SCHEMA_VERSION,
            'packet_id': packet_id or self.packet_id,
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
                    'action': 'Inspect interface operational state.',
                    'priority': 1,
                    'risk': 'read_only',
                },
                {
                    'action': 'Review recent approved configuration changes.',
                    'priority': 2,
                    'risk': 'read_only',
                }
            ],
            'tags': ['incident_opened', 'open', 'warning'],
        }
        value.update(changes)
        return value

    def response(self, output=None, packet_id=None):
        value = output if output is not None else self.output(packet_id)
        return json.dumps(
            {
                'model': self.caller.MODEL_REFERENCE,
                'done': True,
                'done_reason': 'stop',
                'eval_count': 120,
                'message': {
                    'role': 'assistant',
                    'content': json.dumps(value, indent=2),
                },
            }
        ).encode()

    def invoke(self, transport):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.caller.run(
                self.database,
                config_path=CONFIG,
                prompt_path=PROMPT,
                output_schema_path=OUTPUT_SCHEMA,
                transport=transport,
                now=lambda: '2026-08-24T08:30:00+00:00',
            )

    def rows(self, statement, parameters=()):
        connection = sqlite3.connect(self.database)
        rows = connection.execute(statement, parameters).fetchall()
        connection.close()
        return rows

    def test_success_is_versioned_structured_and_idempotent(self):
        requests = []

        def transport(request_json):
            requests.append(json.loads(request_json))
            return self.response()

        self.assertEqual(self.invoke(transport), 0)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request['model'], 'gemma4:latest')
        self.assertIs(request['stream'], False)
        self.assertIs(request['think'], False)
        self.assertEqual(request['options']['temperature'], 0)
        self.assertEqual(request['format']['additionalProperties'], False)
        user = json.loads(request['messages'][1]['content'])
        self.assertEqual(user['packet']['packet_id'], self.packet_id)
        self.assertIn('incident_opened', user['allowed_tags'])
        self.assertEqual(
            hashlib.sha256(canonical_json(user['packet']).encode()).hexdigest(),
            user['packet_sha256'],
        )
        self.assertEqual(
            self.rows('SELECT status, error_code FROM reasoning_runs'),
            [('SUCCEEDED', None)],
        )
        self.assertEqual(
            self.rows(
                'SELECT prompt_version,output_schema_sha256,created_at '
                'FROM reasoning_prompt_versions'
            ),
            [
                (
                    self.caller.PROMPT_VERSION,
                    self.caller.OUTPUT_SCHEMA_SHA256,
                    self.caller.PROMPT_VERSION_CREATED_AT,
                )
            ],
        )
        result = self.rows(
            'SELECT result_json, result_sha256 FROM reasoning_results'
        )[0]
        self.assertEqual(hashlib.sha256(result[0].encode()).hexdigest(), result[1])
        state = tuple(self.rows('SELECT * FROM reasoning_runs'))
        self.assertEqual(self.invoke(transport), 0)
        self.assertEqual(len(requests), 1)
        self.assertEqual(tuple(self.rows('SELECT * FROM reasoning_runs')), state)

    def test_unavailable_is_terminal_safe_failure_without_retry(self):
        incident_before = tuple(self.rows('SELECT * FROM incidents'))
        calls = []

        def unavailable(request_json):
            calls.append(request_json)
            raise self.caller.InferenceFailure('INFERENCE_UNAVAILABLE')

        self.assertEqual(self.invoke(unavailable), 1)
        self.assertEqual(
            self.rows('SELECT status, error_code FROM reasoning_runs'),
            [('INFERENCE_UNAVAILABLE', 'inference_unavailable')],
        )
        self.assertEqual(self.rows('SELECT COUNT(*) FROM reasoning_results'), [(0,)])
        self.assertEqual(tuple(self.rows('SELECT * FROM incidents')), incident_before)
        self.assertEqual(self.invoke(unavailable), 0)
        self.assertEqual(len(calls), 1)

    def test_invalid_output_is_recorded_without_storing_untrusted_content(self):
        bad = self.output(packet_id='pkt-v1-wrong')
        self.assertEqual(self.invoke(lambda _: self.response(bad)), 1)
        self.assertEqual(
            self.rows('SELECT status, error_code FROM reasoning_runs'),
            [('INVALID_OUTPUT', 'invalid_output')],
        )
        self.assertEqual(self.rows('SELECT COUNT(*) FROM reasoning_results'), [(0,)])

    def test_extra_output_field_is_refused(self):
        bad = self.output(unexpected='value')
        self.assertEqual(self.invoke(lambda _: self.response(bad)), 1)
        self.assertEqual(
            self.rows('SELECT status FROM reasoning_runs'),
            [('INVALID_OUTPUT',)],
        )

    def test_noncritical_packet_cannot_be_escalated_to_critical(self):
        bad = self.output(severity='critical')
        self.assertEqual(self.invoke(lambda _: self.response(bad)), 1)
        self.assertEqual(
            self.rows('SELECT status FROM reasoning_runs'),
            [('INVALID_OUTPUT',)],
        )

    def test_action_required_needs_meaningful_read_only_first_action(self):
        bad = self.output(
            recommended_actions=[
                {'action': 'read_only', 'priority': 1, 'risk': 'read_only'},
                {
                    'action': 'Restart the interface.',
                    'priority': 2,
                    'risk': 'reversible',
                },
            ]
        )
        self.assertEqual(self.invoke(lambda _: self.response(bad)), 1)
        self.assertEqual(
            self.rows('SELECT status FROM reasoning_runs'),
            [('INVALID_OUTPUT',)],
        )

    def test_output_schema_prevents_risk_labels_as_action_text(self):
        schema = json.loads(OUTPUT_SCHEMA.read_text(encoding='utf-8'))
        action_text = schema['properties']['recommended_actions']['items'][
            'properties'
        ]['action']
        self.assertEqual(
            set(action_text['not']['enum']), self.caller.ACTION_RISKS
        )

    def test_action_required_cannot_claim_zero_confidence(self):
        bad = self.output(confidence=0)
        self.assertEqual(self.invoke(lambda _: self.response(bad)), 1)
        self.assertEqual(
            self.rows('SELECT status FROM reasoning_runs'),
            [('INVALID_OUTPUT',)],
        )

    def test_tags_must_come_from_deterministic_packet_values(self):
        bad = self.output(tags=['invented-tag'])
        self.assertEqual(self.invoke(lambda _: self.response(bad)), 1)
        self.assertEqual(
            self.rows('SELECT status FROM reasoning_runs'),
            [('INVALID_OUTPUT',)],
        )

    def test_change_action_requires_approval_label(self):
        bad = self.output(
            recommended_actions=[
                {
                    'action': 'Inspect interface operational state.',
                    'priority': 1,
                    'risk': 'read_only',
                },
                {
                    'action': 'Restart the interface if it remains down.',
                    'priority': 2,
                    'risk': 'reversible',
                },
            ]
        )
        self.assertEqual(self.invoke(lambda _: self.response(bad)), 1)
        self.assertEqual(
            self.rows('SELECT status FROM reasoning_runs'),
            [('INVALID_OUTPUT',)],
        )

    def test_started_run_after_interruption_prevents_duplicate_inference(self):
        def interrupted(_):
            raise SystemExit('synthetic interruption')

        with self.assertRaises(SystemExit):
            self.invoke(interrupted)
        self.assertEqual(
            self.rows('SELECT status, completed_at FROM reasoning_runs'),
            [('STARTED', None)],
        )
        calls = []
        self.assertEqual(self.invoke(lambda value: calls.append(value)), 0)
        self.assertEqual(calls, [])

    def test_highest_priority_pending_packet_is_selected_first(self):
        high_packet = self.add_packet(priority=100, sequence=2)
        selected = []

        def transport(request_json):
            packet = json.loads(json.loads(request_json)['messages'][1]['content'])[
                'packet'
            ]
            selected.append(packet['packet_id'])
            return self.response(packet_id=packet['packet_id'])

        self.assertEqual(self.invoke(transport), 0)
        self.assertEqual(selected, [high_packet])

    def test_forbidden_packet_content_fails_before_run_reservation(self):
        original = json.loads(
            self.rows(
                'SELECT packet_json FROM reasoning_packets WHERE packet_id = ?',
                (self.packet_id,),
            )[0][0]
        )
        original['incident']['nested'] = {'raw_message': 'must not reach model'}
        changed = canonical_json(original)
        connection = sqlite3.connect(self.database)
        connection.execute('DROP TRIGGER reasoning_packets_no_update')
        connection.execute(
            '''
            UPDATE reasoning_packets
            SET packet_json = ?, packet_sha256 = ?
            WHERE packet_id = ?
            ''',
            (
                changed,
                hashlib.sha256(changed.encode()).hexdigest(),
                self.packet_id,
            ),
        )
        connection.commit()
        connection.close()
        calls = []
        self.assertEqual(self.invoke(lambda value: calls.append(value)), 1)
        self.assertEqual(calls, [])
        self.assertEqual(self.rows('SELECT COUNT(*) FROM reasoning_runs'), [(0,)])

    def test_version_and_result_rows_are_append_only(self):
        self.assertEqual(self.invoke(lambda _: self.response()), 0)
        connection = sqlite3.connect(self.database)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE reasoning_results SET title = 'changed'"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE reasoning_model_versions SET provider = 'ollama'"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE reasoning_runs SET diagnostics_json = '{}'"
            )
        connection.close()

    def test_prompt_hash_mismatch_fails_before_database_change(self):
        bad_prompt = Path(self.directory.name) / 'prompt.txt'
        bad_prompt.write_text('different', encoding='utf-8')
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = self.caller.run(
                self.database,
                config_path=CONFIG,
                prompt_path=bad_prompt,
                output_schema_path=OUTPUT_SCHEMA,
                transport=lambda _: self.response(),
            )
        self.assertEqual(result, 1)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM reasoning_runs'), [(0,)])

    def test_transport_endpoint_is_fixed_to_loopback(self):
        with self.assertRaises(self.caller.InferenceFailure) as raised:
            self.caller.ollama_request('{}', 'http://192.0.2.10:11434/api/chat')
        self.assertEqual(raised.exception.status, 'TRANSPORT_ERROR')


if __name__ == '__main__':
    unittest.main()
