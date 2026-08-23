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
    'enrichment': SBIN_DIR / 'enrich-events.py',
}
PUBLIC_ABSOLUTE_PREFIXES = (
    '/etc/network-log-gx10/',
    '/usr/bin/',
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
                self.assertIsNone(IPV4_RE.search(text))
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

    def test_enrichment_synthetic_classification_contract(self):
        enrichment = load_application('enrichment')

        repeat = enrichment.classify(
            '',
            'last message repeated 3 times',
            '',
            'router-a.example.invalid',
        )
        self.assertEqual(repeat['family'], 'syslog_repeat')
        self.assertEqual(repeat['repeat_count'], 3)

        bgp = enrichment.classify(
            'BGP-5-ADJCHANGE',
            '%BGP-5-ADJCHANGE: peer 192.0.2.10 '
            '(VRF default AS 64512) old state Idle event Established '
            'new state Established',
            '',
            'router-a.example.invalid',
        )
        self.assertEqual(bgp['family'], 'bgp')
        self.assertEqual(bgp['vendor_hint'], 'arista_eos')
        self.assertEqual(bgp['state'], 'up')
        self.assertEqual(bgp['signal_type'], 'recovery')

        ospf = enrichment.classify(
            'OSPF-5-NBR_RETRANSMISSIONS',
            '%OSPF-5-NBR_RETRANSMISSIONS: ospf-1 [42] Nbr 192.0.2.20',
            '',
            'router-b.example.invalid',
        )
        self.assertEqual(ospf['protocol'], 'ospf')
        self.assertEqual(ospf['state'], 'retransmissions')
        self.assertEqual(ospf['signal_type'], 'degradation')


if __name__ == '__main__':
    unittest.main()
