#!/usr/bin/env python3
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import hashlib
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
CONFIGURATOR_PATH = GX10_DIR / 'install' / 'configure-result-sender.py'
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
        cls.configurator = load_module(
            'result_sender_configurator_test', CONFIGURATOR_PATH
        )

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

    def test_verifier_distinguishes_inactive_and_active_timer_state(self):
        state = {'user': 'network-log-agent', 'group': 'network-log-agent'}

        def value(unit, property_name):
            values = {
                (self.verifier.SERVICE, 'LoadState'): 'loaded',
                (self.verifier.TIMER, 'LoadState'): 'loaded',
                (self.verifier.SERVICE, 'FragmentPath'): str(
                    self.verifier.SYSTEMD_DIR / self.verifier.SERVICE
                ),
                (self.verifier.TIMER, 'FragmentPath'): str(
                    self.verifier.SYSTEMD_DIR / self.verifier.TIMER
                ),
                (self.verifier.SERVICE, 'DropInPaths'): str(
                    self.verifier.DROPIN_PATH
                ),
                (self.verifier.TIMER, 'DropInPaths'): '',
                (self.verifier.SERVICE, 'UnitFileState'): 'static',
                (self.verifier.TIMER, 'UnitFileState'): 'enabled',
                (self.verifier.TIMER, 'ActiveState'): 'active',
                (self.verifier.SERVICE, 'ActiveState'): 'inactive',
                (self.verifier.SERVICE, 'NRestarts'): '0',
                (self.verifier.SERVICE, 'User'): state['user'],
                (self.verifier.SERVICE, 'Group'): state['group'],
            }
            return values[(unit, property_name)]

        with mock.patch.object(self.verifier, 'systemctl_value', side_effect=value):
            self.verifier.validate_units(state, active=True)
            with self.assertRaisesRegex(ValueError, 'enablement differs'):
                self.verifier.validate_units(state, active=False)

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

    def private_state(self):
        ssh_dir = self.root / 'ssh'
        outbox = self.root / 'outbox'
        ssh_dir.mkdir()
        outbox.mkdir()
        ready = outbox / 'ready'
        delivered = outbox / 'delivered'
        ready.mkdir()
        delivered.mkdir()
        reader = ssh_dir / 'spool-reader.key'
        known = ssh_dir / 'known_hosts'
        reader.write_bytes(b'reader-key\n')
        known.write_bytes(b'pinned-host\n')
        return {
            'uid': 1000,
            'gid': 1000,
            'root': outbox,
            'ready': ready,
            'delivered': delivered,
            'identity': ssh_dir / 'result-writer.key',
            'known_hosts': ssh_dir / 'result-writer-known_hosts',
        }

    def runtime_inputs(self, state):
        return {
            'host': 'collector.example.invalid',
            'port': 1,
            'reader_identity': state['identity'].parent / 'spool-reader.key',
            'source_known_hosts': state['identity'].parent / 'known_hosts',
        }

    def test_configurator_installs_private_state_last_config_and_stays_inactive(self):
        state = self.private_state()
        config = self.root / 'result-sender.json'
        identity_input = self.root / 'input.key'
        identity_input.write_bytes(b'writer-key\n')
        calls = []

        def fake_install(path, data, mode, uid, gid):
            path = Path(path)
            path.write_bytes(data)
            path.chmod(mode)
            calls.append(path)

        verifier = types.SimpleNamespace(
            runtime_state=lambda: state,
            runtime_inputs=lambda *args: self.runtime_inputs(state),
            validate_file=lambda *args, **kwargs: None,
            verify_staged=mock.Mock(),
            verify_configured=mock.Mock(),
        )
        with (
            mock.patch.object(self.configurator, 'SENDER_CONFIG', config),
            mock.patch.object(self.configurator, 'load_verifier', return_value=verifier),
            mock.patch.object(self.configurator, 'require_inactive'),
            mock.patch.object(
                self.configurator,
                'validate_identity_input',
                return_value='writer-public',
            ),
            mock.patch.object(
                self.configurator,
                'public_key',
                return_value='reader-public',
            ),
            mock.patch.object(
                self.configurator,
                'expected_configuration',
                return_value=b'{"schema_version":1}\n',
            ),
            mock.patch.object(
                self.configurator,
                'install_bytes',
                side_effect=fake_install,
            ),
        ):
            result = self.configurator.configure(identity_input)
        self.assertEqual(result, {'created': 3, 'reused': 0})
        self.assertEqual(
            calls,
            [
                state['identity'],
                state['known_hosts'],
                config,
            ],
        )
        verifier.verify_staged.assert_called_once_with()
        verifier.verify_configured.assert_called_once_with(
            self.configurator.RUNTIME_CONFIG,
            None,
        )

    def test_configurator_failure_removes_only_new_private_state(self):
        state = self.private_state()
        config = self.root / 'result-sender.json'
        identity_input = self.root / 'input.key'
        identity_input.write_bytes(b'writer-key\n')

        def fake_install(path, data, mode, uid, gid):
            Path(path).write_bytes(data)

        verifier = types.SimpleNamespace(
            runtime_state=lambda: state,
            runtime_inputs=lambda *args: self.runtime_inputs(state),
            validate_file=lambda *args, **kwargs: None,
            verify_staged=mock.Mock(),
            verify_configured=mock.Mock(
                side_effect=ValueError('injected configured verify')
            ),
        )
        with (
            mock.patch.object(self.configurator, 'SENDER_CONFIG', config),
            mock.patch.object(self.configurator, 'load_verifier', return_value=verifier),
            mock.patch.object(self.configurator, 'require_inactive'),
            mock.patch.object(
                self.configurator,
                'validate_identity_input',
                return_value='writer-public',
            ),
            mock.patch.object(
                self.configurator,
                'public_key',
                return_value='reader-public',
            ),
            mock.patch.object(
                self.configurator,
                'expected_configuration',
                return_value=b'{"schema_version":1}\n',
            ),
            mock.patch.object(
                self.configurator,
                'install_bytes',
                side_effect=fake_install,
            ),
        ):
            with self.assertRaisesRegex(ValueError, 'injected configured verify'):
                self.configurator.configure(identity_input)
        self.assertFalse(state['identity'].exists())
        self.assertFalse(state['known_hosts'].exists())
        self.assertFalse(config.exists())
        self.assertTrue((state['identity'].parent / 'spool-reader.key').exists())
        self.assertTrue((state['identity'].parent / 'known_hosts').exists())

    def test_configurator_refuses_partial_existing_private_state(self):
        state = self.private_state()
        config = self.root / 'result-sender.json'
        state['identity'].write_bytes(b'existing-writer\n')
        identity_input = self.root / 'input.key'
        identity_input.write_bytes(b'writer-key\n')
        verifier = types.SimpleNamespace(
            runtime_state=lambda: state,
            runtime_inputs=lambda *args: self.runtime_inputs(state),
            validate_file=lambda *args, **kwargs: None,
        )
        with (
            mock.patch.object(self.configurator, 'SENDER_CONFIG', config),
            mock.patch.object(self.configurator, 'load_verifier', return_value=verifier),
            mock.patch.object(self.configurator, 'require_inactive'),
            mock.patch.object(
                self.configurator,
                'validate_identity_input',
                return_value='writer-public',
            ),
            mock.patch.object(
                self.configurator,
                'public_key',
                return_value='reader-public',
            ),
            mock.patch.object(
                self.configurator,
                'expected_configuration',
                return_value=b'{}\n',
            ),
        ):
            with self.assertRaisesRegex(
                self.configurator.ConfigureError,
                'partial',
            ):
                self.configurator.configure(identity_input)

    def test_configurator_has_no_sftp_execution_path(self):
        source = CONFIGURATOR_PATH.read_text(encoding='utf-8')
        self.assertNotIn('/usr/bin/sftp', source)
        self.assertNotIn("['sftp'", source)
        self.assertIn("Path('/usr/bin/ssh-keygen')", source)

    def test_writer_public_key_derivation_ignores_optional_comment(self):
        encoded = 'x' * 40
        result = types.SimpleNamespace(
            returncode=0,
            stdout=f'ssh-ed25519 {encoded} dedicated-writer-v1\n',
            stderr='',
        )
        with mock.patch.object(self.configurator.subprocess, 'run', return_value=result):
            self.assertEqual(
                self.configurator.public_key(self.root / 'input.key'),
                f'ssh-ed25519 {encoded}',
            )
        with mock.patch.object(self.verifier.subprocess, 'run', return_value=result):
            self.assertEqual(
                self.verifier.public_key(self.root / 'installed.key'),
                f'ssh-ed25519 {encoded}',
            )

    def test_verifier_derives_exact_captured_legacy_runtime_contract(self):
        state = self.private_state()
        reader = state['identity'].parent / 'spool-reader.key'
        known = state['identity'].parent / 'known_hosts'
        source = self.root / 'captured-fetch.py'
        source.write_text(
            'from pathlib import Path\n'
            f'DB = Path({str(self.root / "state.db")!r})\n'
            f'TMP_DIR = Path({str(self.root / "tmp")!r})\n'
            f'INCOMING_DIR = Path({str(self.root / "incoming")!r})\n'
            "SFTP_HOST = 'collector.example.invalid'\n"
            "SFTP_PORT = '1'\n"
            "SFTP_USER = 'reader'\n"
            f'SSH_KEY = Path({str(reader)!r})\n'
            f'KNOWN_HOSTS = Path({str(known)!r})\n',
            encoding='utf-8',
        )
        source.chmod(0o755)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        with (
            mock.patch.object(self.verifier, 'validate_file'),
            mock.patch.object(self.verifier, 'LEGACY_FETCH_SHA256', digest),
        ):
            runtime = self.verifier.runtime_inputs(
                state,
                legacy_fetch_source=source,
            )
        self.assertEqual(runtime['host'], 'collector.example.invalid')
        self.assertEqual(runtime['port'], 1)
        self.assertEqual(runtime['reader_identity'], reader)
        self.assertEqual(runtime['source_known_hosts'], known)

    def test_configurator_renders_canonical_runtime_configuration(self):
        state = self.private_state()
        rendered = self.configurator.expected_configuration(
            self.runtime_inputs(state),
            state,
        )
        parsed = json.loads(rendered)
        self.assertEqual(parsed['schema_version'], 1)
        self.assertEqual(parsed['sftp_user'], 'ai_results_writer')
        self.assertEqual(parsed['sftp_host'], 'collector.example.invalid')
        self.assertEqual(parsed['sftp_port'], 1)
        self.assertEqual(
            rendered,
            (json.dumps(parsed, separators=(',', ':'), sort_keys=True) + '\n').encode(),
        )


if __name__ == '__main__':
    unittest.main()
