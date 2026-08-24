#!/usr/bin/env python3
from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
LIBEXEC_DIR = Path('/usr/local/libexec/network-log-gx10')
CONFIG_DIR = Path('/etc/network-log-gx10')
CONFIG_PATH = CONFIG_DIR / 'managed-reasoning.json'
SYSTEMD_DIR = Path('/etc/systemd/system')
SERVICE = 'network-log-gx10-reasoning.service'
TIMER = 'network-log-gx10-reasoning.timer'
DROPIN_DIR = SYSTEMD_DIR / f'{SERVICE}.d'
DROPIN_PATH = DROPIN_DIR / '10-runtime.conf'
CONFIRMATION = 'INSTALL-UNSCHEDULED-MANAGED-REASONING'
SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_.@-]+$')
SAFE_PATH_RE = re.compile(r'^/[A-Za-z0-9_./@+-]+$')
ARTIFACTS = (
    (
        GX10_DIR / 'config' / 'reasoning-runtime-v2.json',
        CONFIG_DIR / 'reasoning-runtime-v2.json',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'incident-assessment-output-v2.json',
        CONFIG_DIR / 'incident-assessment-output-v2.json',
        0o644,
    ),
    (
        GX10_DIR / 'sbin' / 'run-local-reasoning.py',
        LIBEXEC_DIR / 'run-local-reasoning.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-managed-reasoning.py',
        LIBEXEC_DIR / 'run-managed-reasoning.py',
        0o755,
    ),
    (
        GX10_DIR / 'systemd' / SERVICE,
        SYSTEMD_DIR / SERVICE,
        0o644,
    ),
    (
        GX10_DIR / 'systemd' / TIMER,
        SYSTEMD_DIR / TIMER,
        0o644,
    ),
)
DEPENDENCIES = (
    (
        GX10_DIR / 'sbin' / 'build-reasoning-packets.py',
        LIBEXEC_DIR / 'build-reasoning-packets.py',
        0o755,
    ),
    (
        GX10_DIR / 'prompts' / 'incident-assessment-v2.txt',
        CONFIG_DIR / 'incident-assessment-v2.txt',
        0o644,
    ),
)
REQUIRED_TABLES = {
    'recent_events',
    'agent_state',
    'incidents',
    'incident_evidence',
    'incident_transitions',
    'reasoning_packets',
    'reasoning_model_versions',
    'reasoning_prompt_versions',
    'reasoning_runs',
    'reasoning_results',
}
PREVIOUS_TIMER_BYTES = (
    '[Unit]\n'
    'Description=Schedule network log GX10 managed local reasoning\n'
    '\n[Timer]\n'
    'OnBootSec=15min\n'
    'OnUnitInactiveSec=5min\n'
    'AccuracySec=15s\n'
    'Unit=network-log-gx10-reasoning.service\n'
    '\n[Install]\n'
    'WantedBy=timers.target\n'
).encode()
PREVIOUS_ARTIFACT_SHA256 = {
    CONFIG_DIR / 'reasoning-runtime-v2.json': (
        'e7bde8d878e71d8a1b11af01170ff332920aae1df1a65536b516abf5862428f0'
    ),
    CONFIG_DIR / 'incident-assessment-output-v2.json': (
        '1ec4e28d0d18320c7469d4f1bb26a5c766515ff008c5803d24ce214ded69928a'
    ),
    LIBEXEC_DIR / 'run-local-reasoning.py': (
        'e9b894afa16fd5f138cfeec299be58328fd02454db2b53c3e395809e04d58cd0'
    ),
    LIBEXEC_DIR / 'run-managed-reasoning.py': (
        'c0c095661a7042be57230fb8fc856c03f5fe191ab604e4e246138f28156a3bee'
    ),
}


class InstallError(ValueError):
    pass


def validate_regular(path, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise InstallError(f'{label} is not a regular file')
    details = path.stat()
    if details.st_nlink != 1:
        raise InstallError(f'{label} must not be hard-linked')
    return details


def validate_exact_file(source, target, mode, uid=0, gid=0):
    source_details = validate_regular(source, 'repository reasoning artifact')
    target_details = validate_regular(target, 'installed reasoning artifact')
    if (
        source_details.st_size != target_details.st_size
        or Path(source).read_bytes() != Path(target).read_bytes()
        or target_details.st_uid != uid
        or target_details.st_gid != gid
        or stat.S_IMODE(target_details.st_mode) != mode
    ):
        raise InstallError('installed reasoning artifact differs')


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def preflight_bytes(target, data):
    target = Path(target)
    if target.exists() or target.is_symlink():
        validate_regular(target, 'existing managed reasoning artifact')
        if target.read_bytes() != data:
            raise InstallError('existing managed reasoning artifact differs')


def install_bytes(target, data, mode, uid=0, gid=0):
    target = Path(target)
    preflight_bytes(target, data)
    if target.exists():
        details = target.stat()
        if (
            details.st_uid != uid
            or details.st_gid != gid
            or stat.S_IMODE(details.st_mode) != mode
        ):
            raise InstallError(
                'existing managed reasoning artifact metadata differs'
            )
        return False
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{target.name}.',
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.link(temporary, target, follow_symlinks=False)
        temporary.unlink()
        fsync_directory(target.parent)
        return True
    finally:
        if temporary.exists():
            temporary.unlink()


def install_or_upgrade_bytes(
    target,
    data,
    previous_data,
    mode,
    uid=0,
    gid=0,
):
    target = Path(target)
    if not target.exists() and not target.is_symlink():
        install_bytes(target, data, mode, uid, gid)
        return 'created'
    details = validate_regular(
        target, 'existing managed reasoning upgrade artifact'
    )
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise InstallError(
            'existing managed reasoning upgrade metadata differs'
        )
    current = target.read_bytes()
    if current == data:
        return 'reused'
    if current != previous_data:
        raise InstallError(
            'existing managed reasoning upgrade artifact differs'
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{target.name}.', dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.replace(temporary, target)
        fsync_directory(target.parent)
        return 'upgraded'
    finally:
        if temporary.exists():
            temporary.unlink()


def install_or_upgrade_sha256(
    target,
    data,
    previous_sha256,
    mode,
    uid=0,
    gid=0,
):
    target = Path(target)
    if not target.exists() and not target.is_symlink():
        install_bytes(target, data, mode, uid, gid)
        return 'created', None
    details = validate_regular(
        target, 'existing managed reasoning upgrade artifact'
    )
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise InstallError(
            'existing managed reasoning upgrade metadata differs'
        )
    current = target.read_bytes()
    if current == data:
        return 'reused', None
    if hashlib.sha256(current).hexdigest() != previous_sha256:
        raise InstallError(
            'existing managed reasoning upgrade artifact differs'
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{target.name}.', dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.replace(temporary, target)
        fsync_directory(target.parent)
        return 'upgraded', current
    finally:
        if temporary.exists():
            temporary.unlink()


def render_config(database):
    database = Path(database)
    if not database.is_absolute() or '..' in database.parts:
        raise InstallError('managed reasoning database path is invalid')
    return (
        json.dumps(
            {'database_path': str(database)},
            separators=(',', ':'),
            sort_keys=True,
        )
        + '\n'
    ).encode()


def render_dropin(
    runtime_user,
    runtime_group,
    correlation_unit,
    ollama_unit,
    database,
):
    for value in (
        runtime_user,
        runtime_group,
        correlation_unit,
        ollama_unit,
    ):
        if not isinstance(value, str) or not SAFE_NAME_RE.fullmatch(value):
            raise InstallError('managed reasoning runtime identity is invalid')
    writable_directory = str(Path(database).parent)
    if not SAFE_PATH_RE.fullmatch(writable_directory):
        raise InstallError('managed reasoning writable path is invalid')
    return (
        '[Unit]\n'
        'After=\n'
        f'After={correlation_unit} {ollama_unit}\n'
        '\n[Service]\n'
        f'User={runtime_user}\n'
        f'Group={runtime_group}\n'
        'ReadWritePaths=\n'
        f'ReadWritePaths={writable_directory}\n'
    ).encode()


def validate_database(database):
    connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
    try:
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise InstallError('managed reasoning quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise InstallError('managed reasoning foreign_key_check failed')
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not REQUIRED_TABLES <= tables:
            raise InstallError('managed reasoning database schema differs')
    finally:
        connection.close()


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def validate_runtime_inputs(
    database,
    runtime_user,
    runtime_group,
    correlation_unit,
    ollama_unit,
):
    user = pwd.getpwnam(runtime_user)
    group = grp.getgrnam(runtime_group)
    database_details = validate_regular(database, 'application database')
    if (
        database_details.st_uid != user.pw_uid
        or database_details.st_gid != group.gr_gid
        or stat.S_IMODE(database_details.st_mode) != 0o640
        or user.pw_gid != group.gr_gid
    ):
        raise InstallError('application database identity differs')
    validate_database(database)
    for unit in (correlation_unit, ollama_unit):
        if not SAFE_NAME_RE.fullmatch(unit):
            raise InstallError('managed reasoning dependency identity is invalid')
        if systemctl_value(unit, 'LoadState') != 'loaded':
            raise InstallError('managed reasoning dependency is not loaded')
    for source, target, mode in DEPENDENCIES:
        validate_exact_file(source, target, mode)
    return user, group


def ensure_directory(path, uid, gid, mode, created):
    path = Path(path)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise InstallError('managed reasoning directory differs')
        details = path.stat()
        if (
            details.st_uid != uid
            or details.st_gid != gid
            or stat.S_IMODE(details.st_mode) != mode
        ):
            raise InstallError('managed reasoning directory metadata differs')
        return
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise InstallError('managed reasoning directory parent differs')
    path.mkdir(mode=mode)
    os.chown(path, uid, gid)
    os.chmod(path, mode)
    fsync_directory(path.parent)
    created.append(path)


def apply_install(
    database,
    runtime_user,
    runtime_group,
    correlation_unit,
    ollama_unit,
):
    _, group = validate_runtime_inputs(
        database,
        runtime_user,
        runtime_group,
        correlation_unit,
        ollama_unit,
    )
    for source, _, _ in ARTIFACTS:
        validate_regular(source, 'repository managed reasoning artifact')
    config = render_config(database)
    dropin = render_dropin(
        runtime_user,
        runtime_group,
        correlation_unit,
        ollama_unit,
        database,
    )
    created_directories = []
    created_files = []
    upgraded_files = []
    try:
        ensure_directory(
            LIBEXEC_DIR.parent, 0, 0, 0o755, created_directories
        )
        ensure_directory(LIBEXEC_DIR, 0, 0, 0o755, created_directories)
        ensure_directory(
            CONFIG_DIR, 0, group.gr_gid, 0o750, created_directories
        )
        ensure_directory(DROPIN_DIR, 0, 0, 0o755, created_directories)
        for source, target, mode in ARTIFACTS:
            source_bytes = source.read_bytes()
            if target in PREVIOUS_ARTIFACT_SHA256:
                action, previous = install_or_upgrade_sha256(
                    target,
                    source_bytes,
                    PREVIOUS_ARTIFACT_SHA256[target],
                    mode,
                )
                if action == 'created':
                    created_files.append(target)
                elif action == 'upgraded':
                    upgraded_files.append(
                        (target, previous, source_bytes, mode)
                    )
            elif target == SYSTEMD_DIR / TIMER:
                action = install_or_upgrade_bytes(
                    target,
                    source_bytes,
                    PREVIOUS_TIMER_BYTES,
                    mode,
                )
                if action == 'created':
                    created_files.append(target)
                elif action == 'upgraded':
                    upgraded_files.append(
                        (target, PREVIOUS_TIMER_BYTES, source_bytes, mode)
                    )
            elif install_bytes(target, source_bytes, mode):
                created_files.append(target)
        if install_bytes(CONFIG_PATH, config, 0o640, gid=group.gr_gid):
            created_files.append(CONFIG_PATH)
        if install_bytes(DROPIN_PATH, dropin, 0o644):
            created_files.append(DROPIN_PATH)
        subprocess.run(
            [
                'systemd-analyze',
                'verify',
                str(SYSTEMD_DIR / SERVICE),
                str(SYSTEMD_DIR / TIMER),
            ],
            check=True,
        )
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        if systemctl_value(TIMER, 'UnitFileState') not in {
            'disabled',
            'static',
        }:
            raise InstallError(
                'managed reasoning timer is already enabled'
            )
        for unit in (TIMER, SERVICE):
            if systemctl_value(unit, 'ActiveState') not in {
                'inactive',
                'unknown',
            }:
                raise InstallError(
                    'managed reasoning unit is already active'
                )
    except Exception:
        for path, data, current_data, mode in reversed(upgraded_files):
            try:
                install_or_upgrade_bytes(
                    path, data, current_data, mode
                )
            except (InstallError, OSError):
                pass
        for path in reversed(created_files):
            try:
                path.unlink()
            except OSError:
                pass
        for path in reversed(created_directories):
            try:
                path.rmdir()
            except OSError:
                pass
        subprocess.run(['systemctl', 'daemon-reload'], check=False)
        raise


def disable_runtime():
    subprocess.run(['systemctl', 'disable', '--now', TIMER], check=False)
    subprocess.run(['systemctl', 'stop', SERVICE], check=False)
    subprocess.run(['systemctl', 'reset-failed', SERVICE], check=False)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Install the unscheduled GX10 managed reasoning boundary'
    )
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--runtime-user', required=True)
    parser.add_argument('--runtime-group', required=True)
    parser.add_argument('--correlation-unit', required=True)
    parser.add_argument('--ollama-unit', default='ollama.service')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--apply', action='store_true')
    action.add_argument('--disable', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise InstallError('run the managed reasoning installer as root')
        if os.environ.get('GX10_REASONING_INSTALL_CONFIRM') != CONFIRMATION:
            raise InstallError(
                'managed reasoning install confirmation is absent'
            )
        if args.apply:
            apply_install(
                args.database.resolve(strict=True),
                args.runtime_user,
                args.runtime_group,
                args.correlation_unit,
                args.ollama_unit,
            )
            action = 'installed'
        else:
            disable_runtime()
            action = 'disabled'
        print(f'gx10_managed_reasoning={action}')
        print('GX10_MANAGED_REASONING_INSTALL=PASS')
        return 0
    except (
        KeyError,
        OSError,
        sqlite3.Error,
        InstallError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
