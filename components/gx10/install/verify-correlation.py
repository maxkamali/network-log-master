#!/usr/bin/env python3
from __future__ import annotations

import argparse
import grp
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
SYSTEMD_DIR = Path('/etc/systemd/system')
DEFAULT_DATABASE = Path('/var/lib/network-log-gx10/state/events.sqlite3')
CONFIG_PATH = Path('/etc/network-log-gx10/correlation.json')
DROPIN_PATH = (
    SYSTEMD_DIR
    / 'network-log-gx10-correlation.service.d'
    / '10-runtime.conf'
)
SERVICE = 'network-log-gx10-correlation.service'
TIMER = 'network-log-gx10-correlation.timer'
PROJECTION_CURSOR = 'normalized_projection_v1_last_event_id'
INCIDENT_CURSOR = 'incident_engine_v1_last_event_id'
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
INCIDENT_OBJECTS = {
    'incidents',
    'incident_evidence',
    'incident_transitions',
    'idx_incidents_active_correlation',
    'idx_incidents_status_last_seen',
    'idx_incidents_entity',
    'idx_incident_evidence_time',
    'idx_incident_transitions_time',
    'incident_evidence_no_update',
    'incident_evidence_no_delete',
    'incident_transitions_no_update',
    'incident_transitions_no_delete',
}


def validate_file(path, mode, source=None, uid=0, gid=0):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('managed correlation artifact is not a regular file')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ValueError('managed correlation artifact metadata differs')
    if source is not None and Path(source).read_bytes() != path.read_bytes():
        raise ValueError('managed correlation installed source differs')


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def cursor_value(connection, key):
    row = connection.execute(
        'SELECT value FROM agent_state WHERE key = ?',
        (key,),
    ).fetchone()
    if row is None:
        return 0
    try:
        value = int(row[0])
    except (TypeError, ValueError) as exc:
        raise ValueError('managed correlation cursor is invalid') from exc
    if value < 0 or str(value) != row[0]:
        raise ValueError('managed correlation cursor is invalid')
    return value


def validate_database(path, require_caught_up):
    connection = sqlite3.connect(f'file:{Path(path)}?mode=ro', uri=True)
    try:
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('managed correlation quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('managed correlation foreign_key_check failed')
        objects = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%'"
            )
        }
        if not INCIDENT_OBJECTS <= objects:
            raise ValueError('managed correlation schema differs')
        recent_max = connection.execute(
            'SELECT COALESCE(MAX(id), 0) FROM recent_events'
        ).fetchone()[0]
        canonical_max = connection.execute(
            'SELECT COALESCE(MAX(event_id), 0) FROM event_enrichment '
            'WHERE classification_version = 4'
        ).fetchone()[0]
        projection_cursor = cursor_value(connection, PROJECTION_CURSOR)
        incident_cursor = cursor_value(connection, INCIDENT_CURSOR)
        projection_lag = recent_max - projection_cursor
        incident_lag = canonical_max - incident_cursor
        if (
            projection_lag < 0
            or incident_lag < 0
            or (require_caught_up and (projection_lag or incident_lag))
        ):
            raise ValueError('managed correlation watermark differs')
        duplicate_active = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT correlation_key FROM incidents
                WHERE status != 'RESOLVED'
                GROUP BY correlation_key HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        mismatched = connection.execute(
            """
            SELECT COUNT(*) FROM incidents AS i
            WHERE i.occurrence_count != (
                SELECT COUNT(*) FROM incident_evidence AS e
                WHERE e.incident_id = i.incident_id
            )
            OR i.repeat_count_total != (
                SELECT COALESCE(SUM(e.repeat_count), 0)
                FROM incident_evidence AS e
                WHERE e.incident_id = i.incident_id
            )
            """
        ).fetchone()[0]
        if duplicate_active or mismatched:
            raise ValueError('managed correlation incident invariant differs')
        return {
            'recent_max': recent_max,
            'projection_cursor': projection_cursor,
            'projection_lag': projection_lag,
            'canonical_rows': connection.execute(
                'SELECT COUNT(*) FROM event_enrichment '
                'WHERE classification_version = 4'
            ).fetchone()[0],
            'incident_cursor': incident_cursor,
            'incident_lag': incident_lag,
            'incidents': connection.execute(
                'SELECT COUNT(*) FROM incidents'
            ).fetchone()[0],
            'active': connection.execute(
                "SELECT COUNT(*) FROM incidents WHERE status != 'RESOLVED'"
            ).fetchone()[0],
            'evidence': connection.execute(
                'SELECT COUNT(*) FROM incident_evidence'
            ).fetchone()[0],
            'transitions': connection.execute(
                'SELECT COUNT(*) FROM incident_transitions'
            ).fetchone()[0],
        }
    finally:
        connection.close()


def validate_private_runtime(database):
    service_user = systemctl_value(SERVICE, 'User')
    service_group = systemctl_value(SERVICE, 'Group')
    if (
        not SAFE_NAME_RE.fullmatch(service_user)
        or not SAFE_NAME_RE.fullmatch(service_group)
    ):
        raise ValueError('private correlation identity is invalid')
    uid = pwd.getpwnam(service_user).pw_uid
    gid = grp.getgrnam(service_group).gr_gid
    validate_file(CONFIG_PATH, 0o640, uid=0, gid=gid)
    validate_file(DROPIN_PATH, 0o644)
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    if config != {'database_path': str(Path(database))}:
        raise ValueError('private correlation configuration differs')
    lines = DROPIN_PATH.read_text(encoding='utf-8').splitlines()
    if (
        len(lines) != 7
        or lines[0] != '[Unit]'
        or lines[1] != 'After='
        or not lines[2].startswith('After=')
        or lines[3] != ''
        or lines[4] != '[Service]'
        or lines[5] != f'User={service_user}'
        or lines[6] != f'Group={service_group}'
    ):
        raise ValueError('private correlation drop-in content differs')
    pipeline_unit = lines[2].removeprefix('After=')
    if not SAFE_NAME_RE.fullmatch(pipeline_unit):
        raise ValueError('private correlation pipeline identity is invalid')
    if systemctl_value(pipeline_unit, 'LoadState') != 'loaded':
        raise ValueError('private correlation pipeline unit is not loaded')
    if systemctl_value(SERVICE, 'DropInPaths') != str(DROPIN_PATH):
        raise ValueError('private correlation drop-in boundary differs')
    database_details = Path(database).stat()
    if database_details.st_uid != uid or database_details.st_gid != gid:
        raise ValueError('private correlation database identity differs')


def validate_systemd(active, private_runtime):
    for unit in (SERVICE, TIMER):
        if systemctl_value(unit, 'LoadState') != 'loaded':
            raise ValueError('managed correlation unit is not loaded')
        if Path(systemctl_value(unit, 'FragmentPath')) != SYSTEMD_DIR / unit:
            raise ValueError('managed correlation fragment path differs')
    if not private_runtime and (
        systemctl_value(SERVICE, 'DropInPaths')
        or systemctl_value(TIMER, 'DropInPaths')
    ):
        raise ValueError('managed correlation has an unexpected drop-in')
    if systemctl_value(SERVICE, 'UnitFileState') != 'static':
        raise ValueError('managed correlation service state differs')
    expected_timer = 'enabled' if active else 'disabled'
    if systemctl_value(TIMER, 'UnitFileState') != expected_timer:
        raise ValueError('managed correlation timer enablement differs')
    timer_state = systemctl_value(TIMER, 'ActiveState')
    service_state = systemctl_value(SERVICE, 'ActiveState')
    if active:
        if timer_state != 'active' or service_state == 'failed':
            raise ValueError('managed correlation active state differs')
        if systemctl_value(SERVICE, 'Result') != 'success':
            raise ValueError('managed correlation service result differs')
    elif timer_state != 'inactive' or service_state != 'inactive':
        raise ValueError('managed correlation installed state differs')


def parse_args():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--installed', action='store_true')
    mode.add_argument('--active', action='store_true')
    parser.add_argument('--database', type=Path, default=DEFAULT_DATABASE)
    parser.add_argument('--private-runtime', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError('run the managed correlation verifier as root')
        for source, target, mode in ARTIFACTS:
            validate_file(target, mode, source=source)
        validate_systemd(args.active, args.private_runtime)
        if args.private_runtime:
            validate_private_runtime(args.database)
        state = validate_database(args.database, args.active)
        print(
            'MANAGED_CORRELATION_VERIFY '
            f'recent_max_id={state["recent_max"]} '
            f'projection_cursor={state["projection_cursor"]} '
            f'projection_lag={state["projection_lag"]} '
            f'canonical_rows={state["canonical_rows"]} '
            f'incident_cursor={state["incident_cursor"]} '
            f'incident_lag={state["incident_lag"]} '
            f'incidents={state["incidents"]} active={state["active"]} '
            f'evidence={state["evidence"]} '
            f'transitions={state["transitions"]}'
        )
        label = 'ACTIVE' if args.active else 'INSTALLED'
        print(f'GX10_MANAGED_CORRELATION_{label}_VERIFY=PASS')
        return 0
    except (
        KeyError,
        OSError,
        sqlite3.Error,
        subprocess.CalledProcessError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
