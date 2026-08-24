#!/usr/bin/env python3
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import types
import unittest
from unittest import mock


GX10_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = GX10_DIR / 'sbin' / 'run-result-outbox.py'
INSTALLER_PATH = GX10_DIR / 'install' / 'install-result-outbox.py'
VERIFIER_PATH = GX10_DIR / 'install' / 'verify-result-outbox.py'
ACTIVATOR_PATH = GX10_DIR / 'install' / 'activate-result-outbox.py'
SERVICE_PATH = (
    GX10_DIR / 'systemd' / 'network-log-gx10-result-outbox.service'
)
TIMER_PATH = (
    GX10_DIR / 'systemd' / 'network-log-gx10-result-outbox.timer'
)
PRODUCER_PATH = GX10_DIR / 'sbin' / 'build-result-outbox.py'


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ResultOutboxManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_module('managed_outbox_runner_test', RUNNER_PATH)
        cls.installer = load_module(
            'managed_outbox_installer_test', INSTALLER_PATH
        )
        cls.verifier = load_module(
            'managed_outbox_verifier_test', VERIFIER_PATH
        )
        cls.activator = load_module(
            'managed_outbox_activator_test', ACTIVATOR_PATH
        )
        cls.producer = load_module(
            'managed_outbox_producer_test', PRODUCER_PATH
        )

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_runner_invokes_only_bound_local_paths(self):
        config = {
            'database_path': self.root / 'events.sqlite3',
            'ready_path': self.root / 'outbox' / 'ready',
            'delivered_path': self.root / 'outbox' / 'delivered',
        }
        calls = []

        def build(database, ready, delivered):
            calls.append((database, ready, delivered))
            return {
                'total': 3,
                'created': 2,
                'reused': 1,
                'ready': 3,
                'delivered': 0,
                'recovered': 0,
                'written_bytes': 512,
            }

        producer = types.SimpleNamespace(build=build)
        with (
            mock.patch.object(self.runner, 'load_config', return_value=config),
            mock.patch.object(
                self.runner, 'load_producer', return_value=producer
            ),
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()),
        ):
            result = self.runner.run()
        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                (
                    config['database_path'],
                    config['ready_path'],
                    config['delivered_path'],
                )
            ],
        )
        self.assertIn('GX10_MANAGED_RESULT_OUTBOX=PASS', output.getvalue())

    def test_runner_hash_is_bound_to_current_producer(self):
        expected = hashlib.sha256(PRODUCER_PATH.read_bytes()).hexdigest()
        self.assertEqual(self.runner.PRODUCER_SHA256, expected)
        with mock.patch.object(self.runner, 'validate_regular'):
            altered = self.root / 'producer.py'
            altered.write_text('value = 1\n', encoding='utf-8')
            with self.assertRaisesRegex(
                self.runner.ManagedOutboxError, 'hash differs'
            ):
                self.runner.load_producer(altered)

    def test_systemd_boundary_has_no_network_and_is_bounded(self):
        service = SERVICE_PATH.read_text(encoding='utf-8')
        timer = TIMER_PATH.read_text(encoding='utf-8')
        for line in (
            'Type=oneshot',
            'PrivateNetwork=yes',
            'RestrictAddressFamilies=AF_UNIX',
            'NoNewPrivileges=yes',
            'ProtectSystem=strict',
            'ReadWritePaths=/var/lib/network-log-gx10/result-outbox',
        ):
            self.assertIn(line, service)
        self.assertNotIn('Environment=', service)
        self.assertNotIn('ssh', service.casefold())
        self.assertIn('OnUnitInactiveSec=1min', timer)
        self.assertIn(
            'Unit=network-log-gx10-result-outbox.service', timer
        )

    def test_installer_atomic_file_publication(self):
        target = self.root / 'artifact'
        self.installer.install_bytes(
            target,
            b'exact bytes\n',
            0o640,
            os.geteuid(),
            os.getegid(),
        )
        self.assertEqual(target.read_bytes(), b'exact bytes\n')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
        self.assertEqual(
            list(self.root.glob('.artifact.install-*')), []
        )

    def create_database(self):
        database = self.root / 'events.sqlite3'
        connection = sqlite3.connect(database)
        connection.executescript(
            '''
            CREATE TABLE reasoning_packets (packet_id TEXT PRIMARY KEY);
            CREATE TABLE reasoning_model_versions (
              model_version TEXT PRIMARY KEY
            );
            CREATE TABLE reasoning_prompt_versions (
              prompt_version TEXT PRIMARY KEY
            );
            CREATE TABLE reasoning_runs (
              run_id TEXT PRIMARY KEY,
              status TEXT NOT NULL
            );
            CREATE TABLE reasoning_results (
              run_id TEXT PRIMARY KEY
            );
            INSERT INTO reasoning_runs VALUES ('run-1','SUCCEEDED');
            INSERT INTO reasoning_results VALUES ('run-1');
            '''
        )
        connection.commit()
        connection.close()
        return database

    def test_verifier_database_requires_terminal_result_invariant(self):
        database = self.create_database()
        state = self.verifier.validate_database(database)
        self.assertEqual(state, {'results': 1, 'started': 0})
        connection = sqlite3.connect(database)
        connection.execute(
            "INSERT INTO reasoning_runs VALUES ('run-2','STARTED')"
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(
            ValueError, 'reasoning state differs'
        ):
            self.verifier.validate_database(database)

    def test_activation_reasoning_snapshot_is_deterministic(self):
        database = self.create_database()
        connection = sqlite3.connect(database)
        connection.execute(
            "INSERT INTO reasoning_runs VALUES ('run-2','INVALID_OUTPUT')"
        )
        connection.commit()
        connection.close()
        first = self.activator.reasoning_snapshot(database)
        second = self.activator.reasoning_snapshot(database)
        self.assertEqual(first, second)
        self.assertEqual(first['runs'], 2)
        self.assertEqual(first['results'], 1)
        self.assertEqual(first['failures'], 1)
        self.assertRegex(first['digest'], r'^[0-9a-f]{64}$')

    def test_verifier_inventory_uses_service_file_identity(self):
        ready = self.root / 'ready'
        ready.mkdir()
        name = 'ai-result-v1-' + 'a' * 32 + '.jsonl'
        data = b'{"title":"synthetic"}\n'
        path = ready / name
        path.write_bytes(data)
        path.chmod(0o640)
        records = {name: data}
        names = self.verifier.inventory(
            ready,
            records,
            self.producer,
            os.geteuid(),
            os.getegid(),
        )
        self.assertEqual(names, {name})
        with self.assertRaisesRegex(ValueError, 'file differs'):
            self.verifier.inventory(
                ready,
                records,
                self.producer,
                os.geteuid() + 1,
                os.getegid(),
            )

    def test_install_sources_and_public_units_have_expected_modes(self):
        for source, _, mode in self.installer.ARTIFACTS:
            self.assertTrue(source.is_file())
            self.assertEqual(stat.S_IMODE(source.stat().st_mode), mode)
        self.assertNotIn('IdentityFile', INSTALLER_PATH.read_text())
        self.assertNotIn('known_hosts', INSTALLER_PATH.read_text())
        self.assertEqual(
            stat.S_IMODE(ACTIVATOR_PATH.stat().st_mode), 0o755
        )


if __name__ == '__main__':
    unittest.main()
