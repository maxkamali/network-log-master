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
CONFIG_PATH = CONFIG_DIR / 'managed-reasoning.json'
SERVICE = 'network-log-gx10-reasoning.service'
TIMER = 'network-log-gx10-reasoning.timer'
DROPIN_PATH = SYSTEMD_DIR / f'{SERVICE}.d' / '10-runtime.conf'
PROJECTION_CURSOR = 'normalized_projection_v1_last_event_id'
INCIDENT_CURSOR = 'incident_engine_v1_last_event_id'
SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_.@-]+$')
ARTIFACTS = (
    (
        GX10_DIR / 'sbin' / 'run-managed-reasoning.py',
        LIBEXEC_DIR / 'run-managed-reasoning.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-managed-ai.py',
        LIBEXEC_DIR / 'run-managed-ai.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'triage-uncovered-events.py',
        LIBEXEC_DIR / 'triage-uncovered-events.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'incident-engine.py',
        LIBEXEC_DIR / 'incident-engine.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'build-reasoning-packets.py',
        LIBEXEC_DIR / 'build-reasoning-packets.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'build-incident-outbox.py',
        LIBEXEC_DIR / 'build-incident-outbox.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-correlation.py',
        LIBEXEC_DIR / 'run-correlation.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-incident-outbox.py',
        LIBEXEC_DIR / 'run-incident-outbox.py',
        0o755,
    ),
    (
        GX10_DIR / 'config' / 'triage-runtime-v1.json',
        CONFIG_DIR / 'triage-runtime-v1.json',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'uncovered-event-triage-v1.txt',
        CONFIG_DIR / 'uncovered-event-triage-v1.txt',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'uncovered-event-triage-output-v1.json',
        CONFIG_DIR / 'uncovered-event-triage-output-v1.json',
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
DEPENDENCIES = (
    (
        GX10_DIR / 'sbin' / 'run-local-reasoning.py',
        LIBEXEC_DIR / 'run-local-reasoning.py',
        0o755,
    ),
    (
        GX10_DIR / 'config' / 'reasoning-runtime-v2.json',
        CONFIG_DIR / 'reasoning-runtime-v2.json',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'incident-assessment-v2.txt',
        CONFIG_DIR / 'incident-assessment-v2.txt',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'incident-assessment-output-v2.json',
        CONFIG_DIR / 'incident-assessment-output-v2.json',
        0o644,
    ),
)


def load_runner():
    path = GX10_DIR / 'sbin' / 'run-managed-reasoning.py'
    specification = importlib.util.spec_from_file_location(
        'managed_reasoning_verifier_runner', path
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


RUNNER = load_runner()


def validate_file(path, mode, source=None, uid=0, gid=0):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(
            'managed reasoning artifact is not a regular file'
        )
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ValueError('managed reasoning artifact metadata differs')
    if source is not None and Path(source).read_bytes() != path.read_bytes():
        raise ValueError('managed reasoning installed source differs')


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
        'SELECT value FROM agent_state WHERE key = ?', (key,)
    ).fetchone()
    if row is None:
        return 0
    try:
        value = int(row[0])
    except (TypeError, ValueError) as exc:
        raise ValueError('managed reasoning cursor is invalid') from exc
    if value < 0 or str(value) != row[0]:
        raise ValueError('managed reasoning cursor is invalid')
    return value


def validate_database(path, require_caught_up=True):
    state = RUNNER.snapshot(Path(path))
    if state['started']:
        raise ValueError(
            'managed reasoning has an unreconciled STARTED reservation'
        )
    connection = sqlite3.connect(f'file:{Path(path)}?mode=ro', uri=True)
    try:
        recent = connection.execute(
            'SELECT COALESCE(MAX(id), 0) FROM recent_events'
        ).fetchone()[0]
        canonical = connection.execute(
            'SELECT COALESCE(MAX(event_id), 0) FROM event_enrichment '
            'WHERE classification_version = 4'
        ).fetchone()[0]
        projection = cursor_value(connection, PROJECTION_CURSOR)
        incident = cursor_value(connection, INCIDENT_CURSOR)
        projection_lag = recent - projection
        incident_lag = canonical - incident
        triage_tables = {
            'triage_signatures', 'triage_batches', 'triage_runs',
            'triage_decisions', 'event_detection_overrides',
            'triage_incident_summaries', 'learned_detection_rules',
        }
        present = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not triage_tables <= present:
            raise ValueError('managed AI triage schema differs')
        triage_cursor = cursor_value(connection, 'ai_triage_v1_last_event_id')
        if triage_cursor > incident:
            raise ValueError('managed AI triage cursor differs')
        if (
            projection_lag < 0
            or incident_lag < 0
            or (require_caught_up and (projection_lag or incident_lag))
        ):
            raise ValueError(
                'managed reasoning deterministic watermark differs'
            )
        state.update(
            {
                'recent': recent,
                'projection_lag': projection_lag,
                'incident_lag': incident_lag,
                'triage_lag': incident - triage_cursor,
            }
        )
        return state
    finally:
        connection.close()


def validate_private_runtime(database):
    service_user = systemctl_value(SERVICE, 'User')
    service_group = systemctl_value(SERVICE, 'Group')
    if (
        not SAFE_NAME_RE.fullmatch(service_user)
        or not SAFE_NAME_RE.fullmatch(service_group)
    ):
        raise ValueError('private reasoning identity is invalid')
    uid = pwd.getpwnam(service_user).pw_uid
    gid = grp.getgrnam(service_group).gr_gid
    validate_file(CONFIG_PATH, 0o640, uid=0, gid=gid)
    validate_file(DROPIN_PATH, 0o644)
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    if config != {'database_path': str(Path(database))}:
        raise ValueError('private reasoning configuration differs')
    lines = DROPIN_PATH.read_text(encoding='utf-8').splitlines()
    writable_directory = str(Path(database).parent)
    if (
        len(lines) != 9
        or lines[0] != '[Unit]'
        or lines[1] != 'After='
        or not lines[2].startswith('After=')
        or len(lines[2].removeprefix('After=').split()) != 2
        or lines[3] != ''
        or lines[4] != '[Service]'
        or lines[5] != f'User={service_user}'
        or lines[6] != f'Group={service_group}'
        or lines[7] != 'ReadWritePaths='
        or lines[8] != f'ReadWritePaths={writable_directory}'
    ):
        raise ValueError('private reasoning drop-in content differs')
    correlation_unit, ollama_unit = (
        lines[2].removeprefix('After=').split()
    )
    for unit in (correlation_unit, ollama_unit):
        if (
            not SAFE_NAME_RE.fullmatch(unit)
            or systemctl_value(unit, 'LoadState') != 'loaded'
        ):
            raise ValueError(
                'private reasoning dependency state differs'
            )
    if (
        systemctl_value(correlation_unit, 'ActiveState') == 'failed'
        or not correlation_unit.endswith('.service')
    ):
        raise ValueError('private correlation dependency differs')
    correlation_timer = correlation_unit.removesuffix('.service') + '.timer'
    if (
        systemctl_value(correlation_timer, 'LoadState') != 'loaded'
        or systemctl_value(correlation_timer, 'UnitFileState') != 'enabled'
        or systemctl_value(correlation_timer, 'ActiveState') != 'active'
        or systemctl_value(ollama_unit, 'ActiveState') != 'active'
    ):
        raise ValueError(
            'private reasoning dependency state differs'
        )
    if systemctl_value(SERVICE, 'DropInPaths') != str(DROPIN_PATH):
        raise ValueError('private reasoning drop-in boundary differs')
    database_details = Path(database).stat()
    if (
        database_details.st_uid != uid
        or database_details.st_gid != gid
        or stat.S_IMODE(database_details.st_mode) != 0o640
    ):
        raise ValueError('private reasoning database identity differs')


def validate_systemd(active, private_runtime):
    for unit in (SERVICE, TIMER):
        if systemctl_value(unit, 'LoadState') != 'loaded':
            raise ValueError('managed reasoning unit is not loaded')
        if Path(systemctl_value(unit, 'FragmentPath')) != SYSTEMD_DIR / unit:
            raise ValueError(
                'managed reasoning fragment path differs'
            )
    if not private_runtime and (
        systemctl_value(SERVICE, 'DropInPaths')
        or systemctl_value(TIMER, 'DropInPaths')
    ):
        raise ValueError('managed reasoning has an unexpected drop-in')
    if systemctl_value(SERVICE, 'UnitFileState') != 'static':
        raise ValueError('managed reasoning service state differs')
    expected_timer = 'enabled' if active else 'disabled'
    if systemctl_value(TIMER, 'UnitFileState') != expected_timer:
        raise ValueError('managed reasoning timer enablement differs')
    timer_state = systemctl_value(TIMER, 'ActiveState')
    service_state = systemctl_value(SERVICE, 'ActiveState')
    if active:
        if timer_state != 'active' or service_state == 'failed':
            raise ValueError('managed reasoning active state differs')
        if systemctl_value(SERVICE, 'Result') != 'success':
            raise ValueError('managed reasoning service result differs')
    elif timer_state != 'inactive' or service_state != 'inactive':
        raise ValueError('managed reasoning installed state differs')
    if systemctl_value(SERVICE, 'NRestarts') != '0':
        raise ValueError('managed reasoning restart count differs')


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
            raise ValueError('run the managed reasoning verifier as root')
        for source, target, mode in (*DEPENDENCIES, *ARTIFACTS):
            validate_file(target, mode, source=source)
        validate_systemd(args.active, args.private_runtime)
        if args.private_runtime:
            validate_private_runtime(args.database)
        state = validate_database(args.database)
        print(
            'MANAGED_REASONING_VERIFY '
            f'recent_max_id={state["recent"]} '
            f'projection_lag={state["projection_lag"]} '
            f'incident_lag={state["incident_lag"]} '
            f'triage_lag={state["triage_lag"]} '
            f'packets={state["packets"]} pending={state["pending"]} '
            f'model_versions={state["model_versions"]} '
            f'prompt_versions={state["prompt_versions"]} '
            f'runs={state["runs"]} started={state["started"]} '
            f'succeeded={state["succeeded"]} failures={state["failures"]} '
            f'results={state["results"]}'
        )
        label = 'ACTIVE' if args.active else 'INSTALLED'
        print(f'GX10_MANAGED_REASONING_{label}_VERIFY=PASS')
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
