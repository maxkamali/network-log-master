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
OUTBOX_ROOT = Path('/var/lib/network-log-gx10/result-outbox')
SNAPSHOT_ROOT = Path('/var/lib/network-log-gx10/outbox-snapshot')
READY_DIR = OUTBOX_ROOT / 'ready'
DELIVERED_DIR = OUTBOX_ROOT / 'delivered'
CONFIG_PATH = CONFIG_DIR / 'result-outbox.json'
SNAPSHOT_CONFIG_PATH = CONFIG_DIR / 'outbox-snapshot.json'
MANAGED_CONFIG_PATH = CONFIG_DIR / 'managed-reasoning.json'
SERVICE = 'network-log-gx10-result-outbox.service'
TIMER = 'network-log-gx10-result-outbox.timer'
SNAPSHOT_SERVICE = 'network-log-gx10-outbox-snapshot.service'
REASONING_SERVICE = 'network-log-gx10-reasoning.service'
DROPIN_PATH = SYSTEMD_DIR / f'{SERVICE}.d' / '10-runtime.conf'
SNAPSHOT_DROPIN_PATH = (
    SYSTEMD_DIR / f'{SNAPSHOT_SERVICE}.d' / '10-runtime.conf'
)
SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_.@-]+$')
ARTIFACTS = (
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
        GX10_DIR / 'systemd' / SNAPSHOT_SERVICE,
        SYSTEMD_DIR / SNAPSHOT_SERVICE,
        0o644,
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
    'incidents',
    'reasoning_packets',
    'reasoning_model_versions',
    'reasoning_prompt_versions',
    'reasoning_runs',
    'reasoning_results',
}


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def service_identity():
    user = systemctl_value(REASONING_SERVICE, 'User')
    group = systemctl_value(REASONING_SERVICE, 'Group')
    if (
        SAFE_NAME_RE.fullmatch(user) is None
        or SAFE_NAME_RE.fullmatch(group) is None
    ):
        raise ValueError('managed result outbox identity differs')
    return user, group, pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid


def load_managed_database(path=MANAGED_CONFIG_PATH):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError('managed reasoning configuration differs')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('managed reasoning configuration differs') from exc
    if not isinstance(data, dict) or set(data) != {'database_path'}:
        raise ValueError('managed reasoning configuration differs')
    value = data['database_path']
    if not isinstance(value, str) or not value.startswith('/'):
        raise ValueError('managed reasoning database path differs')
    database = Path(value)
    if '..' in database.parts:
        raise ValueError('managed reasoning database path differs')
    return database


def validate_file(path, mode, *, source=None, uid=0, gid=0):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(
            'managed result outbox artifact is not a regular file'
        )
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ValueError('managed result outbox artifact metadata differs')
    if source is not None and Path(source).read_bytes() != path.read_bytes():
        raise ValueError('managed result outbox installed source differs')


def validate_directory(path, uid, gid, mode=0o700):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('managed result outbox directory differs')
    details = path.stat()
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ValueError('managed result outbox directory metadata differs')


def validate_database(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('managed result outbox database differs')
    connection = sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)
    try:
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('managed result outbox quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('managed result outbox foreign_key_check failed')
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not REQUIRED_TABLES <= tables:
            raise ValueError('managed result outbox schema differs')
        counts = connection.execute(
            '''
            SELECT
              (SELECT COUNT(*) FROM reasoning_results),
              (SELECT COUNT(*) FROM reasoning_runs WHERE status='SUCCEEDED'),
              (SELECT COUNT(*) FROM reasoning_runs WHERE status='STARTED'),
              (SELECT COUNT(*) FROM incidents)
            '''
        ).fetchone()
        if counts[0] != counts[1] or counts[2]:
            raise ValueError('managed result outbox reasoning state differs')
        return {
            'results': counts[0],
            'started': counts[2],
            'incidents': counts[3],
        }
    finally:
        connection.close()


def load_producer():
    path = LIBEXEC_DIR / 'build-result-outbox.py'
    specification = importlib.util.spec_from_file_location(
        'verified_installed_result_outbox', path
    )
    if specification is None or specification.loader is None:
        raise ValueError('managed result outbox producer cannot be loaded')
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_incident_producer():
    path = LIBEXEC_DIR / 'build-incident-outbox.py'
    specification = importlib.util.spec_from_file_location(
        'verified_installed_incident_outbox', path
    )
    if specification is None or specification.loader is None:
        raise ValueError('managed incident outbox producer cannot be loaded')
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def validate_private_runtime(
    database,
    snapshot_database,
    snapshot_root,
    root,
    ready,
    delivered,
):
    user, group, uid, gid = service_identity()
    validate_file(CONFIG_PATH, 0o640, uid=0, gid=gid)
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    if config != {
        'database_path': str(Path(snapshot_database)),
        'delivered_path': str(Path(delivered)),
        'ready_path': str(Path(ready)),
    }:
        raise ValueError('managed result outbox configuration differs')
    validate_file(SNAPSHOT_CONFIG_PATH, 0o640, uid=0, gid=gid)
    snapshot_config = json.loads(
        SNAPSHOT_CONFIG_PATH.read_text(encoding='utf-8')
    )
    if snapshot_config != {
        'snapshot_database_path': str(Path(snapshot_database)),
        'source_database_path': str(Path(database)),
    }:
        raise ValueError('managed outbox snapshot configuration differs')
    validate_file(DROPIN_PATH, 0o644)
    lines = DROPIN_PATH.read_text(encoding='utf-8').splitlines()
    if lines != [
        '[Service]',
        f'User={user}',
        f'Group={group}',
        'ReadWritePaths=',
        f'ReadWritePaths={root}',
    ]:
        raise ValueError('managed result outbox drop-in differs')
    validate_file(SNAPSHOT_DROPIN_PATH, 0o644)
    snapshot_lines = SNAPSHOT_DROPIN_PATH.read_text(
        encoding='utf-8'
    ).splitlines()
    if snapshot_lines != [
        '[Service]',
        f'User={user}',
        f'Group={group}',
        'ReadWritePaths=',
        f'ReadWritePaths={Path(database).parent}',
    ]:
        raise ValueError('managed outbox snapshot drop-in differs')
    validate_directory(root, uid, gid)
    validate_directory(snapshot_root, uid, gid)
    validate_directory(ready, uid, gid)
    validate_directory(delivered, uid, gid)
    allowed = {'ready', 'delivered'}
    lock = Path(root) / '.result-outbox.lock'
    if lock.exists() or lock.is_symlink():
        validate_file(lock, 0o600, uid=uid, gid=gid)
        allowed.add(lock.name)
    ledger = Path(root) / '.incident-export-v1.sqlite3'
    if ledger.exists() or ledger.is_symlink():
        validate_file(ledger, 0o600, uid=uid, gid=gid)
        allowed.add(ledger.name)
    if {path.name for path in Path(root).iterdir()} != allowed:
        raise ValueError('managed result outbox root entries differ')
    snapshot_allowed = set()
    snapshot_lock = Path(snapshot_root) / '.outbox-snapshot.lock'
    if snapshot_lock.exists() or snapshot_lock.is_symlink():
        validate_file(snapshot_lock, 0o600, uid=uid, gid=gid)
        snapshot_allowed.add(snapshot_lock.name)
    if Path(snapshot_database).exists() or Path(snapshot_database).is_symlink():
        validate_file(snapshot_database, 0o600, uid=uid, gid=gid)
        snapshot_allowed.add(Path(snapshot_database).name)
    if {path.name for path in Path(snapshot_root).iterdir()} != snapshot_allowed:
        raise ValueError('managed outbox snapshot root entries differ')
    database_details = Path(database).stat()
    if database_details.st_uid != uid or database_details.st_gid != gid:
        raise ValueError('managed result outbox database identity differs')
    return uid, gid


def validate_units(active):
    for unit in (SNAPSHOT_SERVICE, SERVICE, TIMER):
        if systemctl_value(unit, 'LoadState') != 'loaded':
            raise ValueError('managed result outbox unit is not loaded')
        if Path(systemctl_value(unit, 'FragmentPath')) != SYSTEMD_DIR / unit:
            raise ValueError('managed result outbox fragment path differs')
    if systemctl_value(SERVICE, 'DropInPaths') != str(DROPIN_PATH):
        raise ValueError('managed result outbox drop-in state differs')
    if systemctl_value(SNAPSHOT_SERVICE, 'DropInPaths') != str(
        SNAPSHOT_DROPIN_PATH
    ):
        raise ValueError('managed outbox snapshot drop-in state differs')
    if systemctl_value(TIMER, 'DropInPaths'):
        raise ValueError('managed result outbox timer drop-in differs')
    if systemctl_value(SERVICE, 'UnitFileState') != 'static':
        raise ValueError('managed result outbox service enablement differs')
    if systemctl_value(SNAPSHOT_SERVICE, 'UnitFileState') != 'static':
        raise ValueError('managed outbox snapshot enablement differs')
    expected = 'enabled' if active else 'disabled'
    if systemctl_value(TIMER, 'UnitFileState') != expected:
        raise ValueError('managed result outbox timer enablement differs')
    timer_state = systemctl_value(TIMER, 'ActiveState')
    service_state = systemctl_value(SERVICE, 'ActiveState')
    snapshot_state = systemctl_value(SNAPSHOT_SERVICE, 'ActiveState')
    if active:
        if (
            timer_state != 'active'
            or service_state == 'failed'
            or snapshot_state == 'failed'
        ):
            raise ValueError('managed result outbox active state differs')
        if systemctl_value(SERVICE, 'Result') != 'success':
            raise ValueError('managed result outbox service result differs')
    elif (
        timer_state != 'inactive'
        or service_state != 'inactive'
        or snapshot_state != 'inactive'
    ):
        raise ValueError('managed result outbox inactive state differs')
    if systemctl_value(SERVICE, 'NRestarts') != '0':
        raise ValueError('managed result outbox restart count differs')
    if systemctl_value(SNAPSHOT_SERVICE, 'NRestarts') != '0':
        raise ValueError('managed outbox snapshot restart count differs')
    if active and systemctl_value(SNAPSHOT_SERVICE, 'Result') != 'success':
        raise ValueError('managed outbox snapshot service result differs')


def inventory(directory, records, producer, incident_producer, uid, gid):
    result_names = set()
    incident_names = set()
    for path in sorted(Path(directory).iterdir(), key=lambda item: item.name):
        if (
            producer.PARTIAL_RE.fullmatch(path.name)
            or incident_producer.PARTIAL_RE.fullmatch(path.name)
        ):
            raise ValueError('managed result outbox has a stale partial')
        if path.is_symlink() or not path.is_file():
            raise ValueError('managed result outbox entry differs')
        details = path.stat()
        if (
            details.st_nlink != 1
            or details.st_uid != uid
            or details.st_gid != gid
            or stat.S_IMODE(details.st_mode) != 0o640
        ):
            raise ValueError('managed result outbox file differs')
        if producer.FINAL_RE.fullmatch(path.name):
            if (
                path.name not in records
                or path.read_bytes() not in records[path.name]
            ):
                raise ValueError('managed result outbox file differs')
            result_names.add(path.name)
        elif incident_producer.FINAL_RE.fullmatch(path.name):
            incident_producer.validate_file(path, expected_uid=uid)
            incident_names.add(path.name)
        else:
            raise ValueError('managed result outbox entry differs')
    return result_names, incident_names


def verify(
    database,
    root,
    ready,
    delivered,
    *,
    active,
    allow_populated_inactive=False,
):
    database = Path(database)
    snapshot_root = database.parent / 'outbox-snapshot'
    snapshot_database = snapshot_root / 'events.sqlite3'
    for source, target, mode in ARTIFACTS:
        validate_file(target, mode, source=source)
    source_state = validate_database(database)
    uid, gid = validate_private_runtime(
        database,
        snapshot_database,
        snapshot_root,
        root,
        ready,
        delivered,
    )
    validate_units(active)
    snapshot_exists = snapshot_database.exists() or snapshot_database.is_symlink()
    if active and not snapshot_exists:
        raise ValueError('managed outbox snapshot is absent')
    state = (
        validate_database(snapshot_database)
        if snapshot_exists
        else source_state
    )
    producer = load_producer()
    incident_producer = load_incident_producer()
    records = producer.load_records(
        snapshot_database if snapshot_exists else database
    )
    ready_names, incident_ready = inventory(
        ready, records, producer, incident_producer, uid, gid
    )
    delivered_names, incident_delivered = inventory(
        delivered, records, producer, incident_producer, uid, gid
    )
    if ready_names & delivered_names:
        raise ValueError('managed result outbox state is duplicated')
    if incident_ready & incident_delivered:
        raise ValueError('managed incident outbox state is duplicated')
    if (
        not active
        and not allow_populated_inactive
        and (
            ready_names or delivered_names
            or incident_ready or incident_delivered
        )
    ):
        raise ValueError('inactive managed result outbox is not empty')
    if len(ready_names) + len(delivered_names) > state['results']:
        raise ValueError('managed result outbox file count differs')
    return {
        'results': state['results'],
        'ready': len(ready_names),
        'delivered': len(delivered_names),
        'incidents': state['incidents'],
        'incident_ready': len(incident_ready),
        'incident_delivered': len(incident_delivered),
    }


def parse_args():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--installed', action='store_true')
    mode.add_argument('--active', action='store_true')
    parser.add_argument('--database', type=Path)
    parser.add_argument('--outbox-root', type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError('run the managed result outbox verifier as root')
        database = args.database or load_managed_database()
        root = args.outbox_root or database.parent / 'result-outbox'
        state = verify(
            database,
            root,
            root / 'ready',
            root / 'delivered',
            active=args.active,
        )
        print(
            'MANAGED_RESULT_OUTBOX_VERIFY schema=1 '
            f'results={state["results"]} ready={state["ready"]} '
            f'delivered={state["delivered"]} '
            f'active={"yes" if args.active else "no"}'
        )
        print('GX10_MANAGED_RESULT_OUTBOX_VERIFY=PASS')
        return 0
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_RESULT_OUTBOX_VERIFY=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
