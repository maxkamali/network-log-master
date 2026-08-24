#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
GUARD_PATH = GX10_DIR / 'install' / 'migrate-reasoning-packets.py'
SPEC = importlib.util.spec_from_file_location(
    'migrate_reasoning_packets',
    GUARD_PATH,
)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


def digest(value):
    return hashlib.sha256(value).hexdigest()


class ReasoningMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.root.chmod(0o700)
        self.references = self.root / 'references'
        self.references.mkdir(mode=0o700)
        self.install = self.root / 'install'
        self.install.mkdir(mode=0o700)
        self.recovery = self.root / 'recovery'
        self.recovery.mkdir(mode=0o700)
        self.database = self.root / 'events.sqlite3'
        self.target = self.install / 'build-reasoning-packets.py'
        self.backup = self.recovery / 'events-before-reasoning.sqlite3'
        self.candidate = self.root / 'candidate.py'
        self.builder = b'#!/usr/bin/env python3\nprint("packet")\n'
        self.candidate.write_bytes(self.builder)
        self.candidate.chmod(0o755)

        connection = sqlite3.connect(self.database)
        connection.executescript(GUARD.BASE_SCHEMA.read_text(encoding='utf-8'))
        connection.executescript(
            GUARD.INCIDENT_SCHEMA.read_text(encoding='utf-8')
        )
        connection.commit()
        connection.close()

        self.saved = {
            name: getattr(GUARD, name)
            for name in (
                'BUILDER_SOURCE',
                'BUILDER_SHA256',
                'REFERENCE_ROOTS',
                'TARGET_UID',
                'TARGET_GID',
            )
        }
        self.addCleanup(self.restore)
        GUARD.BUILDER_SOURCE = self.candidate
        GUARD.BUILDER_SHA256 = digest(self.builder)
        GUARD.REFERENCE_ROOTS = (self.references,)
        GUARD.TARGET_UID = os.getuid()
        GUARD.TARGET_GID = os.getgid()

    def restore(self):
        for name, value in self.saved.items():
            setattr(GUARD, name, value)

    def table_names(self):
        connection = sqlite3.connect(self.database)
        values = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        connection.close()
        return values

    def test_apply_verify_and_empty_state_rollback(self):
        GUARD.apply_migration(self.database, self.target, self.backup)
        self.assertEqual(self.target.read_bytes(), self.builder)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o600)
        self.assertIn('reasoning_packets', self.table_names())
        GUARD.validate_installed_state(
            self.database,
            self.target,
            self.backup,
        )
        GUARD.rollback_migration(self.database, self.target, self.backup)
        self.assertFalse(self.target.exists())
        self.assertNotIn('reasoning_packets', self.table_names())
        self.assertTrue(self.backup.exists())

    def test_divergent_database_is_refused_before_backup(self):
        connection = sqlite3.connect(self.database)
        connection.execute('CREATE TABLE divergent (value TEXT)')
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(GUARD.MigrationError, 'exact incident schema'):
            GUARD.apply_migration(self.database, self.target, self.backup)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.backup.exists())

    def test_scheduler_reference_is_refused(self):
        (self.references / 'scheduled').write_text(str(self.target))
        with self.assertRaisesRegex(GUARD.MigrationError, 'scheduler reference'):
            GUARD.apply_migration(self.database, self.target, self.backup)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.backup.exists())

    def test_backup_is_exact_pre_reasoning_state(self):
        GUARD.apply_migration(self.database, self.target, self.backup)
        backup = sqlite3.connect(self.backup)
        try:
            self.assertNotIn(
                'reasoning_packets',
                {
                    row[0]
                    for row in backup.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                },
            )
            self.assertEqual(backup.execute('PRAGMA quick_check').fetchone()[0], 'ok')
        finally:
            backup.close()

    def test_rollback_refuses_nonempty_packet_state(self):
        GUARD.apply_migration(self.database, self.target, self.backup)
        packet = json.dumps(
            {
                'packet_id': 'pkt-v1-synthetic',
                'packet_version': 1,
                'policy_version': 1,
                'wake': {
                    'primary_reason': 'incident_opened',
                    'priority': 90,
                    'reasons': ['incident_opened'],
                },
            },
            separators=(',', ':'),
            sort_keys=True,
        )
        connection = sqlite3.connect(self.database)
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute(
            "INSERT INTO source_files (remote_path, status, discovered_at) "
            "VALUES ('/spool/synthetic', 'processed', '2026-08-24T00:00:00+00:00')"
        )
        event_id = connection.execute(
            '''
            INSERT INTO recent_events (
                source_file, record_number, timestamp, timestamp_epoch_ms,
                severity, message, event_json
            ) VALUES (
                '/spool/synthetic', 1, '2026-08-24T00:00:00+00:00', 1,
                'warning', 'synthetic', '{}'
            )
            '''
        ).lastrowid
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
                'inc-v1-synthetic', 'correlation', 'OPEN', 'synthetic',
                'synthetic', 'synthetic', 'synthetic', 'warning',
                '2026-08-24T00:00:00+00:00', 1,
                '2026-08-24T00:00:00+00:00', 1, 1, 1, 0, 'down',
                '2026-08-24T00:00:00+00:00', NULL, NULL, ?, '{}', 1,
                '2026-08-24T00:00:00+00:00',
                '2026-08-24T00:00:00+00:00'
            )
            ''',
            (event_id,),
        )
        connection.execute(
            '''
            INSERT INTO reasoning_packets VALUES (
                'pkt-v1-synthetic', 'inc-v1-synthetic', 1, 1,
                'incident_opened', '["incident_opened"]', 90, ?, 1, 1,
                1, 0, 1, '2026-08-24T00:00:00+00:00', ?, ?
            )
            ''',
            (
                event_id,
                packet,
                hashlib.sha256(packet.encode()).hexdigest(),
            ),
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(GUARD.MigrationError, 'nonempty'):
            GUARD.rollback_migration(self.database, self.target, self.backup)
        self.assertTrue(self.target.exists())
        self.assertIn('reasoning_packets', self.table_names())


if __name__ == '__main__':
    unittest.main()
