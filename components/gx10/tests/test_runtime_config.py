#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

GX10_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GX10_DIR / 'sbin'))

from runtime_config import load_runtime_config


class RuntimeConfigTests(unittest.TestCase):
    def write_config(self, data):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'runtime.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def valid_data(self):
        return {
            'sftp_host': 'collector.example.invalid',
            'sftp_port': 2222,
            'sftp_user': 'spool-reader',
        }

    def test_valid_config_uses_public_filesystem_contract(self):
        config = load_runtime_config(self.write_config(self.valid_data()))
        self.assertEqual(config.sftp_port, '2222')
        self.assertEqual(
            config.database_path,
            Path('/var/lib/network-log-gx10/state/events.sqlite3'),
        )
        self.assertEqual(
            config.private_key_path,
            Path('/var/lib/network-log-gx10/.ssh/spool-reader.key'),
        )

    def test_string_port_is_normalized(self):
        data = self.valid_data()
        data['sftp_port'] = '2222'
        self.assertEqual(load_runtime_config(self.write_config(data)).sftp_port, '2222')

    def test_missing_or_extra_keys_fail(self):
        missing = self.valid_data()
        del missing['sftp_user']
        with self.assertRaises(ValueError):
            load_runtime_config(self.write_config(missing))

        extra = self.valid_data()
        extra['password'] = 'must-not-be-accepted'
        with self.assertRaises(ValueError):
            load_runtime_config(self.write_config(extra))

    def test_invalid_identity_values_fail(self):
        for key, value in (
            ('sftp_host', 'host with spaces'),
            ('sftp_user', 'user@host'),
            ('sftp_port', 0),
            ('sftp_port', 65536),
            ('sftp_port', 'not-a-port'),
        ):
            with self.subTest(key=key, value=value):
                data = self.valid_data()
                data[key] = value
                with self.assertRaises(ValueError):
                    load_runtime_config(self.write_config(data))


if __name__ == '__main__':
    unittest.main()
