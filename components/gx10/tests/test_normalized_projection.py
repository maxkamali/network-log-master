#!/usr/bin/env python3
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


GX10_DIR = Path(__file__).resolve().parents[1]
APPLICATION = GX10_DIR / 'sbin' / 'enrich-events.py'
SCHEMA = GX10_DIR / 'sql' / 'initialize.sql'


def load_projection(database):
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        spec = importlib.util.spec_from_file_location(
            'gx10_normalized_projection_test',
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


def normalized_event(**changes):
    event = {
        'schema_version': 1,
        'timestamp': '2026-08-24T06:12:00+00:00',
        'ingest_timestamp': '2026-08-24T06:12:01+00:00',
        'device_timestamp': None,
        'hostname': 'router-a.example.invalid',
        'source_ip': '192.0.2.10',
        'source_port': 514,
        'facility': 'local7',
        'severity': 'info',
        'appname': 'syslog',
        'message': '%BGP-5-ADJCHANGE: synthetic',
        'raw_message': '%BGP-5-ADJCHANGE: synthetic',
        'parse_status': 'parsed',
        'vendor': 'arista',
        'os_family': 'eos',
        'event_code': 'BGP-5-ADJCHANGE',
        'event_family': 'bgp',
        'protocol': 'bgp',
        'signal_type': 'state_transition',
        'entity_type': 'bgp_peer',
        'entity_key': 'BGP|router-a.example.invalid|default|192.0.2.20',
        'state': 'down',
        'repeat_count': 1,
        'attention_eligible': True,
        'suppression_rule_id': None,
        'attributes': {
            'normalization_path': 'parser',
            'peer': '192.0.2.20',
        },
    }
    event.update(changes)
    return event


class NormalizedProjectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
        connection = sqlite3.connect(self.database)
        connection.executescript(SCHEMA.read_text())
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
        self.projection = load_projection(self.database)

    def insert_event(self, value):
        connection = sqlite3.connect(self.database)
        cursor = connection.execute(
            """
            INSERT INTO recent_events (
                source_file,
                record_number,
                timestamp,
                message,
                event_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                '/spool/2026/08/24/06/syslog-20260824-0612.jsonl.zst',
                connection.execute(
                    'SELECT COUNT(*) + 1 FROM recent_events'
                ).fetchone()[0],
                '2026-08-24T06:12:00+00:00',
                value.get('message', 'raw') if isinstance(value, dict) else 'raw',
                json.dumps(value, separators=(',', ':'), sort_keys=True),
            ),
        )
        event_id = cursor.lastrowid
        connection.commit()
        connection.close()
        return event_id

    def state(self):
        connection = sqlite3.connect(self.database)
        rows = connection.execute(
            """
            SELECT
                event_id,
                event_code,
                family,
                entity_type,
                entity_key,
                state,
                attention_eligible,
                suppression_rule_id,
                repeat_count,
                classification_version,
                vendor_hint,
                protocol,
                signal_type,
                attributes_json
            FROM event_enrichment
            ORDER BY event_id
            """
        ).fetchall()
        cursor = connection.execute(
            'SELECT value FROM agent_state WHERE key = ?',
            (self.projection.CURSOR_KEY,),
        ).fetchone()
        connection.close()
        return rows, cursor

    def run_projection(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.projection.main()

    def test_projection_preserves_history_is_idempotent_and_advances(self):
        historical_id = self.insert_event({'message': 'raw'})
        connection = sqlite3.connect(self.database)
        connection.execute(
            """
            INSERT INTO event_enrichment (
                event_id,
                classified_at,
                classification_version
            ) VALUES (?, ?, 3)
            """,
            (historical_id, '2026-08-23T00:00:00+00:00'),
        )
        connection.commit()
        connection.close()

        suppressed_id = self.insert_event(
            normalized_event(
                event_code='ICMPV6-3-ND_LOG',
                event_family='icmpv6',
                protocol='',
                signal_type='observation',
                entity_type='unknown',
                entity_key='',
                state='',
                attributes={'normalization_path': 'generic'},
            )
        )
        canonical_id = self.insert_event(normalized_event())

        self.assertEqual(self.run_projection(), 0)
        rows, cursor = self.state()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], historical_id)
        self.assertEqual(rows[0][9], 3)

        suppressed = next(row for row in rows if row[0] == suppressed_id)
        self.assertEqual(suppressed[1], 'ICMPV6-3-ND_LOG')
        self.assertEqual(suppressed[2], 'icmpv6')
        self.assertIsNone(suppressed[3])
        self.assertEqual(suppressed[6], 0)
        self.assertEqual(suppressed[7], 1)
        self.assertEqual(suppressed[9], 4)

        canonical = next(row for row in rows if row[0] == canonical_id)
        self.assertEqual(canonical[1], 'BGP-5-ADJCHANGE')
        self.assertEqual(canonical[2], 'bgp')
        self.assertEqual(canonical[3], 'bgp_peer')
        self.assertEqual(
            canonical[4],
            'BGP|router-a.example.invalid|default|192.0.2.20',
        )
        self.assertEqual(canonical[5], 'down')
        self.assertEqual(canonical[6], 1)
        self.assertIsNone(canonical[7])
        self.assertEqual(canonical[9], 4)
        self.assertEqual(canonical[10], 'arista')
        self.assertEqual(canonical[11], 'bgp')
        self.assertEqual(canonical[12], 'state_transition')
        self.assertEqual(
            json.loads(canonical[13]),
            normalized_event()['attributes'],
        )
        self.assertEqual(cursor, (str(canonical_id),))

        before = rows
        self.assertEqual(self.run_projection(), 0)
        rows, cursor = self.state()
        self.assertEqual(rows, before)

        appended_id = self.insert_event(
            normalized_event(
                event_code='FUTURE-1-EVENT',
                event_family='future',
                protocol='',
                signal_type='observation',
                entity_type='unknown',
                entity_key='',
                state='',
                attributes={'normalization_path': 'generic'},
            )
        )
        self.assertEqual(self.run_projection(), 0)
        rows, cursor = self.state()
        self.assertEqual(len(rows), 4)
        self.assertEqual(cursor, (str(appended_id),))

    def test_malformed_normalized_event_rolls_back_projection_and_cursor(self):
        malformed = normalized_event()
        malformed['repeat_count'] = 0
        self.insert_event(malformed)
        self.assertEqual(self.run_projection(), 1)
        rows, cursor = self.state()
        self.assertEqual(rows, [])
        self.assertIsNone(cursor)

    def test_newer_projection_state_fails_without_advancing_cursor(self):
        event_id = self.insert_event(normalized_event())
        connection = sqlite3.connect(self.database)
        connection.execute(
            """
            INSERT INTO event_enrichment (
                event_id,
                classified_at,
                classification_version
            ) VALUES (?, ?, 5)
            """,
            (event_id, '2026-08-24T00:00:00+00:00'),
        )
        connection.commit()
        connection.close()
        self.assertEqual(self.run_projection(), 1)
        rows, cursor = self.state()
        self.assertEqual(rows[0][9], 5)
        self.assertIsNone(cursor)


if __name__ == '__main__':
    unittest.main()
