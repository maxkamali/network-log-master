#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
CANDIDATE = GX10_DIR / "sbin" / "enrich-events.py"
LEGACY_SHA256 = (
    "6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0"
)
PROJECTION_SHA256 = (
    "f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079"
)
CONFIRMATION = "RETIRE-TRANSITIONAL-PARSER"
TARGET_UID = 0
TARGET_GID = 0
REFERENCE_ROOTS = (
    Path("/etc/systemd/system"),
    Path("/etc/cron.d"),
    Path("/etc/cron.daily"),
    Path("/etc/cron.hourly"),
    Path("/etc/cron.monthly"),
    Path("/etc/cron.weekly"),
)


class RetirementError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular_file(
    path: Path,
    label: str,
    *,
    owner: int | None = None,
    group: int | None = None,
    mode: int | None = None,
) -> os.stat_result:
    if path.is_symlink() or not path.is_file():
        raise RetirementError(f"{label} is not a real regular file")
    details = path.stat()
    if details.st_nlink != 1:
        raise RetirementError(f"{label} must not be hard-linked")
    if owner is not None and details.st_uid != owner:
        raise RetirementError(f"{label} has unexpected owner")
    if group is not None and details.st_gid != group:
        raise RetirementError(f"{label} has unexpected group")
    if mode is not None and stat.S_IMODE(details.st_mode) != mode:
        raise RetirementError(f"{label} has unexpected mode")
    return details


def require_protected_parent(path: Path) -> None:
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise RetirementError("backup parent is not a real directory")
    details = parent.stat()
    if details.st_uid != TARGET_UID or stat.S_IMODE(details.st_mode) & 0o077:
        raise RetirementError("backup parent is not root-only")


def reference_count(target: Path) -> int:
    needle = str(target)
    matches = 0
    for root in REFERENCE_ROOTS:
        if not root.is_dir() or root.is_symlink():
            continue
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                matches += needle in path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    return matches


def write_backup(source: Path, backup: Path) -> None:
    require_protected_parent(backup)
    if backup.exists() or backup.is_symlink():
        raise RetirementError("protected rollback file already exists")
    descriptor = os.open(
        backup,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    try:
        with source.open("rb") as input_handle, os.fdopen(
            descriptor, "wb"
        ) as output_handle:
            for chunk in iter(
                lambda: input_handle.read(1024 * 1024),
                b"",
            ):
                output_handle.write(chunk)
            output_handle.flush()
            os.fsync(output_handle.fileno())
    except Exception:
        try:
            backup.unlink()
        except OSError:
            pass
        raise
    os.chown(backup, TARGET_UID, TARGET_GID)
    os.chmod(backup, 0o600)
    fsync_directory(backup.parent)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_replace(target: Path, data: bytes, details: os.stat_result) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.retirement.",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary, details.st_uid, details.st_gid)
        os.chmod(temporary, stat.S_IMODE(details.st_mode))
        os.replace(temporary, target)
        fsync_directory(target.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_candidate() -> bytes:
    require_regular_file(CANDIDATE, "repository projection candidate")
    if sha256_file(CANDIDATE) != PROJECTION_SHA256:
        raise RetirementError("repository projection candidate hash differs")
    return CANDIDATE.read_bytes()


def validate_retired_state(target: Path, backup: Path) -> None:
    require_regular_file(
        target,
        "installed projection",
        owner=TARGET_UID,
        group=TARGET_GID,
        mode=0o755,
    )
    require_regular_file(
        backup,
        "protected rollback file",
        owner=TARGET_UID,
        group=TARGET_GID,
        mode=0o600,
    )
    if sha256_file(target) != PROJECTION_SHA256:
        raise RetirementError("installed projection hash differs")
    if sha256_file(backup) != LEGACY_SHA256:
        raise RetirementError("protected rollback hash differs")
    if reference_count(target) != 0:
        raise RetirementError("installed projection unexpectedly has a scheduler reference")


def apply_retirement(target: Path, backup: Path) -> None:
    candidate = validate_candidate()
    details = require_regular_file(
        target,
        "installed transitional enrichment",
        owner=TARGET_UID,
        group=TARGET_GID,
        mode=0o755,
    )
    if sha256_file(target) != LEGACY_SHA256:
        raise RetirementError("installed transitional enrichment hash differs")
    if reference_count(target) != 0:
        raise RetirementError("transitional enrichment has a scheduler reference")
    write_backup(target, backup)
    atomic_replace(target, candidate, details)
    try:
        validate_retired_state(target, backup)
    except Exception:
        atomic_replace(target, backup.read_bytes(), details)
        raise


def rollback_retirement(target: Path, backup: Path) -> None:
    validate_candidate()
    details = require_regular_file(
        target,
        "installed projection",
        owner=TARGET_UID,
        group=TARGET_GID,
        mode=0o755,
    )
    require_regular_file(
        backup,
        "protected rollback file",
        owner=TARGET_UID,
        group=TARGET_GID,
        mode=0o600,
    )
    if sha256_file(target) != PROJECTION_SHA256:
        raise RetirementError("installed projection hash differs")
    if sha256_file(backup) != LEGACY_SHA256:
        raise RetirementError("protected rollback hash differs")
    if reference_count(target) != 0:
        raise RetirementError("installed projection unexpectedly has a scheduler reference")
    atomic_replace(target, backup.read_bytes(), details)
    if sha256_file(target) != LEGACY_SHA256:
        raise RetirementError("transitional-enrichment rollback failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guarded GX10 transitional-enrichment retirement"
    )
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--apply", action="store_true")
    action.add_argument("--verify", action="store_true")
    action.add_argument("--rollback", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise RetirementError("run the retirement guard as root")
        if os.environ.get("GX10_RETIRE_CONFIRM") != CONFIRMATION:
            raise RetirementError("retirement confirmation is absent")
        target = args.target.resolve(strict=True)
        backup = args.backup
        if args.apply:
            apply_retirement(target, backup)
            action = "applied"
        elif args.rollback:
            rollback_retirement(target, backup)
            action = "rolled_back"
        else:
            validate_candidate()
            validate_retired_state(target, backup)
            action = "verified"
        print(f"gx10_transitional_enrichment_retirement={action}")
        print("GX10_TRANSITIONAL_ENRICHMENT_RETIREMENT=PASS")
        return 0
    except (OSError, RetirementError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
