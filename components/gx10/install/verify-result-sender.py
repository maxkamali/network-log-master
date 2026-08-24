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


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def validate_file(path, mode, uid, gid, source=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('managed result sender artifact differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ValueError('managed result sender artifact metadata differs')
    if source is not None and path.read_bytes() != Path(source).read_bytes():
        raise ValueError('managed result sender installed source differs')


def absolute_path(value, label):
    if not isinstance(value, str) or not value.startswith('/'):
        raise ValueError(f'managed result sender {label} differs')
    path = Path(value)
    if '..' in path.parts:
        raise ValueError(f'managed result sender {label} differs')
    return path


def service_identity():
    user = systemctl_value(OUTBOX_SERVICE, 'User')
    group = systemctl_value(OUTBOX_SERVICE, 'Group')
    if SAFE_NAME_RE.fullmatch(user) is None or SAFE_NAME_RE.fullmatch(group) is None:
        raise ValueError('managed result sender identity differs')
    account = pwd.getpwnam(user)
    group_entry = grp.getgrnam(group)
    if account.pw_gid != group_entry.gr_gid:
        raise ValueError('managed result sender identity differs')
    return user, group, account.pw_uid, group_entry.gr_gid, Path(account.pw_dir)


def validate_directory(path, uid, gid, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('managed result sender directory differs')
    details = path.stat()
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ValueError('managed result sender directory metadata differs')


def runtime_state():
    user, group, uid, gid, home = service_identity()
    validate_file(OUTBOX_CONFIG, 0o640, 0, gid)
    try:
        data = json.loads(OUTBOX_CONFIG.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('managed result outbox configuration differs') from exc
    if not isinstance(data, dict) or set(data) != {
        'database_path',
        'delivered_path',
        'ready_path',
    }:
        raise ValueError('managed result outbox configuration differs')
    database = absolute_path(data['database_path'], 'database path')
    ready = absolute_path(data['ready_path'], 'ready path')
    delivered = absolute_path(data['delivered_path'], 'delivered path')
    if ready == delivered or ready.parent != delivered.parent:
        raise ValueError('managed result outbox layout differs')
    for directory in (ready.parent, ready, delivered):
        validate_directory(directory, uid, gid, 0o700)
    validate_directory(home / '.ssh', uid, gid, 0o700)
    return {
        'user': user,
        'group': group,
        'uid': uid,
        'gid': gid,
        'database': database,
        'root': ready.parent,
        'ready': ready,
        'delivered': delivered,
        'identity': home / '.ssh/result-writer.key',
        'known_hosts': home / '.ssh/result-writer-known_hosts',
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


def validate_units(state):
    for unit in (SERVICE, TIMER):
        if systemctl_value(unit, 'LoadState') != 'loaded':
            raise ValueError('managed result sender unit is not loaded')
        if Path(systemctl_value(unit, 'FragmentPath')) != SYSTEMD_DIR / unit:
            raise ValueError('managed result sender fragment path differs')
    if systemctl_value(SERVICE, 'DropInPaths') != str(DROPIN_PATH):
        raise ValueError('managed result sender drop-in state differs')
    if systemctl_value(TIMER, 'DropInPaths'):
        raise ValueError('managed result sender timer drop-in differs')
    if systemctl_value(SERVICE, 'UnitFileState') != 'static':
        raise ValueError('managed result sender service state differs')
    if systemctl_value(TIMER, 'UnitFileState') != 'disabled':
        raise ValueError('managed result sender timer is not disabled')
    if systemctl_value(TIMER, 'ActiveState') != 'inactive':
        raise ValueError('managed result sender timer is not inactive')
    if systemctl_value(SERVICE, 'ActiveState') != 'inactive':
        raise ValueError('managed result sender service is not inactive')
    if systemctl_value(SERVICE, 'NRestarts') != '0':
        raise ValueError('managed result sender restart count differs')
    if systemctl_value(SERVICE, 'User') != state['user']:
        raise ValueError('managed result sender effective user differs')
    if systemctl_value(SERVICE, 'Group') != state['group']:
        raise ValueError('managed result sender effective group differs')


def verify_staged():
    state = runtime_state()
    for source, target, mode in ARTIFACTS:
        validate_file(target, mode, 0, 0, source=source)
    validate_file(DROPIN_PATH, 0o644, 0, 0)
    if DROPIN_PATH.read_bytes() != render_dropin(state):
        raise ValueError('managed result sender drop-in differs')
    for path in (SENDER_CONFIG, state['identity'], state['known_hosts']):
        if Path(path).exists() or Path(path).is_symlink():
            raise ValueError('managed result sender private state exists')
    validate_file('/usr/bin/sftp', 0o755, 0, 0)
    validate_units(state)
    if systemctl_value(OUTBOX_TIMER, 'UnitFileState') != 'enabled':
        raise ValueError('managed result outbox timer is not enabled')
    if systemctl_value(OUTBOX_TIMER, 'ActiveState') != 'active':
        raise ValueError('managed result outbox timer is not active')
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError('run the managed result sender verifier as root')
        if not args.staged:
            raise ValueError('managed result sender verification mode is absent')
        verify_staged()
        print(
            'MANAGED_RESULT_SENDER_VERIFY schema=1 staged=yes '
            'timer_enabled=no service_active=no config_installed=no '
            'credentials_installed=no'
        )
        print('GX10_MANAGED_RESULT_SENDER_VERIFY=PASS')
        return 0
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_RESULT_SENDER_VERIFY=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
