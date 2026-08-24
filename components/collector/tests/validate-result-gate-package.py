#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "components/collector/sbin/ai-results-gate"
TESTS = Path(__file__).resolve().parent


def main() -> int:
    try:
        source = GATE.read_text(encoding="utf-8", errors="strict")
        compile(source, str(GATE), "exec")

        if not os.access(GATE, os.X_OK):
            raise ValueError("AI result gate executable mode missing")

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
                "test_ai_results_gate.py",
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
