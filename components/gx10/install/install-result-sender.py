#!/usr/bin/env python3
from __future__ import annotations

import argparse
import grp
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
LIBEXEC_DIR = Path('/usr/local/libexec/network-log-gx10')
CONFIG_DIR = Path('/etc/network-log-gx10')
SYSTEMD_DIR = Path('/etc/systemd/system')
OUTBOX_CONFIG = CONFIG_DIR / 'result-outbox.json'
SENDER_CONFIG = CONFIG_DIR / 'result-sender.json'
SERVICE = 'network-log-gx10-result-sender.service'
TIMER = 'network-log-gx10-result-sender.timer'
OUTBOX_SERVICE = 'network-log-gx10-result-outbox.service'
OUTBOX_TIMER = 'network-log-gx10-result-outbox.timer'
DROPIN_PATH = SYSTEMD_DIR / f'{SERVICE}.d' / '10-runtime.conf'
SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_.@-]+$')
ARTIFACTS = (
    (
        GX10_DIR / 'sbin' / 'send-result-outbox.py',
        LIBEXEC_DIR / 'send-result-outbox.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-result-sender.py',
        LIBEXEC_DIR / 'run-result-sender.py',
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


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def run_systemctl(*arguments):
    subprocess.run(
        ['systemctl', *arguments],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def validate_file(path, mode, uid, gid):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise InstallError('result sender artifact differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise InstallError('result sender artifact metadata differs')


def validate_source(path, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise InstallError('repository result sender artifact differs')
    details = path.stat()
    if details.st_nlink != 1 or stat.S_IMODE(details.st_mode) != mode:
        raise InstallError('repository result sender artifact metadata differs')


def absolute_path(value, label):
    if not isinstance(value, str) or not value.startswith('/'):
        raise InstallError(f'result sender {label} differs')
    path = Path(value)
    if '..' in path.parts:
        raise InstallError(f'result sender {label} differs')
    return path


def service_identity():
    user = systemctl_value(OUTBOX_SERVICE, 'User')
    group = systemctl_value(OUTBOX_SERVICE, 'Group')
    if SAFE_NAME_RE.fullmatch(user) is None or SAFE_NAME_RE.fullmatch(group) is None:
        raise InstallError('result sender service identity differs')
    account = pwd.getpwnam(user)
    group_entry = grp.getgrnam(group)
    if account.pw_gid != group_entry.gr_gid:
        raise InstallError('result sender service identity differs')
    return user, group, account.pw_uid, group_entry.gr_gid, Path(account.pw_dir)


def load_outbox_config(path=OUTBOX_CONFIG):
    user, group, uid, gid, home = service_identity()
    validate_file(path, 0o640, 0, gid)
    if Path(path).stat().st_size > 4096:
        raise InstallError('result outbox configuration is too large')
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError('result outbox configuration differs') from exc
    if not isinstance(data, dict) or set(data) != {
        'database_path',
        'delivered_path',
        'ready_path',
    }:
        raise InstallError('result outbox configuration differs')
    database = absolute_path(data['database_path'], 'database path')
    ready = absolute_path(data['ready_path'], 'ready path')
    delivered = absolute_path(data['delivered_path'], 'delivered path')
    if ready == delivered or ready.parent != delivered.parent:
        raise InstallError('result outbox layout differs')
    root = ready.parent
    for directory in (root, ready, delivered):
        if directory.is_symlink() or not directory.is_dir():
            raise InstallError('result outbox directory differs')
        details = directory.stat()
        if (
            details.st_uid != uid
            or details.st_gid != gid
            or stat.S_IMODE(details.st_mode) != 0o700
        ):
            raise InstallError('result outbox directory metadata differs')
    ssh_dir = home / '.ssh'
    if ssh_dir.is_symlink() or not ssh_dir.is_dir():
        raise InstallError('result sender SSH directory differs')
    ssh_details = ssh_dir.stat()
    if (
        ssh_details.st_uid != uid
        or ssh_details.st_gid != gid
        or stat.S_IMODE(ssh_details.st_mode) != 0o700
    ):
        raise InstallError('result sender SSH directory metadata differs')
    return {
        'user': user,
        'group': group,
        'uid': uid,
        'gid': gid,
        'database': database,
        'root': root,
        'ready': ready,
        'delivered': delivered,
        'identity': ssh_dir / 'result-writer.key',
        'known_hosts': ssh_dir / 'result-writer-known_hosts',
    }


def render_dropin(state):
    return (
        '[Service]\n'
        f'User={state["user"]}\n'
        f'Group={state["group"]}\n'
        'ReadWritePaths=\n'
        f'ReadWritePaths={state["root"]}\n'
        'ReadOnlyPaths=\n'
        f'ReadOnlyPaths={SENDER_CONFIG}\n'
        f'ReadOnlyPaths={state["identity"]}\n'
        f'ReadOnlyPaths={state["known_hosts"]}\n'
        'InaccessiblePaths=\n'
        f'InaccessiblePaths={state["database"]}\n'
    ).encode('utf-8')


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def install_bytes(path, data, mode, uid, gid):
    path = Path(path)
    temporary = path.parent / f'.{path.name}.install-{os.getpid()}'
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, 'wb', closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def preflight():
    state = load_outbox_config()
    if systemctl_value(OUTBOX_TIMER, 'UnitFileState') != 'enabled':
        raise InstallError('result outbox timer is not enabled')
    if systemctl_value(OUTBOX_TIMER, 'ActiveState') != 'active':
        raise InstallError('result outbox timer is not active')
    for source, target, mode in ARTIFACTS:
        validate_source(source, mode)
        if Path(target).exists() or Path(target).is_symlink():
            raise InstallError('result sender target already exists')
    for path in (SENDER_CONFIG, state['identity'], state['known_hosts'], DROPIN_PATH):
        if Path(path).exists() or Path(path).is_symlink():
            raise InstallError('result sender private target already exists')
    for unit in (SERVICE, TIMER):
        if systemctl_value(unit, 'LoadState') != 'not-found':
            raise InstallError('result sender unit already exists')
    for directory in (LIBEXEC_DIR, CONFIG_DIR, SYSTEMD_DIR):
        if directory.is_symlink() or not directory.is_dir():
            raise InstallError('result sender parent directory differs')
    validate_file('/usr/bin/sftp', 0o755, 0, 0)
    return state


def load_verifier():
    path = SCRIPT_DIR / 'verify-result-sender.py'
    specification = importlib.util.spec_from_file_location(
        'result_sender_install_verifier', path
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def install():
    state = preflight()
    created_files = []
    created_directories = []
    try:
        for source, target, mode in ARTIFACTS:
            created_files.append(Path(target))
            install_bytes(target, Path(source).read_bytes(), mode, 0, 0)
        DROPIN_PATH.parent.mkdir(mode=0o755)
        created_directories.append(DROPIN_PATH.parent)
        created_files.append(DROPIN_PATH)
        install_bytes(DROPIN_PATH, render_dropin(state), 0o644, 0, 0)
        run_systemctl('daemon-reload')
        run_systemctl('disable', '--now', TIMER)
        subprocess.run(
            ['systemd-analyze', 'verify', SYSTEMD_DIR / SERVICE, SYSTEMD_DIR / TIMER],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        verifier = load_verifier()
        verifier.verify_staged()
        return state
    except Exception:
        try:
            run_systemctl('disable', '--now', TIMER)
        except Exception:
            pass
        for path in reversed(created_files):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except (FileNotFoundError, OSError):
                pass
        try:
            run_systemctl('daemon-reload')
        except Exception:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Install the inactive managed GX10 result sender'
    )
    parser.add_argument(
        '--confirm-install-inactive-result-sender', action='store_true'
    )
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise InstallError('run the result sender installer as root')
        if not args.confirm_install_inactive_result_sender:
            raise InstallError('inactive result sender confirmation is absent')
        install()
        print(
            'RESULT_SENDER_INSTALL schema=1 timer_enabled=no '
            'service_active=no config_installed=no credentials_installed=no'
        )
        print('GX10_RESULT_SENDER_INACTIVE_INSTALL=PASS')
        return 0
    except (OSError, subprocess.CalledProcessError, InstallError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_RESULT_SENDER_INACTIVE_INSTALL=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
