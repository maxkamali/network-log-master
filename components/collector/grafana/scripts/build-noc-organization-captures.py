#!/usr/bin/env python3
"""Create the two organization-scoped NOC dashboard resources safely."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from dashboard_api import (
    DashboardApiError,
    clean_payload,
    load_captures,
)


GRAFANA_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = GRAFANA_ROOT.parents[2]
SOURCE_DIRECTORY = GRAFANA_ROOT / "dashboards"
SOURCE_NAMES = (
    "noc-view.json",
    "ai-incident-analysis-enhanced.json",
)
MAIN_ORG_PARAMETER_RE = re.compile(r'([?&])orgId=1(?=(&|$))')


def rewrite_org_links(value: Any, old: int, new: int) -> tuple[Any, int]:
    """Recursively rewrite only the explicit Grafana orgId query parameter."""
    if isinstance(value, dict):
        result = {}
        changes = 0
        for key, child in value.items():
            rewritten, child_changes = rewrite_org_links(child, old, new)
            result[key] = rewritten
            changes += child_changes
        return result, changes
    if isinstance(value, list):
        result = []
        changes = 0
        for child in value:
            rewritten, child_changes = rewrite_org_links(child, old, new)
            result.append(rewritten)
            changes += child_changes
        return result, changes
    if isinstance(value, str):
        if old != 1:
            raise DashboardApiError("only the main organization can be rewritten")
        return MAIN_ORG_PARAMETER_RE.subn(
            lambda match: match.group(1) + f"orgId={new}",
            value,
        )
    return value, 0


def build_capture(document: dict[str, Any], org_id: int) -> tuple[dict, int]:
    if org_id <= 1:
        raise DashboardApiError("NOC organization id must be greater than one")
    prepared = clean_payload(copy.deepcopy(document))
    prepared["metadata"]["namespace"] = f"org-{org_id}"
    prepared["spec"], changes = rewrite_org_links(
        prepared["spec"],
        1,
        org_id,
    )
    if changes < 1:
        raise DashboardApiError(
            "dashboard has no main-organization drilldown link to scope"
        )
    return prepared, changes


def prepare_output_directory(path: Path) -> Path:
    if path.is_symlink():
        raise DashboardApiError("NOC staging output must not be a symlink")
    resolved = path.resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise DashboardApiError(
            "NOC staging output must remain outside the public repository"
        )
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise DashboardApiError("NOC staging output must be a new empty directory")
    else:
        path.mkdir(mode=0o700, parents=True)
    os.chmod(path, 0o700)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output = prepare_output_directory(args.output_dir)
    for name in SOURCE_NAMES:
        source = SOURCE_DIRECTORY / name
        document = json.loads(source.read_text(encoding="utf-8", errors="strict"))
        prepared, changes = build_capture(document, args.org_id)
        target = output / name
        target.write_text(
            json.dumps(prepared, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.chmod(target, 0o600)
        print(f"{name} organization_links_rewritten={changes}")

    captures = load_captures(output)
    if len(captures) != len(SOURCE_NAMES):
        raise DashboardApiError("unexpected NOC staging capture count")
    print("GRAFANA_NOC_STAGING_CAPTURES=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DashboardApiError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
