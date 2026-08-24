#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys


RUN_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
DEVICE_RE = re.compile(r"^[A-Za-z0-9._:%+-]{1,256}$")
MAX_MAPPINGS = 10000


class BackfillError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def validate_private_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise BackfillError("device mapping is not a regular file")
    details = path.stat()
    if details.st_nlink != 1 or stat.S_IMODE(details.st_mode) != 0o600:
        raise BackfillError("device mapping metadata differs")
    if details.st_size <= 0 or details.st_size > 4 * 1024 * 1024:
        raise BackfillError("device mapping size differs")


def load_mapping(path):
    validate_private_file(path)
    rows = {}
    for number, line in enumerate(
        Path(path).read_text(encoding="utf-8", errors="strict").splitlines(),
        start=1,
    ):
        if not line:
            raise BackfillError(f"mapping line {number} is empty")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BackfillError(f"mapping line {number} is invalid JSON") from exc
        if (
            not isinstance(row, dict)
            or set(row) != {"device", "run_id"}
            or canonical_json(row) != line
            or not isinstance(row["run_id"], str)
            or RUN_ID_RE.fullmatch(row["run_id"]) is None
            or not isinstance(row["device"], str)
            or DEVICE_RE.fullmatch(row["device"]) is None
        ):
            raise BackfillError(f"mapping line {number} differs")
        previous = rows.setdefault(row["run_id"], row["device"])
        if previous != row["device"]:
            raise BackfillError("mapping contains a divergent run identity")
    if not rows or len(rows) > MAX_MAPPINGS:
        raise BackfillError("mapping count differs")
    return rows


def sql_literal(value):
    if "'" in value or "\\" in value:
        raise BackfillError("mapping value is not SQL-literal safe")
    return f"'{value}'"


def render_sql(rows):
    ordered = sorted(rows.items())
    arguments = []
    run_ids = []
    for run_id, device in ordered:
        arguments.extend(
            [f"run_id = {sql_literal(run_id)}", sql_literal(device)]
        )
        run_ids.append(sql_literal(run_id))
    arguments.append("device")
    identity_list = ", ".join(run_ids)
    return (
        "ALTER TABLE observability.ai_updates\n"
        f"UPDATE device = multiIf({', '.join(arguments)})\n"
        f"WHERE run_id IN ({identity_list})\n"
        "SETTINGS mutations_sync = 2;\n"
        "SELECT\n"
        "    count() AS mapped_rows,\n"
        "    countIf(device = '') AS missing_devices,\n"
        "    uniqExact(run_id) AS unique_runs\n"
        "FROM observability.ai_updates\n"
        f"WHERE run_id IN ({identity_list})\n"
        "FORMAT TSVWithNames;\n"
    )


def write_exclusive(path, data):
    path = Path(path)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if path.exists():
            os.chmod(path, 0o600)


def main():
    parser = argparse.ArgumentParser(
        description="Build a private ClickHouse AI-device backfill query"
    )
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = load_mapping(args.mapping)
    write_exclusive(args.output, render_sql(rows))
    print(f"AI_DEVICE_BACKFILL_BUILD=PASS mappings={len(rows)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BackfillError, OSError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
