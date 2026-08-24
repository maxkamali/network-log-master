#!/usr/bin/env python3
from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys


RUNTIME_USER = "network-log-normalizer"
RUNTIME_GROUP = "network-log-normalizer"
READER_GROUP = "ai_spool_readers"
STATE_ROOT = Path("/var/lib/network-log-normalizer")
HANDOFF_LEDGER = STATE_ROOT / "handoff.sqlite3"
SHADOW_LEDGER = STATE_ROOT / "state.sqlite3"
SHADOW_ROOT = Path("/var/spool/network-log-normalizer-shadow")
HANDOFF_ROOT = Path("/var/spool/network-log-normalizer-handoff")
PLAN_PATH = Path("/etc/network-log-normalizer/handoff-plan.json")
LIBRARY_ROOT = Path("/usr/local/lib/network-log-normalizer")
MANIFEST_PATH = LIBRARY_ROOT / "handoff-package-manifest.json"
MODULE_TARGET = LIBRARY_ROOT / "network_log_normalizer/handoff.py"
LAUNCHER_TARGET = Path("/usr/local/sbin/network-log-normalizer-handoff")
VERIFIER_TARGET = Path(
    "/usr/local/sbin/verify-network-log-normalizer-handoff"
)
SERVICE_TARGET = Path(
    "/etc/systemd/system/network-log-normalizer-handoff.service"
)
TIMER_TARGET = Path(
    "/etc/systemd/system/network-log-normalizer-handoff.timer"
)
SERVICE_UNIT = SERVICE_TARGET.name
TIMER_UNIT = TIMER_TARGET.name
SFTP_VIEW = Path("/srv/ai-spool-reader/spool")

EXPECTED_TARGETS = {
    str(MODULE_TARGET),
    str(LAUNCHER_TARGET),
    str(VERIFIER_TARGET),
    str(SERVICE_TARGET),
    str(TIMER_TARGET),
}

EXPECTED_HANDOFF_ACL = """user::rwx
group::r-x
group:ai_spool_readers:r-x
mask::r-x
other::---
default:user::rwx
default:group::r-x
default:group:ai_spool_readers:r-x
default:mask::r-x
default:other::---"""


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
        raise VerifyError(f"{label} mode differs")
    if uid is not None and details.st_uid != uid:
        raise VerifyError(f"{label} owner differs")
    if gid is not None and details.st_gid != gid:
        raise VerifyError(f"{label} group differs")
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
        raise VerifyError(f"{label} mode differs")
    if uid is not None and details.st_uid != uid:
        raise VerifyError(f"{label} owner differs")
    if gid is not None and details.st_gid != gid:
        raise VerifyError(f"{label} group differs")
    return details


def load_manifest() -> dict[str, str]:
    require_file(MANIFEST_PATH, "handoff package manifest", mode=0o644, uid=0, gid=0)
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"invalid handoff package manifest: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "artifacts"}:
        raise VerifyError("handoff package manifest keys differ")
    if data["schema_version"] != 1 or not isinstance(data["artifacts"], dict):
        raise VerifyError("handoff package manifest schema differs")
    if set(data["artifacts"]) != EXPECTED_TARGETS:
        raise VerifyError("handoff package manifest inventory differs")
    for target, digest in data["artifacts"].items():
        if not isinstance(digest, str) or len(digest) != 64:
            raise VerifyError(f"handoff package digest is invalid: {target}")
    return data["artifacts"]


def verify_artifacts(manifest: dict[str, str]) -> None:
    for target_text, expected in sorted(manifest.items()):
        target = Path(target_text)
        executable = target.parent == Path("/usr/local/sbin")
        require_file(
            target,
            "installed handoff artifact",
            mode=0o755 if executable else 0o644,
            uid=0,
            gid=0,
        )
        if sha256_file(target) != expected:
            raise VerifyError(f"installed handoff artifact hash differs: {target}")


def verify_runtime_paths() -> tuple[int, int]:
    try:
        user = pwd.getpwnam(RUNTIME_USER)
        group = grp.getgrnam(RUNTIME_GROUP)
        grp.getgrnam(READER_GROUP)
    except KeyError as exc:
        raise VerifyError(f"required handoff identity is missing: {exc}") from exc
    if user.pw_gid != group.gr_gid:
        raise VerifyError("handoff runtime primary group differs")
    require_directory(
        HANDOFF_ROOT,
        "handoff root",
        mode=0o750,
        uid=user.pw_uid,
        gid=group.gr_gid,
    )
    require_directory(
        SHADOW_ROOT,
        "shadow root",
        mode=0o750,
        uid=user.pw_uid,
        gid=group.gr_gid,
    )
    require_directory(
        STATE_ROOT,
        "normalizer state root",
        mode=0o750,
        uid=user.pw_uid,
        gid=group.gr_gid,
    )
    require_file(
        PLAN_PATH,
        "handoff plan",
        mode=0o640,
        uid=0,
        gid=group.gr_gid,
    )
    require_file(
        SHADOW_LEDGER,
        "shadow ledger",
        mode=0o640,
        uid=user.pw_uid,
        gid=group.gr_gid,
    )
    require_file(
        HANDOFF_LEDGER,
        "handoff ledger",
        mode=0o640,
        uid=user.pw_uid,
        gid=group.gr_gid,
    )
    acl = subprocess.run(
        [
            "getfacl",
            "--absolute-names",
            "--omit-header",
            str(HANDOFF_ROOT),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    if acl != EXPECTED_HANDOFF_ACL:
        raise VerifyError("handoff root ACL differs")
    return user.pw_uid, group.gr_gid


def unit_state(unit: str) -> tuple[str, str]:
    active = subprocess.run(
        ["systemctl", "is-active", unit],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()
    enabled = subprocess.run(
        ["systemctl", "is-enabled", unit],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()
    return active, enabled


def verify_unit_state(mode: str) -> None:
    subprocess.run(
        ["systemd-analyze", "verify", str(SERVICE_TARGET), str(TIMER_TARGET)],
        check=True,
    )
    service_active, _ = unit_state(SERVICE_UNIT)
    timer_active, timer_enabled = unit_state(TIMER_UNIT)
    if service_active != "inactive":
        raise VerifyError("handoff service must be inactive for stable verification")
    if mode == "staged":
        if timer_active != "inactive" or timer_enabled != "disabled":
            raise VerifyError("staged handoff timer state differs")
    elif timer_active != "inactive" or timer_enabled != "enabled":
        raise VerifyError("prepared handoff timer state differs")


def verify_core_handoff() -> None:
    result = subprocess.run(
        [
            "runuser",
            "-u",
            RUNTIME_USER,
            "--",
            str(LAUNCHER_TARGET),
            "verify",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or "NORMALIZER_HANDOFF_VERIFY=PASS" not in (
        result.stdout
    ):
        raise VerifyError("core handoff verifier failed")


def verify_cutover_mount() -> None:
    result = subprocess.run(
        [
            "findmnt",
            "-rn",
            "-o",
            "FSROOT,OPTIONS",
            "--mountpoint",
            str(SFTP_VIEW),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    fields = result.stdout.strip().split(maxsplit=1)
    if len(fields) != 2 or fields[0] != str(HANDOFF_ROOT):
        raise VerifyError("GX10 SFTP bind source differs from handoff root")
    options = set(fields[1].split(","))
    if not {"ro", "nosuid", "nodev", "noexec"} <= options:
        raise VerifyError("GX10 SFTP handoff bind options differ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independent normalizer handoff runtime verifier"
    )
    parser.add_argument(
        "--mode",
        choices=("staged", "prepared", "cutover"),
        required=True,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if os.geteuid() != 0:
            raise VerifyError("run the handoff verifier as root")
        manifest = load_manifest()
        verify_artifacts(manifest)
        verify_runtime_paths()
        verify_unit_state(args.mode)
        verify_core_handoff()
        if args.mode == "cutover":
            verify_cutover_mount()
        print(f"normalizer_handoff_mode={args.mode}")
        print("NORMALIZER_HANDOFF_RUNTIME_VERIFY=PASS")
        return 0
    except (
        OSError,
        subprocess.CalledProcessError,
        VerifyError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
