#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "components/collector/sbin/ai-results-gate"
FIRST_LIVE = ROOT / "components/collector/sbin/verify-first-live-provenance.py"
TESTS = Path(__file__).resolve().parent


def main() -> int:
    try:
        for executable, label in (
            (GATE, "AI result gate"),
            (FIRST_LIVE, "first-live provenance verifier"),
        ):
            source = executable.read_text(encoding="utf-8", errors="strict")
            compile(source, str(executable), "exec")
            if not os.access(executable, os.X_OK):
                raise ValueError(f"{label} executable mode missing")

        for pattern in (
            "test_ai_results_gate.py",
            "test_first_live_provenance.py",
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    str(TESTS),
                    "-p",
                    pattern,
                ],
                cwd=ROOT,
                check=True,
            )
        print("AI_RESULTS_GATE_PACKAGE_VALIDATION=PASS")
        return 0
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
