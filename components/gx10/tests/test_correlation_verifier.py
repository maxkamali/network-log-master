#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
VERIFIER_PATH = GX10_DIR / 'install' / 'verify-correlation.py'
SPEC = importlib.util.spec_from_file_location(
    'verify_correlation',
    VERIFIER_PATH,
)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class CorrelationVerifierTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
        connection = sqlite3.connect(self.database)
        connection.executescript(
            (GX10_DIR / 'sql' / 'initialize.sql').read_text()
        )
        connection.executescript(
            (GX10_DIR / 'sql' / 'incident-v1.sql').read_text()
        )
        connection.execute(
            """
            INSERT INTO source_files (remote_path, status, discovered_at)
            VALUES ('/spool/synthetic', 'processed', 'synthetic')
            """
        )
        connection.commit()
        connection.close()

    def add_recent(self):
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
            ) VALUES (
                '/spool/synthetic', 1,
                '2026-08-24T00:00:00+00:00', 1787529600000,
                'info', 'synthetic', '{}'
            )
            """
        )
        connection.commit()
        connection.close()
        return cursor.lastrowid

    def test_empty_incident_schema_is_caught_up(self):
        state = VERIFIER.validate_database(
            self.database,
            require_caught_up=True,
        )
        self.assertEqual(state['projection_lag'], 0)
        self.assertEqual(state['incident_lag'], 0)

    def test_active_verification_rejects_projection_lag(self):
        self.add_recent()
        installed = VERIFIER.validate_database(
            self.database,
            require_caught_up=False,
        )
        self.assertEqual(installed['projection_lag'], 1)
        with self.assertRaisesRegex(ValueError, 'watermark differs'):
            VERIFIER.validate_database(
                self.database,
                require_caught_up=True,
            )

    def test_exact_projection_and_incident_watermarks_pass(self):
        event_id = self.add_recent()
        connection = sqlite3.connect(self.database)
        connection.execute(
            """
            INSERT INTO event_enrichment (
                event_id,
                classified_at,
                classification_version,
                attention_eligible
            ) VALUES (?, 'synthetic', 4, 0)
            """,
            (event_id,),
        )
        connection.executemany(
            'INSERT INTO agent_state (key, value, updated_at) VALUES (?, ?, ?)',
            (
                (VERIFIER.PROJECTION_CURSOR, str(event_id), 'synthetic'),
                (VERIFIER.INCIDENT_CURSOR, str(event_id), 'synthetic'),
            ),
        )
        connection.commit()
        connection.close()
        state = VERIFIER.validate_database(
            self.database,
            require_caught_up=True,
        )
        self.assertEqual(state['canonical_rows'], 1)
        self.assertEqual(state['projection_lag'], 0)
        self.assertEqual(state['incident_lag'], 0)


if __name__ == '__main__':
    unittest.main()
