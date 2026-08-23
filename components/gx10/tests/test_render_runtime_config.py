#!/usr/bin/env python3
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

GX10_DIR = Path(__file__).resolve().parents[1]
RENDERER_PATH = GX10_DIR / 'install' / 'render-runtime-config.py'
SPEC = importlib.util.spec_from_file_location('render_runtime_config', RENDERER_PATH)
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)


class RenderRuntimeConfigTests(unittest.TestCase):
    def valid_environment(self):
        return {
            'GX10_SFTP_HOST': 'collector.example.invalid',
            'GX10_SFTP_PORT': '2222',
            'GX10_SFTP_USER': 'spool-reader',
        }

    def test_build_payload_normalizes_port(self):
        self.assertEqual(
            RENDERER.build_payload(self.valid_environment()),
            {
                'sftp_host': 'collector.example.invalid',
                'sftp_port': 2222,
                'sftp_user': 'spool-reader',
            },
        )

    def test_missing_input_fails(self):
        data = self.valid_environment()
        del data['GX10_SFTP_HOST']
        with self.assertRaises(ValueError):
            RENDERER.build_payload(data)

    def test_invalid_inputs_fail_without_echoing_values(self):
        for key, value in (
            ('GX10_SFTP_HOST', 'host with spaces'),
            ('GX10_SFTP_PORT', '0'),
            ('GX10_SFTP_PORT', '65536'),
            ('GX10_SFTP_PORT', 'not-a-port'),
            ('GX10_SFTP_USER', 'user@host'),
        ):
            with self.subTest(key=key, value=value):
                data = self.valid_environment()
                data[key] = value
                with self.assertRaises(ValueError) as raised:
                    RENDERER.build_payload(data)
                self.assertNotIn(value, str(raised.exception))

    def test_existing_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target.json'
            target.write_text('{}\n', encoding='utf-8')
            link = root / 'runtime.json'
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                RENDERER.verify_existing(link, b'{}\n', os.getgid())


if __name__ == '__main__':
    unittest.main()
