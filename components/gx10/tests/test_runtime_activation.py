#!/usr/bin/env python3
import importlib.util
import sqlite3
import tempfile
import unittest
from unittest import mock
from pathlib import Path

GX10_DIR = Path(__file__).resolve().parents[1]


def load_script(name, filename):
    path = GX10_DIR / 'install' / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = load_script('verify_runtime', 'verify-runtime.py')
ACTIVATOR = load_script('activate_runtime', 'activate-runtime.py')


class RuntimeActivationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
        connection = sqlite3.connect(self.database)
        try:
            connection.executescript(
                (GX10_DIR / 'sql' / 'initialize.sql').read_text(encoding='utf-8')
            )
            connection.executescript(
                (GX10_DIR / 'sql' / 'incident-v1.sql').read_text(encoding='utf-8')
            )
            connection.executescript(
                (GX10_DIR / 'sql' / 'reasoning-v1.sql').read_text(encoding='utf-8')
            )
            connection.executescript(
                (GX10_DIR / 'sql' / 'inference-v1.sql').read_text(encoding='utf-8')
            )
        finally:
            connection.close()

    def test_exact_empty_database_passes_preactivation_guard(self):
        VERIFIER.validate_database(
            self.database,
            require_empty=True,
            schema_path=GX10_DIR / 'sql' / 'initialize.sql',
        )

    def test_nonempty_database_is_refused(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "INSERT INTO agent_state VALUES ('cursor', '1', 'synthetic')"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(ValueError, 'nonempty application state'):
            VERIFIER.validate_database(
                self.database,
                require_empty=True,
                schema_path=GX10_DIR / 'sql' / 'initialize.sql',
            )

    def test_schema_drift_is_refused(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute('CREATE TABLE unexpected (value TEXT)')
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(ValueError, 'schema differs'):
            VERIFIER.validate_database(
                self.database,
                require_empty=True,
                schema_path=GX10_DIR / 'sql' / 'initialize.sql',
            )

    def test_activation_requires_two_explicit_confirmations(self):
        with self.assertRaisesRegex(ValueError, 'CLEAN_INSTALL_CONFIRM'):
            ACTIVATOR.require_authorization(0, {})
        with self.assertRaisesRegex(ValueError, 'GX10_ACTIVATE_CONFIRM'):
            ACTIVATOR.require_authorization(
                0,
                {'CLEAN_INSTALL_CONFIRM': 'YES-CLEAN-GX10'},
            )
        ACTIVATOR.require_authorization(
            0,
            {
                'CLEAN_INSTALL_CONFIRM': 'YES-CLEAN-GX10',
                'GX10_ACTIVATE_CONFIRM': 'ENABLE-VERIFIED-GX10',
            },
        )

    def test_activation_unit_order_is_ollama_then_timer(self):
        self.assertEqual(
            ACTIVATOR.ACTIVATION_UNITS,
            ('ollama.service', 'network-log-gx10.timer'),
        )
        self.assertEqual(
            ACTIVATOR.OLLAMA_PREACTIVATION_ARGS,
            ('--offline', '--hash-blobs'),
        )

    def test_preactivation_spool_must_be_empty(self):
        path = Path(self.directory.name) / 'spool'
        path.mkdir()
        VERIFIER.require_empty_directory(path)
        (path / 'unexpected').write_text('synthetic', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'preexisting spool'):
            VERIFIER.require_empty_directory(path)

    def test_rollback_stops_pipeline_then_disables_changed_units(self):
        with mock.patch.object(ACTIVATOR.subprocess, 'run') as run:
            ACTIVATOR.rollback(list(ACTIVATOR.ACTIVATION_UNITS))
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(
            commands,
            [
                ['systemctl', 'stop', 'network-log-gx10.service'],
                [
                    'systemctl',
                    'disable',
                    '--now',
                    'network-log-gx10.timer',
                ],
                ['systemctl', 'disable', '--now', 'ollama.service'],
            ],
        )


if __name__ == '__main__':
    unittest.main()
