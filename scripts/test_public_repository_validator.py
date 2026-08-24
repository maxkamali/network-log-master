#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / 'validate-public-repository.py'
SPEC = importlib.util.spec_from_file_location(
    'validate_public_repository',
    VALIDATOR_PATH,
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class PublicRepositoryValidatorTests(unittest.TestCase):
    def execution_authority(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'CURRENT_STATE.md'
            path.write_text(text, encoding='utf-8')
            with mock.patch.object(VALIDATOR, 'CURRENT_STATE', path):
                VALIDATOR.validate_execution_authority()

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

    def test_execution_authority_accepts_one_next_while_in_progress(self):
        self.execution_authority('1. `NEXT` — bounded work\n')

    def test_execution_authority_accepts_explicit_complete_state_without_next(self):
        self.execution_authority(
            'End-to-end working-system target: `COMPLETE`\n'
            'There is no remaining `NEXT` item.\n'
        )

    def test_execution_authority_refuses_implicit_zero_next_state(self):
        with self.assertRaisesRegex(ValueError, 'while work remains'):
            self.execution_authority('1. `DONE` — incomplete authority\n')

    def test_execution_authority_refuses_complete_state_with_numbered_next(self):
        with self.assertRaisesRegex(ValueError, 'end-to-end COMPLETE'):
            self.execution_authority(
                'End-to-end working-system target: `COMPLETE`\n'
                'There is no remaining `NEXT` item.\n'
                '2. `NEXT` — contradictory work\n'
            )


if __name__ == '__main__':
    unittest.main()
