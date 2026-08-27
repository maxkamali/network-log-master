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
PRODUCER_PATH = GX10_DIR / 'sbin' / 'create-outbox-snapshot.py'
RUNNER_PATH = GX10_DIR / 'sbin' / 'run-outbox-snapshot.py'
SERVICE_PATH = (
    GX10_DIR / 'systemd' / 'network-log-gx10-outbox-snapshot.service'
)
OUTBOX_SERVICE_PATH = (
    GX10_DIR / 'systemd' / 'network-log-gx10-result-outbox.service'
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class OutboxSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = load_module('outbox_snapshot_producer_test', PRODUCER_PATH)
        cls.runner = load_module('outbox_snapshot_runner_test', RUNNER_PATH)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.snapshot_root = self.root / 'snapshot'
        self.snapshot_root.mkdir(mode=0o700)
        self.snapshot_root.chmod(0o700)
        self.source = self.root / 'events.sqlite3'
        self.target = self.snapshot_root / 'events.sqlite3'

    def create_source(self, *, wal=False):
        connection = sqlite3.connect(self.source)
        if wal:
            self.assertEqual(
                connection.execute('PRAGMA journal_mode=WAL').fetchone()[0],
                'wal',
            )
        connection.executescript(
            '''
            CREATE TABLE incidents (incident_id TEXT PRIMARY KEY);
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
            CREATE TABLE reasoning_results (run_id TEXT PRIMARY KEY);
            INSERT INTO incidents VALUES ('incident-1');
            INSERT INTO reasoning_runs VALUES ('run-1','SUCCEEDED');
            INSERT INTO reasoning_results VALUES ('run-1');
            '''
        )
        connection.commit()
        return connection

    def test_online_backup_captures_consistent_active_wal_state(self):
        writer = self.create_source(wal=True)
        self.addCleanup(writer.close)
        writer.execute("INSERT INTO incidents VALUES ('incident-2')")
        writer.commit()

        result = self.producer.create_snapshot(self.source, self.target)

        self.assertEqual(result['results'], 1)
        self.assertEqual(result['incidents'], 2)
        self.assertEqual(result['attempts'], 1)
        self.assertGreater(result['bytes'], 0)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        connection = sqlite3.connect(
            f'{self.target.as_uri()}?mode=ro', uri=True
        )
        try:
            self.assertEqual(
                connection.execute('PRAGMA quick_check').fetchone()[0], 'ok'
            )
            self.assertEqual(
                connection.execute('SELECT COUNT(*) FROM incidents').fetchone()[0],
                2,
            )
        finally:
            connection.close()
        self.assertEqual(
            list(self.snapshot_root.glob(f'.{self.target.name}.partial-*')),
            [],
        )

    def test_failure_preserves_last_valid_snapshot(self):
        connection = self.create_source()
        connection.close()
        self.producer.create_snapshot(self.source, self.target)
        original = self.target.read_bytes()
        self.source.write_bytes(b'not sqlite')

        with self.assertRaises(sqlite3.DatabaseError):
            self.producer.create_snapshot(self.source, self.target)

        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(
            list(self.snapshot_root.glob(f'.{self.target.name}.partial-*')),
            [],
        )

    def test_transient_open_failure_is_bounded_and_retried(self):
        connection = self.create_source()
        connection.close()
        real = self.producer.snapshot_once
        calls = []

        def transient_then_success(source, temporary):
            calls.append((source, temporary))
            if len(calls) < 3:
                raise sqlite3.OperationalError('unable to open database file')
            return real(source, temporary)

        with mock.patch.object(
            self.producer,
            'snapshot_once',
            side_effect=transient_then_success,
        ):
            result = self.producer.create_snapshot(
                self.source,
                self.target,
                attempts=3,
                retry_delay=0,
            )
        self.assertEqual(result['attempts'], 3)
        self.assertEqual(len(calls), 3)

    def test_invalid_or_linked_paths_fail_closed(self):
        connection = self.create_source()
        connection.close()
        linked = self.snapshot_root / 'linked.sqlite3'
        linked.symlink_to(self.source)
        with self.assertRaisesRegex(
            self.producer.SnapshotError, 'published snapshot'
        ):
            self.producer.create_snapshot(self.source, linked)
        with self.assertRaisesRegex(
            self.producer.SnapshotError, 'attempt bound'
        ):
            self.producer.create_snapshot(
                self.source, self.target, attempts=11
            )

    def test_runner_is_hash_bound_and_invokes_only_configured_paths(self):
        expected = hashlib.sha256(PRODUCER_PATH.read_bytes()).hexdigest()
        self.assertEqual(self.runner.PRODUCER_SHA256, expected)
        config = {
            'source_database_path': self.source,
            'snapshot_database_path': self.target,
        }
        calls = []
        producer = types.SimpleNamespace(
            create_snapshot=lambda source, target: (
                calls.append((source, target))
                or {'results': 2, 'incidents': 3, 'bytes': 4096, 'attempts': 1}
            )
        )
        with (
            mock.patch.object(self.runner, 'load_config', return_value=config),
            mock.patch.object(self.runner, 'load_producer', return_value=producer),
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()),
        ):
            result = self.runner.run()
        self.assertEqual(result, 0)
        self.assertEqual(calls, [(self.source, self.target)])
        self.assertIn('GX10_MANAGED_OUTBOX_SNAPSHOT=PASS', output.getvalue())

    def test_service_is_networkless_and_outbox_requires_success(self):
        snapshot = SERVICE_PATH.read_text(encoding='utf-8')
        outbox = OUTBOX_SERVICE_PATH.read_text(encoding='utf-8')
        for line in (
            'Type=oneshot',
            'PrivateNetwork=yes',
            'RestrictAddressFamilies=AF_UNIX',
            'NoNewPrivileges=yes',
            'ProtectSystem=strict',
            'ReadWritePaths=/var/lib/network-log-gx10/state',
        ):
            self.assertIn(line, snapshot)
        self.assertNotIn('ssh', snapshot.casefold())
        self.assertIn(
            'Requires=network-log-gx10-outbox-snapshot.service', outbox
        )
        self.assertIn(
            'network-log-gx10-outbox-snapshot.service',
            next(line for line in outbox.splitlines() if line.startswith('After=')),
        )


if __name__ == '__main__':
    unittest.main()
