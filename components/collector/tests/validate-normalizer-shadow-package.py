#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = ROOT / "components/collector/normalizer"
TEST_DIR = Path(__file__).resolve().parent


def main() -> int:
    try:
        files = [
            path
            for path in PACKAGE_DIR.rglob("*")
            if path.is_file() and not path.is_symlink()
        ]
        if not files:
            raise ValueError("normalizer shadow package inventory is empty")
        for path in files:
            if path.suffix == ".py":
                compile(
                    path.read_text(encoding="utf-8", errors="strict"),
                    str(path),
                    "exec",
                )
            if path.name in {
                "install-shadow.py",
                "install-handoff.py",
                "verify-shadow.py",
                "verify-handoff.py",
                "network-log-normalizer-shadow",
                "network-log-normalizer-handoff",
            } and not os.access(path, os.X_OK):
                raise ValueError(f"package executable mode missing: {path.name}")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(TEST_DIR),
                "-p",
                "test_normalizer_shadow_package.py",
            ],
            cwd=ROOT,
            check=True,
        )
        print("NORMALIZER_SHADOW_PACKAGE_VALIDATION=PASS")
        return 0
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
