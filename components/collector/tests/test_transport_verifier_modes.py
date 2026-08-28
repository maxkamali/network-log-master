#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[3]
TRANSPORT = ROOT / "components/collector/filesystem/verify-transport.sh"
RUNTIME = ROOT / "components/collector/install/verify-runtime.sh"


class TransportVerifierModeTests(unittest.TestCase):
    def run_script(self, path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(path), *arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_help_exposes_bounded_modes_without_host_inspection(self) -> None:
        for path, option in (
            (TRANSPORT, "--reader-bind-source"),
            (RUNTIME, "--transport-view"),
        ):
            result = self.run_script(path, "--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(option, result.stdout)
            self.assertIn("raw|handoff", result.stdout)

    def test_unknown_modes_fail_before_host_inspection(self) -> None:
        transport = self.run_script(
            TRANSPORT, "--reader-bind-source", "unexpected"
        )
        self.assertNotEqual(transport.returncode, 0)
        self.assertIn("unsupported reader bind source", transport.stderr)

        runtime = self.run_script(RUNTIME, "--transport-view", "unexpected")
        self.assertNotEqual(runtime.returncode, 0)
        self.assertIn("unsupported transport view", runtime.stderr)

    def test_raw_default_and_exact_handoff_mapping_are_retained(self) -> None:
        transport = TRANSPORT.read_text(encoding="utf-8")
        self.assertIn('READER_BIND_SOURCE="raw"', transport)
        self.assertIn('READER_SOURCE_PATH="/var/spool/vector-ai"', transport)
        self.assertIn(
            'READER_SOURCE_PATH="/var/spool/network-log-normalizer-handoff"',
            transport,
        )
        self.assertIn("-o FSROOT", transport)
        self.assertIn(
            '"$READER_SOURCE_PATH /srv/ai-spool-reader/spool '
            'none bind,ro,nosuid,nodev,noexec 0 0"',
            transport,
        )
        self.assertIn("exact_line_count", transport)
        self.assertIn("fstab_target_count", transport)
        self.assertIn('$2 == target', transport)
        self.assertIn("OTHER_READER_FSTAB_LINE", transport)
        self.assertIn('reader_bind_source=$READER_BIND_SOURCE', transport)

    def test_runtime_plumbs_selected_mode_to_transport_verifier(self) -> None:
        runtime = RUNTIME.read_text(encoding="utf-8")
        self.assertIn('TRANSPORT_VIEW="raw"', runtime)
        self.assertIn(
            '--reader-bind-source "$TRANSPORT_VIEW"',
            runtime,
        )
        self.assertIn('collector_transport_view=$TRANSPORT_VIEW', runtime)


if __name__ == "__main__":
    unittest.main()
