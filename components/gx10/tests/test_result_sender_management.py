#!/usr/bin/env python3
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock


GX10_DIR = Path(__file__).resolve().parents[1]
SENDER_PATH = GX10_DIR / 'sbin' / 'send-result-outbox.py'
RUNNER_PATH = GX10_DIR / 'sbin' / 'run-result-sender.py'
INSTALLER_PATH = GX10_DIR / 'install' / 'install-result-sender.py'
VERIFIER_PATH = GX10_DIR / 'install' / 'verify-result-sender.py'
SERVICE_PATH = GX10_DIR / 'systemd/network-log-gx10-result-sender.service'
TIMER_PATH = GX10_DIR / 'systemd/network-log-gx10-result-sender.timer'
EXAMPLE_PATH = GX10_DIR / 'config/result-sender.example.json'


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ResultSenderManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_module('result_sender_runner_test', RUNNER_PATH)
        cls.installer = load_module('result_sender_installer_test', INSTALLER_PATH)
        cls.verifier = load_module('result_sender_verifier_test', VERIFIER_PATH)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def example(self):
        return json.loads(EXAMPLE_PATH.read_text(encoding='utf-8'))

    def test_runner_is_bound_to_current_sender_hash(self):
        self.assertEqual(
            self.runner.SENDER_SHA256,
            hashlib.sha256(SENDER_PATH.read_bytes()).hexdigest(),
        )

    def test_private_configuration_contract_is_strict(self):
        parsed = self.runner.parse_config(self.example())
        self.assertEqual(parsed['host'], 'collector.example.invalid')
        self.assertEqual(parsed['port'], 2222)
        self.assertEqual(parsed['identity'].name, 'result-writer.key')
        self.assertEqual(
            parsed['known_hosts'].name,
            'result-writer-known_hosts',
        )
        for key, value in (
            ('sftp_port', 0),
            ('sftp_host', 'host with spaces'),
            ('sftp_user', 'user@host'),
            ('identity_path', '/tmp/spool-reader.key'),
            ('known_hosts_path', '/tmp/known_hosts'),
        ):
            changed = self.example()
            changed[key] = value
            with self.assertRaises(self.runner.ManagedSenderError):
                self.runner.parse_config(changed)

    def test_runner_passes_only_bound_values_to_sender(self):
        config = self.runner.parse_config(self.example())
        calls = []

        def send_one(*arguments):
            calls.append(arguments)
            return {
                'ready': 2,
                'delivered': 1,
                'attempted': 1,
                'sent': 1,
                'sent_bytes': 512,
            }

        with (
            mock.patch.object(self.runner, 'load_config', return_value=config),
            mock.patch.object(
                self.runner,
                'load_sender',
                return_value=types.SimpleNamespace(send_one=send_one),
            ),
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(self.runner.run(), 0)
        self.assertEqual(
            calls,
            [
                (
                    config['ready'],
                    config['delivered'],
                    config['host'],
                    config['port'],
                    config['user'],
                    config['identity'],
                    config['known_hosts'],
                )
            ],
        )
        self.assertIn('GX10_MANAGED_RESULT_SENDER=PASS', output.getvalue())

    def test_service_is_network_capable_but_least_privilege_and_bounded(self):
        service = SERVICE_PATH.read_text(encoding='utf-8')
        timer = TIMER_PATH.read_text(encoding='utf-8')
        for value in (
            'ConditionPathExists=/etc/network-log-gx10/result-sender.json',
            'Type=oneshot',
            'TimeoutStartSec=45s',
            'NoNewPrivileges=yes',
            'ProtectSystem=strict',
            'ProtectHome=yes',
            'ReadWritePaths=/var/lib/network-log-gx10/result-outbox',
            'InaccessiblePaths=/var/lib/network-log-gx10/state/events.sqlite3',
            'RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6',
            'CapabilityBoundingSet=',
        ):
            self.assertIn(value, service)
        self.assertNotIn('PrivateNetwork=yes', service)
        self.assertNotIn('Environment=', service)
        self.assertIn('OnUnitInactiveSec=1min', timer)
        self.assertNotIn('Persistent=true', timer)

    def test_installer_is_inactive_and_installs_no_private_input(self):
        source = INSTALLER_PATH.read_text(encoding='utf-8')
        self.assertNotIn("run_systemctl('enable'", source)
        self.assertNotIn("run_systemctl('start'", source)
        self.assertIn("run_systemctl('disable', '--now', TIMER)", source)
        self.assertNotIn('IdentityFile', source)
        self.assertNotIn('BEGIN OPENSSH PRIVATE KEY', source)
        targets = {target.name for _, target, _ in self.installer.ARTIFACTS}
        self.assertEqual(
            targets,
            {
                'send-result-outbox.py',
                'run-result-sender.py',
                'network-log-gx10-result-sender.service',
                'network-log-gx10-result-sender.timer',
            },
        )

    def test_runtime_dropin_binds_only_outbox_and_hides_database(self):
        state = {
            'user': 'network-log-agent',
            'group': 'network-log-agent',
            'root': Path('/srv/synthetic/outbox'),
            'database': Path('/srv/synthetic/state.sqlite3'),
            'identity': Path('/srv/synthetic/.ssh/result-writer.key'),
            'known_hosts': Path(
                '/srv/synthetic/.ssh/result-writer-known_hosts'
            ),
        }
        installer = self.installer.render_dropin(state)
        verifier = self.verifier.render_dropin(state)
        self.assertEqual(installer, verifier)
        text = installer.decode('utf-8')
        self.assertIn('ReadWritePaths=/srv/synthetic/outbox', text)
        self.assertIn(
            'InaccessiblePaths=/srv/synthetic/state.sqlite3',
            text,
        )
        self.assertNotIn('spool-reader.key', text)

    def test_postinstall_verification_failure_removes_created_artifacts(self):
        source_dir = self.root / 'source'
        target_dir = self.root / 'target'
        systemd_dir = self.root / 'systemd'
        source_dir.mkdir()
        target_dir.mkdir()
        systemd_dir.mkdir()
        artifacts = []
        for index in range(4):
            source = source_dir / f'source-{index}'
            target = target_dir / f'target-{index}'
            source.write_text(f'artifact-{index}\n', encoding='utf-8')
            artifacts.append((source, target, 0o755 if index < 2 else 0o644))
        dropin = systemd_dir / 'sender.service.d/10-runtime.conf'
        state = {
            'user': 'network-log-agent',
            'group': 'network-log-agent',
            'root': Path('/srv/synthetic/outbox'),
            'database': Path('/srv/synthetic/state.sqlite3'),
            'identity': Path('/srv/synthetic/.ssh/result-writer.key'),
            'known_hosts': Path(
                '/srv/synthetic/.ssh/result-writer-known_hosts'
            ),
        }

        def fake_install(path, data, mode, uid, gid):
            path = Path(path)
            path.write_bytes(data)
            path.chmod(mode)

        verifier = types.SimpleNamespace(
            verify_staged=mock.Mock(side_effect=ValueError('injected verify'))
        )
        with (
            mock.patch.object(self.installer, 'ARTIFACTS', tuple(artifacts)),
            mock.patch.object(self.installer, 'DROPIN_PATH', dropin),
            mock.patch.object(self.installer, 'preflight', return_value=state),
            mock.patch.object(self.installer, 'install_bytes', side_effect=fake_install),
            mock.patch.object(self.installer, 'run_systemctl'),
            mock.patch.object(self.installer.subprocess, 'run'),
            mock.patch.object(self.installer, 'load_verifier', return_value=verifier),
        ):
            with self.assertRaisesRegex(ValueError, 'injected verify'):
                self.installer.install()
        self.assertTrue(all(not target.exists() for _, target, _ in artifacts))
        self.assertFalse(dropin.exists())
        self.assertFalse(dropin.parent.exists())

    def test_public_example_contains_no_private_material(self):
        text = EXAMPLE_PATH.read_text(encoding='utf-8')
        self.assertIn('collector.example.invalid', text)
        self.assertNotIn('PRIVATE KEY', text)
        self.assertNotIn('password', text.casefold())


if __name__ == '__main__':
    unittest.main()
