#!/usr/bin/env python3
from __future__ import annotations

import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
LIBEXEC_DIR = Path('/usr/local/libexec/network-log-gx10')
CONFIG_DIR = Path('/etc/network-log-gx10')
CONFIG_PATH = CONFIG_DIR / 'correlation.json'
SYSTEMD_DIR = Path('/etc/systemd/system')
SERVICE = 'network-log-gx10-correlation.service'
TIMER = 'network-log-gx10-correlation.timer'
DROPIN_DIR = SYSTEMD_DIR / f'{SERVICE}.d'
DROPIN_PATH = DROPIN_DIR / '10-runtime.conf'
CONFIRMATION = 'INSTALL-UNSCHEDULED-CORRELATION'
SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_.@-]+$')
ARTIFACTS = (
    (
        GX10_DIR / 'sbin' / 'enrich-events.py',
        LIBEXEC_DIR / 'enrich-events.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'incident-engine.py',
        LIBEXEC_DIR / 'incident-engine.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-correlation.py',
        LIBEXEC_DIR / 'run-correlation.py',
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


def validate_directory(path, uid, gid, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise InstallError('managed correlation directory differs')
    details = path.stat()
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise InstallError('managed correlation directory metadata differs')


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def preflight_bytes(target, data):
    target = Path(target)
    if target.exists() or target.is_symlink():
        validate_regular(target, 'existing managed correlation artifact')
        if target.read_bytes() != data:
            raise InstallError('existing managed correlation artifact differs')


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
            raise InstallError('existing managed correlation metadata differs')
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


def render_config(database):
    database = Path(database)
    if not database.is_absolute() or '..' in database.parts:
        raise InstallError('managed correlation database path is invalid')
    return (
        json.dumps(
            {'database_path': str(database)},
            separators=(',', ':'),
            sort_keys=True,
        )
        + '\n'
    ).encode()


def render_dropin(runtime_user, runtime_group, pipeline_unit):
    for value in (runtime_user, runtime_group, pipeline_unit):
        if not isinstance(value, str) or not SAFE_NAME_RE.fullmatch(value):
            raise InstallError('managed correlation runtime identity is invalid')
    return (
        '[Unit]\n'
        'After=\n'
        f'After={pipeline_unit}\n'
        '\n[Service]\n'
        f'User={runtime_user}\n'
        f'Group={runtime_group}\n'
    ).encode()


def validate_runtime_inputs(database, runtime_user, runtime_group, pipeline_unit):
    user = pwd.getpwnam(runtime_user)
    group = grp.getgrnam(runtime_group)
    database_details = validate_regular(database, 'application database')
    if database_details.st_uid != user.pw_uid or database_details.st_gid != group.gr_gid:
        raise InstallError('application database identity differs')
    if stat.S_IMODE(database_details.st_mode) != 0o640:
        raise InstallError('application database mode differs')
    if user.pw_gid != group.gr_gid:
        raise InstallError('runtime primary group differs')
    result = subprocess.run(
        ['systemctl', 'show', pipeline_unit, '--property=LoadState', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()
    if result != 'loaded':
        raise InstallError('pipeline unit is not loaded')
    return user, group


def ensure_directory(path, uid, gid, mode, created):
    path = Path(path)
    if path.exists() or path.is_symlink():
        validate_directory(path, uid, gid, mode)
        return
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise InstallError('managed correlation directory parent differs')
    path.mkdir(mode=mode)
    os.chown(path, uid, gid)
    os.chmod(path, mode)
    fsync_directory(path.parent)
    created.append(path)


def apply_install(database, runtime_user, runtime_group, pipeline_unit):
    _, group = validate_runtime_inputs(
        database,
        runtime_user,
        runtime_group,
        pipeline_unit,
    )
    for source, _, _ in ARTIFACTS:
        validate_regular(source, 'repository managed correlation artifact')
    config = render_config(database)
    dropin = render_dropin(runtime_user, runtime_group, pipeline_unit)
    for source, target, _ in ARTIFACTS:
        if target.parent in (LIBEXEC_DIR, SYSTEMD_DIR):
            continue
        if target.parent.is_symlink() or not target.parent.is_dir():
            raise InstallError('managed correlation target parent differs')
        preflight_bytes(target, source.read_bytes())

    created_directories = []
    created_files = []
    try:
        ensure_directory(
            LIBEXEC_DIR.parent,
            0,
            0,
            0o755,
            created_directories,
        )
        ensure_directory(LIBEXEC_DIR, 0, 0, 0o755, created_directories)
        ensure_directory(CONFIG_DIR, 0, group.gr_gid, 0o750, created_directories)
        ensure_directory(DROPIN_DIR, 0, 0, 0o755, created_directories)
        for source, target, mode in ARTIFACTS:
            if install_bytes(target, source.read_bytes(), mode):
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
        if subprocess.run(
            ['systemctl', 'is-enabled', '--quiet', TIMER],
            check=False,
        ).returncode == 0:
            raise InstallError('managed correlation timer is already enabled')
        for unit in (TIMER, SERVICE):
            state = subprocess.run(
                ['systemctl', 'is-active', unit],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout.strip()
            if state not in {'inactive', 'unknown'}:
                raise InstallError('managed correlation unit is already active')
    except Exception:
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


def parse_args():
    parser = argparse.ArgumentParser(
        description='Install the unscheduled GX10 managed correlation boundary'
    )
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--runtime-user', required=True)
    parser.add_argument('--runtime-group', required=True)
    parser.add_argument('--pipeline-unit', required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--apply', action='store_true')
    action.add_argument('--disable', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise InstallError('run the correlation installer as root')
        if os.environ.get('GX10_CORRELATION_INSTALL_CONFIRM') != CONFIRMATION:
            raise InstallError('managed correlation install confirmation is absent')
        if args.apply:
            apply_install(
                args.database.resolve(strict=True),
                args.runtime_user,
                args.runtime_group,
                args.pipeline_unit,
            )
            action = 'installed'
        else:
            disable_runtime()
            action = 'disabled'
        print(f'gx10_managed_correlation={action}')
        print('GX10_MANAGED_CORRELATION_INSTALL=PASS')
        return 0
    except (
        KeyError,
        OSError,
        InstallError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
