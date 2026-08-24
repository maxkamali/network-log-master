from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
from typing import Any

from .shadow import (
    DEFAULT_LEDGER_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_ZSTD_PATH,
    ShadowError,
    file_snapshot,
    output_relative_path,
    validate_ledger,
    validate_source_relative_path,
)


DEFAULT_HANDOFF_ROOT = Path("/var/spool/network-log-normalizer-handoff")
DEFAULT_HANDOFF_LEDGER_PATH = Path(
    "/var/lib/network-log-normalizer/handoff.sqlite3"
)
DEFAULT_HANDOFF_PLAN_PATH = Path(
    "/etc/network-log-normalizer/handoff-plan.json"
)
DEFAULT_MAX_FILES = 100
MAX_PLAN_BYTES = 4096
HANDOFF_LEDGER_VERSION = 1

HANDOFF_LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS handoff_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    first_normalized_source_path TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL CHECK (length(plan_sha256) = 64),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS handoff_files (
    source_path TEXT PRIMARY KEY,
    shadow_output_path TEXT NOT NULL UNIQUE,
    output_size INTEGER NOT NULL CHECK (output_size >= 0),
    output_sha256 TEXT NOT NULL CHECK (length(output_sha256) = 64),
    record_count INTEGER NOT NULL CHECK (record_count >= 0),
    published_at TEXT NOT NULL
);
"""

HANDOFF_STATE_COLUMNS = (
    "singleton",
    "schema_version",
    "first_normalized_source_path",
    "plan_sha256",
    "created_at",
)

HANDOFF_FILE_COLUMNS = (
    "source_path",
    "shadow_output_path",
    "output_size",
    "output_sha256",
    "record_count",
    "published_at",
)


class HandoffError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HandoffPlan:
    first_normalized_source_path: str
    sha256: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise HandoffError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _regular_file(path: Path, label: str) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise HandoffError(f"cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise HandoffError(f"{label} is not a regular nonsymlink file")
    if details.st_nlink != 1:
        raise HandoffError(f"{label} must not be hard-linked")
    return details


def _regular_directory(path: Path, label: str) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise HandoffError(f"cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise HandoffError(f"{label} is not a regular nonsymlink directory")
    return details


def _validate_source_path(relative: Path) -> None:
    try:
        validate_source_relative_path(relative)
    except ShadowError as exc:
        raise HandoffError(str(exc)) from exc


def load_handoff_plan(path: Path, *, secure: bool = True) -> HandoffPlan:
    details = _regular_file(path, "handoff plan")
    if details.st_size > MAX_PLAN_BYTES:
        raise HandoffError("handoff plan exceeds size limit")
    if secure:
        if details.st_uid != 0:
            raise HandoffError("handoff plan must be owned by root")
        if details.st_gid != os.getegid():
            raise HandoffError("handoff plan group must match the runtime group")
        if stat.S_IMODE(details.st_mode) != 0o640:
            raise HandoffError("handoff plan mode must be 0640")
    try:
        raw = path.read_bytes()
        data = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"invalid handoff plan JSON: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {
        "schema_version",
        "first_normalized_source_path",
    }:
        raise HandoffError("handoff plan has unexpected keys")
    if data["schema_version"] != 1:
        raise HandoffError("unsupported handoff plan schema version")
    first_path = data["first_normalized_source_path"]
    if not isinstance(first_path, str):
        raise HandoffError("first normalized source path must be a string")
    _validate_source_path(Path(first_path))
    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return HandoffPlan(
        first_normalized_source_path=first_path,
        sha256=hashlib.sha256(canonical).hexdigest(),
    )


def _prepare_ledger_file(path: Path) -> None:
    _regular_directory(path.parent, "handoff ledger parent")
    if path.exists() or path.is_symlink():
        details = _regular_file(path, "handoff ledger")
        if stat.S_IMODE(details.st_mode) & 0o027:
            raise HandoffError(
                "handoff ledger must not be group-writable or world-accessible"
            )
        if details.st_uid != os.geteuid() or details.st_gid != os.getegid():
            raise HandoffError(
                "handoff ledger owner/group must match the runtime identity"
            )
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o640)
    os.close(descriptor)


def connect_handoff_ledger(
    path: Path,
    plan: HandoffPlan,
) -> sqlite3.Connection:
    _prepare_ledger_file(path)
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA synchronous=FULL")
    connection.executescript(HANDOFF_LEDGER_SQL)
    connection.execute(f"PRAGMA user_version={HANDOFF_LEDGER_VERSION}")
    row = connection.execute("SELECT * FROM handoff_state").fetchone()
    if row is None:
        connection.execute(
            """
            INSERT INTO handoff_state (
                singleton,
                schema_version,
                first_normalized_source_path,
                plan_sha256,
                created_at
            ) VALUES (1, 1, ?, ?, ?)
            """,
            (
                plan.first_normalized_source_path,
                plan.sha256,
                utc_now(),
            ),
        )
        connection.commit()
    validate_handoff_ledger(connection, plan)
    return connection


def validate_handoff_ledger(
    connection: sqlite3.Connection,
    plan: HandoffPlan,
) -> None:
    result = connection.execute("PRAGMA quick_check").fetchone()
    if result is None or result[0] != "ok":
        raise HandoffError("handoff ledger integrity check failed")
    if connection.execute("PRAGMA user_version").fetchone()[0] != (
        HANDOFF_LEDGER_VERSION
    ):
        raise HandoffError("unexpected handoff ledger schema version")
    state_columns = tuple(
        row[1]
        for row in connection.execute("PRAGMA table_info(handoff_state)")
    )
    file_columns = tuple(
        row[1]
        for row in connection.execute("PRAGMA table_info(handoff_files)")
    )
    if state_columns != HANDOFF_STATE_COLUMNS:
        raise HandoffError("unexpected handoff state schema")
    if file_columns != HANDOFF_FILE_COLUMNS:
        raise HandoffError("unexpected handoff file schema")
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if tables != {"handoff_state", "handoff_files"}:
        raise HandoffError("unexpected handoff ledger table inventory")
    rows = connection.execute("SELECT * FROM handoff_state").fetchall()
    if len(rows) != 1:
        raise HandoffError("handoff ledger must contain exactly one state row")
    row = rows[0]
    if (
        row["singleton"] != 1
        or row["schema_version"] != 1
        or row["first_normalized_source_path"]
        != plan.first_normalized_source_path
        or row["plan_sha256"] != plan.sha256
    ):
        raise HandoffError("handoff plan differs from initialized ledger")


def _open_shadow_ledger(path: Path) -> sqlite3.Connection:
    details = _regular_file(path, "shadow ledger")
    if stat.S_IMODE(details.st_mode) != 0o640:
        raise HandoffError("shadow ledger mode must be 0640")
    if details.st_uid != os.geteuid() or details.st_gid != os.getegid():
        raise HandoffError(
            "shadow ledger owner/group must match the runtime identity"
        )
    resolved = path.resolve(strict=True)
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro",
        uri=True,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    validate_ledger(connection)
    return connection


def _run_zstd_test(zstd_path: Path, path: Path) -> None:
    _regular_file(zstd_path, "Zstandard executable")
    result = subprocess.run(
        [str(zstd_path), "-q", "-t", "--", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise HandoffError("handoff Zstandard integrity validation failed")


def _require_runtime_file_metadata(path: Path, label: str) -> None:
    details = _regular_file(path, label)
    if stat.S_IMODE(details.st_mode) != 0o640:
        raise HandoffError(f"{label} mode must be 0640")
    if details.st_uid != os.geteuid() or details.st_gid != os.getegid():
        raise HandoffError(f"{label} owner/group must match the runtime identity")


def _ensure_handoff_target(handoff_root: Path, relative: Path) -> Path:
    _regular_directory(handoff_root, "handoff root")
    current = handoff_root
    for component in relative.parent.parts:
        current = current / component
        try:
            current.mkdir(mode=0o750)
        except FileExistsError:
            pass
        _regular_directory(current, "handoff partition")
    return handoff_root / relative


def _verified_shadow_row(
    row: sqlite3.Row,
    shadow_output_root: Path,
    zstd_path: Path,
) -> tuple[Path, int, str, int]:
    source_relative = Path(row["source_path"])
    _validate_source_path(source_relative)
    expected_output = output_relative_path(source_relative).as_posix()
    if row["output_path"] != expected_output:
        raise HandoffError("shadow ledger output path differs from contract")
    if row["input_records"] != row["output_records"]:
        raise HandoffError("shadow ledger cardinality differs")
    output = shadow_output_root / Path(row["output_path"])
    _require_runtime_file_metadata(output, "shadow output")
    snapshot = file_snapshot(output, "shadow output")
    if (
        snapshot.size != row["output_size"]
        or snapshot.sha256 != row["output_sha256"]
    ):
        raise HandoffError("shadow output differs from shadow ledger")
    _run_zstd_test(zstd_path, output)
    return (
        output,
        snapshot.size,
        snapshot.sha256,
        row["output_records"],
    )


def _publish_or_adopt(
    source: Path,
    target: Path,
    *,
    expected_size: int,
    expected_sha256: str,
    zstd_path: Path,
) -> str:
    if target.exists() or target.is_symlink():
        _require_runtime_file_metadata(target, "existing handoff file")
        existing = file_snapshot(target, "existing handoff file")
        if (
            existing.size != expected_size
            or existing.sha256 != expected_sha256
        ):
            raise HandoffError("existing handoff file differs from shadow output")
        _run_zstd_test(zstd_path, target)
        return "adopted"

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".partial",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as input_handle, os.fdopen(
            descriptor,
            "wb",
        ) as output_handle:
            shutil.copyfileobj(input_handle, output_handle)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.chmod(temporary, 0o640)
        candidate = file_snapshot(temporary, "temporary handoff file")
        if (
            candidate.size != expected_size
            or candidate.sha256 != expected_sha256
        ):
            raise HandoffError("temporary handoff copy differs from shadow output")
        _run_zstd_test(zstd_path, temporary)
        try:
            os.link(temporary, target, follow_symlinks=False)
        except FileExistsError as exc:
            raise HandoffError(
                "handoff target appeared during atomic publication"
            ) from exc
        temporary.unlink()
        directory_descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return "published"
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def publish_handoff(
    *,
    plan: HandoffPlan,
    shadow_ledger_path: Path,
    handoff_ledger_path: Path,
    shadow_output_root: Path,
    handoff_root: Path,
    zstd_path: Path = DEFAULT_ZSTD_PATH,
    max_files: int = DEFAULT_MAX_FILES,
) -> dict[str, int]:
    if max_files < 1:
        raise HandoffError("max-files must be at least 1")
    _regular_directory(shadow_output_root, "shadow output root")
    _regular_directory(handoff_root, "handoff root")
    summary = {
        "selected_files": 0,
        "published_files": 0,
        "adopted_files": 0,
        "published_records": 0,
        "pending_files": 0,
    }
    with connect_handoff_ledger(handoff_ledger_path, plan) as handoff, \
            _open_shadow_ledger(shadow_ledger_path) as shadow:
        cursor_row = handoff.execute(
            "SELECT MAX(source_path) FROM handoff_files"
        ).fetchone()
        after_path = cursor_row[0]
        if after_path is None:
            query = """
                SELECT * FROM shadow_files
                WHERE status = 'completed' AND source_path >= ?
                ORDER BY source_path
            """
            parameters = (plan.first_normalized_source_path,)
        else:
            _validate_source_path(Path(after_path))
            query = """
                SELECT * FROM shadow_files
                WHERE status = 'completed' AND source_path > ?
                ORDER BY source_path
            """
            parameters = (after_path,)
        remaining = shadow.execute(
            f"SELECT COUNT(*) FROM ({query})",
            parameters,
        ).fetchone()[0]
        selected = shadow.execute(
            query + " LIMIT ?",
            (*parameters, max_files),
        ).fetchall()
        summary["selected_files"] = len(selected)
        summary["pending_files"] = max(0, remaining - len(selected))
        for row in selected:
            source_relative = Path(row["source_path"])
            if source_relative.as_posix() < plan.first_normalized_source_path:
                raise HandoffError("shadow row precedes handoff floor")
            shadow_output, size, digest, records = _verified_shadow_row(
                row,
                shadow_output_root,
                zstd_path,
            )
            target = _ensure_handoff_target(handoff_root, source_relative)
            result = _publish_or_adopt(
                shadow_output,
                target,
                expected_size=size,
                expected_sha256=digest,
                zstd_path=zstd_path,
            )
            handoff.execute(
                """
                INSERT INTO handoff_files (
                    source_path,
                    shadow_output_path,
                    output_size,
                    output_sha256,
                    record_count,
                    published_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_relative.as_posix(),
                    row["output_path"],
                    size,
                    digest,
                    records,
                    utc_now(),
                ),
            )
            handoff.commit()
            summary[f"{result}_files"] += 1
            summary["published_records"] += records
    return summary


def verify_handoff(
    *,
    plan: HandoffPlan,
    shadow_ledger_path: Path,
    handoff_ledger_path: Path,
    shadow_output_root: Path,
    handoff_root: Path,
    zstd_path: Path = DEFAULT_ZSTD_PATH,
) -> dict[str, int]:
    _regular_directory(shadow_output_root, "shadow output root")
    _regular_directory(handoff_root, "handoff root")
    with connect_handoff_ledger(handoff_ledger_path, plan) as handoff, \
            _open_shadow_ledger(shadow_ledger_path) as shadow:
        rows = handoff.execute(
            "SELECT * FROM handoff_files ORDER BY source_path"
        ).fetchall()
        expected_paths: set[str] = set()
        total_records = 0
        for row in rows:
            source_text = row["source_path"]
            _validate_source_path(Path(source_text))
            if source_text < plan.first_normalized_source_path:
                raise HandoffError("handoff ledger path precedes handoff floor")
            shadow_row = shadow.execute(
                "SELECT * FROM shadow_files WHERE source_path = ?",
                (source_text,),
            ).fetchone()
            if shadow_row is None or shadow_row["status"] != "completed":
                raise HandoffError("handoff row lacks completed shadow evidence")
            _, size, digest, records = _verified_shadow_row(
                shadow_row,
                shadow_output_root,
                zstd_path,
            )
            if (
                row["shadow_output_path"] != shadow_row["output_path"]
                or row["output_size"] != size
                or row["output_sha256"] != digest
                or row["record_count"] != records
            ):
                raise HandoffError("handoff ledger differs from shadow evidence")
            target = handoff_root / Path(source_text)
            _require_runtime_file_metadata(target, "handoff file")
            target_snapshot = file_snapshot(target, "handoff file")
            if (
                target_snapshot.size != size
                or target_snapshot.sha256 != digest
            ):
                raise HandoffError("handoff file differs from shadow evidence")
            _run_zstd_test(zstd_path, target)
            expected_paths.add(source_text)
            total_records += records

        actual_paths: set[str] = set()
        for candidate in handoff_root.rglob("*"):
            if candidate.is_dir() and not candidate.is_symlink():
                continue
            relative = candidate.relative_to(handoff_root)
            _regular_file(candidate, "handoff tree file")
            _validate_source_path(relative)
            actual_paths.add(relative.as_posix())
        if actual_paths != expected_paths:
            raise HandoffError("handoff tree and handoff ledger inventory differ")

        completed_paths = {
            row[0]
            for row in shadow.execute(
                """
                SELECT source_path FROM shadow_files
                WHERE status = 'completed' AND source_path >= ?
                """,
                (plan.first_normalized_source_path,),
            )
        }
        if completed_paths != expected_paths:
            raise HandoffError("completed shadow files are missing from handoff")
    return {
        "verified_files": len(expected_paths),
        "verified_records": total_records,
        "missing_files": 0,
        "orphan_files": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Forward-only verified normalizer handoff publisher"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("publish", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "--plan", type=Path, default=DEFAULT_HANDOFF_PLAN_PATH
        )
        subparser.add_argument(
            "--shadow-ledger", type=Path, default=DEFAULT_LEDGER_PATH
        )
        subparser.add_argument(
            "--handoff-ledger",
            type=Path,
            default=DEFAULT_HANDOFF_LEDGER_PATH,
        )
        subparser.add_argument(
            "--shadow-output-root", type=Path, default=DEFAULT_OUTPUT_ROOT
        )
        subparser.add_argument(
            "--handoff-root", type=Path, default=DEFAULT_HANDOFF_ROOT
        )
        subparser.add_argument("--zstd", type=Path, default=DEFAULT_ZSTD_PATH)
        if command == "publish":
            subparser.add_argument(
                "--max-files", type=int, default=DEFAULT_MAX_FILES
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = load_handoff_plan(args.plan)
        arguments = {
            "plan": plan,
            "shadow_ledger_path": args.shadow_ledger,
            "handoff_ledger_path": args.handoff_ledger,
            "shadow_output_root": args.shadow_output_root,
            "handoff_root": args.handoff_root,
            "zstd_path": args.zstd,
        }
        if args.command == "publish":
            summary = publish_handoff(
                **arguments,
                max_files=args.max_files,
            )
            print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
            print("NORMALIZER_HANDOFF_PUBLISH=PASS")
        else:
            summary = verify_handoff(**arguments)
            print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
            print("NORMALIZER_HANDOFF_VERIFY=PASS")
        return 0
    except (
        HandoffError,
        OSError,
        ShadowError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
