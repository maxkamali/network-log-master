#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
SCRIPT = GX10_DIR / 'sbin' / 'build-incident-outbox.py'


def load_module():
    specification = importlib.util.spec_from_file_location(
        'incident_outbox_test', SCRIPT
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


OUTBOX = load_module()


class IncidentOutboxTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'outbox'
        self.ready = self.root / 'ready'
        self.delivered = self.root / 'delivered'
        self.root.mkdir(mode=0o700)
        self.ready.mkdir(mode=0o700)
        self.delivered.mkdir(mode=0o700)
        self.database = Path(self.temporary.name) / 'state.sqlite3'
        connection = sqlite3.connect(self.database)
        connection.execute(
            '''
            CREATE TABLE incidents (
                incident_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                event_family TEXT NOT NULL,
                protocol TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                severity TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL,
                repeat_count_total INTEGER NOT NULL,
                observation_state_changes INTEGER NOT NULL,
                last_observation_state TEXT,
                opened_at TEXT,
                recovering_at TEXT,
                resolved_at TEXT,
                engine_version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE incident_transitions (
                incident_id TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                reason TEXT NOT NULL
            )
            '''
        )
        connection.commit()
        connection.close()

    def add_incident(self, number, *, status='OPEN', state_changes=0):
        timestamp = f'2026-08-24T08:{number % 60:02d}:00+00:00'
        resolved_at = timestamp if status == 'RESOLVED' else None
        connection = sqlite3.connect(self.database)
        connection.execute(
            '''
            INSERT INTO incidents VALUES (
                ?, ?, 'ethport', 'ethernet', 'interface', ?, 'warning',
                '2026-08-24T08:00:00+00:00', ?, 2, 2, ?, 'down',
                '2026-08-24T08:00:00+00:00', NULL, ?, 1, ?
            )
            ''',
            (
                f'inc-v1-{number:032x}',
                status,
                f'INTERFACE|router-{number}.example.invalid|Ethernet{number}',
                timestamp,
                state_changes,
                resolved_at,
                timestamp,
            ),
        )
        connection.commit()
        connection.close()

    def records(self):
        result = []
        for path in sorted(self.ready.glob('incident-state-v*-*.jsonl')):
            result.extend(
                json.loads(line)
                for line in path.read_text(encoding='utf-8').splitlines()
            )
        return result

    def test_initial_export_batches_and_exact_noop(self):
        for number in range(205):
            self.add_incident(number, state_changes=number % 2)

        first = OUTBOX.build(self.database, self.ready, self.delivered)

        self.assertEqual(first['incidents'], 205)
        self.assertEqual(first['changed'], 205)
        self.assertEqual(first['created'], 3)
        self.assertEqual(len(self.records()), 205)
        self.assertTrue((self.root / OUTBOX.LEDGER_NAME).exists())
        second = OUTBOX.build(self.database, self.ready, self.delivered)
        self.assertEqual(second['changed'], 0)
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['ready'], 3)

    def test_changed_incident_adds_one_immutable_batch(self):
        self.add_incident(1)
        OUTBOX.build(self.database, self.ready, self.delivered)
        original = tuple(path.read_bytes() for path in self.ready.iterdir())
        connection = sqlite3.connect(self.database)
        connection.execute(
            '''
            UPDATE incidents SET
                status='RESOLVED', resolved_at=?, updated_at=?,
                last_seen=?, observation_state_changes=2
            WHERE incident_id=?
            ''',
            (
                '2026-08-24T09:00:00+00:00',
                '2026-08-24T09:00:00+00:00',
                '2026-08-24T09:00:00+00:00',
                f'inc-v1-{1:032x}',
            ),
        )
        connection.commit()
        connection.close()

        state = OUTBOX.build(self.database, self.ready, self.delivered)

        self.assertEqual(state['changed'], 1)
        self.assertEqual(state['created'], 1)
        self.assertTrue(all(data in tuple(path.read_bytes() for path in self.ready.iterdir()) for data in original))
        latest = max(self.records(), key=lambda row: row['snapshot_version'])
        self.assertEqual(latest['lifecycle_status'], 'RESOLVED')
        self.assertTrue(latest['interface_flap'])

    def test_flap_projection_is_deterministic_and_has_no_ai_fields(self):
        self.add_incident(7, state_changes=3)
        OUTBOX.build(self.database, self.ready, self.delivered)
        record = self.records()[0]
        self.assertEqual(record['device'], 'router-7.example.invalid')
        self.assertEqual(record['entity_name'], 'Ethernet7')
        self.assertTrue(record['interface_flap'])
        self.assertEqual(record['type'], 'incident_lifecycle')
        self.assertEqual(record['producer_version'], 2)
        self.assertEqual(record['recurrence_count'], 0)
        self.assertTrue(record['snapshot_id'].startswith('state-v2-'))
        self.assertNotIn('model', record)
        self.assertNotIn('recommended_actions', record)

    def test_recurrence_count_is_derived_from_adverse_relapse_transitions(self):
        self.add_incident(8)
        connection = sqlite3.connect(self.database)
        connection.executemany(
            'INSERT INTO incident_transitions VALUES (?, ?, ?, ?)',
            [
                (f'inc-v1-{8:032x}', 'RECOVERING', 'OPEN', 'adverse_relapse'),
                (f'inc-v1-{8:032x}', 'OPEN', 'RECOVERING', 'recovery_evidence'),
                (f'inc-v1-{8:032x}', 'RECOVERING', 'OPEN', 'adverse_relapse'),
            ],
        )
        connection.commit()
        connection.close()

        OUTBOX.build(self.database, self.ready, self.delivered)

        self.assertEqual(self.records()[0]['recurrence_count'], 2)

    def test_ai_triage_incident_projects_summary_category_and_protocol(self):
        connection = sqlite3.connect(self.database)
        connection.executescript(
            '''
            CREATE TABLE triage_incident_summaries (
                incident_id TEXT, source_id TEXT, title TEXT, summary TEXT,
                created_at TEXT
            );
            CREATE TABLE triage_decisions (
                decision_id TEXT PRIMARY KEY, category TEXT
            );
            CREATE TABLE learned_detection_rules (
                rule_id TEXT PRIMARY KEY, category TEXT
            );
            '''
        )
        incident_id = 'inc-v1-triage'
        connection.execute(
            '''
            INSERT INTO incidents VALUES (
                ?, 'OPEN', 'unknown', '', 'event_signature',
                'event_signature|switch-a.example.invalid|BUFFER|signature',
                'warning', '2026-08-24T08:00:00+00:00',
                '2026-08-24T08:05:00+00:00', 2, 2, 0, 'detected',
                '2026-08-24T08:00:00+00:00', NULL, NULL, 2,
                '2026-08-24T08:05:00+00:00'
            )
            ''',
            (incident_id,),
        )
        connection.execute(
            "INSERT INTO triage_decisions VALUES('decision-1','capacity')"
        )
        connection.execute(
            '''
            INSERT INTO triage_incident_summaries VALUES(
                ?,'decision-1','ASIC buffer pressure',
                'A switch reported sustained buffer pressure.',
                '2026-08-24T08:05:00+00:00'
            )
            ''',
            (incident_id,),
        )
        connection.commit()
        connection.close()

        OUTBOX.build(self.database, self.ready, self.delivered)
        record = self.records()[0]
        self.assertEqual(record['title'], 'ASIC buffer pressure')
        self.assertEqual(
            record['body'], 'A switch reported sustained buffer pressure.'
        )
        self.assertEqual(record['event_family'], 'capacity')
        self.assertEqual(record['protocol'], 'event-triage')

    def test_legacy_version_1_delivery_remains_valid_during_version_2_export(self):
        self.add_incident(9)
        current = OUTBOX.load_incidents(self.database)
        record = json.loads(next(iter(current.values()))[1])
        record.pop('recurrence_count')
        record['producer_version'] = 1
        record['snapshot_id'] = 'state-v1-' + 'b' * 32
        record['snapshot_version'] = 1787559000000
        data = (OUTBOX.canonical_json(record) + '\n').encode('utf-8')
        path = self.delivered / OUTBOX.output_name(data)
        path.write_bytes(data)
        path.chmod(0o640)

        state = OUTBOX.build(self.database, self.ready, self.delivered)

        self.assertEqual(state['delivered'], 1)
        self.assertEqual(state['created'], 1)
        self.assertTrue(next(self.ready.iterdir()).name.startswith('incident-state-v2-'))

    def test_tampered_lifecycle_file_is_refused(self):
        self.add_incident(1)
        OUTBOX.build(self.database, self.ready, self.delivered)
        path = next(self.ready.iterdir())
        path.write_bytes(path.read_bytes().replace(b'warning', b'critical'))
        with self.assertRaisesRegex(
            OUTBOX.IncidentOutboxError, 'filename digest differs'
        ):
            OUTBOX.build(self.database, self.ready, self.delivered)

    def test_unknown_ledger_incident_is_refused(self):
        self.add_incident(1)
        OUTBOX.build(self.database, self.ready, self.delivered)
        connection = sqlite3.connect(self.root / OUTBOX.LEDGER_NAME)
        connection.execute(
            'INSERT INTO current_exports VALUES (?, ?, ?)',
            ('unknown', '0' * 64, '2026-08-24T09:00:00+00:00'),
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(
            OUTBOX.IncidentOutboxError, 'unknown incidents'
        ):
            OUTBOX.build(self.database, self.ready, self.delivered)


if __name__ == '__main__':
    unittest.main()
