#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import time


SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
LIBEXEC_DIR = Path('/usr/local/libexec/network-log-gx10')
CONFIG_DIR = Path('/etc/network-log-gx10')
SYSTEMD_DIR = Path('/etc/systemd/system')
SERVICE = 'network-log-gx10-result-outbox.service'
TIMER = 'network-log-gx10-result-outbox.timer'
SNAPSHOT_SERVICE = 'network-log-gx10-outbox-snapshot.service'
DROPIN_PATH = SYSTEMD_DIR / f'{SERVICE}.d' / '10-runtime.conf'
SNAPSHOT_DROPIN_PATH = (
    SYSTEMD_DIR / f'{SNAPSHOT_SERVICE}.d' / '10-runtime.conf'
)
CONFIG_PATH = CONFIG_DIR / 'result-outbox.json'
SNAPSHOT_CONFIG_PATH = CONFIG_DIR / 'outbox-snapshot.json'
LEGACY_SERVICE_SHA256 = (
    '290a303406fc21e6cf15bac74ff982acd7808eeb02a3c085cc4f79a8f334a7a0'
)
UNCHANGED_ARTIFACTS = (
    (
        GX10_DIR / 'sbin' / 'build-result-outbox.py',
        LIBEXEC_DIR / 'build-result-outbox.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-result-outbox.py',
        LIBEXEC_DIR / 'run-result-outbox.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'build-incident-outbox.py',
        LIBEXEC_DIR / 'build-incident-outbox.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-incident-outbox.py',
        LIBEXEC_DIR / 'run-incident-outbox.py',
        0o755,
    ),
    (
        GX10_DIR / 'systemd' / TIMER,
        SYSTEMD_DIR / TIMER,
        0o644,
    ),
)
NEW_ARTIFACTS = (
    (
        GX10_DIR / 'sbin' / 'create-outbox-snapshot.py',
        LIBEXEC_DIR / 'create-outbox-snapshot.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-outbox-snapshot.py',
        LIBEXEC_DIR / 'run-outbox-snapshot.py',
        0o755,
    ),
    (
        GX10_DIR / 'systemd' / SNAPSHOT_SERVICE,
        SYSTEMD_DIR / SNAPSHOT_SERVICE,
        0o644,
    ),
)
REPLACED_SERVICE_SOURCE = GX10_DIR / 'systemd' / SERVICE
REPLACED_SERVICE_TARGET = SYSTEMD_DIR / SERVICE


class UpgradeError(ValueError):
    pass


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise UpgradeError('result outbox upgrade module cannot be loaded')
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def validate_file(path, mode, *, uid=0, gid=0, expected=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise UpgradeError('result outbox upgrade artifact differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise UpgradeError('result outbox upgrade metadata differs')
    data = path.read_bytes()
    if expected is not None and data != expected:
        raise UpgradeError('result outbox upgrade artifact differs')
    return data


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def run_systemctl(*arguments, check=True):
    return subprocess.run(
        ['systemctl', *arguments],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def wait_settled(unit, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = systemctl_value(unit, 'ActiveState')
        if state in {'inactive', 'failed'}:
            return state
        time.sleep(0.2)
    raise UpgradeError('result outbox service did not settle')


def wait_new_successful_cycle(previous_invocation, timeout=360):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        outbox_state = systemctl_value(SERVICE, 'ActiveState')
        snapshot_state = systemctl_value(SNAPSHOT_SERVICE, 'ActiveState')
        if outbox_state == 'failed' or snapshot_state == 'failed':
            raise UpgradeError('natural result outbox cycle failed')
        invocation = systemctl_value(SERVICE, 'InvocationID')
        if (
            invocation
            and invocation != previous_invocation
            and outbox_state == 'inactive'
            and snapshot_state == 'inactive'
        ):
            if (
                systemctl_value(SERVICE, 'Result') != 'success'
                or systemctl_value(SNAPSHOT_SERVICE, 'Result') != 'success'
            ):
                raise UpgradeError('natural result outbox result differs')
            return
        time.sleep(0.5)
    raise UpgradeError('natural result outbox cycle did not settle')


def install_bytes(path, data, mode, uid=0, gid=0):
    path = Path(path)
    temporary = path.with_name(f'.{path.name}.upgrade-{os.getpid()}')
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
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def render_json(data):
    return (
        json.dumps(data, separators=(',', ':'), sort_keys=True) + '\n'
    ).encode('utf-8')


def validate_backup_parent(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise UpgradeError('protected backup path differs')
    if path.exists() or path.is_symlink():
        raise UpgradeError('protected backup already exists')
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise UpgradeError('protected backup parent differs')
    details = parent.stat()
    if details.st_uid != 0 or stat.S_IMODE(details.st_mode) & 0o022:
        raise UpgradeError('protected backup parent metadata differs')


def legacy_preflight(installer, database, root, backup):
    user, group, uid, gid = installer.service_identity()
    installer.validate_database(database, uid, gid)
    ready = root / 'ready'
    delivered = root / 'delivered'
    for directory in (root, ready, delivered):
        details = directory.stat()
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or details.st_uid != uid
            or details.st_gid != gid
            or stat.S_IMODE(details.st_mode) != 0o700
        ):
            raise UpgradeError('legacy result outbox directory differs')
    for source, target, mode in UNCHANGED_ARTIFACTS:
        validate_file(source, mode, uid=os.geteuid(), gid=os.getegid())
        validate_file(target, mode, expected=source.read_bytes())
    service_bytes = validate_file(REPLACED_SERVICE_TARGET, 0o644)
    if sha256_bytes(service_bytes) != LEGACY_SERVICE_SHA256:
        raise UpgradeError('legacy result outbox service differs')
    validate_file(CONFIG_PATH, 0o640, gid=gid)
    legacy_config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    if legacy_config != {
        'database_path': str(database),
        'delivered_path': str(delivered),
        'ready_path': str(ready),
    }:
        raise UpgradeError('legacy result outbox configuration differs')
    validate_file(DROPIN_PATH, 0o644)
    legacy_dropin = DROPIN_PATH.read_text(encoding='utf-8').splitlines()
    if legacy_dropin != [
        '[Service]',
        f'User={user}',
        f'Group={group}',
        'ReadWritePaths=',
        f'ReadWritePaths={root}',
    ]:
        raise UpgradeError('legacy result outbox drop-in differs')
    if systemctl_value(TIMER, 'UnitFileState') != 'enabled':
        raise UpgradeError('legacy result outbox timer enablement differs')
    if systemctl_value(TIMER, 'ActiveState') != 'active':
        raise UpgradeError('legacy result outbox timer state differs')
    for _, target, _ in NEW_ARTIFACTS:
        if target.exists() or target.is_symlink():
            raise UpgradeError('outbox snapshot target already exists')
    snapshot_root = database.parent / 'outbox-snapshot'
    for path in (SNAPSHOT_CONFIG_PATH, SNAPSHOT_DROPIN_PATH, snapshot_root):
        if path.exists() or path.is_symlink():
            raise UpgradeError('outbox snapshot private target already exists')
    if systemctl_value(SNAPSHOT_SERVICE, 'LoadState') != 'not-found':
        raise UpgradeError('outbox snapshot unit already exists')
    validate_backup_parent(backup)
    return user, group, uid, gid, ready, delivered, snapshot_root


def create_backup(path, files):
    path = Path(path)
    path.mkdir(mode=0o700)
    os.chown(path, 0, 0)
    os.chmod(path, 0o700)
    manifest = {}
    for label, source in files:
        data = Path(source).read_bytes()
        target = path / label
        install_bytes(target, data, 0o600)
        manifest[label] = sha256_bytes(data)
    install_bytes(
        path / 'manifest.json', render_json(manifest), 0o600
    )


def upgrade(backup):
    installer = load_module(
        'result_outbox_snapshot_upgrade_installer',
        SCRIPT_DIR / 'install-result-outbox.py',
    )
    verifier = load_module(
        'result_outbox_snapshot_upgrade_verifier',
        SCRIPT_DIR / 'verify-result-outbox.py',
    )
    database = installer.load_managed_database().resolve(strict=True)
    root = database.parent / 'result-outbox'
    (
        user,
        group,
        uid,
        gid,
        ready,
        delivered,
        snapshot_root,
    ) = legacy_preflight(installer, database, root, backup)
    snapshot_database = snapshot_root / 'events.sqlite3'
    legacy = {
        REPLACED_SERVICE_TARGET: REPLACED_SERVICE_TARGET.read_bytes(),
        CONFIG_PATH: CONFIG_PATH.read_bytes(),
        DROPIN_PATH: DROPIN_PATH.read_bytes(),
    }
    create_backup(
        backup,
        (
            ('result-outbox.service', REPLACED_SERVICE_TARGET),
            ('result-outbox.json', CONFIG_PATH),
            ('result-outbox-runtime.conf', DROPIN_PATH),
        ),
    )

    created_files = []
    created_directories = []
    mutated = False
    try:
        run_systemctl('disable', '--now', TIMER)
        wait_settled(SERVICE)
        run_systemctl('reset-failed', SERVICE, check=False)

        snapshot_root.mkdir(mode=0o700)
        os.chown(snapshot_root, uid, gid)
        os.chmod(snapshot_root, 0o700)
        created_directories.append(snapshot_root)
        for source, target, mode in NEW_ARTIFACTS:
            install_bytes(target, source.read_bytes(), mode)
            created_files.append(target)
        install_bytes(
            REPLACED_SERVICE_TARGET,
            REPLACED_SERVICE_SOURCE.read_bytes(),
            0o644,
        )
        mutated = True
        install_bytes(
            CONFIG_PATH,
            render_json(
                {
                    'database_path': str(snapshot_database),
                    'delivered_path': str(delivered),
                    'ready_path': str(ready),
                }
            ),
            0o640,
            gid=gid,
        )
        snapshot_config = render_json(
            {
                'snapshot_database_path': str(snapshot_database),
                'source_database_path': str(database),
            }
        )
        install_bytes(SNAPSHOT_CONFIG_PATH, snapshot_config, 0o640, gid=gid)
        created_files.append(SNAPSHOT_CONFIG_PATH)
        snapshot_dropin_dir = SNAPSHOT_DROPIN_PATH.parent
        snapshot_dropin_dir.mkdir(mode=0o755)
        created_directories.append(snapshot_dropin_dir)
        snapshot_dropin = (
            '[Service]\n'
            f'User={user}\n'
            f'Group={group}\n'
            'ReadWritePaths=\n'
            f'ReadWritePaths={database.parent}\n'
        ).encode('utf-8')
        install_bytes(SNAPSHOT_DROPIN_PATH, snapshot_dropin, 0o644)
        created_files.append(SNAPSHOT_DROPIN_PATH)

        subprocess.run(
            [
                'systemd-analyze',
                'verify',
                str(SYSTEMD_DIR / SNAPSHOT_SERVICE),
                str(SYSTEMD_DIR / SERVICE),
                str(SYSTEMD_DIR / TIMER),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        run_systemctl('daemon-reload')
        run_systemctl('start', SERVICE)
        if systemctl_value(SNAPSHOT_SERVICE, 'Result') != 'success':
            raise UpgradeError('outbox snapshot service failed')
        if systemctl_value(SERVICE, 'Result') != 'success':
            raise UpgradeError('result outbox service failed')
        inactive = verifier.verify(
            database,
            root,
            ready,
            delivered,
            active=False,
            allow_populated_inactive=True,
        )
        manual_invocation = systemctl_value(SERVICE, 'InvocationID')
        run_systemctl('enable', '--now', TIMER)
        wait_new_successful_cycle(manual_invocation)
        active = verifier.verify(
            database, root, ready, delivered, active=True
        )
        if active['results'] < inactive['results']:
            raise UpgradeError('result outbox activation result count regressed')
        return active
    except Exception:
        run_systemctl('disable', '--now', TIMER, check=False)
        run_systemctl('stop', SERVICE, SNAPSHOT_SERVICE, check=False)
        if mutated:
            install_bytes(
                REPLACED_SERVICE_TARGET, legacy[REPLACED_SERVICE_TARGET], 0o644
            )
            install_bytes(CONFIG_PATH, legacy[CONFIG_PATH], 0o640, gid=gid)
            install_bytes(DROPIN_PATH, legacy[DROPIN_PATH], 0o644)
        for path in reversed(created_files):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        run_systemctl('daemon-reload', check=False)
        run_systemctl('reset-failed', SERVICE, check=False)
        run_systemctl('enable', '--now', TIMER, check=False)
        raise


def check_upgrade(backup):
    installer = load_module(
        'result_outbox_snapshot_check_installer',
        SCRIPT_DIR / 'install-result-outbox.py',
    )
    database = installer.load_managed_database().resolve(strict=True)
    root = database.parent / 'result-outbox'
    legacy_preflight(installer, database, root, backup)
    unit_check = subprocess.run(
        [
            'systemd-analyze',
            'verify',
            str(GX10_DIR / 'systemd' / SNAPSHOT_SERVICE),
            str(GX10_DIR / 'systemd' / SERVICE),
            str(GX10_DIR / 'systemd' / TIMER),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    expected_missing = (
        f'{SNAPSHOT_SERVICE}: Command '
        '/usr/local/libexec/network-log-gx10/run-outbox-snapshot.py '
        'is not executable: No such file or directory'
    )
    messages = [line.strip() for line in unit_check.stderr.splitlines() if line.strip()]
    if unit_check.returncode and messages != [expected_missing]:
        raise UpgradeError('candidate result outbox unit verification failed')


def parse_args():
    parser = argparse.ArgumentParser(
        description='Upgrade the active GX10 outbox to a stable SQLite snapshot'
    )
    parser.add_argument('--backup-dir', type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument(
        '--confirm-live-outbox-snapshot-upgrade', action='store_true'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise UpgradeError('run the result outbox upgrade as root')
        if args.check:
            check_upgrade(args.backup_dir)
            print(
                'RESULT_OUTBOX_SNAPSHOT_UPGRADE_CHECK schema=1 '
                'legacy_exact=yes candidate_units_valid=yes mutation=no'
            )
            print('GX10_RESULT_OUTBOX_SNAPSHOT_UPGRADE_CHECK=PASS')
            return 0
        state = upgrade(args.backup_dir)
        print(
            'RESULT_OUTBOX_SNAPSHOT_UPGRADE schema=1 '
            f'results={state["results"]} ready={state["ready"]} '
            f'delivered={state["delivered"]} incidents={state["incidents"]} '
            'timer_enabled=yes source_database_modified=no '
            'credentials_installed=no transmission_changed=no'
        )
        print('GX10_RESULT_OUTBOX_SNAPSHOT_UPGRADE=PASS')
        return 0
    except (OSError, sqlite3.Error, subprocess.SubprocessError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_RESULT_OUTBOX_SNAPSHOT_UPGRADE=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
