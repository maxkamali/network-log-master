#!/usr/bin/env python3
from __future__ import annotations

import argparse
import grp
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import sqlite3
import stat
import subprocess
import sys
import time


RUNTIME_USER = "network-log-normalizer"
RUNTIME_GROUP = "network-log-normalizer"
SOURCE_GROUP = "vector"
SOURCE_ROOT = Path("/var/spool/vector-ai")
OUTPUT_ROOT = Path("/var/spool/network-log-normalizer-shadow")
STATE_ROOT = Path("/var/lib/network-log-normalizer")
LEDGER_PATH = STATE_ROOT / "state.sqlite3"
CONFIG_ROOT = Path("/etc/network-log-normalizer")
INVENTORY_PATH = CONFIG_ROOT / "platform-inventory.json"
LIBRARY_ROOT = Path("/usr/local/lib/network-log-normalizer")
MANIFEST_PATH = LIBRARY_ROOT / "package-manifest.json"
ZSTD_PATH = Path("/usr/bin/zstd")
TIMER_UNIT = "network-log-normalizer-shadow.timer"
MAX_OUTPUT_LINE_BYTES = 4 * 1024 * 1024
ACTIVE_VERIFY_TIMEOUT_SECONDS = 120
ACTIVE_VERIFY_POLL_SECONDS = 0.1

PACKAGE_FILES = {
    "__init__.py",
    "envelope.py",
    "normalizer.py",
    "parsers/__init__.py",
    "parsers/base.py",
    "parsers/dispatcher.py",
    "parsers/eos_bgp.py",
    "parsers/iosxr_bgp.py",
    "parsers/nxos_ethport.py",
    "parsers/nxos_ospf.py",
    "platform.py",
    "rules/__init__.py",
    "schema.py",
    "shadow.py",
}

EXPECTED_TARGETS = {
    str(LIBRARY_ROOT / "network_log_normalizer" / relative)
    for relative in PACKAGE_FILES
} | {
    "/usr/local/lib/network-log-normalizer/versions.env",
    "/usr/local/sbin/network-log-normalizer-shadow",
    "/usr/local/sbin/verify-network-log-normalizer-shadow",
    "/etc/systemd/system/network-log-normalizer-shadow.service",
    "/etc/systemd/system/network-log-normalizer-shadow.timer",
}

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

SUPPORTED_PLATFORMS = {
    ("arista", "eos"),
    ("cisco", "iosxr"),
    ("cisco", "nxos"),
}


class VerifyError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_file(
    path: Path,
    label: str,
    *,
    mode: int | None = None,
    uid: int | None = None,
    gid: int | None = None,
) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise VerifyError(f"cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise VerifyError(f"{label} is not a regular nonsymlink file")
    if details.st_nlink != 1:
        raise VerifyError(f"{label} must not be hard-linked")
    if mode is not None and stat.S_IMODE(details.st_mode) != mode:
        raise VerifyError(f"{label} has unexpected mode")
    if uid is not None and details.st_uid != uid:
        raise VerifyError(f"{label} has unexpected owner")
    if gid is not None and details.st_gid != gid:
        raise VerifyError(f"{label} has unexpected group")
    return details


def require_directory(
    path: Path,
    label: str,
    *,
    mode: int | None = None,
    uid: int | None = None,
    gid: int | None = None,
) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise VerifyError(f"cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise VerifyError(f"{label} is not a regular nonsymlink directory")
    if mode is not None and stat.S_IMODE(details.st_mode) != mode:
        raise VerifyError(f"{label} has unexpected mode")
    if uid is not None and details.st_uid != uid:
        raise VerifyError(f"{label} has unexpected owner")
    if gid is not None and details.st_gid != gid:
        raise VerifyError(f"{label} has unexpected group")
    return details


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, str]:
    require_file(path, "installed package manifest", mode=0o644, uid=0, gid=0)
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"invalid installed package manifest: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "artifacts"}:
        raise VerifyError("installed package manifest has unexpected keys")
    if data["schema_version"] != 1 or not isinstance(data["artifacts"], dict):
        raise VerifyError("installed package manifest schema differs")
    if set(data["artifacts"]) != EXPECTED_TARGETS:
        raise VerifyError("installed package manifest inventory differs")
    for target, digest in data["artifacts"].items():
        if not isinstance(digest, str) or len(digest) != 64:
            raise VerifyError(f"invalid manifest digest: {target}")
    return data["artifacts"]


def verify_artifacts(manifest: dict[str, str]) -> None:
    for target_text, expected in sorted(manifest.items()):
        target = Path(target_text)
        executable = target.parent == Path("/usr/local/sbin")
        require_file(
            target,
            "installed artifact",
            mode=0o755 if executable else 0o644,
            uid=0,
            gid=0,
        )
        if sha256_file(target) != expected:
            raise VerifyError(f"installed artifact hash differs: {target}")


def verify_dependency_versions() -> None:
    path = LIBRARY_ROOT / "versions.env"
    require_file(path, "installed dependency version contract", mode=0o644, uid=0, gid=0)
    values = {}
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        if not line or "=" not in line:
            raise VerifyError("dependency version contract is invalid")
        key, value = line.split("=", 1)
        if key in values or not key or not value:
            raise VerifyError("dependency version contract is invalid")
        values[key] = value
    if set(values) != {"PYTHON3_VERSION", "ZSTD_VERSION"}:
        raise VerifyError("dependency version contract keys differ")
    expected = {
        "python3": values["PYTHON3_VERSION"],
        "zstd": values["ZSTD_VERSION"],
    }
    for package, version in expected.items():
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Version}", package],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout != version:
            raise VerifyError(f"installed dependency version differs: {package}")
    for executable in (Path("/usr/bin/python3"), ZSTD_PATH):
        if not executable.exists() or not os.access(executable, os.X_OK):
            raise VerifyError(f"required executable is missing: {executable}")


def verify_identity_and_paths() -> tuple[int, int]:
    try:
        runtime_user = pwd.getpwnam(RUNTIME_USER)
        runtime_group = grp.getgrnam(RUNTIME_GROUP)
        source_group = grp.getgrnam(SOURCE_GROUP)
    except KeyError as exc:
        raise VerifyError(f"runtime identity is missing: {exc}") from exc
    if runtime_user.pw_gid != runtime_group.gr_gid:
        raise VerifyError("runtime primary group differs")
    if runtime_user.pw_dir != str(STATE_ROOT):
        raise VerifyError("runtime home differs")
    if Path(runtime_user.pw_shell).name != "nologin":
        raise VerifyError("runtime shell differs")
    if set(os.getgrouplist(RUNTIME_USER, runtime_user.pw_gid)) != {
        runtime_group.gr_gid,
        source_group.gr_gid,
    }:
        raise VerifyError("runtime supplementary groups differ")
    source_details = require_directory(SOURCE_ROOT, "source root")
    if source_details.st_gid != source_group.gr_gid:
        raise VerifyError("source root group differs")
    if stat.S_IMODE(source_details.st_mode) & 0o002:
        raise VerifyError("source root is world-writable")
    require_directory(
        OUTPUT_ROOT,
        "output root",
        mode=0o750,
        uid=runtime_user.pw_uid,
        gid=runtime_group.gr_gid,
    )
    require_directory(
        STATE_ROOT,
        "state root",
        mode=0o750,
        uid=runtime_user.pw_uid,
        gid=runtime_group.gr_gid,
    )
    require_directory(
        CONFIG_ROOT,
        "configuration root",
        mode=0o750,
        uid=0,
        gid=runtime_group.gr_gid,
    )
    return runtime_user.pw_uid, runtime_group.gr_gid


def _reject_duplicate_pairs(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise VerifyError(f"duplicate inventory key: {key}")
        output[key] = value
    return output


def verify_inventory(runtime_gid: int) -> int:
    details = require_file(
        INVENTORY_PATH,
        "platform inventory",
        mode=0o640,
        uid=0,
        gid=runtime_gid,
    )
    if details.st_size > 1024 * 1024:
        raise VerifyError("platform inventory exceeds size limit")
    try:
        data = json.loads(
            INVENTORY_PATH.read_text(encoding="utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"invalid platform inventory: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "platforms"}:
        raise VerifyError("platform inventory keys differ")
    if data["schema_version"] != 1 or not isinstance(data["platforms"], dict):
        raise VerifyError("platform inventory schema differs")
    for source_ip, entry in data["platforms"].items():
        try:
            canonical = str(ipaddress.ip_address(source_ip))
        except ValueError as exc:
            raise VerifyError("platform inventory contains invalid identity") from exc
        if canonical != source_ip:
            raise VerifyError("platform inventory identity is not canonical")
        if not isinstance(entry, dict) or set(entry) != {
            "vendor_hint",
            "os_family_hint",
        }:
            raise VerifyError("platform inventory entry keys differ")
        if (entry["vendor_hint"], entry["os_family_hint"]) not in (
            SUPPORTED_PLATFORMS
        ):
            raise VerifyError("platform inventory contains unsupported platform")
    return len(data["platforms"])


def zstd_test(path: Path) -> None:
    result = subprocess.run(
        [str(ZSTD_PATH), "-q", "-t", "--", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise VerifyError("output Zstandard integrity check failed")


def count_output_records(path: Path) -> int:
    process = subprocess.Popen(
        [str(ZSTD_PATH), "-q", "-dc", "--", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    count = 0
    try:
        while True:
            line = process.stdout.readline(MAX_OUTPUT_LINE_BYTES + 2)
            if line == b"":
                break
            if len(line) > MAX_OUTPUT_LINE_BYTES + 1:
                raise VerifyError("normalized output line exceeds size limit")
            if len(line) == MAX_OUTPUT_LINE_BYTES + 1 and not line.endswith(b"\n"):
                raise VerifyError("normalized output line exceeds size limit")
            try:
                record = json.loads(line.decode("utf-8", errors="strict"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise VerifyError("normalized output JSON differs") from exc
            if not isinstance(record, dict) or record.get("schema_version") != 1:
                raise VerifyError("normalized output schema differs")
            if not isinstance(record.get("timestamp"), str):
                raise VerifyError("normalized output timestamp differs")
            if not isinstance(record.get("message"), str):
                raise VerifyError("normalized output message differs")
            count += 1
        if process.wait(timeout=300) != 0:
            raise VerifyError("normalized output decode failed")
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()
        assert process.stderr is not None
        process.stderr.close()
    return count


def _read_ledger_rows(runtime_uid: int, runtime_gid: int) -> list[sqlite3.Row]:
    if not LEDGER_PATH.exists() and not LEDGER_PATH.is_symlink():
        if any(OUTPUT_ROOT.iterdir()):
            raise VerifyError("output exists without ledger")
        return []
    require_file(
        LEDGER_PATH,
        "ledger",
        mode=0o640,
        uid=runtime_uid,
        gid=runtime_gid,
    )
    connection = sqlite3.connect(f"file:{LEDGER_PATH}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise VerifyError("ledger integrity check failed")
        if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise VerifyError("ledger schema version differs")
        columns = tuple(
            row[1]
            for row in connection.execute("PRAGMA table_info(shadow_files)")
        )
        if columns != LEDGER_COLUMNS:
            raise VerifyError("ledger columns differ")
        rows = connection.execute(
            "SELECT * FROM shadow_files ORDER BY source_path"
        ).fetchall()
    finally:
        connection.close()
    return rows


def _row_output(row: sqlite3.Row) -> Path:
    relative = Path(row["output_path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise VerifyError("ledger output path is unsafe")
    return OUTPUT_ROOT / relative


def _row_fingerprint(row: sqlite3.Row) -> tuple[object, ...]:
    return tuple(row[column] for column in LEDGER_COLUMNS)


def _verify_completed_output(
    row: sqlite3.Row,
    output: Path,
    runtime_uid: int,
    runtime_gid: int,
) -> int:
    details = require_file(
        output,
        "normalized output",
        mode=0o640,
        uid=runtime_uid,
        gid=runtime_gid,
    )
    if details.st_size != row["output_size"]:
        raise VerifyError("normalized output size differs")
    if sha256_file(output) != row["output_sha256"]:
        raise VerifyError("normalized output hash differs")
    zstd_test(output)
    actual_records = count_output_records(output)
    if actual_records != row["output_records"]:
        raise VerifyError("normalized output record count differs")
    if row["input_records"] != row["output_records"]:
        raise VerifyError("ledger cardinality differs")
    return actual_records


def verify_ledger_and_outputs(
    runtime_uid: int,
    runtime_gid: int,
    *,
    allow_concurrent: bool = False,
) -> dict[str, int]:
    deadline = time.monotonic() + ACTIVE_VERIFY_TIMEOUT_SECONDS
    verified_rows: dict[str, tuple[object, ...]] = {}

    while True:
        rows = _read_ledger_rows(runtime_uid, runtime_gid)
        current_rows = {row["source_path"]: row for row in rows}
        if set(verified_rows) - set(current_rows):
            raise VerifyError("verified ledger row disappeared")

        expected_outputs: set[Path] = set()
        processing_outputs: set[Path] = set()
        completed = 0
        records = 0

        for source_path, row in current_rows.items():
            fingerprint = _row_fingerprint(row)
            previous = verified_rows.get(source_path)
            if previous is not None and previous != fingerprint:
                raise VerifyError("verified ledger row changed")

            output = _row_output(row)
            if row["status"] == "processing":
                processing_outputs.add(output)
                continue
            if row["status"] != "completed":
                raise VerifyError("ledger contains invalid source status")

            expected_outputs.add(output)
            completed += 1
            records += row["output_records"]
            if previous is None:
                _verify_completed_output(
                    row,
                    output,
                    runtime_uid,
                    runtime_gid,
                )
                verified_rows[source_path] = fingerprint

        actual_outputs = {
            path
            for path in OUTPUT_ROOT.rglob("*.normalized.jsonl.zst")
            if path.is_file() and not path.is_symlink()
        }
        if expected_outputs - actual_outputs:
            raise VerifyError("completed output is missing from inventory")
        unexpected_outputs = actual_outputs - expected_outputs
        if unexpected_outputs - processing_outputs:
            if allow_concurrent:
                refreshed_rows = _read_ledger_rows(runtime_uid, runtime_gid)
                refreshed = {
                    row["source_path"]: _row_fingerprint(row)
                    for row in refreshed_rows
                }
                current = {
                    source_path: _row_fingerprint(row)
                    for source_path, row in current_rows.items()
                }
                if refreshed != current:
                    continue
            raise VerifyError("orphan output differs from ledger")

        if (
            not processing_outputs
            and not unexpected_outputs
            and len(verified_rows) == completed
        ):
            return {"completed_files": completed, "records": records}

        if not allow_concurrent:
            if processing_outputs:
                raise VerifyError("ledger contains incomplete source file")
            raise VerifyError("output inventory differs from ledger")
        if time.monotonic() >= deadline:
            raise VerifyError("active output inventory did not stabilize")
        time.sleep(ACTIVE_VERIFY_POLL_SECONDS)


def verify_unit_state(mode: str) -> None:
    enabled = subprocess.run(
        ["systemctl", "is-enabled", "--quiet", TIMER_UNIT],
        check=False,
    ).returncode == 0
    active = subprocess.run(
        ["systemctl", "is-active", "--quiet", TIMER_UNIT],
        check=False,
    ).returncode == 0
    if mode == "staged" and (enabled or active):
        raise VerifyError("staged shadow timer must be disabled and inactive")
    if mode == "active" and not (enabled and active):
        raise VerifyError("active shadow timer must be enabled and active")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independent normalizer shadow runtime verifier"
    )
    parser.add_argument("--mode", choices=("staged", "active"), required=True)
    args = parser.parse_args(argv)
    try:
        if os.geteuid() != 0:
            raise VerifyError("run this verifier as root")
        require_file(ZSTD_PATH, "Zstandard executable")
        manifest = load_manifest()
        verify_artifacts(manifest)
        verify_dependency_versions()
        runtime_uid, runtime_gid = verify_identity_and_paths()
        inventory_entries = verify_inventory(runtime_gid)
        totals = verify_ledger_and_outputs(
            runtime_uid,
            runtime_gid,
            allow_concurrent=args.mode == "active",
        )
        verify_unit_state(args.mode)
        print(f"platform_entries={inventory_entries}")
        print(f"completed_files={totals['completed_files']}")
        print(f"normalized_records={totals['records']}")
        print(f"normalizer_shadow_mode={args.mode}")
        print("NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS")
        return 0
    except (
        KeyError,
        OSError,
        sqlite3.Error,
        subprocess.SubprocessError,
        VerifyError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
