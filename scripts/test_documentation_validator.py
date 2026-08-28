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
            (root / 'docs/DOCUMENTATION_GUIDE.md').write_text(
                '../SECURITY.md PROJECT_JOURNAL.md', encoding='utf-8'
            )
            (root / 'docs/AI_HANDOFF.md').write_text(
                'complete through execution-order item 41', encoding='utf-8'
            )
            with mock.patch.object(VALIDATOR, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'stale current-summary'):
                    VALIDATOR.validate_entry_contract()

    def test_markdown_shape_rejects_unbalanced_fence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'broken.md'
            path.write_text('# Title\n\n```text\nopen\n', encoding='utf-8')
            with mock.patch.object(VALIDATOR, 'ROOT', Path(directory)):
                with self.assertRaisesRegex(ValueError, 'unbalanced Markdown'):
                    VALIDATOR.validate_markdown_shape((path,))

    def test_reference_index_rejects_unlisted_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / 'docs'
            docs.mkdir()
            guide = docs / 'DOCUMENTATION_GUIDE.md'
            guide.write_text('# Documentation Guide\n', encoding='utf-8')
            (docs / 'UNLISTED.md').write_text('# Unlisted\n', encoding='utf-8')
            with mock.patch.object(VALIDATOR, 'ROOT', root), \
                    mock.patch.object(VALIDATOR, 'DOCS_DIR', docs), \
                    mock.patch.object(VALIDATOR, 'GUIDE', guide):
                with self.assertRaisesRegex(ValueError, 'unindexed document'):
                    VALIDATOR.validate_reference_index()

    def test_entry_contract_rejects_missing_current_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, values in VALIDATOR.REQUIRED_CURRENT_CONTRACTS.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('\n'.join(values), encoding='utf-8')
            target = root / 'docs/TWO_SERVER_REBUILD.md'
            target.write_text('current functional target\n', encoding='utf-8')
            with mock.patch.object(VALIDATOR, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'current contract'):
                    VALIDATOR.validate_current_contracts()

    def test_current_contracts_cover_rebuild_extensions(self):
        self.assertIn(
            'activate normalizer shadow before gx10 correlation',
            VALIDATOR.REQUIRED_CURRENT_CONTRACTS['docs/TWO_SERVER_REBUILD.md'],
        )
        self.assertIn(
            'phase 12: full-system acceptance and reboot recovery',
            VALIDATOR.REQUIRED_CURRENT_CONTRACTS[
                'components/gx10/CLEAN_MACHINE_RUNBOOK.md'
            ],
        )
        self.assertIn(
            'components/collector/sbin/verify-first-live-provenance.py',
            VALIDATOR.REQUIRED_CURRENT_CONTRACTS[
                'docs/RESULT_TRANSPORT.md'
            ],
        )
        self.assertIn(
            'build-noc-organization-captures.py',
            VALIDATOR.REQUIRED_CURRENT_CONTRACTS['docs/GRAFANA.md'],
        )

    def test_current_contracts_cover_semantic_boundaries(self):
        self.assertIn(
            'ordinary incident assessment records an immutable terminal no-result',
            VALIDATOR.REQUIRED_CURRENT_CONTRACTS['docs/OPERATIONS.md'],
        )
        self.assertIn(
            'hidden triage instead retains its immutable batch pending for bounded retry',
            VALIDATOR.REQUIRED_CURRENT_CONTRACTS['docs/OPERATIONS.md'],
        )
        self.assertIn(
            'historical base reconstruction order',
            VALIDATOR.REQUIRED_CURRENT_CONTRACTS[
                'components/gx10/REBUILD_STATUS.md'
            ],
        )
        self.assertIn(
            'all six current dashboards are captured',
            VALIDATOR.REQUIRED_CURRENT_CONTRACTS[
                'components/collector/REBUILD_STATUS.md'
            ],
        )

    def test_stale_summary_checks_keep_merged_entries(self):
        acceptance = VALIDATOR.STALE_SUMMARIES['docs/ACCEPTANCE.md']
        self.assertIn('complete through item 42', acceptance)
        self.assertIn('next stability/retirement gate', acceptance)
        collector = VALIDATOR.STALE_SUMMARIES['components/collector/README.md']
        self.assertIn('queue placement uses `entity_type = interface`', collector)
        self.assertIn(
            'project-wide two-server documentation and acceptance reconciliation follows',
            collector,
        )
        transport = VALIDATOR.STALE_SUMMARIES['docs/RESULT_TRANSPORT.md']
        self.assertIn('## remaining gates', transport)
        self.assertIn('the candidate gate creates', transport)
        self.assertIn('not reconstructable from the public tree', transport)
        clean_runbook = VALIDATOR.STALE_SUMMARIES[
            'components/gx10/CLEAN_MACHINE_RUNBOOK.md'
        ]
        self.assertIn(
            'repository currently lacks the retained two-host qualification package',
            clean_runbook,
        )

    def test_reachability_rejects_orphaned_component_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / 'docs'
            components = root / 'components'
            docs.mkdir()
            components.mkdir()
            (root / 'README.md').write_text('# Root\n', encoding='utf-8')
            (docs / 'DOCUMENTATION_GUIDE.md').write_text(
                '# Guide\n', encoding='utf-8'
            )
            orphan = components / 'ORPHAN.md'
            orphan.write_text('# Orphan\n', encoding='utf-8')
            with mock.patch.object(VALIDATOR, 'ROOT', root), \
                    mock.patch.object(VALIDATOR, 'DOCS_DIR', docs), \
                    mock.patch.object(VALIDATOR, 'GUIDE', docs / 'DOCUMENTATION_GUIDE.md'):
                with self.assertRaisesRegex(ValueError, 'unreachable'):
                    VALIDATOR.validate_documentation_reachability()

    def test_reachability_rejects_orphaned_root_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('# Root\n', encoding='utf-8')
            (root / 'FUTURE.md').write_text('# Future\n', encoding='utf-8')
            with mock.patch.object(VALIDATOR, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'FUTURE.md'):
                    VALIDATOR.validate_documentation_reachability()

    def test_reachability_rejects_orphan_outside_standard_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notes = root / 'future'
            notes.mkdir()
            (root / 'README.md').write_text('# Root\n', encoding='utf-8')
            (notes / 'ROADMAP-NOTE.md').write_text(
                '# Roadmap note\n',
                encoding='utf-8',
            )
            with mock.patch.object(VALIDATOR, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'future/ROADMAP-NOTE.md'):
                    VALIDATOR.validate_documentation_reachability()


if __name__ == '__main__':
    unittest.main()
