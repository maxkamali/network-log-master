#!/usr/bin/env python3
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
GUARD_PATH = GX10_DIR / 'install' / 'migrate-local-reasoning.py'
SPEC = importlib.util.spec_from_file_location('migrate_local_reasoning', GUARD_PATH)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class LocalReasoningMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.root.chmod(0o700)
        self.references = self.root / 'references'
        self.references.mkdir(mode=0o700)
        self.install = self.root / 'install'
        self.install.mkdir(mode=0o700)
        self.configuration = self.root / 'configuration'
        self.configuration.mkdir(mode=0o700)
        self.recovery = self.root / 'recovery'
        self.recovery.mkdir(mode=0o700)
        self.database = self.root / 'events.sqlite3'
        self.backup = self.recovery / 'events-before-inference.sqlite3'
        self.packet_builder = self.install / 'build-reasoning-packets.py'
        self.packet_builder.write_bytes(b'#!/usr/bin/env python3\nprint("packet")\n')
        self.packet_builder.chmod(0o755)
        self.targets = (
            self.install / 'run-local-reasoning.py',
            self.configuration / 'reasoning-runtime-v2.json',
            self.configuration / 'incident-assessment-v2.txt',
            self.configuration / 'incident-assessment-output-v2.json',
        )

        connection = sqlite3.connect(self.database)
        for schema in (GUARD.BASE_SCHEMA, GUARD.INCIDENT_SCHEMA, GUARD.PACKET_SCHEMA):
            connection.executescript(schema.read_text(encoding='utf-8'))
        connection.commit()
        connection.close()

        self.saved = {
            name: getattr(GUARD, name)
            for name in (
                'PACKET_BUILDER_SHA256',
                'REFERENCE_ROOTS',
                'TARGET_UID',
                'TARGET_GID',
            )
        }
        self.addCleanup(self.restore)
        GUARD.PACKET_BUILDER_SHA256 = hashlib.sha256(
            self.packet_builder.read_bytes()
        ).hexdigest()
        GUARD.REFERENCE_ROOTS = (self.references,)
        GUARD.TARGET_UID = os.getuid()
        GUARD.TARGET_GID = os.getgid()

    def restore(self):
        for name, value in self.saved.items():
            setattr(GUARD, name, value)

    def table_names(self, database=None):
        connection = sqlite3.connect(database or self.database)
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        connection.close()
        return names

    def apply(self):
        GUARD.apply_migration(
            self.database,
            self.targets,
            self.packet_builder,
            self.backup,
        )

    def test_apply_verify_and_empty_state_rollback(self):
        self.apply()
        for (_, source, _, mode), target in zip(GUARD.ARTIFACTS, self.targets):
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(target.stat().st_mode & 0o777, mode)
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o600)
        self.assertTrue(set(GUARD.INFERENCE_TABLES) <= self.table_names())
        GUARD.validate_installed_state(
            self.database,
            self.targets,
            self.packet_builder,
            self.backup,
        )
        GUARD.rollback_migration(
            self.database,
            self.targets,
            self.packet_builder,
            self.backup,
        )
        self.assertTrue(all(not target.exists() for target in self.targets))
        self.assertTrue(set(GUARD.INFERENCE_TABLES).isdisjoint(self.table_names()))
        self.assertTrue(self.backup.exists())

    def test_divergent_database_is_refused_before_backup(self):
        connection = sqlite3.connect(self.database)
        connection.execute('CREATE TABLE divergent (value TEXT)')
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(GUARD.MigrationError, 'exact reasoning packet'):
            self.apply()
        self.assertFalse(self.backup.exists())
        self.assertTrue(all(not target.exists() for target in self.targets))

    def test_scheduler_reference_is_refused_before_backup(self):
        (self.references / 'scheduled').write_text(
            str(self.targets[0]),
            encoding='utf-8',
        )
        with self.assertRaisesRegex(GUARD.MigrationError, 'scheduler reference'):
            self.apply()
        self.assertFalse(self.backup.exists())
        self.assertTrue(all(not target.exists() for target in self.targets))

    def test_backup_is_exact_pre_inference_state(self):
        self.apply()
        self.assertTrue(set(GUARD.INFERENCE_TABLES).isdisjoint(self.table_names(self.backup)))
        connection = sqlite3.connect(self.backup)
        self.assertEqual(connection.execute('PRAGMA quick_check').fetchone()[0], 'ok')
        connection.close()

    def test_rollback_refuses_nonempty_inference_state(self):
        self.apply()
        connection = sqlite3.connect(self.database)
        connection.execute(
            '''
            INSERT INTO reasoning_model_versions VALUES (
                'model-v1', 'ollama', 'model:latest', ?, 'sha256:' || ?,
                '{}', '2026-08-24T08:30:00+00:00'
            )
            ''',
            ('a' * 64, 'b' * 64),
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(GUARD.MigrationError, 'nonempty inference'):
            GUARD.rollback_migration(
                self.database,
                self.targets,
                self.packet_builder,
                self.backup,
            )
        self.assertTrue(all(target.exists() for target in self.targets))
        self.assertTrue(set(GUARD.INFERENCE_TABLES) <= self.table_names())

    def test_partial_artifact_failure_rolls_back_schema_and_created_files(self):
        original = GUARD.install_one
        calls = []

        def fail_second(source, target, mode):
            calls.append(target)
            if len(calls) == 2:
                raise GUARD.MigrationError('synthetic artifact failure')
            original(source, target, mode)

        GUARD.install_one = fail_second
        self.addCleanup(setattr, GUARD, 'install_one', original)
        with self.assertRaisesRegex(GUARD.MigrationError, 'synthetic artifact failure'):
            self.apply()
        self.assertTrue(set(GUARD.INFERENCE_TABLES).isdisjoint(self.table_names()))
        self.assertTrue(all(not target.exists() for target in self.targets))
        self.assertTrue(self.backup.exists())


if __name__ == '__main__':
    unittest.main()
