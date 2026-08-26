#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest
from unittest import mock


GX10_DIR = Path(__file__).resolve().parents[1]
SCHEMAS = tuple(
    GX10_DIR / 'sql' / name
    for name in (
        'initialize.sql', 'incident-v1.sql', 'reasoning-v1.sql',
        'inference-v1.sql',
    )
)
MIGRATION_PATH = GX10_DIR / 'install' / 'migrate-ai-triage.py'


class AiTriageMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / 'events.sqlite3'
        self.backup = self.root / 'before-ai-triage.sqlite3'
        connection = sqlite3.connect(self.database)
        for schema in SCHEMAS:
            connection.executescript(schema.read_text(encoding='utf-8'))
        connection.execute(
            "INSERT INTO source_files(remote_path,status,discovered_at) "
            "VALUES('/spool/synthetic','processed','2026-08-26T00:00:00+00:00')"
        )
        for number, timestamp in enumerate(
            (1787620000000, 1787710000000), start=1
        ):
            connection.execute(
                '''
                INSERT INTO recent_events(
                    source_file,record_number,timestamp,timestamp_epoch_ms,
                    severity,message,event_json
                ) VALUES('/spool/synthetic',?,'2026-08-26T00:00:00+00:00',?,
                         'error','synthetic','{}')
                ''',
                (number, timestamp),
            )
        connection.execute(
            "INSERT INTO agent_state VALUES(" 
            "'incident_engine_v1_last_event_id','2','2026-08-26T04:00:00+00:00')"
        )
        connection.commit()
        connection.close()
        self.database.chmod(0o640)
        specification = importlib.util.spec_from_file_location(
            'ai_triage_migration_test', MIGRATION_PATH
        )
        self.migration = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(self.migration)

    def test_adds_schema_backup_and_24_hour_cursor_floor(self):
        inactive = types.SimpleNamespace(returncode=3)
        with mock.patch.object(
            self.migration.subprocess, 'run', return_value=inactive
        ), mock.patch.object(self.migration.os, 'chown'):
            self.migration.migrate(
                self.database, self.backup, 1787716800000
            )
        self.assertTrue(self.backup.is_file())
        connection = sqlite3.connect(self.database)
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        cursor = connection.execute(
            "SELECT value FROM agent_state WHERE key='ai_triage_v1_last_event_id'"
        ).fetchone()[0]
        connection.close()
        self.assertTrue(self.migration.TRIAGE_TABLES <= tables)
        self.assertEqual(cursor, '1')

    def test_refuses_active_reasoning_service(self):
        active = types.SimpleNamespace(returncode=0)
        with mock.patch.object(
            self.migration.subprocess, 'run', return_value=active
        ):
            with self.assertRaisesRegex(
                self.migration.MigrationError, 'stop the managed reasoning'
            ):
                self.migration.migrate(
                    self.database, self.backup, 1787716800000
                )


if __name__ == '__main__':
    unittest.main()
