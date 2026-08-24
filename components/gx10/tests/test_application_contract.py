#!/usr/bin/env python3
import ast
import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path

GX10_DIR = Path(__file__).resolve().parents[1]
SBIN_DIR = GX10_DIR / 'sbin'
APPLICATIONS = {
    'fetch': SBIN_DIR / 'fetch-spool.py',
    'ingest': SBIN_DIR / 'ingest-spool.py',
    'projection': SBIN_DIR / 'enrich-events.py',
    'incident': SBIN_DIR / 'incident-engine.py',
    'correlation': SBIN_DIR / 'run-correlation.py',
    'reasoning_packets': SBIN_DIR / 'build-reasoning-packets.py',
    'local_reasoning': SBIN_DIR / 'run-local-reasoning.py',
}
PUBLIC_ABSOLUTE_PREFIXES = (
    '/etc/network-log-gx10/',
    '/usr/bin/',
    '/usr/local/libexec/network-log-gx10/',
    '/var/lib/network-log-gx10/',
    '/var/spool/network-log-gx10/',
)
IPV4_RE = re.compile(
    r'(?<![0-9])'
    r'(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})'
    r'(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}'
    r'(?![0-9])'
)


def load_application(name):
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=Path('/var/lib/network-log-gx10/state/events.sqlite3'),
        incoming_dir=Path('/var/spool/network-log-gx10/incoming'),
        processed_dir=Path('/var/spool/network-log-gx10/processed'),
        temp_dir=Path('/var/spool/network-log-gx10/tmp'),
        private_key_path=Path('/var/lib/network-log-gx10/.ssh/spool-reader.key'),
        known_hosts_path=Path('/var/lib/network-log-gx10/.ssh/known_hosts'),
        sftp_host='collector.example.invalid',
        sftp_port='2222',
        sftp_user='spool-reader',
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        spec = importlib.util.spec_from_file_location(
            f'gx10_{name}',
            APPLICATIONS[name],
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules['runtime_config']
        else:
            sys.modules['runtime_config'] = previous


class ApplicationContractTests(unittest.TestCase):
    def test_sources_contain_no_deployment_ipv4_or_private_paths(self):
        for name, path in APPLICATIONS.items():
            with self.subTest(application=name):
                text = path.read_text(encoding='utf-8')
                addresses = [match.group(0) for match in IPV4_RE.finditer(text)]
                if name == 'local_reasoning':
                    self.assertTrue(addresses)
                    self.assertEqual(set(addresses), {'127.0.0.1'})
                else:
                    self.assertEqual(addresses, [])
                tree = ast.parse(text)
                absolute = {
                    node.value
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value.startswith('/')
                }
                for value in absolute:
                    self.assertTrue(
                        value == '/'
                        or value == '/spool/%Y/%m/%d/%H'
                        or (
                            name == 'local_reasoning'
                            and value == '/api/chat'
                        )
                        or value.startswith(PUBLIC_ABSOLUTE_PREFIXES),
                        value,
                    )

    def test_fetch_preserves_strict_sftp_and_zstd_contract(self):
        fetch = load_application('fetch')
        command = fetch.sftp_base_command()
        self.assertEqual(command[0], '/usr/bin/sftp')
        for required in (
            '-q',
            '-P',
            '-i',
            'IdentitiesOnly=yes',
            'StrictHostKeyChecking=yes',
            '-b',
            '-',
        ):
            self.assertIn(required, command)
        self.assertTrue(
            any(value.startswith('UserKnownHostsFile=') for value in command)
        )
        self.assertEqual(
            fetch.list_remote_hour.__code__.co_consts.count('/spool/%Y/%m/%d/%H'),
            1,
        )

    def test_ingest_timestamp_contract(self):
        ingest = load_application('ingest')
        self.assertEqual(
            ingest.parse_epoch_ms('2026-08-23T12:00:00Z'),
            1787486400000,
        )
        with self.assertRaises(ValueError):
            ingest.parse_epoch_ms('2026-08-23T12:00:00')

    def test_normalized_projection_uses_canonical_fields_and_local_policy(self):
        projection = load_application('projection')
        event = {
            'schema_version': 1,
            'timestamp': '2026-08-24T06:12:00+00:00',
            'ingest_timestamp': '2026-08-24T06:12:01+00:00',
            'device_timestamp': None,
            'hostname': 'router-a.example.invalid',
            'source_ip': '192.0.2.10',
            'source_port': 514,
            'facility': 'local7',
            'severity': 'info',
            'appname': 'syslog',
            'message': '%ICMPV6-3-ND_LOG: synthetic',
            'raw_message': '%ICMPV6-3-ND_LOG: synthetic',
            'parse_status': 'parsed',
            'vendor': 'cisco',
            'os_family': 'nxos',
            'event_code': 'ICMPV6-3-ND_LOG',
            'event_family': 'icmpv6',
            'protocol': 'icmpv6',
            'signal_type': 'observation',
            'entity_type': 'unknown',
            'entity_key': '',
            'state': '',
            'repeat_count': 1,
            'attention_eligible': True,
            'suppression_rule_id': None,
            'attributes': {'normalization_path': 'generic'},
        }
        self.assertIs(
            projection.validate_normalized_event(event),
            event,
        )
        values = projection.project_normalized_event(
            event,
            [(1, 'event_code_exact', 'ICMPV6-3-ND_LOG', None)],
            '2026-08-24T06:13:00+00:00',
        )
        self.assertEqual(values['event_code'], event['event_code'])
        self.assertEqual(values['family'], event['event_family'])
        self.assertEqual(values['vendor_hint'], event['vendor'])
        self.assertEqual(values['protocol'], event['protocol'])
        self.assertIsNone(values['entity_type'])
        self.assertIsNone(values['entity_key'])
        self.assertEqual(values['attention_eligible'], 0)
        self.assertEqual(values['suppression_rule_id'], 1)
        self.assertEqual(values['classification_version'], 4)

        self.assertIsNone(
            projection.validate_normalized_event({'message': 'raw'})
        )
        malformed = dict(event)
        malformed['source_port'] = True
        with self.assertRaises(projection.ProjectionError):
            projection.validate_normalized_event(malformed)


if __name__ == '__main__':
    unittest.main()
