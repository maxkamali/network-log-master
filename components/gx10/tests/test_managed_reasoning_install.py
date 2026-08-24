#!/usr/bin/env python3
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


GX10_DIR = Path(__file__).resolve().parents[1]


def load(name, filename):
    path = GX10_DIR / 'install' / filename
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLER = load(
    'install_managed_reasoning', 'install-managed-reasoning.py'
)
ACTIVATOR = load(
    'activate_managed_reasoning', 'activate-managed-reasoning.py'
)


class ManagedReasoningInstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_private_config_is_canonical_and_absolute(self):
        database = self.root / 'events.sqlite3'
        rendered = INSTALLER.render_config(database)
        self.assertEqual(
            json.loads(rendered), {'database_path': str(database)}
        )
        self.assertTrue(rendered.endswith(b'\n'))
        with self.assertRaisesRegex(INSTALLER.InstallError, 'path is invalid'):
            INSTALLER.render_config(Path('relative.sqlite3'))

    def test_dropin_binds_identity_dependencies_and_database_parent(self):
        database = self.root / 'state' / 'events.sqlite3'
        rendered = INSTALLER.render_dropin(
            'runtime-user',
            'runtime-group',
            'correlation.service',
            'ollama.service',
            database,
        ).decode()
        self.assertEqual(
            rendered,
            '[Unit]\n'
            'After=\n'
            'After=correlation.service ollama.service\n'
            '\n[Service]\n'
            'User=runtime-user\n'
            'Group=runtime-group\n'
            'ReadWritePaths=\n'
            f'ReadWritePaths={database.parent}\n',
        )
        with self.assertRaisesRegex(
            INSTALLER.InstallError, 'identity is invalid'
        ):
            INSTALLER.render_dropin(
                'runtime-user\nRootDirectory=/',
                'runtime-group',
                'correlation.service',
                'ollama.service',
                database,
            )

    def test_atomic_file_install_reuses_exact_and_refuses_divergence(self):
        target = self.root / 'artifact'
        self.assertTrue(
            INSTALLER.install_bytes(
                target,
                b'candidate\n',
                0o640,
                os.getuid(),
                os.getgid(),
            )
        )
        self.assertFalse(
            INSTALLER.install_bytes(
                target,
                b'candidate\n',
                0o640,
                os.getuid(),
                os.getgid(),
            )
        )
        with self.assertRaisesRegex(
            INSTALLER.InstallError, 'artifact differs'
        ):
            INSTALLER.install_bytes(
                target,
                b'divergent\n',
                0o640,
                os.getuid(),
                os.getgid(),
            )

    def test_timer_upgrade_accepts_only_exact_prior_version(self):
        target = self.root / 'reasoning.timer'
        target.write_bytes(INSTALLER.PREVIOUS_TIMER_BYTES)
        target.chmod(0o644)
        current = b'current timer\n'
        self.assertEqual(
            INSTALLER.install_or_upgrade_bytes(
                target,
                current,
                INSTALLER.PREVIOUS_TIMER_BYTES,
                0o644,
                os.getuid(),
                os.getgid(),
            ),
            'upgraded',
        )
        self.assertEqual(target.read_bytes(), current)
        self.assertEqual(
            INSTALLER.install_or_upgrade_bytes(
                target,
                current,
                INSTALLER.PREVIOUS_TIMER_BYTES,
                0o644,
                os.getuid(),
                os.getgid(),
            ),
            'reused',
        )
        target.write_bytes(b'divergent\n')
        with self.assertRaisesRegex(
            INSTALLER.InstallError, 'upgrade artifact differs'
        ):
            INSTALLER.install_or_upgrade_bytes(
                target,
                current,
                INSTALLER.PREVIOUS_TIMER_BYTES,
                0o644,
                os.getuid(),
                os.getgid(),
            )

    def test_runner_upgrade_accepts_only_exact_prior_hash(self):
        target = self.root / 'managed-runner.py'
        previous = b'previous runner\n'
        current = b'current runner\n'
        target.write_bytes(previous)
        target.chmod(0o755)
        previous_sha256 = hashlib.sha256(previous).hexdigest()
        action, saved = INSTALLER.install_or_upgrade_sha256(
            target,
            current,
            previous_sha256,
            0o755,
            os.getuid(),
            os.getgid(),
        )
        self.assertEqual(action, 'upgraded')
        self.assertEqual(saved, previous)
        self.assertEqual(target.read_bytes(), current)
        action, saved = INSTALLER.install_or_upgrade_sha256(
            target,
            current,
            previous_sha256,
            0o755,
            os.getuid(),
            os.getgid(),
        )
        self.assertEqual((action, saved), ('reused', None))
        target.write_bytes(b'divergent\n')
        with self.assertRaisesRegex(
            INSTALLER.InstallError, 'upgrade artifact differs'
        ):
            INSTALLER.install_or_upgrade_sha256(
                target,
                current,
                previous_sha256,
                0o755,
                os.getuid(),
                os.getgid(),
            )

    def test_compatibility_upgrade_targets_are_exact_and_narrow(self):
        self.assertEqual(
            set(INSTALLER.PREVIOUS_ARTIFACT_SHA256),
            {
                INSTALLER.CONFIG_DIR
                / 'incident-assessment-output-v2.json',
                INSTALLER.CONFIG_DIR / 'reasoning-runtime-v2.json',
                INSTALLER.LIBEXEC_DIR / 'run-local-reasoning.py',
                INSTALLER.LIBEXEC_DIR / 'run-managed-reasoning.py',
            },
        )
        self.assertEqual(
            set(INSTALLER.PREVIOUS_ARTIFACT_SHA256.values()),
            {
                '1ec4e28d0d18320c7469d4f1bb26a5c766515ff008c5803d24ce214ded69928a',
                'e7bde8d878e71d8a1b11af01170ff332920aae1df1a65536b516abf5862428f0',
                'e9b894afa16fd5f138cfeec299be58328fd02454db2b53c3e395809e04d58cd0',
                'c0c095661a7042be57230fb8fc856c03f5fe191ab604e4e246138f28156a3bee',
            },
        )

    def test_activation_orders_backup_cycle_then_timer(self):
        database = self.root / 'events.sqlite3'
        database.touch()
        backup = self.root / 'backup.sqlite3'
        with mock.patch.object(ACTIVATOR, 'run_verifier') as verifier, mock.patch.object(
            ACTIVATOR, 'create_backup'
        ) as create_backup, mock.patch.object(
            ACTIVATOR, 'counts', side_effect=[(0, 0, 0), (4, 1, 1)]
        ), mock.patch.object(ACTIVATOR.subprocess, 'run') as run:
            ACTIVATOR.activate(database, backup)
        create_backup.assert_called_once_with(database, backup)
        self.assertEqual(
            [call.args for call in verifier.call_args_list],
            [
                (database, '--installed'),
                (database, '--installed'),
                (database, '--active'),
            ],
        )
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ['systemctl', 'start', ACTIVATOR.SERVICE],
                ['systemctl', 'enable', '--now', ACTIVATOR.TIMER],
            ],
        )

    def test_activation_failure_disables_only_reasoning(self):
        database = self.root / 'events.sqlite3'
        database.touch()
        backup = self.root / 'backup.sqlite3'
        with mock.patch.object(
            ACTIVATOR,
            'run_verifier',
            side_effect=[None, ValueError('synthetic failure')],
        ), mock.patch.object(ACTIVATOR, 'create_backup'), mock.patch.object(
            ACTIVATOR, 'counts', return_value=(0, 0, 0)
        ), mock.patch.object(ACTIVATOR.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'synthetic failure'):
                ACTIVATOR.activate(database, backup)
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ['systemctl', 'start', ACTIVATOR.SERVICE],
                ['systemctl', 'disable', '--now', ACTIVATOR.TIMER],
                ['systemctl', 'stop', ACTIVATOR.SERVICE],
                ['systemctl', 'reset-failed', ACTIVATOR.SERVICE],
            ],
        )

    def test_activation_rejects_more_than_one_run(self):
        database = self.root / 'events.sqlite3'
        database.touch()
        backup = self.root / 'backup.sqlite3'
        with mock.patch.object(ACTIVATOR, 'run_verifier'), mock.patch.object(
            ACTIVATOR, 'create_backup'
        ), mock.patch.object(
            ACTIVATOR, 'counts', side_effect=[(0, 0, 0), (4, 2, 1)]
        ), mock.patch.object(ACTIVATOR.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'bounded cycle'):
                ACTIVATOR.activate(database, backup)
        self.assertIn(
            ['systemctl', 'disable', '--now', ACTIVATOR.TIMER],
            [call.args[0] for call in run.call_args_list],
        )


if __name__ == '__main__':
    unittest.main()
