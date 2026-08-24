#!/usr/bin/env python3
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


GX10_DIR = Path(__file__).resolve().parents[1]
GUARD_PATH = (
    GX10_DIR / 'install' / 'retire-transitional-enrichment.py'
)
SPEC = importlib.util.spec_from_file_location(
    'retire_transitional_enrichment',
    GUARD_PATH,
)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


def digest(value):
    return hashlib.sha256(value).hexdigest()


class EnrichmentRetirementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.root.chmod(0o700)
        self.references = self.root / 'references'
        self.references.mkdir(mode=0o700)
        self.candidate = self.root / 'candidate.py'
        self.target = self.root / 'installed.py'
        self.backup = self.root / 'rollback.py'
        self.legacy = b'legacy parser\n'
        self.projection = b'canonical projection\n'
        self.candidate.write_bytes(self.projection)
        self.candidate.chmod(0o755)
        self.target.write_bytes(self.legacy)
        self.target.chmod(0o755)

        self.saved = {
            name: getattr(GUARD, name)
            for name in (
                'CANDIDATE',
                'LEGACY_SHA256',
                'PROJECTION_SHA256',
                'REFERENCE_ROOTS',
                'TARGET_UID',
                'TARGET_GID',
            )
        }
        self.addCleanup(self.restore)
        GUARD.CANDIDATE = self.candidate
        GUARD.LEGACY_SHA256 = digest(self.legacy)
        GUARD.PROJECTION_SHA256 = digest(self.projection)
        GUARD.REFERENCE_ROOTS = (self.references,)
        GUARD.TARGET_UID = os.getuid()
        GUARD.TARGET_GID = os.getgid()

    def restore(self):
        for name, value in self.saved.items():
            setattr(GUARD, name, value)

    def test_apply_verify_and_nondestructive_rollback(self):
        GUARD.apply_retirement(self.target, self.backup)
        self.assertEqual(self.target.read_bytes(), self.projection)
        self.assertEqual(self.backup.read_bytes(), self.legacy)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o600)
        GUARD.validate_retired_state(self.target, self.backup)

        GUARD.rollback_retirement(self.target, self.backup)
        self.assertEqual(self.target.read_bytes(), self.legacy)
        self.assertEqual(self.backup.read_bytes(), self.legacy)

    def test_divergent_target_is_refused_before_backup(self):
        self.target.write_bytes(b'divergent\n')
        with self.assertRaisesRegex(
            GUARD.RetirementError,
            'hash differs',
        ):
            GUARD.apply_retirement(self.target, self.backup)
        self.assertFalse(self.backup.exists())

    def test_scheduler_reference_is_refused(self):
        (self.references / 'scheduled').write_text(str(self.target))
        with self.assertRaisesRegex(
            GUARD.RetirementError,
            'scheduler reference',
        ):
            GUARD.apply_retirement(self.target, self.backup)
        self.assertFalse(self.backup.exists())

    def test_failed_postcheck_restores_legacy_target(self):
        with mock.patch.object(
            GUARD,
            'validate_retired_state',
            side_effect=GUARD.RetirementError('synthetic failure'),
        ):
            with self.assertRaisesRegex(
                GUARD.RetirementError,
                'synthetic failure',
            ):
                GUARD.apply_retirement(self.target, self.backup)
        self.assertEqual(self.target.read_bytes(), self.legacy)
        self.assertEqual(self.backup.read_bytes(), self.legacy)


if __name__ == '__main__':
    unittest.main()
