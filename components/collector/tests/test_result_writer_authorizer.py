#!/usr/bin/env python3
import base64
import importlib.util
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
AUTHORIZER_PATH = ROOT / 'collector/install/authorize-result-writer-key.py'


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ResultWriterAuthorizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authorizer = load_module('result_writer_authorizer_test', AUTHORIZER_PATH)
        cls.encoded = base64.b64encode(b'x' * 48).decode('ascii')
        cls.line = f'ssh-ed25519 {cls.encoded} dedicated-writer-v1\n'.encode()
        cls.pair = ('ssh-ed25519', cls.encoded)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.ssh_dir = self.root / 'ssh'
        self.ssh_dir.mkdir()
        self.authorized = self.ssh_dir / 'authorized_keys'
        self.authorized.write_bytes(b'# retained\nssh-ed25519 OLDKEY retained\n')
        self.authorized.chmod(0o600)
        self.backup_dir = self.root / 'backups'
        self.backup = self.backup_dir / 'pre-v1'
        self.uid = os.getuid()
        self.gid = os.getgid()
        self.account = types.SimpleNamespace(pw_uid=self.uid, pw_gid=self.gid)
        self.group = types.SimpleNamespace(gr_gid=self.gid)

    def tearDown(self):
        self.temporary.cleanup()

    def patches(self, *, sshd_returncode=0):
        def ensure_backup_directory():
            self.backup_dir.mkdir()
            return True

        real_validate_file = self.authorizer.validate_file

        def validate_file(path, mode, uid, gid, maximum=256 * 1024):
            if Path(path) == self.backup:
                uid = self.uid
                gid = self.gid
            return real_validate_file(path, mode, uid, gid, maximum)

        return (
            mock.patch.object(self.authorizer, 'AUTHORIZED_KEYS', self.authorized),
            mock.patch.object(self.authorizer, 'BACKUP_DIR', self.backup_dir),
            mock.patch.object(self.authorizer, 'BACKUP', self.backup),
            mock.patch.object(
                self.authorizer.pwd,
                'getpwnam',
                return_value=self.account,
            ),
            mock.patch.object(
                self.authorizer.grp,
                'getgrnam',
                return_value=self.group,
            ),
            mock.patch.object(
                self.authorizer,
                'read_public_key',
                return_value=(self.line, self.pair),
            ),
            mock.patch.object(
                self.authorizer,
                'ensure_backup_directory',
                side_effect=ensure_backup_directory,
            ),
            mock.patch.object(self.authorizer.os, 'chown'),
            mock.patch.object(
                self.authorizer,
                'validate_file',
                side_effect=validate_file,
            ),
            mock.patch.object(
                self.authorizer.subprocess,
                'run',
                return_value=types.SimpleNamespace(returncode=sshd_returncode),
            ),
        )

    def test_authorize_appends_once_and_preserves_exact_backup(self):
        original = self.authorized.read_bytes()
        patches = self.patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            result = self.authorizer.authorize(self.root / 'input.pub')
        self.assertEqual(result, {'created': 1, 'reused': 0, 'backup_created': 1})
        self.assertEqual(self.backup.read_bytes(), original)
        self.assertEqual(self.authorized.read_bytes(), original + self.line)
        self.assertEqual(
            self.authorizer.authorized_key_pairs(self.authorized.read_bytes()).count(
                self.pair
            ),
            1,
        )

    def test_authorize_sshd_failure_restores_exact_original(self):
        original = self.authorized.read_bytes()
        patches = self.patches(sshd_returncode=1)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            with self.assertRaisesRegex(
                self.authorizer.AuthorizeError,
                'SSH configuration',
            ):
                self.authorizer.authorize(self.root / 'input.pub')
        self.assertEqual(self.authorized.read_bytes(), original)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.backup_dir.exists())

    def test_authorize_reuses_existing_exact_key_without_backup(self):
        self.authorized.write_bytes(self.authorized.read_bytes() + self.line)
        patches = self.patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            result = self.authorizer.authorize(self.root / 'input.pub')
        self.assertEqual(result, {'created': 0, 'reused': 1, 'backup_created': 0})
        self.assertFalse(self.backup.exists())

    def test_authorize_refuses_duplicate_existing_key(self):
        self.authorized.write_bytes(self.authorized.read_bytes() + self.line * 2)
        patches = self.patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            with self.assertRaisesRegex(
                self.authorizer.AuthorizeError,
                'duplicated',
            ):
                self.authorizer.authorize(self.root / 'input.pub')
        self.assertFalse(self.backup.exists())

    def test_public_input_refuses_private_key_marker(self):
        path = self.root / 'input.pub'
        path.write_bytes(b'-----BEGIN ' + b'PRIVATE KEY-----\n')
        with mock.patch.object(self.authorizer, 'validate_file'):
            with self.assertRaisesRegex(
                self.authorizer.AuthorizeError,
                'public key input',
            ):
                self.authorizer.read_public_key(path)


if __name__ == '__main__':
    unittest.main()
