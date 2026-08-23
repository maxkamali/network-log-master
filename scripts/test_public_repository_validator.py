#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / 'validate-public-repository.py'
SPEC = importlib.util.spec_from_file_location(
    'validate_public_repository',
    VALIDATOR_PATH,
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class PublicRepositoryValidatorTests(unittest.TestCase):
    def test_documentation_addresses_and_package_version_are_allowed(self):
        VALIDATOR.validate_text(
            Path('synthetic'),
            ' '.join(('192.0.2.10', '127.0.0.1', '26.3.17.110')),
            'synthetic',
        )

    def test_private_address_is_refused(self):
        private_address = '.'.join(('10', '25', '40', '8'))
        with self.assertRaisesRegex(ValueError, 'non-public IPv4'):
            VALIDATOR.validate_text(
                Path('synthetic'),
                private_address,
                'synthetic',
            )

    def test_token_pattern_is_refused(self):
        synthetic_token = ('github_' + 'pat_') + ('a' * 24)
        with self.assertRaisesRegex(ValueError, 'token/access-key'):
            VALIDATOR.validate_text(
                Path('synthetic'),
                synthetic_token,
                'synthetic',
            )

    def test_private_key_marker_is_refused(self):
        marker = '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----'
        with self.assertRaisesRegex(ValueError, 'private key'):
            VALIDATOR.validate_text(
                Path('synthetic'),
                marker,
                'synthetic',
            )

    def test_sensitive_artifact_paths_are_refused(self):
        for path in (
            'operator-inputs.env',
            'runtime.sqlite3',
            'private.key',
            'secrets/value.txt',
        ):
            with self.subTest(path=path):
                self.assertTrue(VALIDATOR.sensitive_path(path))


if __name__ == '__main__':
    unittest.main()
