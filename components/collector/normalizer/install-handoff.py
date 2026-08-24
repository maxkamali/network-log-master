#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = Path(__file__).resolve().parent
NORMALIZER_SOURCE = ROOT / "components/normalizer/src"
sys.path.insert(0, str(NORMALIZER_SOURCE))

from network_log_normalizer.handoff import load_handoff_plan


MANIFEST_PATH = PACKAGE_DIR / "handoff-package-manifest.json"
RUNTIME_USER = "network-log-normalizer"
RUNTIME_GROUP = "network-log-normalizer"
READER_GROUP = "ai_spool_readers"
STATE_ROOT = Path("/var/lib/network-log-normalizer")
SHADOW_ROOT = Path("/var/spool/network-log-normalizer-shadow")
HANDOFF_ROOT = Path("/var/spool/network-log-normalizer-handoff")
CONFIG_ROOT = Path("/etc/network-log-normalizer")
PLAN_TARGET = CONFIG_ROOT / "handoff-plan.json"
LIBRARY_ROOT = Path("/usr/local/lib/network-log-normalizer")
MODULE_TARGET = (
    LIBRARY_ROOT / "network_log_normalizer/handoff.py"
)
SYSTEMD_ROOT = Path("/etc/systemd/system")
LAUNCHER_TARGET = Path("/usr/local/sbin/network-log-normalizer-handoff")
VERIFIER_TARGET = Path(
    "/usr/local/sbin/verify-network-log-normalizer-handoff"
)
SERVICE_TARGET = SYSTEMD_ROOT / "network-log-normalizer-handoff.service"
TIMER_TARGET = SYSTEMD_ROOT / "network-log-normalizer-handoff.timer"
TIMER_UNIT = TIMER_TARGET.name
MINIMUM_FUTURE_SECONDS = 600

EXPECTED_TARGETS = {
    MODULE_TARGET,
    LAUNCHER_TARGET,
    VERIFIER_TARGET,
    SERVICE_TARGET,
    TIMER_TARGET,
}


class InstallError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_regular_file(path: Path, label: str) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise InstallError(f"cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise InstallError(f"{label} is not a regular nonsymlink file")
    if details.st_nlink != 1:
        raise InstallError(f"{label} must not be hard-linked")
    return details


def validate_directory(path: Path, label: str) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise InstallError(f"cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise InstallError(f"{label} is not a regular nonsymlink directory")
    return details


def load_manifest(path: Path = MANIFEST_PATH) -> dict[Path, str]:
    validate_regular_file(path, "handoff package manifest")
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallError(f"invalid handoff package manifest: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "artifacts"}:
        raise InstallError("handoff package manifest has unexpected keys")
    if data["schema_version"] != 1 or not isinstance(data["artifacts"], dict):
        raise InstallError("handoff package manifest schema differs")
    output: dict[Path, str] = {}
    for target_text, digest in data["artifacts"].items():
        target = Path(target_text)
        if not target.is_absolute() or ".." in target.parts:
            raise InstallError("handoff package manifest target is unsafe")
        if not isinstance(digest, str) or len(digest) != 64:
            raise InstallError("handoff package manifest digest is invalid")
        output[target] = digest
    if set(output) != EXPECTED_TARGETS:
        raise InstallError("handoff package manifest inventory differs")
    return output


def source_for_target(target: Path) -> Path:
    mapping = {
        MODULE_TARGET: (
            NORMALIZER_SOURCE / "network_log_normalizer/handoff.py"
        ),
        LAUNCHER_TARGET: PACKAGE_DIR / "network-log-normalizer-handoff",
        VERIFIER_TARGET: PACKAGE_DIR / "verify-handoff.py",
        SERVICE_TARGET: (
            PACKAGE_DIR / "systemd/network-log-normalizer-handoff.service"
        ),
        TIMER_TARGET: (
            PACKAGE_DIR / "systemd/network-log-normalizer-handoff.timer"
        ),
    }
    try:
        return mapping[target]
    except KeyError as exc:
        raise InstallError(f"unexpected handoff package target: {target}") from exc


def validate_repository_artifacts(manifest: dict[Path, str]) -> None:
    for target, expected in manifest.items():
        source = source_for_target(target)
        validate_regular_file(source, "handoff repository artifact")
        if sha256_file(source) != expected:
            raise InstallError(
                f"handoff repository artifact hash differs: {source}"
            )


def validate_private_plan_input(path: Path) -> None:
    details = validate_regular_file(path, "private handoff plan input")
    if details.st_size == 0:
        raise InstallError("private handoff plan input is empty")
    if stat.S_IMODE(details.st_mode) not in {0o400, 0o600}:
        raise InstallError(
            "private handoff plan input mode must be 0400 or 0600"
        )


def plan_floor_datetime(source_path: str) -> datetime:
    relative = Path(source_path)
    parts = relative.parts
    if len(parts) != 5:
        raise InstallError("handoff plan path partition depth differs")
    stem = relative.name.removeprefix("syslog-").removesuffix(
        ".jsonl.zst"
    )
    try:
        value = datetime.strptime(stem, "%Y%m%d-%H%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise InstallError("handoff plan floor time is invalid") from exc
    expected = value.strftime("%Y/%m/%d/%H/syslog-%Y%m%d-%H%M.jsonl.zst")
    if relative.as_posix() != expected:
        raise InstallError("handoff plan path/time differs")
    return value


def require_future_plan(path: Path) -> None:
    try:
        plan = load_handoff_plan(path, secure=False)
    except ValueError as exc:
        raise InstallError(str(exc)) from exc
    floor = plan_floor_datetime(plan.first_normalized_source_path)
    minimum = datetime.now(timezone.utc) + timedelta(
        seconds=MINIMUM_FUTURE_SECONDS
    )
    if floor < minimum:
        raise InstallError(
            "handoff plan floor must be at least 10 minutes in the future"
        )


def install_or_verify_file(
    source: Path,
    target: Path,
    *,
    mode: int,
    uid: int,
    gid: int,
) -> None:
    validate_regular_file(source, "handoff installation source")
    target.parent.mkdir(parents=True, exist_ok=True)
    validate_directory(target.parent, "handoff installation target parent")
    if target.exists() or target.is_symlink():
        details = validate_regular_file(
            target,
            "existing handoff installation target",
        )
        if source.read_bytes() != target.read_bytes():
            raise InstallError(
                f"existing handoff installation target differs: {target}"
            )
        if details.st_uid != uid or details.st_gid != gid:
            os.chown(target, uid, gid)
        os.chmod(target, mode)
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
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
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.link(temporary, target, follow_symlinks=False)
        temporary.unlink()
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def runtime_identity() -> tuple[int, int]:
    try:
        user = pwd.getpwnam(RUNTIME_USER)
        group = grp.getgrnam(RUNTIME_GROUP)
        grp.getgrnam(READER_GROUP)
    except KeyError as exc:
        raise InstallError(f"required runtime identity is missing: {exc}") from exc
    if user.pw_gid != group.gr_gid:
        raise InstallError("normalizer runtime primary group differs")
    if user.pw_dir != str(STATE_ROOT):
        raise InstallError("normalizer runtime home differs")
    if Path(user.pw_shell).name != "nologin":
        raise InstallError("normalizer runtime shell differs")
    return user.pw_uid, group.gr_gid


def require_existing_shadow_runtime(uid: int, gid: int) -> None:
    for path, label, mode in (
        (STATE_ROOT, "normalizer state root", 0o750),
        (SHADOW_ROOT, "normalizer shadow root", 0o750),
        (CONFIG_ROOT, "normalizer configuration root", 0o750),
        (LIBRARY_ROOT, "normalizer library root", None),
    ):
        details = validate_directory(path, label)
        if mode is not None and stat.S_IMODE(details.st_mode) != mode:
            raise InstallError(f"{label} mode differs")
        expected_uid = 0 if path in {CONFIG_ROOT, LIBRARY_ROOT} else uid
        expected_gid = 0 if path == LIBRARY_ROOT else gid
        if details.st_uid != expected_uid or details.st_gid != expected_gid:
            raise InstallError(f"{label} owner/group differs")
    subprocess.run(
        [
            "/usr/local/sbin/verify-network-log-normalizer-shadow",
            "--mode",
            "active",
        ],
        check=True,
    )


def require_handoff_timer_inactive_disabled() -> None:
    if subprocess.run(
        ["systemctl", "is-active", "--quiet", TIMER_UNIT],
        check=False,
    ).returncode == 0:
        raise InstallError("normalizer handoff timer is unexpectedly active")
    if subprocess.run(
        ["systemctl", "is-enabled", "--quiet", TIMER_UNIT],
        check=False,
    ).returncode == 0:
        raise InstallError("normalizer handoff timer is unexpectedly enabled")


def ensure_handoff_root(uid: int, gid: int) -> None:
    if HANDOFF_ROOT.exists() or HANDOFF_ROOT.is_symlink():
        details = validate_directory(HANDOFF_ROOT, "handoff root")
        if any(HANDOFF_ROOT.iterdir()):
            raise InstallError("initial handoff root must be empty")
    else:
        HANDOFF_ROOT.mkdir(mode=0o750)
        details = HANDOFF_ROOT.stat()
    if details.st_uid != uid or details.st_gid != gid:
        os.chown(HANDOFF_ROOT, uid, gid)
    os.chmod(HANDOFF_ROOT, 0o750)
    subprocess.run(["setfacl", "-b", str(HANDOFF_ROOT)], check=True)
    subprocess.run(["setfacl", "-k", str(HANDOFF_ROOT)], check=False)
    subprocess.run(
        [
            "setfacl",
            "-m",
            "u::rwx,g::r-x,g:ai_spool_readers:r-x,m::r-x,o::---",
            str(HANDOFF_ROOT),
        ],
        check=True,
    )
    subprocess.run(
        [
            "setfacl",
            "-m",
            "d:u::rwx,d:g::r-x,d:g:ai_spool_readers:r-x,d:m::r-x,d:o::---",
            str(HANDOFF_ROOT),
        ],
        check=True,
    )


def main() -> int:
    try:
        if os.geteuid() != 0:
            raise InstallError("run this handoff staging installer as root")
        if os.environ.get("NORMALIZER_HANDOFF_INSTALL_CONFIRM") != (
            "YES-STAGE-NORMALIZER-HANDOFF"
        ):
            raise InstallError(
                "NORMALIZER_HANDOFF_INSTALL_CONFIRM must equal "
                "YES-STAGE-NORMALIZER-HANDOFF"
            )
        plan_source_text = os.environ.get("HANDOFF_PLAN_FILE", "")
        if not plan_source_text:
            raise InstallError("HANDOFF_PLAN_FILE is required")
        plan_source = Path(plan_source_text)
        validate_private_plan_input(plan_source)
        require_future_plan(plan_source)
        require_handoff_timer_inactive_disabled()
        manifest = load_manifest()
        validate_repository_artifacts(manifest)
        uid, gid = runtime_identity()
        require_existing_shadow_runtime(uid, gid)
        require_handoff_timer_inactive_disabled()
        ensure_handoff_root(uid, gid)
        install_or_verify_file(
            plan_source,
            PLAN_TARGET,
            mode=0o640,
            uid=0,
            gid=gid,
        )
        for target in sorted(manifest, key=lambda value: value.as_posix()):
            source = source_for_target(target)
            executable = target.parent == Path("/usr/local/sbin")
            install_or_verify_file(
                source,
                target,
                mode=0o755 if executable else 0o644,
                uid=0,
                gid=0,
            )
        install_or_verify_file(
            MANIFEST_PATH,
            LIBRARY_ROOT / MANIFEST_PATH.name,
            mode=0o644,
            uid=0,
            gid=0,
        )
        subprocess.run(
            [
                "systemd-analyze",
                "verify",
                str(SERVICE_TARGET),
                str(TIMER_TARGET),
            ],
            check=True,
        )
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        require_handoff_timer_inactive_disabled()
        subprocess.run(
            [
                "runuser",
                "-u",
                RUNTIME_USER,
                "--",
                str(LAUNCHER_TARGET),
                "verify",
            ],
            check=True,
        )
        subprocess.run(
            [str(VERIFIER_TARGET), "--mode", "staged"],
            check=True,
        )
        print("NORMALIZER_HANDOFF_INSTALL=STAGED")
        print("normalizer_handoff_timer=disabled,inactive")
        return 0
    except (
        InstallError,
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
