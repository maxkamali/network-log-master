#!/usr/bin/env python3
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

GX10_DIR = Path(__file__).resolve().parents[1]
INSTALLER_PATH = GX10_DIR / 'install' / 'install-applications.py'
SPEC = importlib.util.spec_from_file_location('install_applications', INSTALLER_PATH)
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class ApplicationInstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'source'
        self.target = self.root / 'target'
        self.source.write_text('public artifact\n', encoding='utf-8')

    def install(self):
        INSTALLER.install_one(
            self.source,
            self.target,
            0o640,
            os.getuid(),
            os.getgid(),
        )

    def test_atomic_install_and_exact_reuse(self):
        self.install()
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.target.stat().st_nlink, 1)
        self.install()

    def test_divergent_existing_target_is_refused(self):
        self.target.write_text('different\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.install()

    def test_symbolic_link_target_is_refused(self):
        other = self.root / 'other'
        other.write_text('public artifact\n', encoding='utf-8')
        self.target.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'real regular file'):
            self.install()

    def test_hard_link_target_is_refused(self):
        other = self.root / 'other'
        other.write_text('public artifact\n', encoding='utf-8')
        os.link(other, self.target)
        with self.assertRaisesRegex(ValueError, 'hard-linked'):
            self.install()

    def test_runtime_file_contract_checks_mode_and_ownership(self):
        self.source.chmod(0o640)
        INSTALLER.validate_runtime_file(
            self.source,
            'synthetic runtime file',
            os.getuid(),
            os.getgid(),
            0o640,
        )
        self.source.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'unexpected mode'):
            INSTALLER.validate_runtime_file(
                self.source,
                'synthetic runtime file',
                os.getuid(),
                os.getgid(),
                0o640,
            )


if __name__ == '__main__':
    unittest.main()
