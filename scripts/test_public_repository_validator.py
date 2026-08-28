#!/usr/bin/env python3
import importlib.util
import json
import os
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
            'admin.txt',
            '.netrc',
            '.env.production',
            'operator-inputs.env',
            'password.txt',
            'runtime.sqlite3',
            'private.key',
            'secrets/value.txt',
        ):
            with self.subTest(path=path):
                self.assertTrue(VALIDATOR.sensitive_path(path))

    def test_literal_credential_assignment_is_refused(self):
        name = 'pass' + 'word'
        synthetic = f'{name}=' + 'MixedCase123456789'
        with self.assertRaisesRegex(ValueError, 'literal credential assignment'):
            VALIDATOR.validate_text(Path('synthetic'), synthetic, 'synthetic')

    def test_credential_placeholders_and_code_are_allowed(self):
        name = 'pass' + 'word'
        VALIDATOR.validate_text(
            Path('synthetic'),
            '\n'.join((f'{name}=${{OPERATOR_VALUE}}', f'{name}=read_secret_file()')),
            'synthetic',
        )

    def test_short_quoted_credential_literal_is_refused(self):
        name = 'pass' + 'word'
        synthetic = name + '=' + '"' + 'tiny' + '"'
        with self.assertRaisesRegex(ValueError, 'literal credential assignment'):
            VALIDATOR.validate_text(Path('synthetic'), synthetic, 'synthetic')

    def test_history_short_credential_literal_is_refused(self):
        name = 'pass' + 'word'
        synthetic = name + '=x'
        finding = ('a' * 40, 'docs/example.md', synthetic)
        with mock.patch.object(
            VALIDATOR,
            'history_grep',
            side_effect=([], [finding]),
        ):
            with self.assertRaisesRegex(ValueError, 'history sensitive-content'):
                VALIDATOR.validate_history_content()

    def test_underscore_and_dotted_credential_literals_are_refused(self):
        name = 'api_' + 'key'
        for value in ('private_value', 'private.value'):
            with self.subTest(value=value):
                synthetic = name + '=' + '"' + value + '"'
                with self.assertRaisesRegex(
                    ValueError,
                    'literal credential assignment',
                ):
                    VALIDATOR.validate_text(Path('synthetic'), synthetic, 'synthetic')

    def test_placeholder_words_inside_a_literal_do_not_bypass_scanning(self):
        name = 'pass' + 'word'
        for value in ('example_actual_value', 'redacted_but_still_literal'):
            with self.subTest(value=value):
                synthetic = name + '=' + '"' + value + '"'
                with self.assertRaisesRegex(
                    ValueError,
                    'literal credential assignment',
                ):
                    VALIDATOR.validate_text(Path('synthetic'), synthetic, 'synthetic')

    def test_safe_credential_indirections_remain_allowed(self):
        name = 'pass' + 'word'
        VALIDATOR.validate_text(
            Path('synthetic'),
            '\n'.join((
                name + '=password',
                name + '=path.read_text(',
                name + '=load_password(args.password_file)',
                name + '=args.password',
                name + '=os.environ["OPERATOR_PASSWORD"]',
                name + '=__GRAFANA_READER_PASSWORD__',
                name + '=SECRET[reader-password]',
            )),
            'synthetic',
        )

    def test_documentation_and_loopback_ipv6_are_allowed(self):
        VALIDATOR.validate_text(
            Path('synthetic'),
            '2001:db8::5 ::1',
            'synthetic',
        )

    def test_non_public_ipv6_ranges_are_refused(self):
        values = (
            ':'.join(('fd00', '', '1')),
            ':'.join(('fe80', '', '1')),
            ':'.join(('2606', '4700', '4700', '', '1111')),
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'non-public IPv6'):
                    VALIDATOR.validate_text(Path('synthetic'), value, 'synthetic')

    def test_non_address_colon_syntax_is_ignored(self):
        VALIDATOR.validate_text(
            Path('synthetic'),
            '2026-08-28T10:20:30Z dict[str, int] https://example.com',
            'synthetic',
        )

    def test_dashboard_capture_refuses_server_owned_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'components/collector/grafana/dashboards/test.json'
            path.parent.mkdir(parents=True)
            document = {
                'apiVersion': 'dashboard.grafana.app/v2',
                'kind': 'Dashboard',
                'metadata': {
                    'name': 'test',
                    'namespace': 'default',
                    'uid': 'server-object-identity',
                },
                'spec': {},
                'status': {},
            }
            with mock.patch.object(VALIDATOR, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'server-owned metadata'):
                    VALIDATOR.validate_text(
                        path,
                        json.dumps(document),
                        'dashboard.json',
                    )

    def test_local_denylist_is_private_and_does_not_echo_match(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'repository'
            root.mkdir()
            denylist = base / 'publication-denylist.txt'
            private_term = 'environment' + ' identity'
            denylist.write_text(private_term + '\n', encoding='utf-8')
            os.chmod(denylist, 0o600)
            with mock.patch.object(VALIDATOR, 'ROOT', root), \
                    mock.patch.dict(
                        os.environ,
                        {VALIDATOR.LOCAL_DENYLIST_ENV: str(denylist)},
                        clear=False,
                    ):
                terms = VALIDATOR.load_local_denylist()
                with self.assertRaises(ValueError) as context:
                    VALIDATOR.validate_local_denylist_text(
                        'contains ' + private_term,
                        'synthetic',
                        terms,
                    )
            self.assertNotIn(private_term, str(context.exception))

    def test_local_denylist_refuses_repository_or_broad_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repository'
            root.mkdir()
            inside = root / 'denylist.txt'
            inside.write_text('private-term\n', encoding='utf-8')
            os.chmod(inside, 0o600)
            with mock.patch.object(VALIDATOR, 'ROOT', root), \
                    mock.patch.dict(
                        os.environ,
                        {VALIDATOR.LOCAL_DENYLIST_ENV: str(inside)},
                        clear=False,
                    ):
                with self.assertRaisesRegex(ValueError, 'outside the repository'):
                    VALIDATOR.load_local_denylist()

            outside = Path(directory) / 'denylist.txt'
            outside.write_text('private-term\n', encoding='utf-8')
            os.chmod(outside, 0o644)
            with mock.patch.object(VALIDATOR, 'ROOT', root), \
                    mock.patch.dict(
                        os.environ,
                        {VALIDATOR.LOCAL_DENYLIST_ENV: str(outside)},
                        clear=False,
                    ):
                with self.assertRaisesRegex(ValueError, 'group/world'):
                    VALIDATOR.load_local_denylist()

    def test_history_denylist_uses_stdin_and_does_not_echo_match(self):
        private_term = 'historical' + '-environment-identity'
        revision = 'a' * 40
        grep_result = mock.Mock(
            returncode=0,
            stdout=(revision + ':docs/example.md\n').encode('utf-8'),
            stderr=b'',
            args=['git', 'grep'],
        )
        rev_list = mock.Mock(stdout=(revision + '\n').encode('ascii'))
        with mock.patch.object(VALIDATOR, 'git', return_value=rev_list), \
                mock.patch.object(
                    VALIDATOR.subprocess,
                    'run',
                    return_value=grep_result,
                ) as run:
            with self.assertRaises(ValueError) as context:
                VALIDATOR.validate_history_local_denylist((private_term,))
        self.assertNotIn(private_term, str(context.exception))
        self.assertIn(private_term.encode('utf-8'), run.call_args.kwargs['input'])
        self.assertNotIn(private_term, ' '.join(run.call_args.args[0]))

    def test_embedded_url_credential_is_refused(self):
        synthetic = 'https://' + 'operator:private-value@' + 'example.com/path'
        with self.assertRaisesRegex(ValueError, 'embedded credentials'):
            VALIDATOR.validate_text(Path('synthetic'), synthetic, 'synthetic')

    def test_authorization_literal_is_refused(self):
        synthetic = 'Author' + 'ization: Bearer ' + 'MixedCase123456789'
        with self.assertRaisesRegex(ValueError, 'literal authorization'):
            VALIDATOR.validate_text(Path('synthetic'), synthetic, 'synthetic')

    def test_jwt_like_credential_is_refused(self):
        synthetic = '.'.join(('eyJ' + 'a' * 12, 'b' * 12, 'c' * 12))
        with self.assertRaisesRegex(ValueError, 'JWT-like'):
            VALIDATOR.validate_text(Path('synthetic'), synthetic, 'synthetic')

    def test_non_documentation_email_is_refused(self):
        synthetic = 'operator' + '@' + 'private.invalid.example.org'
        with self.assertRaisesRegex(ValueError, 'email identity'):
            VALIDATOR.validate_text(Path('synthetic'), synthetic, 'synthetic')

    def test_documentation_email_is_allowed(self):
        VALIDATOR.validate_text(
            Path('synthetic'),
            'operator' + '@' + 'example.com',
            'synthetic',
        )

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

    def test_rollback_tag_name_shape(self):
        self.assertIsNotNone(
            VALIDATOR.ROLLBACK_TAG_RE.fullmatch(
                'pre-documentation-audit-20260827'
            )
        )
        self.assertIsNone(
            VALIDATOR.ROLLBACK_TAG_RE.fullmatch('release-20260827')
        )
        self.assertIsNone(
            VALIDATOR.ROLLBACK_TAG_RE.fullmatch('pre-audit-latest')
        )


if __name__ == '__main__':
    unittest.main()
