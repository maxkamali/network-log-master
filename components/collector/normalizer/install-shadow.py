#!/usr/bin/env python3
from __future__ import annotations

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
MANIFEST_PATH = PACKAGE_DIR / "package-manifest.json"
RUNTIME_USER = "network-log-normalizer"
RUNTIME_GROUP = "network-log-normalizer"
SOURCE_GROUP = "vector"
RUNTIME_HOME = Path("/var/lib/network-log-normalizer")
OUTPUT_ROOT = Path("/var/spool/network-log-normalizer-shadow")
SOURCE_ROOT = Path("/var/spool/vector-ai")
CONFIG_ROOT = Path("/etc/network-log-normalizer")
INVENTORY_TARGET = CONFIG_ROOT / "platform-inventory.json"
LIBRARY_ROOT = Path("/usr/local/lib/network-log-normalizer")
SYSTEMD_ROOT = Path("/etc/systemd/system")
TIMER_UNIT = "network-log-normalizer-shadow.timer"
VERSIONS_SOURCE = PACKAGE_DIR / "versions.env"
VERSIONS_TARGET = LIBRARY_ROOT / "versions.env"


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
    validate_regular_file(path, "package manifest")
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallError(f"invalid package manifest: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "artifacts"}:
        raise InstallError("package manifest has unexpected keys")
    if data["schema_version"] != 1 or not isinstance(data["artifacts"], dict):
        raise InstallError("package manifest schema differs")
    output: dict[Path, str] = {}
    for target_text, digest in data["artifacts"].items():
        target = Path(target_text)
        if not target.is_absolute() or ".." in target.parts:
            raise InstallError("package manifest target is unsafe")
        if not isinstance(digest, str) or len(digest) != 64:
            raise InstallError("package manifest digest is invalid")
        output[target] = digest
    if not output:
        raise InstallError("package manifest is empty")
    return output


def source_for_target(target: Path) -> Path:
    package_target = LIBRARY_ROOT / "network_log_normalizer"
    if target.is_relative_to(package_target):
        relative = target.relative_to(package_target)
        return (
            ROOT
            / "components/normalizer/src/network_log_normalizer"
            / relative
        )
    fixed = {
        VERSIONS_TARGET: VERSIONS_SOURCE,
        Path("/usr/local/sbin/network-log-normalizer-shadow"):
            PACKAGE_DIR / "network-log-normalizer-shadow",
        Path("/usr/local/sbin/verify-network-log-normalizer-shadow"):
            PACKAGE_DIR / "verify-shadow.py",
        SYSTEMD_ROOT / "network-log-normalizer-shadow.service":
            PACKAGE_DIR / "systemd/network-log-normalizer-shadow.service",
        SYSTEMD_ROOT / "network-log-normalizer-shadow.timer":
            PACKAGE_DIR / "systemd/network-log-normalizer-shadow.timer",
    }
    try:
        return fixed[target]
    except KeyError as exc:
        raise InstallError(f"unexpected package manifest target: {target}") from exc


def validate_repository_artifacts(manifest: dict[Path, str]) -> None:
    for target, expected in manifest.items():
        source = source_for_target(target)
        validate_regular_file(source, "repository artifact")
        if sha256_file(source) != expected:
            raise InstallError(f"repository artifact hash differs: {source}")


def load_versions(path: Path = VERSIONS_SOURCE) -> dict[str, str]:
    validate_regular_file(path, "dependency version contract")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        if not line or "=" not in line:
            raise InstallError("dependency version contract is invalid")
        key, value = line.split("=", 1)
        if key in values or not key or not value:
            raise InstallError("dependency version contract is invalid")
        values[key] = value
    if set(values) != {"PYTHON3_VERSION", "ZSTD_VERSION"}:
        raise InstallError("dependency version contract keys differ")
    return values


def installed_package_version(package: str) -> str:
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", package],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise InstallError(f"required package is missing: {package}")
    return result.stdout


def verify_dependency_versions() -> None:
    values = load_versions()
    expected = {
        "python3": values["PYTHON3_VERSION"],
        "zstd": values["ZSTD_VERSION"],
    }
    for package, version in expected.items():
        actual = installed_package_version(package)
        if actual != version:
            raise InstallError(
                f"{package} expected={version} actual={actual}"
            )
    for executable in (Path("/usr/bin/python3"), Path("/usr/bin/zstd")):
        if not executable.exists() or not os.access(executable, os.X_OK):
            raise InstallError(f"required executable is missing: {executable}")


def validate_private_inventory_input(path: Path) -> None:
    details = validate_regular_file(path, "private platform inventory input")
    if details.st_size == 0:
        raise InstallError("private platform inventory input is empty")
    if stat.S_IMODE(details.st_mode) not in {0o400, 0o600}:
        raise InstallError("private platform inventory input mode must be 0400 or 0600")


def install_or_verify_file(
    source: Path,
    target: Path,
    *,
    mode: int,
    uid: int,
    gid: int,
) -> None:
    validate_regular_file(source, "installation source")
    target.parent.mkdir(parents=True, exist_ok=True)
    validate_directory(target.parent, "installation target parent")
    if target.exists() or target.is_symlink():
        details = validate_regular_file(target, "existing installation target")
        if source.read_bytes() != target.read_bytes():
            raise InstallError(f"existing installation target differs: {target}")
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


def ensure_runtime_identity() -> tuple[int, int]:
    try:
        source_group = grp.getgrnam(SOURCE_GROUP)
    except KeyError as exc:
        raise InstallError(f"required source group is missing: {SOURCE_GROUP}") from exc
    try:
        runtime_group = grp.getgrnam(RUNTIME_GROUP)
    except KeyError:
        subprocess.run(["groupadd", "--system", RUNTIME_GROUP], check=True)
        runtime_group = grp.getgrnam(RUNTIME_GROUP)
    try:
        runtime_user = pwd.getpwnam(RUNTIME_USER)
    except KeyError:
        subprocess.run(
            [
                "useradd",
                "--system",
                "--gid",
                RUNTIME_GROUP,
                "--groups",
                SOURCE_GROUP,
                "--home-dir",
                str(RUNTIME_HOME),
                "--shell",
                "/usr/sbin/nologin",
                "--no-create-home",
                RUNTIME_USER,
            ],
            check=True,
        )
        runtime_user = pwd.getpwnam(RUNTIME_USER)
    if runtime_user.pw_gid != runtime_group.gr_gid:
        raise InstallError("runtime user has unexpected primary group")
    if runtime_user.pw_dir != str(RUNTIME_HOME):
        raise InstallError("runtime user has unexpected home")
    if Path(runtime_user.pw_shell).name != "nologin":
        raise InstallError("runtime user has unexpected shell")
    group_ids = os.getgrouplist(RUNTIME_USER, runtime_user.pw_gid)
    if set(group_ids) != {runtime_group.gr_gid, source_group.gr_gid}:
        raise InstallError("runtime user has unexpected supplementary groups")
    subprocess.run(["usermod", "--lock", RUNTIME_USER], check=True)
    return runtime_user.pw_uid, runtime_group.gr_gid


def ensure_directory(path: Path, mode: int, uid: int, gid: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    details = validate_directory(path, "runtime directory")
    if any(path.iterdir()):
        if path == OUTPUT_ROOT:
            raise InstallError("initial shadow output root must be empty")
        if path == RUNTIME_HOME:
            raise InstallError("initial shadow state root must be empty")
    if details.st_uid != uid or details.st_gid != gid:
        os.chown(path, uid, gid)
    os.chmod(path, mode)


def require_timer_inactive_disabled() -> None:
    if subprocess.run(
        ["systemctl", "is-active", "--quiet", TIMER_UNIT],
        check=False,
    ).returncode == 0:
        raise InstallError("normalizer shadow timer is unexpectedly active")
    if subprocess.run(
        ["systemctl", "is-enabled", "--quiet", TIMER_UNIT],
        check=False,
    ).returncode == 0:
        raise InstallError("normalizer shadow timer is unexpectedly enabled")


def main() -> int:
    try:
        if os.geteuid() != 0:
            raise InstallError("run this staging installer as root")
        if os.environ.get("NORMALIZER_SHADOW_INSTALL_CONFIRM") != (
            "YES-INSTALL-NORMALIZER-SHADOW"
        ):
            raise InstallError(
                "NORMALIZER_SHADOW_INSTALL_CONFIRM must equal "
                "YES-INSTALL-NORMALIZER-SHADOW"
            )
        inventory_source_text = os.environ.get("PLATFORM_INVENTORY_FILE", "")
        if not inventory_source_text:
            raise InstallError("PLATFORM_INVENTORY_FILE is required")
        inventory_source = Path(inventory_source_text)
        validate_private_inventory_input(inventory_source)
        source_details = validate_directory(SOURCE_ROOT, "Vector source root")
        source_group = grp.getgrnam(SOURCE_GROUP)
        if source_details.st_gid != source_group.gr_gid:
            raise InstallError("Vector source root has unexpected group")
        if stat.S_IMODE(source_details.st_mode) & 0o002:
            raise InstallError("Vector source root must not be world-writable")
        require_timer_inactive_disabled()
        manifest = load_manifest()
        validate_repository_artifacts(manifest)
        verify_dependency_versions()
        runtime_uid, runtime_gid = ensure_runtime_identity()
        ensure_directory(RUNTIME_HOME, 0o750, runtime_uid, runtime_gid)
        ensure_directory(OUTPUT_ROOT, 0o750, runtime_uid, runtime_gid)
        CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
        os.chown(CONFIG_ROOT, 0, runtime_gid)
        os.chmod(CONFIG_ROOT, 0o750)
        install_or_verify_file(
            inventory_source,
            INVENTORY_TARGET,
            mode=0o640,
            uid=0,
            gid=runtime_gid,
        )
        for target, _ in manifest.items():
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
            LIBRARY_ROOT / "package-manifest.json",
            mode=0o644,
            uid=0,
            gid=0,
        )
        subprocess.run(
            [
                "systemd-analyze",
                "verify",
                str(SYSTEMD_ROOT / "network-log-normalizer-shadow.service"),
                str(SYSTEMD_ROOT / TIMER_UNIT),
            ],
            check=True,
        )
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        require_timer_inactive_disabled()
        subprocess.run(
            [
                "/usr/local/sbin/verify-network-log-normalizer-shadow",
                "--mode",
                "staged",
            ],
            check=True,
        )
        print("NORMALIZER_SHADOW_INSTALL=STAGED")
        print("normalizer_shadow_timer=disabled,inactive")
        return 0
    except (
        InstallError,
        KeyError,
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
