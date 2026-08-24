#!/usr/bin/env python3
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
GUARD_PATH = GX10_DIR / 'install' / 'migrate-incident-engine.py'
SPEC = importlib.util.spec_from_file_location(
    'migrate_incident_engine',
    GUARD_PATH,
)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


def digest(value):
    return hashlib.sha256(value).hexdigest()


class IncidentMigrationTests(unittest.TestCase):
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
        self.target = self.install / 'incident-engine.py'
        self.backup = self.recovery / 'events-before-incident.sqlite3'
        self.candidate = self.root / 'candidate.py'
        self.engine = b'#!/usr/bin/env python3\nprint("incident")\n'
        self.candidate.write_bytes(self.engine)
        self.candidate.chmod(0o755)

        connection = sqlite3.connect(self.database)
        connection.executescript(GUARD.BASE_SCHEMA.read_text())
        connection.commit()
        connection.close()

        self.saved = {
            name: getattr(GUARD, name)
            for name in (
                'ENGINE_SOURCE',
                'ENGINE_SHA256',
                'REFERENCE_ROOTS',
                'TARGET_UID',
                'TARGET_GID',
            )
        }
        self.addCleanup(self.restore)
        GUARD.ENGINE_SOURCE = self.candidate
        GUARD.ENGINE_SHA256 = digest(self.engine)
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
        self.assertEqual(self.target.read_bytes(), self.engine)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o600)
        self.assertTrue(
            {'incidents', 'incident_evidence', 'incident_transitions'}
            <= self.table_names()
        )
        GUARD.validate_installed_state(
            self.database,
            self.target,
            self.backup,
        )

        GUARD.rollback_migration(self.database, self.target, self.backup)
        self.assertFalse(self.target.exists())
        self.assertFalse(
            {'incidents', 'incident_evidence', 'incident_transitions'}
            & self.table_names()
        )
        self.assertTrue(self.backup.exists())

    def test_divergent_database_is_refused_before_backup(self):
        connection = sqlite3.connect(self.database)
        connection.execute('CREATE TABLE divergent (value TEXT)')
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(
            GUARD.MigrationError,
            'exact base schema',
        ):
            GUARD.apply_migration(
                self.database,
                self.target,
                self.backup,
            )
        self.assertFalse(self.target.exists())
        self.assertFalse(self.backup.exists())

    def test_scheduler_reference_is_refused(self):
        (self.references / 'scheduled').write_text(str(self.target))
        with self.assertRaisesRegex(
            GUARD.MigrationError,
            'scheduler reference',
        ):
            GUARD.apply_migration(
                self.database,
                self.target,
                self.backup,
            )
        self.assertFalse(self.target.exists())
        self.assertFalse(self.backup.exists())

    def test_suppression_drift_is_refused_before_backup(self):
        connection = sqlite3.connect(self.database)
        connection.execute(
            'UPDATE suppression_rules SET enabled = 0 WHERE id = 1'
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(
            GUARD.MigrationError,
            'suppression corpus differs',
        ):
            GUARD.apply_migration(
                self.database,
                self.target,
                self.backup,
            )
        self.assertFalse(self.target.exists())
        self.assertFalse(self.backup.exists())

    def test_rollback_refuses_cursor_or_incident_state(self):
        GUARD.apply_migration(self.database, self.target, self.backup)
        connection = sqlite3.connect(self.database)
        connection.execute(
            'INSERT INTO agent_state (key, value, updated_at) VALUES (?, ?, ?)',
            (GUARD.CURSOR_KEY, '0', '2026-08-24T00:00:00+00:00'),
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(
            GUARD.MigrationError,
            'cursor',
        ):
            GUARD.rollback_migration(
                self.database,
                self.target,
                self.backup,
            )
        self.assertTrue(self.target.exists())
        self.assertIn('incidents', self.table_names())


if __name__ == '__main__':
    unittest.main()
