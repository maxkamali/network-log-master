from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

from . import SCHEMA_VERSION, __version__, normalize_record


DEFAULT_SOURCE_ROOT = Path("/var/spool/vector-ai")
DEFAULT_OUTPUT_ROOT = Path("/var/spool/network-log-normalizer-shadow")
DEFAULT_LEDGER_PATH = Path(
    "/var/lib/network-log-normalizer/state.sqlite3"
)
DEFAULT_INVENTORY_PATH = Path(
    "/etc/network-log-normalizer/platform-inventory.json"
)
DEFAULT_ZSTD_PATH = Path("/usr/bin/zstd")
DEFAULT_SETTLE_SECONDS = 120
DEFAULT_MAX_FILES = 100
MAX_INVENTORY_BYTES = 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
LEDGER_VERSION = 1

SOURCE_PATH_RE = re.compile(
    r"^(?P<year>[0-9]{4})/"
    r"(?P<month>[0-9]{2})/"
    r"(?P<day>[0-9]{2})/"
    r"(?P<hour>[0-9]{2})/"
    r"syslog-(?P=year)(?P=month)(?P=day)-"
    r"(?P=hour)(?P<minute>[0-9]{2})[.]jsonl[.]zst$"
)

SUPPORTED_PLATFORMS = {
    ("arista", "eos"),
    ("cisco", "iosxr"),
    ("cisco", "nxos"),
}

LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS shadow_files (
    source_path TEXT PRIMARY KEY,
    source_size INTEGER NOT NULL CHECK (source_size >= 0),
    source_mtime_ns INTEGER NOT NULL CHECK (source_mtime_ns >= 0),
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
    inventory_sha256 TEXT NOT NULL CHECK (length(inventory_sha256) = 64),
    normalizer_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('processing', 'completed')),
    output_path TEXT NOT NULL UNIQUE,
    output_size INTEGER,
    output_sha256 TEXT,
    input_records INTEGER,
    output_records INTEGER,
    generic_records INTEGER,
    enriched_records INTEGER,
    inventory_hits INTEGER,
    inventory_misses INTEGER,
    parser_error_records INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK (
        status = 'processing'
        OR (
            output_size >= 0
            AND length(output_sha256) = 64
            AND input_records >= 0
            AND output_records = input_records
            AND generic_records >= 0
            AND enriched_records >= 0
            AND generic_records + enriched_records = output_records
            AND inventory_hits >= 0
            AND inventory_misses >= 0
            AND inventory_hits + inventory_misses = input_records
            AND parser_error_records >= 0
            AND completed_at IS NOT NULL
        )
    )
);
"""

LEDGER_COLUMNS = (
    "source_path",
    "source_size",
    "source_mtime_ns",
    "source_sha256",
    "inventory_sha256",
    "normalizer_version",
    "schema_version",
    "status",
    "output_path",
    "output_size",
    "output_sha256",
    "input_records",
    "output_records",
    "generic_records",
    "enriched_records",
    "inventory_hits",
    "inventory_misses",
    "parser_error_records",
    "started_at",
    "completed_at",
)


class ShadowError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Inventory:
    platforms: dict[str, tuple[str, str]]
    sha256: str


@dataclass(frozen=True, slots=True)
class FileSnapshot:
    size: int
    mtime_ns: int
    sha256: str
    device: int
    inode: int


@dataclass(slots=True)
class FileCounts:
    input_records: int = 0
    output_records: int = 0
    generic_records: int = 0
    enriched_records: int = 0
    inventory_hits: int = 0
    inventory_misses: int = 0
    parser_error_records: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "input_records": self.input_records,
            "output_records": self.output_records,
            "generic_records": self.generic_records,
            "enriched_records": self.enriched_records,
            "inventory_hits": self.inventory_hits,
            "inventory_misses": self.inventory_misses,
            "parser_error_records": self.parser_error_records,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ShadowError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _regular_file_metadata(path: Path, label: str) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise ShadowError(f"cannot inspect {label}: {exc}") from exc

    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise ShadowError(f"{label} is not a regular nonsymlink file")
    if details.st_nlink != 1:
        raise ShadowError(f"{label} must not be hard-linked")
    return details


def _regular_directory(path: Path, label: str) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise ShadowError(f"cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise ShadowError(f"{label} is not a regular nonsymlink directory")
    return details


def load_inventory(path: Path, *, secure: bool = True) -> Inventory:
    details = _regular_file_metadata(path, "platform inventory")

    if details.st_size > MAX_INVENTORY_BYTES:
        raise ShadowError("platform inventory exceeds size limit")

    if secure:
        mode = stat.S_IMODE(details.st_mode)
        if details.st_uid != 0:
            raise ShadowError("platform inventory must be owned by root")
        if details.st_gid != os.getgid():
            raise ShadowError(
                "platform inventory group must match the runtime group"
            )
        if mode != 0o640:
            raise ShadowError("platform inventory mode must be 0640")

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShadowError(f"cannot read platform inventory: {exc}") from exc

    try:
        data = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ShadowError(f"invalid platform inventory JSON: {exc}") from exc

    if not isinstance(data, dict) or set(data) != {
        "schema_version",
        "platforms",
    }:
        raise ShadowError("platform inventory has unexpected top-level keys")
    if data["schema_version"] != 1:
        raise ShadowError("unsupported platform inventory schema version")
    if not isinstance(data["platforms"], dict):
        raise ShadowError("platforms must be an object")

    platforms: dict[str, tuple[str, str]] = {}
    for source_ip, entry in data["platforms"].items():
        try:
            canonical = str(ipaddress.ip_address(source_ip))
        except ValueError as exc:
            raise ShadowError(f"invalid platform source identity: {source_ip}") from exc
        if canonical != source_ip:
            raise ShadowError(
                f"platform source identity is not canonical: {source_ip}"
            )
        if not isinstance(entry, dict) or set(entry) != {
            "vendor_hint",
            "os_family_hint",
        }:
            raise ShadowError(
                f"platform entry has unexpected keys: {source_ip}"
            )
        pair = (entry["vendor_hint"], entry["os_family_hint"])
        if pair not in SUPPORTED_PLATFORMS:
            raise ShadowError(
                f"unsupported vendor/OS pair for platform entry: {source_ip}"
            )
        platforms[canonical] = pair

    canonical_json = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return Inventory(
        platforms=platforms,
        sha256=hashlib.sha256(canonical_json).hexdigest(),
    )


def validate_source_relative_path(relative: Path) -> None:
    text = relative.as_posix()
    match = SOURCE_PATH_RE.fullmatch(text)
    if match is None:
        raise ShadowError(f"ineligible source path: {text}")
    try:
        datetime(
            int(match["year"]),
            int(match["month"]),
            int(match["day"]),
            int(match["hour"]),
            int(match["minute"]),
            tzinfo=timezone.utc,
        )
    except ValueError as exc:
        raise ShadowError(f"invalid source partition time: {text}") from exc


def output_relative_path(source_relative: Path) -> Path:
    validate_source_relative_path(source_relative)
    suffix = ".jsonl.zst"
    name = source_relative.name
    return source_relative.with_name(
        name[: -len(suffix)] + ".normalized.jsonl.zst"
    )


def file_snapshot(path: Path, label: str) -> FileSnapshot:
    before = _regular_file_metadata(path, label)
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    digest = hashlib.sha256()
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ShadowError(f"cannot open {label}: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
        ):
            raise ShadowError(f"{label} changed during open")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        opened.st_size != after.st_size
        or opened.st_mtime_ns != after.st_mtime_ns
        or opened.st_dev != after.st_dev
        or opened.st_ino != after.st_ino
    ):
        raise ShadowError(f"{label} changed while hashing")
    return FileSnapshot(
        size=after.st_size,
        mtime_ns=after.st_mtime_ns,
        sha256=digest.hexdigest(),
        device=after.st_dev,
        inode=after.st_ino,
    )


def eligible_source_files(
    source_root: Path,
    *,
    settle_seconds: int = DEFAULT_SETTLE_SECONDS,
    now_ns: int | None = None,
    after_path: str | None = None,
) -> list[Path]:
    _regular_directory(source_root, "source root")
    if settle_seconds < DEFAULT_SETTLE_SECONDS:
        raise ShadowError(
            f"settle time must be at least {DEFAULT_SETTLE_SECONDS} seconds"
        )
    if now_ns is None:
        now_ns = time.time_ns()
    if after_path is not None:
        validate_source_relative_path(Path(after_path))
    minimum_age_ns = settle_seconds * 1_000_000_000
    output: list[Path] = []
    for candidate in source_root.rglob("*.jsonl.zst"):
        relative = candidate.relative_to(source_root)
        try:
            validate_source_relative_path(relative)
        except ShadowError:
            continue
        if after_path is not None and relative.as_posix() <= after_path:
            continue
        details = _regular_file_metadata(candidate, "source file")
        if now_ns - details.st_mtime_ns >= minimum_age_ns:
            output.append(candidate)
    return sorted(output, key=lambda value: value.relative_to(source_root).as_posix())


def _prepare_ledger_file(path: Path) -> None:
    _regular_directory(path.parent, "ledger parent")
    if path.exists() or path.is_symlink():
        details = _regular_file_metadata(path, "ledger")
        mode = stat.S_IMODE(details.st_mode)
        if mode & 0o027:
            raise ShadowError("ledger must not be group-writable or world-accessible")
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o640)
    except OSError as exc:
        raise ShadowError(f"cannot create ledger: {exc}") from exc
    os.close(descriptor)


def connect_ledger(path: Path) -> sqlite3.Connection:
    _prepare_ledger_file(path)
    connection = sqlite3.connect(path, timeout=5)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA synchronous=FULL")
    connection.executescript(LEDGER_SQL)
    connection.execute(f"PRAGMA user_version={LEDGER_VERSION}")
    connection.commit()
    validate_ledger(connection)
    return connection


def validate_ledger(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA quick_check").fetchone()
    if result is None or result[0] != "ok":
        raise ShadowError("ledger integrity check failed")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != LEDGER_VERSION:
        raise ShadowError("unexpected ledger schema version")
    columns = tuple(
        row[1]
        for row in connection.execute("PRAGMA table_info(shadow_files)")
    )
    if columns != LEDGER_COLUMNS:
        raise ShadowError("unexpected ledger schema")


def _source_row(connection: sqlite3.Connection, source_path: str) -> sqlite3.Row | None:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        "SELECT * FROM shadow_files WHERE source_path = ?",
        (source_path,),
    ).fetchone()


def _snapshot_matches_row(snapshot: FileSnapshot, row: sqlite3.Row) -> bool:
    return (
        row["source_size"] == snapshot.size
        and row["source_mtime_ns"] == snapshot.mtime_ns
        and row["source_sha256"] == snapshot.sha256
    )


def _run_zstd_test(zstd_path: Path, path: Path) -> None:
    result = subprocess.run(
        [str(zstd_path), "-q", "-t", "--", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise ShadowError("Zstandard integrity validation failed")


def _canonical_source_ip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def _normalization_input(
    value: Any,
    inventory: Inventory,
) -> tuple[Any, bool]:
    if not isinstance(value, dict):
        return value, False
    record = dict(value)
    record.pop("vendor_hint", None)
    record.pop("os_family_hint", None)
    source_ip = _canonical_source_ip(record.get("source_ip"))
    platform = inventory.platforms.get(source_ip or "")
    if platform is None:
        return record, False
    record["vendor_hint"], record["os_family_hint"] = platform
    return record, True


def _normalize_stream(
    source: Path,
    destination: Path,
    inventory: Inventory,
    zstd_path: Path,
) -> FileCounts:
    counts = FileCounts()
    process = subprocess.Popen(
        [str(zstd_path), "-q", "-dc", "--", str(source)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        with destination.open("wb") as output:
            while True:
                line = process.stdout.readline(MAX_LINE_BYTES + 2)
                if line == b"":
                    break
                if len(line) > MAX_LINE_BYTES + 1:
                    raise ShadowError("input line exceeds size limit")
                if len(line) == MAX_LINE_BYTES + 1 and not line.endswith(b"\n"):
                    raise ShadowError("input line exceeds size limit")
                payload = line[:-1] if line.endswith(b"\n") else line
                if payload.endswith(b"\r"):
                    payload = payload[:-1]
                try:
                    value = json.loads(payload.decode("utf-8", errors="strict"))
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise ShadowError("invalid JSONL source record") from exc
                normalized_input, inventory_hit = _normalization_input(
                    value,
                    inventory,
                )
                event = normalize_record(normalized_input).to_dict()
                encoded = json.dumps(
                    event,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8") + b"\n"
                output.write(encoded)
                counts.input_records += 1
                counts.output_records += 1
                if inventory_hit:
                    counts.inventory_hits += 1
                else:
                    counts.inventory_misses += 1
                if event["attributes"].get("normalization_path") == "parser":
                    counts.enriched_records += 1
                else:
                    counts.generic_records += 1
                if event["attributes"].get("parser_errors"):
                    counts.parser_error_records += 1
            output.flush()
            os.fsync(output.fileno())
        return_code = process.wait(timeout=300)
        if return_code != 0:
            raise ShadowError("Zstandard source decode failed")
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()
        process.stderr.close()
    return counts


def _compress_file(source: Path, destination: Path, zstd_path: Path) -> None:
    with destination.open("wb") as output:
        result = subprocess.run(
            [str(zstd_path), "-q", "-c", "--", str(source)],
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )
        output.flush()
        os.fsync(output.fileno())
    if result.returncode != 0:
        raise ShadowError("Zstandard output compression failed")
    os.chmod(destination, 0o640)
    _run_zstd_test(zstd_path, destination)


def _ensure_output_parent(output_root: Path, relative: Path) -> Path:
    _regular_directory(output_root, "output root")
    current = output_root
    for component in relative.parent.parts:
        current = current / component
        try:
            current.mkdir(mode=0o750)
        except FileExistsError:
            pass
        _regular_directory(current, "output partition")
    return output_root / relative


def _verify_completed_row(
    row: sqlite3.Row,
    output_root: Path,
    zstd_path: Path,
) -> None:
    output_relative = Path(row["output_path"])
    if output_relative.is_absolute() or ".." in output_relative.parts:
        raise ShadowError("ledger contains unsafe output path")
    output = output_root / output_relative
    snapshot = file_snapshot(output, "completed output")
    if (
        snapshot.size != row["output_size"]
        or snapshot.sha256 != row["output_sha256"]
    ):
        raise ShadowError("completed output differs from ledger")
    _run_zstd_test(zstd_path, output)


def process_source_file(
    source: Path,
    *,
    source_root: Path,
    output_root: Path,
    ledger_path: Path,
    inventory: Inventory,
    zstd_path: Path = DEFAULT_ZSTD_PATH,
) -> str:
    _regular_directory(source_root, "source root")
    _regular_directory(output_root, "output root")
    _regular_file_metadata(zstd_path, "Zstandard executable")
    relative = source.relative_to(source_root)
    validate_source_relative_path(relative)
    output_relative = output_relative_path(relative)
    output = _ensure_output_parent(output_root, output_relative)
    before = file_snapshot(source, "source file")

    with connect_ledger(ledger_path) as connection:
        row = _source_row(connection, relative.as_posix())
        if row is not None:
            if not _snapshot_matches_row(before, row):
                raise ShadowError("previously recorded source path changed")
            if row["status"] == "completed":
                _verify_completed_row(row, output_root, zstd_path)
                return "skipped"
            if (
                row["inventory_sha256"] != inventory.sha256
                or row["normalizer_version"] != __version__
                or row["schema_version"] != SCHEMA_VERSION
                or row["output_path"] != output_relative.as_posix()
            ):
                raise ShadowError("incomplete ledger row differs from retry context")
            resuming = True
        else:
            if output.exists() or output.is_symlink():
                raise ShadowError("unexpected existing output without ledger row")
            connection.execute(
                """
                INSERT INTO shadow_files (
                    source_path, source_size, source_mtime_ns,
                    source_sha256, inventory_sha256,
                    normalizer_version, schema_version, status,
                    output_path, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'processing', ?, ?)
                """,
                (
                    relative.as_posix(),
                    before.size,
                    before.mtime_ns,
                    before.sha256,
                    inventory.sha256,
                    __version__,
                    SCHEMA_VERSION,
                    output_relative.as_posix(),
                    utc_now(),
                ),
            )
            connection.commit()
            resuming = False

        raw_descriptor, raw_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".jsonl.partial",
            dir=output.parent,
        )
        os.close(raw_descriptor)
        compressed_descriptor, compressed_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".zst.partial",
            dir=output.parent,
        )
        os.close(compressed_descriptor)
        raw_temporary = Path(raw_name)
        compressed_temporary = Path(compressed_name)
        try:
            counts = _normalize_stream(
                source,
                raw_temporary,
                inventory,
                zstd_path,
            )
            if counts.input_records != counts.output_records:
                raise ShadowError("input/output record count differs")
            _compress_file(raw_temporary, compressed_temporary, zstd_path)
            candidate = file_snapshot(compressed_temporary, "temporary output")
            after = file_snapshot(source, "source postcheck")
            if after != before:
                raise ShadowError("source file changed during processing")

            if output.exists() or output.is_symlink():
                if not resuming:
                    raise ShadowError("unexpected output appeared during processing")
                existing = file_snapshot(output, "resumed output")
                if (
                    existing.size != candidate.size
                    or existing.sha256 != candidate.sha256
                ):
                    raise ShadowError("resumed output differs from regenerated output")
            else:
                try:
                    os.link(compressed_temporary, output, follow_symlinks=False)
                except FileExistsError as exc:
                    raise ShadowError("output appeared during atomic publication") from exc
                os.chmod(output, 0o640)
                directory_descriptor = os.open(output.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)

            connection.execute(
                """
                UPDATE shadow_files SET
                    status = 'completed',
                    output_size = ?,
                    output_sha256 = ?,
                    input_records = ?,
                    output_records = ?,
                    generic_records = ?,
                    enriched_records = ?,
                    inventory_hits = ?,
                    inventory_misses = ?,
                    parser_error_records = ?,
                    completed_at = ?
                WHERE source_path = ? AND status = 'processing'
                """,
                (
                    candidate.size,
                    candidate.sha256,
                    counts.input_records,
                    counts.output_records,
                    counts.generic_records,
                    counts.enriched_records,
                    counts.inventory_hits,
                    counts.inventory_misses,
                    counts.parser_error_records,
                    utc_now(),
                    relative.as_posix(),
                ),
            )
            connection.commit()
        finally:
            for temporary in (raw_temporary, compressed_temporary):
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
    return "completed"


def verify_outputs(
    ledger_path: Path,
    output_root: Path,
    zstd_path: Path = DEFAULT_ZSTD_PATH,
) -> dict[str, int]:
    _regular_directory(output_root, "output root")
    _regular_file_metadata(zstd_path, "Zstandard executable")
    totals = {
        "completed_files": 0,
        "processing_files": 0,
        "input_records": 0,
        "output_records": 0,
    }
    with connect_ledger(ledger_path) as connection:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
            "SELECT * FROM shadow_files ORDER BY source_path"
        ):
            if row["status"] == "processing":
                totals["processing_files"] += 1
                continue
            _verify_completed_row(row, output_root, zstd_path)
            totals["completed_files"] += 1
            totals["input_records"] += row["input_records"]
            totals["output_records"] += row["output_records"]
    return totals


def completed_cursor(ledger_path: Path) -> str | None:
    with connect_ledger(ledger_path) as connection:
        row = connection.execute(
            "SELECT MAX(source_path) FROM shadow_files "
            "WHERE status = 'completed'"
        ).fetchone()
    if row is None or row[0] is None:
        return None
    validate_source_relative_path(Path(row[0]))
    return row[0]


def ledger_totals(ledger_path: Path) -> dict[str, int]:
    with connect_ledger(ledger_path) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed'),
                COUNT(*) FILTER (WHERE status = 'processing'),
                COALESCE(SUM(source_size) FILTER (WHERE status = 'completed'), 0),
                COALESCE(SUM(output_size) FILTER (WHERE status = 'completed'), 0),
                COALESCE(SUM(input_records) FILTER (WHERE status = 'completed'), 0),
                COALESCE(SUM(output_records) FILTER (WHERE status = 'completed'), 0),
                COALESCE(SUM(generic_records) FILTER (WHERE status = 'completed'), 0),
                COALESCE(SUM(enriched_records) FILTER (WHERE status = 'completed'), 0),
                COALESCE(SUM(inventory_hits) FILTER (WHERE status = 'completed'), 0),
                COALESCE(SUM(inventory_misses) FILTER (WHERE status = 'completed'), 0),
                COALESCE(SUM(parser_error_records) FILTER (WHERE status = 'completed'), 0)
            FROM shadow_files
            """
        ).fetchone()
    keys = (
        "ledger_completed_files",
        "ledger_processing_files",
        "ledger_source_bytes",
        "ledger_output_bytes",
        "ledger_input_records",
        "ledger_output_records",
        "ledger_generic_records",
        "ledger_enriched_records",
        "ledger_inventory_hits",
        "ledger_inventory_misses",
        "ledger_parser_error_records",
    )
    return dict(zip(keys, row, strict=True))


def run_cycle(args: argparse.Namespace) -> int:
    started_ns = time.monotonic_ns()
    inventory = load_inventory(args.inventory)
    cursor = completed_cursor(args.ledger)
    files = eligible_source_files(
        args.source_root,
        settle_seconds=args.settle_seconds,
        after_path=cursor,
    )
    selected = files[: args.max_files]
    oldest_age_seconds = 0
    if files:
        oldest_age_seconds = max(
            0,
            (time.time_ns() - files[0].stat().st_mtime_ns) // 1_000_000_000,
        )
    summary = {
        "eligible_unprocessed_files": len(files),
        "selected_files": len(selected),
        "pending_unprocessed_files": max(0, len(files) - len(selected)),
        "oldest_unprocessed_age_seconds": oldest_age_seconds,
        "cycle_completed_files": 0,
        "cycle_skipped_files": 0,
    }
    for source in selected:
        result = process_source_file(
            source,
            source_root=args.source_root,
            output_root=args.output_root,
            ledger_path=args.ledger,
            inventory=inventory,
            zstd_path=args.zstd,
        )
        summary[f"cycle_{result}_files"] += 1
    summary.update(ledger_totals(args.ledger))
    summary["cycle_duration_ms"] = (
        time.monotonic_ns() - started_ns
    ) // 1_000_000
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    print("NORMALIZER_SHADOW_CYCLE=PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Durable collector-side normalizer shadow worker"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("validate-inventory")
    inventory_parser.add_argument(
        "--inventory", type=Path, default=DEFAULT_INVENTORY_PATH
    )

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    run_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    run_parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    run_parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY_PATH)
    run_parser.add_argument("--zstd", type=Path, default=DEFAULT_ZSTD_PATH)
    run_parser.add_argument(
        "--settle-seconds", type=int, default=DEFAULT_SETTLE_SECONDS
    )
    run_parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    verify_parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    verify_parser.add_argument("--zstd", type=Path, default=DEFAULT_ZSTD_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-inventory":
            inventory = load_inventory(args.inventory)
            print(f"platform_entries={len(inventory.platforms)}")
            print("NORMALIZER_PLATFORM_INVENTORY=PASS")
            return 0
        if args.command == "verify":
            totals = verify_outputs(args.ledger, args.output_root, args.zstd)
            print(json.dumps(totals, sort_keys=True, separators=(",", ":")))
            print("NORMALIZER_SHADOW_OUTPUT_VERIFY=PASS")
            return 0
        if args.max_files < 1:
            raise ShadowError("max-files must be at least 1")
        return run_cycle(args)
    except (OSError, ShadowError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
