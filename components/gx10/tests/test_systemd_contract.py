#!/usr/bin/env python3
import unittest
from collections import defaultdict
from pathlib import Path

GX10_DIR = Path(__file__).resolve().parents[1]
SERVICE_PATH = GX10_DIR / 'systemd' / 'network-log-gx10.service'
TIMER_PATH = GX10_DIR / 'systemd' / 'network-log-gx10.timer'


def parse_unit(path):
    sections = defaultdict(list)
    section = None
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            continue
        if section is None or '=' not in line:
            raise ValueError('invalid unit line')
        key, value = line.split('=', 1)
        sections[section].append((key, value))
    return sections


class SystemdContractTests(unittest.TestCase):
    def test_service_preserves_live_chain_and_identity(self):
        unit = parse_unit(SERVICE_PATH)
        service = unit['Service']
        values = defaultdict(list)
        for key, value in service:
            values[key].append(value)

        self.assertEqual(values['Type'], ['oneshot'])
        self.assertEqual(values['User'], ['network-log-agent'])
        self.assertEqual(values['Group'], ['network-log-agent'])
        self.assertEqual(
            values['ExecStart'],
            [
                '/usr/local/libexec/network-log-gx10/fetch-spool.py',
                '/usr/local/libexec/network-log-gx10/ingest-spool.py',
            ],
        )
        self.assertFalse(
            any('enrich-events' in value for value in values['ExecStart'])
        )
        self.assertFalse(
            any('incident-engine' in value for value in values['ExecStart'])
        )
        self.assertEqual(values['UMask'], ['0027'])
        self.assertNotIn('Environment', values)
        self.assertNotIn('EnvironmentFile', values)

    def test_service_preserves_hardening_and_writable_paths(self):
        unit = parse_unit(SERVICE_PATH)
        values = defaultdict(list)
        for key, value in unit['Service']:
            values[key].append(value)

        for key in (
            'NoNewPrivileges',
            'PrivateTmp',
            'PrivateDevices',
            'ProtectKernelTunables',
            'ProtectKernelModules',
            'ProtectKernelLogs',
            'ProtectControlGroups',
            'RestrictNamespaces',
            'LockPersonality',
        ):
            self.assertEqual(values[key], ['yes'], key)
        self.assertEqual(values['ProtectSystem'], ['strict'])
        self.assertEqual(values['ProtectHome'], ['yes'])
        self.assertEqual(values['CapabilityBoundingSet'], [''])
        self.assertEqual(values['AmbientCapabilities'], [''])
        self.assertEqual(
            values['RestrictAddressFamilies'],
            ['AF_UNIX AF_INET AF_INET6'],
        )
        self.assertEqual(
            values['ReadWritePaths'],
            [
                '/var/lib/network-log-gx10',
                '/var/spool/network-log-gx10',
            ],
        )

    def test_timer_preserves_live_monotonic_schedule(self):
        unit = parse_unit(TIMER_PATH)
        timer = dict(unit['Timer'])
        self.assertEqual(timer['OnBootSec'], '2min')
        self.assertEqual(timer['OnUnitInactiveSec'], '1min')
        self.assertEqual(timer['AccuracySec'], '5s')
        self.assertEqual(timer['Unit'], 'network-log-gx10.service')
        self.assertNotIn('OnCalendar', timer)
        self.assertNotIn('RandomizedDelaySec', timer)
        self.assertEqual(
            dict(unit['Install'])['WantedBy'],
            'timers.target',
        )


if __name__ == '__main__':
    unittest.main()
