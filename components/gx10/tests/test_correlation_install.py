#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


GX10_DIR = Path(__file__).resolve().parents[1]


def load(name, filename):
    path = GX10_DIR / 'install' / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALLER = load('install_correlation', 'install-correlation.py')
ACTIVATOR = load('activate_correlation', 'activate-correlation.py')


class CorrelationInstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_private_config_is_canonical_and_absolute(self):
        database = self.root / 'events.sqlite3'
        rendered = INSTALLER.render_config(database)
        self.assertEqual(
            json.loads(rendered),
            {'database_path': str(database)},
        )
        self.assertTrue(rendered.endswith(b'\n'))
        with self.assertRaisesRegex(INSTALLER.InstallError, 'path is invalid'):
            INSTALLER.render_config(Path('relative.sqlite3'))

    def test_dropin_is_strict_and_resets_only_ordering(self):
        rendered = INSTALLER.render_dropin(
            'runtime-user',
            'runtime-group',
            'private-pipeline.service',
        ).decode()
        self.assertEqual(
            rendered,
            '[Unit]\n'
            'After=\n'
            'After=private-pipeline.service\n'
            '\n[Service]\n'
            'User=runtime-user\n'
            'Group=runtime-group\n',
        )
        with self.assertRaisesRegex(
            INSTALLER.InstallError,
            'identity is invalid',
        ):
            INSTALLER.render_dropin(
                'runtime-user\nRootDirectory=/',
                'runtime-group',
                'private-pipeline.service',
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
            INSTALLER.InstallError,
            'artifact differs',
        ):
            INSTALLER.install_bytes(
                target,
                b'divergent\n',
                0o640,
                os.getuid(),
                os.getgid(),
            )

    def test_activation_orders_backfill_before_timer(self):
        database = self.root / 'events.sqlite3'
        database.touch()
        with mock.patch.object(ACTIVATOR, 'run_verifier') as verifier, mock.patch.object(
            ACTIVATOR.subprocess,
            'run',
        ) as run:
            ACTIVATOR.activate(database)
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

    def test_activation_failure_disables_timer_and_preserves_state(self):
        database = self.root / 'events.sqlite3'
        database.write_text('state')
        with mock.patch.object(
            ACTIVATOR,
            'run_verifier',
            side_effect=[None, ValueError('synthetic failure')],
        ), mock.patch.object(ACTIVATOR.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'synthetic failure'):
                ACTIVATOR.activate(database)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(
            commands,
            [
                ['systemctl', 'start', ACTIVATOR.SERVICE],
                ['systemctl', 'disable', '--now', ACTIVATOR.TIMER],
                ['systemctl', 'stop', ACTIVATOR.SERVICE],
            ],
        )
        self.assertEqual(database.read_text(), 'state')


if __name__ == '__main__':
    unittest.main()
