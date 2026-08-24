#!/usr/bin/env python3
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
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
REASONING_SCHEMA = GX10_DIR / 'sql' / 'reasoning-v1.sql'


def load_application(name, filename, database):
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        path = GX10_DIR / 'sbin' / filename
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules['runtime_config']
        else:
            sys.modules['runtime_config'] = previous


def iso(epoch_ms):
    return datetime.fromtimestamp(
        epoch_ms / 1000,
        tz=timezone.utc,
    ).isoformat()


class ReasoningPacketTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
        connection = sqlite3.connect(self.database)
        connection.executescript(BASE_SCHEMA.read_text(encoding='utf-8'))
        connection.executescript(INCIDENT_SCHEMA.read_text(encoding='utf-8'))
        connection.executescript(REASONING_SCHEMA.read_text(encoding='utf-8'))
        connection.execute(
            '''
            INSERT INTO source_files (remote_path, status, discovered_at)
            VALUES (?, 'processed', ?)
            ''',
            (
                '/spool/2026/08/24/07/syslog-20260824-0700.jsonl.zst',
                '2026-08-24T07:01:00+00:00',
            ),
        )
        connection.commit()
        connection.close()
        self.engine = load_application(
            'reasoning_packet_incident_engine',
            'incident-engine.py',
            self.database,
        )
        self.builder = load_application(
            'reasoning_packet_builder',
            'build-reasoning-packets.py',
            self.database,
        )
        self.record_number = 0

    def add_event(
        self,
        epoch_ms,
        *,
        entity_key='INTERFACE|router-a.example.invalid|Ethernet1',
        entity_type='interface',
        family='ethport',
        protocol='ethernet',
        signal='state_transition',
        state='down',
        event_code='ETHPORT-5-IF_DOWN',
        repeat_count=1,
        attention=1,
        severity='warning',
        attributes=None,
    ):
        self.record_number += 1
        if attributes is None:
            attributes = {}
        attributes_json = json.dumps(
            attributes,
            separators=(',', ':'),
            sort_keys=True,
        )
        connection = sqlite3.connect(self.database)
        cursor = connection.execute(
            '''
            INSERT INTO recent_events (
                source_file, record_number, timestamp, timestamp_epoch_ms,
                severity, message, event_json
            ) VALUES (?, ?, ?, ?, ?, 'synthetic event', '{}')
            ''',
            (
                '/spool/2026/08/24/07/syslog-20260824-0700.jsonl.zst',
                self.record_number,
                iso(epoch_ms),
                epoch_ms,
                severity,
            ),
        )
        event_id = cursor.lastrowid
        connection.execute(
            '''
            INSERT INTO event_enrichment (
                event_id, event_code, family, device, entity_type, entity_key,
                state, attention_eligible, classified_at, repeat_count,
                classification_version, vendor_hint, protocol, signal_type,
                attributes_json
            ) VALUES (?, ?, ?, 'router-a.example.invalid', ?, ?, ?, ?, ?, ?,
                      4, 'cisco', ?, ?, ?)
            ''',
            (
                event_id,
                event_code,
                family,
                entity_type,
                entity_key,
                state,
                attention,
                iso(epoch_ms),
                repeat_count,
                protocol,
                signal,
                attributes_json,
            ),
        )
        connection.commit()
        connection.close()
        return event_id

    def run_engine(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.engine.main()

    def run_builder(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.builder.run()

    def rows(self, statement, parameters=()):
        connection = sqlite3.connect(self.database)
        result = connection.execute(statement, parameters).fetchall()
        connection.close()
        return result

    def packet(self, offset=-1):
        value = self.rows(
            'SELECT packet_json FROM reasoning_packets ORDER BY rowid'
        )[offset][0]
        return json.loads(value)

    def test_open_packet_is_canonical_bounded_and_replay_safe(self):
        self.add_event(1787551200000)
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        row = self.rows(
            '''
            SELECT primary_reason, wake_reasons_json, packet_json,
                   packet_sha256
            FROM reasoning_packets
            '''
        )[0]
        self.assertEqual(row[0], 'incident_opened')
        self.assertEqual(json.loads(row[1]), ['incident_opened'])
        self.assertEqual(
            hashlib.sha256(row[2].encode()).hexdigest(),
            row[3],
        )
        self.assertLessEqual(len(row[2].encode()), self.builder.MAX_PACKET_BYTES)
        snapshot = tuple(self.rows('SELECT * FROM reasoning_packets'))
        self.assertEqual(self.run_builder(), 0)
        self.assertEqual(tuple(self.rows('SELECT * FROM reasoning_packets')), snapshot)
        connection = sqlite3.connect(self.database)
        connection.execute(
            'DELETE FROM agent_state WHERE key = ?',
            (self.engine.CURSOR_KEY,),
        )
        connection.commit()
        connection.close()
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        self.assertEqual(tuple(self.rows('SELECT * FROM reasoning_packets')), snapshot)

    def test_critical_ospf_candidate_wakes_without_opening(self):
        self.add_event(
            1787551200000,
            entity_key='OSPF|router-a.example.invalid|1|192.0.2.20',
            entity_type='ospf_neighbor',
            family='ospf',
            protocol='ospf',
            signal='degradation',
            state='retransmissions',
            event_code='OSPF-4-ERRRCV',
            severity='critical',
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        packet = self.packet()
        self.assertEqual(packet['incident']['status'], 'CANDIDATE')
        self.assertEqual(packet['wake']['primary_reason'], 'critical_condition')
        self.assertEqual(
            packet['wake']['reasons'],
            ['critical_condition', 'ospf_retransmission'],
        )

    def test_interface_state_change_creates_flap_packet(self):
        start = 1787551200000
        self.add_event(start)
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        self.add_event(
            start + 60_000,
            signal='recovery',
            state='up',
            event_code='ETHPORT-5-IF_UP',
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        packet = self.packet()
        self.assertEqual(packet['wake']['primary_reason'], 'interface_flap')
        self.assertEqual(
            packet['wake']['reasons'],
            ['interface_flap', 'incident_recovering'],
        )
        self.assertEqual(packet['delta']['state_change_count'], 1)

    def test_resolution_packet_follows_prior_wake(self):
        start = 1787551200000
        self.add_event(start)
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        self.add_event(
            start + 60_000,
            signal='recovery',
            state='up',
            event_code='ETHPORT-5-IF_UP',
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        self.add_event(
            start + 7 * 60_000,
            entity_key=None,
            entity_type=None,
            signal='observation',
            state=None,
            attention=0,
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        self.assertEqual(self.packet()['wake']['primary_reason'], 'incident_resolved')

    def test_historical_resolved_incident_is_not_backfilled(self):
        start = 1787551200000
        self.add_event(start)
        self.add_event(
            start + 60_000,
            signal='recovery',
            state='up',
            event_code='ETHPORT-5-IF_UP',
        )
        self.add_event(
            start + 7 * 60_000,
            entity_key=None,
            entity_type=None,
            signal='observation',
            state=None,
            attention=0,
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM reasoning_packets'), [(0,)])

    def test_meaningful_update_accumulates_below_threshold_evidence(self):
        start = 1787551200000
        self.add_event(start)
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        for offset in range(1, 6):
            self.add_event(
                start + offset * 60_000,
                signal='supporting_evidence',
                state='down',
            )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        packet = self.packet()
        self.assertEqual(packet['wake']['primary_reason'], 'meaningful_update')
        self.assertEqual(packet['delta']['evidence_count'], 5)

    def test_large_attributes_are_replaced_by_digest(self):
        self.add_event(
            1787551200000,
            attributes={'detail': 'x' * 5000},
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        evidence = self.packet()['evidence'][0]
        self.assertTrue(evidence['attributes_omitted'])
        self.assertEqual(len(evidence['attributes_sha256']), 64)
        self.assertNotIn('attributes', evidence)

    def test_raw_and_source_attribute_keys_are_recursively_removed(self):
        self.add_event(
            1787551200000,
            attributes={
                'safe': 'retained',
                'raw_message': 'excluded',
                'nested': [{'source_file': '/excluded', 'state': 'down'}],
            },
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        evidence = self.packet()['evidence'][0]
        self.assertEqual(
            evidence['attributes'],
            {'nested': [{'state': 'down'}], 'safe': 'retained'},
        )
        self.assertEqual(evidence['attributes_redacted_keys'], 2)
        self.assertEqual(len(evidence['attributes_sha256']), 64)
        encoded = json.dumps(evidence, sort_keys=True)
        self.assertNotIn('raw_message', encoded)
        self.assertNotIn('source_file', encoded)

    def test_packet_rows_are_append_only_and_tamper_is_detected(self):
        self.add_event(1787551200000)
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.run_builder(), 0)
        connection = sqlite3.connect(self.database)
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'append-only'):
            connection.execute(
                "UPDATE reasoning_packets SET primary_reason = 'meaningful_update'"
            )
        connection.rollback()
        connection.execute('DROP TRIGGER reasoning_packets_no_update')
        connection.execute("UPDATE reasoning_packets SET packet_json = '{}'")
        connection.commit()
        connection.close()
        self.assertEqual(self.run_builder(), 1)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM reasoning_packets'), [(1,)])


if __name__ == '__main__':
    unittest.main()
