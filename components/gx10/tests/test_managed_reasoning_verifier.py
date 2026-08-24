#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
VERIFIER_PATH = GX10_DIR / 'install' / 'verify-managed-reasoning.py'
SPECIFICATION = importlib.util.spec_from_file_location(
    'managed_reasoning_verifier_test', VERIFIER_PATH
)
VERIFIER = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(VERIFIER)


class ManagedReasoningVerifierTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
        connection = sqlite3.connect(self.database)
        connection.executescript(
            '''
            CREATE TABLE recent_events (id INTEGER PRIMARY KEY);
            CREATE TABLE event_enrichment (
                event_id INTEGER PRIMARY KEY,
                classification_version INTEGER NOT NULL
            );
            CREATE TABLE agent_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE reasoning_packets (packet_id TEXT PRIMARY KEY);
            CREATE TABLE reasoning_model_versions (
                model_version TEXT PRIMARY KEY
            );
            CREATE TABLE reasoning_prompt_versions (
                prompt_version TEXT PRIMARY KEY
            );
            CREATE TABLE reasoning_runs (
                run_id TEXT PRIMARY KEY,
                packet_id TEXT NOT NULL,
                model_version TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE reasoning_results (run_id TEXT PRIMARY KEY);
            '''
        )
        connection.commit()
        connection.close()

    def test_empty_state_is_caught_up_and_healthy(self):
        state = VERIFIER.validate_database(self.database)
        self.assertEqual(state['projection_lag'], 0)
        self.assertEqual(state['incident_lag'], 0)
        self.assertEqual(state['pending'], 0)
        self.assertEqual(state['started'], 0)

    def test_caught_up_verification_rejects_projection_lag(self):
        connection = sqlite3.connect(self.database)
        connection.execute('INSERT INTO recent_events VALUES (1)')
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(ValueError, 'watermark differs'):
            VERIFIER.validate_database(self.database)
        state = VERIFIER.validate_database(
            self.database, require_caught_up=False
        )
        self.assertEqual(state['projection_lag'], 1)

    def test_started_reservation_is_explicitly_unhealthy(self):
        connection = sqlite3.connect(self.database)
        connection.execute(
            'INSERT INTO reasoning_packets VALUES (?)', ('packet-1',)
        )
        connection.execute(
            'INSERT INTO reasoning_runs VALUES (?, ?, ?, ?, 1, ?)',
            (
                'run-1',
                'packet-1',
                VERIFIER.RUNNER.MODEL_VERSION,
                VERIFIER.RUNNER.PROMPT_VERSION,
                'STARTED',
            ),
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(ValueError, 'unreconciled STARTED'):
            VERIFIER.validate_database(self.database)

    def test_success_without_result_is_rejected(self):
        connection = sqlite3.connect(self.database)
        connection.execute(
            'INSERT INTO reasoning_packets VALUES (?)', ('packet-1',)
        )
        connection.execute(
            'INSERT INTO reasoning_runs VALUES (?, ?, ?, ?, 1, ?)',
            (
                'run-1',
                'packet-1',
                VERIFIER.RUNNER.MODEL_VERSION,
                VERIFIER.RUNNER.PROMPT_VERSION,
                'SUCCEEDED',
            ),
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(ValueError, 'result invariant'):
            VERIFIER.validate_database(self.database)


if __name__ == '__main__':
    unittest.main()
