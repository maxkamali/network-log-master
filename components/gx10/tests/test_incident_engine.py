#!/usr/bin/env python3
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
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
APPLICATION = GX10_DIR / 'sbin' / 'incident-engine.py'
BASE_SCHEMA = GX10_DIR / 'sql' / 'initialize.sql'
INCIDENT_SCHEMA = GX10_DIR / 'sql' / 'incident-v1.sql'


def load_engine(database):
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        spec = importlib.util.spec_from_file_location(
            'gx10_incident_engine_test',
            APPLICATION,
        )
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


class IncidentEngineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
        connection = sqlite3.connect(self.database)
        connection.executescript(BASE_SCHEMA.read_text())
        connection.executescript(INCIDENT_SCHEMA.read_text())
        connection.execute(
            """
            INSERT INTO source_files (
                remote_path,
                status,
                discovered_at
            ) VALUES (?, 'processed', ?)
            """,
            (
                '/spool/2026/08/24/06/syslog-20260824-0612.jsonl.zst',
                '2026-08-24T06:14:00+00:00',
            ),
        )
        connection.commit()
        connection.close()
        self.engine = load_engine(self.database)
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
        attributes='{}',
    ):
        self.record_number += 1
        connection = sqlite3.connect(self.database)
        cursor = connection.execute(
            """
            INSERT INTO recent_events (
                source_file,
                record_number,
                timestamp,
                timestamp_epoch_ms,
                severity,
                message,
                event_json
            ) VALUES (?, ?, ?, ?, ?, ?, '{}')
            """,
            (
                '/spool/2026/08/24/06/syslog-20260824-0612.jsonl.zst',
                self.record_number,
                iso(epoch_ms),
                epoch_ms,
                severity,
                'synthetic event',
            ),
        )
        event_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO event_enrichment (
                event_id,
                event_code,
                family,
                device,
                entity_type,
                entity_key,
                state,
                attention_eligible,
                classified_at,
                repeat_count,
                classification_version,
                vendor_hint,
                protocol,
                signal_type,
                attributes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 4, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_code,
                family,
                'router-a.example.invalid',
                entity_type,
                entity_key,
                state,
                attention,
                iso(epoch_ms),
                repeat_count,
                'cisco',
                protocol,
                signal,
                attributes,
            ),
        )
        connection.commit()
        connection.close()
        return event_id

    def run_engine(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.engine.main()

    def rows(self, sql, parameters=()):
        connection = sqlite3.connect(self.database)
        result = connection.execute(sql, parameters).fetchall()
        connection.close()
        return result

    def test_immediate_open_recovery_resolution_recurrence_and_replay(self):
        start = 1787551200000
        first = self.add_event(start)
        recovery = self.add_event(
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

        incidents = self.rows(
            """
            SELECT incident_id, status, occurrence_count, repeat_count_total
            FROM incidents
            ORDER BY first_seen_epoch_ms
            """
        )
        self.assertEqual(len(incidents), 1)
        first_incident = incidents[0][0]
        self.assertEqual(incidents[0][1:], ('RESOLVED', 2, 2))
        transitions = self.rows(
            """
            SELECT from_status, to_status, event_id, reason
            FROM incident_transitions
            WHERE incident_id = ?
            ORDER BY transition_sequence
            """,
            (first_incident,),
        )
        self.assertEqual(
            transitions,
            [
                (None, 'CANDIDATE', first, 'first_adverse_evidence'),
                ('CANDIDATE', 'OPEN', first, 'explicit_adverse_state'),
                ('OPEN', 'RECOVERING', recovery, 'recovery_evidence'),
                ('RECOVERING', 'RESOLVED', None, 'recovery_quiet_period'),
            ],
        )

        recurrence = self.add_event(start + 8 * 60_000)
        self.assertEqual(self.run_engine(), 0)
        incidents = self.rows(
            """
            SELECT incident_id, status
            FROM incidents
            ORDER BY first_seen_epoch_ms
            """
        )
        self.assertEqual(len(incidents), 2)
        self.assertNotEqual(incidents[0][0], incidents[1][0])
        self.assertEqual(incidents[1][1], 'OPEN')
        expected = self.engine.incident_id(
            self.projected_row(recurrence),
            self.engine.correlation_key(self.projected_row(recurrence)),
        )
        self.assertEqual(incidents[1][0], expected)

        snapshot = self.dump_engine_state()
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.dump_engine_state(), snapshot)

        connection = sqlite3.connect(self.database)
        connection.execute(
            'DELETE FROM agent_state WHERE key = ?',
            (self.engine.CURSOR_KEY,),
        )
        connection.commit()
        connection.close()
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(self.dump_engine_state(), snapshot)

    def projected_row(self, event_id):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT
                r.id,
                r.source_file,
                r.record_number,
                r.timestamp,
                r.timestamp_epoch_ms,
                r.severity,
                e.*
            FROM recent_events AS r
            JOIN event_enrichment AS e ON e.event_id = r.id
            WHERE r.id = ?
            """,
            (event_id,),
        ).fetchone()
        connection.close()
        return row

    def dump_engine_state(self):
        connection = sqlite3.connect(self.database)
        result = tuple(
            tuple(
                connection.execute(
                    f'SELECT * FROM {table} ORDER BY rowid'
                ).fetchall()
            )
            for table in (
                'incidents',
                'incident_evidence',
                'incident_transitions',
            )
        )
        connection.close()
        return result

    def test_degradation_threshold_supporting_recovery_and_relapse(self):
        start = 1787551200000
        self.add_event(
            start,
            signal='degradation',
            state='retransmissions',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key='OSPF|router-a.example.invalid|1|192.0.2.20',
            repeat_count=2,
        )
        self.add_event(
            start + 60_000,
            signal='degradation',
            state='retransmissions',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key='OSPF|router-a.example.invalid|1|192.0.2.20',
            repeat_count=3,
        )
        self.add_event(
            start + 2 * 60_000,
            signal='supporting_evidence',
            state='retransmissions',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key='OSPF|router-a.example.invalid|1|192.0.2.20',
        )
        self.add_event(
            start + 3 * 60_000,
            signal='recovery',
            state='up',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key='OSPF|router-a.example.invalid|1|192.0.2.20',
        )
        self.add_event(
            start + 4 * 60_000,
            signal='state_transition',
            state='down',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key='OSPF|router-a.example.invalid|1|192.0.2.20',
        )
        self.assertEqual(self.run_engine(), 0)
        incident = self.rows(
            """
            SELECT status, occurrence_count, repeat_count_total,
                   observation_state_changes
            FROM incidents
            """
        )[0]
        self.assertEqual(incident, ('OPEN', 5, 8, 2))
        transitions = self.rows(
            """
            SELECT from_status, to_status, reason
            FROM incident_transitions
            ORDER BY transition_sequence
            """
        )
        self.assertEqual(
            transitions,
            [
                (None, 'CANDIDATE', 'first_adverse_evidence'),
                ('CANDIDATE', 'OPEN', 'repeated_adverse_evidence'),
                ('OPEN', 'RECOVERING', 'recovery_evidence'),
                ('RECOVERING', 'OPEN', 'adverse_relapse'),
            ],
        )
        context = json.loads(
            self.rows('SELECT context_json FROM incidents')[0][0]
        )
        self.assertEqual(set(context['windows']), {'60m', '180m', '24h'})
        self.assertEqual(context['windows']['60m']['evidence_count'], 5)
        self.assertEqual(context['windows']['60m']['repeat_count_total'], 8)

    def test_ospf_recovery_monitors_for_24_hours_and_relapse_reopens(self):
        start = 1787551200000
        key = 'OSPF|router-a.example.invalid|1|192.0.2.20'
        first = self.add_event(
            start,
            signal='state_transition',
            state='down',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key=key,
        )
        recovery = self.add_event(
            start + 60_000,
            signal='recovery',
            state='up',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key=key,
        )
        self.add_event(
            start + 6 * 60_000,
            entity_key=None,
            entity_type=None,
            signal='observation',
            state=None,
            attention=0,
        )
        relapse = self.add_event(
            start + 23 * 60 * 60_000,
            signal='state_transition',
            state='down',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key=key,
        )
        second_recovery = self.add_event(
            start + 23 * 60 * 60_000 + 60_000,
            signal='recovery',
            state='up',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key=key,
        )
        self.add_event(
            start + 47 * 60 * 60_000,
            entity_key=None,
            entity_type=None,
            signal='observation',
            state=None,
            attention=0,
        )

        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows(
                'SELECT status, occurrence_count, engine_version FROM incidents'
            ),
            [('RECOVERING', 4, self.engine.ENGINE_VERSION)],
        )
        self.assertEqual(
            self.rows(
                '''
                SELECT from_status, to_status, event_id, reason
                FROM incident_transitions
                ORDER BY transition_sequence
                '''
            ),
            [
                (None, 'CANDIDATE', first, 'first_adverse_evidence'),
                ('CANDIDATE', 'OPEN', first, 'explicit_adverse_state'),
                ('OPEN', 'RECOVERING', recovery, 'recovery_evidence'),
                ('RECOVERING', 'OPEN', relapse, 'adverse_relapse'),
                ('OPEN', 'RECOVERING', second_recovery, 'recovery_evidence'),
            ],
        )

        self.add_event(
            start + 47 * 60 * 60_000 + 2 * 60_000,
            entity_key=None,
            entity_type=None,
            signal='observation',
            state=None,
            attention=0,
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows('SELECT status FROM incidents'),
            [('RESOLVED',)],
        )
        self.assertEqual(
            self.rows(
                '''
                SELECT reason FROM incident_transitions
                ORDER BY transition_sequence DESC LIMIT 1
                '''
            ),
            [('protocol_monitoring_period',)],
        )

    def test_bgp_recovery_uses_24_hour_monitoring_deadline(self):
        start = 1787551200000
        key = 'BGP|router-a.example.invalid|192.0.2.30'
        self.add_event(
            start,
            signal='state_transition',
            state='idle',
            protocol='bgp',
            family='bgp',
            entity_type='bgp_peer',
            entity_key=key,
        )
        self.add_event(
            start + 60_000,
            signal='recovery',
            state='established',
            protocol='bgp',
            family='bgp',
            entity_type='bgp_peer',
            entity_key=key,
        )
        self.add_event(
            start + 23 * 60 * 60_000,
            entity_key=None,
            entity_type=None,
            signal='observation',
            state=None,
            attention=0,
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows('SELECT status FROM incidents'),
            [('RECOVERING',)],
        )

        self.add_event(
            start + 24 * 60 * 60_000 + 2 * 60_000,
            entity_key=None,
            entity_type=None,
            signal='observation',
            state=None,
            attention=0,
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows('SELECT status FROM incidents'),
            [('RESOLVED',)],
        )

    def test_protocol_candidate_timeout_monitors_for_24_hours(self):
        start = 1787551200000
        self.add_event(
            start,
            signal='degradation',
            state='retransmissions',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key='OSPF|router-a.example.invalid|1|192.0.2.20',
        )
        self.add_event(
            start + 16 * 60_000,
            entity_type=None,
            entity_key=None,
            signal='observation',
            state=None,
            attention=0,
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows('SELECT status FROM incidents'),
            [('RECOVERING',)],
        )
        self.assertEqual(
            self.rows(
                """
                SELECT reason FROM incident_transitions
                ORDER BY transition_sequence DESC LIMIT 1
                """
            ),
            [('protocol_candidate_monitoring',)],
        )
        self.assertEqual(
            self.rows('SELECT COUNT(*) FROM incident_evidence')[0][0],
            1,
        )

        self.add_event(
            start + 24 * 60 * 60_000 + 16 * 60_000,
            entity_type=None,
            entity_key=None,
            signal='observation',
            state=None,
            attention=0,
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows('SELECT status FROM incidents'),
            [('RESOLVED',)],
        )
        self.assertEqual(
            self.rows(
                """
                SELECT reason FROM incident_transitions
                ORDER BY transition_sequence DESC LIMIT 1
                """
            ),
            [('protocol_monitoring_period',)],
        )

    def test_protocol_candidate_recovery_enters_monitoring(self):
        start = 1787551200000
        key = 'OSPF|router-a.example.invalid|1|192.0.2.20'
        self.add_event(
            start,
            signal='degradation',
            state='retransmissions',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key=key,
        )
        recovery = self.add_event(
            start + 60_000,
            signal='recovery',
            state='up',
            protocol='ospf',
            family='ospf',
            entity_type='ospf_neighbor',
            entity_key=key,
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows('SELECT status, occurrence_count FROM incidents'),
            [('RECOVERING', 2)],
        )
        self.assertEqual(
            self.rows(
                """
                SELECT from_status, to_status, event_id, reason
                FROM incident_transitions
                ORDER BY transition_sequence
                """
            ),
            [
                (None, 'CANDIDATE', 1, 'first_adverse_evidence'),
                (
                    'CANDIDATE',
                    'RECOVERING',
                    recovery,
                    'protocol_candidate_recovery_monitoring',
                ),
            ],
        )

    def test_candidate_deadline_precedes_late_recovery(self):
        start = 1787551200000
        self.add_event(
            start,
            signal='degradation',
            state='retransmissions',
        )
        self.add_event(
            start + 16 * 60_000,
            signal='recovery',
            state='up',
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows('SELECT status, occurrence_count FROM incidents'),
            [('RESOLVED', 1)],
        )
        self.assertEqual(
            self.rows(
                """
                SELECT reason FROM incident_transitions
                ORDER BY transition_sequence
                """
            ),
            [('first_adverse_evidence',), ('candidate_timeout',)],
        )

    def test_supporting_evidence_does_not_extend_candidate_window(self):
        start = 1787551200000
        self.add_event(
            start,
            signal='degradation',
            state='retransmissions',
        )
        self.add_event(
            start + 14 * 60_000,
            signal='supporting_evidence',
            state='retransmissions',
        )
        self.add_event(
            start + 16 * 60_000,
            signal='degradation',
            state='retransmissions',
        )
        self.assertEqual(self.run_engine(), 0)
        self.assertEqual(
            self.rows(
                """
                SELECT status, occurrence_count
                FROM incidents
                ORDER BY first_seen_epoch_ms
                """
            ),
            [('RESOLVED', 2), ('CANDIDATE', 1)],
        )

    def test_malformed_input_rolls_back_incidents_and_cursor(self):
        start = 1787551200000
        self.add_event(start)
        self.add_event(start + 60_000, attributes='[]')
        self.assertEqual(self.run_engine(), 1)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM incidents')[0][0], 0)
        self.assertEqual(
            self.rows('SELECT COUNT(*) FROM incident_evidence')[0][0],
            0,
        )
        self.assertEqual(
            self.rows(
                'SELECT COUNT(*) FROM agent_state WHERE key = ?',
                (self.engine.CURSOR_KEY,),
            )[0][0],
            0,
        )

    def test_evidence_and_transitions_are_append_only(self):
        self.add_event(1787551200000)
        self.assertEqual(self.run_engine(), 0)
        connection = sqlite3.connect(self.database)
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'append-only'):
            connection.execute(
                "UPDATE incident_evidence SET event_code = 'changed'"
            )
        connection.rollback()
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'append-only'):
            connection.execute('DELETE FROM incident_transitions')
        connection.rollback()
        connection.close()

    def test_verifier_rejects_mutable_context_drift(self):
        self.add_event(1787551200000)
        self.assertEqual(self.run_engine(), 0)
        connection = sqlite3.connect(self.database)
        connection.execute("UPDATE incidents SET context_json = '{}'")
        connection.commit()
        connection.close()
        self.assertEqual(self.run_engine(), 1)


if __name__ == '__main__':
    unittest.main()
