#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / 'validate-documentation.py'
SPEC = importlib.util.spec_from_file_location(
    'validate_documentation',
    VALIDATOR_PATH,
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class DocumentationValidatorTests(unittest.TestCase):
    def test_slug_matches_common_github_heading_shape(self):
        self.assertEqual(
            VALIDATOR.slug('Application at a glance'),
            'application-at-a-glance',
        )
        self.assertEqual(
            VALIDATOR.slug('Read [`README.md`](README.md) first'),
            'read-readmemd-first',
        )

    def test_resolve_same_document_anchor(self):
        source = VALIDATOR.ROOT / 'docs' / 'START_HERE.md'
        target, anchor = VALIDATOR.resolve_link(source, '#working-rules')
        self.assertEqual(target, source)
        self.assertEqual(anchor, 'working-rules')

    def test_entry_contract_rejects_stale_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in VALIDATOR.REQUIRED_FILES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('', encoding='utf-8')
            for relative in VALIDATOR.STALE_SUMMARIES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('', encoding='utf-8')
            (root / 'README.md').write_text(
                'docs/START_HERE.md docs/CURRENT_STATE.md', encoding='utf-8'
            )
            (root / 'docs/START_HERE.md').write_text(
                '../README.md ARCHITECTURE.md CURRENT_STATE.md '
                'DOCUMENTATION_GUIDE.md',
                encoding='utf-8',
            )
            (root / 'docs/AI_HANDOFF.md').write_text(
                'complete through execution-order item 41', encoding='utf-8'
            )
            with mock.patch.object(VALIDATOR, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'stale current-summary'):
                    VALIDATOR.validate_entry_contract()


if __name__ == '__main__':
    unittest.main()
