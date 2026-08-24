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
import sqlite3
import stat
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
LIBEXEC_DIR = Path('/usr/local/libexec/network-log-gx10')
CONFIG_DIR = Path('/etc/network-log-gx10')
SYSTEMD_DIR = Path('/etc/systemd/system')
DEFAULT_DATABASE = Path('/var/lib/network-log-gx10/state/events.sqlite3')
DEFAULT_OUTBOX_ROOT = Path('/var/lib/network-log-gx10/result-outbox')
MANAGED_CONFIG_PATH = CONFIG_DIR / 'managed-reasoning.json'
SERVICE = 'network-log-gx10-result-outbox.service'
TIMER = 'network-log-gx10-result-outbox.timer'
REASONING_SERVICE = 'network-log-gx10-reasoning.service'
DROPIN_PATH = SYSTEMD_DIR / f'{SERVICE}.d' / '10-runtime.conf'
CONFIG_PATH = CONFIG_DIR / 'result-outbox.json'
SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_.@-]+$')
ARTIFACTS = (
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
REQUIRED_TABLES = {
    'reasoning_packets',
    'reasoning_model_versions',
    'reasoning_prompt_versions',
    'reasoning_runs',
    'reasoning_results',
}


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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def validate_source(path, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise InstallError(
            'repository result outbox artifact is not a regular file'
        )
    details = path.stat()
    if details.st_nlink != 1 or stat.S_IMODE(details.st_mode) != mode:
        raise InstallError('repository result outbox artifact metadata differs')


def validate_database(path, uid, gid):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise InstallError('result outbox database differs')
    details = path.stat()
    if details.st_uid != uid or details.st_gid != gid:
        raise InstallError('result outbox database identity differs')
    connection = sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)
    try:
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise InstallError('result outbox quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise InstallError('result outbox foreign_key_check failed')
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not REQUIRED_TABLES <= tables:
            raise InstallError('result outbox database schema differs')
        started = connection.execute(
            "SELECT COUNT(*) FROM reasoning_runs WHERE status='STARTED'"
        ).fetchone()[0]
        mismatch = connection.execute(
            '''
            SELECT COUNT(*) FROM reasoning_runs AS run
            WHERE (run.status='SUCCEEDED') != EXISTS (
              SELECT 1 FROM reasoning_results AS result
              WHERE result.run_id=run.run_id
            )
            '''
        ).fetchone()[0]
        if started or mismatch:
            raise InstallError('result outbox reasoning state differs')
    finally:
        connection.close()


def service_identity():
    if systemctl_value(REASONING_SERVICE, 'LoadState') != 'loaded':
        raise InstallError('managed reasoning service is not loaded')
    user = systemctl_value(REASONING_SERVICE, 'User')
    group = systemctl_value(REASONING_SERVICE, 'Group')
    if (
        SAFE_NAME_RE.fullmatch(user) is None
        or SAFE_NAME_RE.fullmatch(group) is None
    ):
        raise InstallError('result outbox runtime identity differs')
    return user, group, pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid


def load_managed_database(path=MANAGED_CONFIG_PATH):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise InstallError('managed reasoning configuration differs')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError('managed reasoning configuration differs') from exc
    if not isinstance(data, dict) or set(data) != {'database_path'}:
        raise InstallError('managed reasoning configuration differs')
    value = data['database_path']
    if not isinstance(value, str) or not value.startswith('/'):
        raise InstallError('managed reasoning database path differs')
    database = Path(value)
    if '..' in database.parts:
        raise InstallError('managed reasoning database path differs')
    return database


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def install_bytes(path, data, mode, uid, gid):
    path = Path(path)
    temporary = path.with_name(f'.{path.name}.install-{os.getpid()}')
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


def preflight(database, root):
    user, group, uid, gid = service_identity()
    validate_database(database, uid, gid)
    for source, target, mode in ARTIFACTS:
        validate_source(source, mode)
        if Path(target).exists() or Path(target).is_symlink():
            raise InstallError('result outbox target already exists')
    for path in (CONFIG_PATH, DROPIN_PATH, root):
        if Path(path).exists() or Path(path).is_symlink():
            raise InstallError('result outbox private target already exists')
    for unit in (SERVICE, TIMER):
        if systemctl_value(unit, 'LoadState') != 'not-found':
            raise InstallError('result outbox unit already exists')
    for directory in (LIBEXEC_DIR, CONFIG_DIR, SYSTEMD_DIR, Path(root).parent):
        if directory.is_symlink() or not directory.is_dir():
            raise InstallError('result outbox parent directory differs')
    return user, group, uid, gid


def load_verifier():
    path = SCRIPT_DIR / 'verify-result-outbox.py'
    specification = importlib.util.spec_from_file_location(
        'result_outbox_install_verifier', path
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def install(database, root):
    database = Path(database)
    if database.is_symlink():
        raise InstallError('result outbox database differs')
    database = database.resolve(strict=True)
    root = Path(root)
    ready = root / 'ready'
    delivered = root / 'delivered'
    user, group, uid, gid = preflight(database, root)
    created_files = []
    created_directories = []
    try:
        root.mkdir(mode=0o700)
        created_directories.append(root)
        for directory in (ready, delivered):
            directory.mkdir(mode=0o700)
            created_directories.append(directory)
        for directory in (root, ready, delivered):
            os.chown(directory, uid, gid)
            os.chmod(directory, 0o700)
        for source, target, mode in ARTIFACTS:
            created_files.append(Path(target))
            install_bytes(target, Path(source).read_bytes(), mode, 0, 0)
        config = (
            json.dumps(
                {
                    'database_path': str(database),
                    'delivered_path': str(delivered),
                    'ready_path': str(ready),
                },
                separators=(',', ':'),
                sort_keys=True,
            )
            + '\n'
        ).encode('utf-8')
        created_files.append(CONFIG_PATH)
        install_bytes(CONFIG_PATH, config, 0o640, 0, gid)
        DROPIN_PATH.parent.mkdir(mode=0o755)
        created_directories.append(DROPIN_PATH.parent)
        dropin = (
            '[Service]\n'
            f'User={user}\n'
            f'Group={group}\n'
            'ReadWritePaths=\n'
            f'ReadWritePaths={root}\n'
        ).encode('utf-8')
        created_files.append(DROPIN_PATH)
        install_bytes(DROPIN_PATH, dropin, 0o644, 0, 0)
        run_systemctl('daemon-reload')
        run_systemctl('disable', '--now', TIMER)
        verifier = load_verifier()
        state = verifier.verify(
            database, root, ready, delivered, active=False
        )
        if state['ready'] or state['delivered']:
            raise InstallError('inactive result outbox is not empty')
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


def parse_args():
    parser = argparse.ArgumentParser(
        description='Install the inactive managed GX10 result outbox'
    )
    parser.add_argument('--database', type=Path)
    parser.add_argument('--outbox-root', type=Path)
    parser.add_argument(
        '--confirm-install-inactive-result-outbox', action='store_true'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise InstallError('run the result outbox installer as root')
        if not args.confirm_install_inactive_result_outbox:
            raise InstallError('inactive result outbox confirmation is absent')
        database = args.database or load_managed_database()
        outbox_root = args.outbox_root or database.parent / 'result-outbox'
        state = install(database, outbox_root)
        print(
            'RESULT_OUTBOX_INSTALL schema=1 '
            f'results={state["results"]} ready=0 delivered=0 '
            'timer_enabled=no service_active=no credentials_installed=no'
        )
        print('GX10_RESULT_OUTBOX_INACTIVE_INSTALL=PASS')
        return 0
    except (OSError, sqlite3.Error, InstallError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_RESULT_OUTBOX_INACTIVE_INSTALL=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
