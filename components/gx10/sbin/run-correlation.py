#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time
import types

try:
    from runtime_config import load_runtime_config
except ModuleNotFoundError as exc:
    if exc.name != 'runtime_config':
        raise
    load_runtime_config = None


CORRELATION_CONFIG_PATH = Path('/etc/network-log-gx10/correlation.json')


def load_database_path(path=CORRELATION_CONFIG_PATH):
    if load_runtime_config is not None:
        return load_runtime_config().database_path
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or set(data) != {'database_path'}:
        return None
    value = data.get('database_path')
    if not isinstance(value, str) or not value.startswith('/'):
        return None
    database = Path(value)
    if '..' in database.parts:
        return None
    return database


DB = load_database_path()
PROJECTION_PATH = Path(
    '/usr/local/libexec/network-log-gx10/enrich-events.py'
)
INCIDENT_PATH = Path(
    '/usr/local/libexec/network-log-gx10/incident-engine.py'
)
PROJECTION_SHA256 = (
    'f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079'
)
INCIDENT_SHA256 = (
    '40c287050bdf4cad4abb3e242c3433f73185a61197d8cf93c977c5d335a3c23f'
)
PROJECTION_CURSOR = 'normalized_projection_v1_last_event_id'
INCIDENT_CURSOR = 'incident_engine_v1_last_event_id'
MAX_CATCHUP_PASSES = 3


class CorrelationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_stage(path: Path, expected_hash: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise CorrelationError('managed correlation stage is not a regular file')
    details = path.stat()
    if details.st_nlink != 1 or stat.S_IMODE(details.st_mode) != 0o755:
        raise CorrelationError('managed correlation stage metadata differs')
    if sha256_file(path) != expected_hash:
        raise CorrelationError('managed correlation stage hash differs')


def load_stage(name: str, path: Path, database: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise CorrelationError('managed correlation stage cannot be loaded')
    module = importlib.util.module_from_spec(specification)
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        specification.loader.exec_module(module)
    finally:
        if previous is None:
            del sys.modules['runtime_config']
        else:
            sys.modules['runtime_config'] = previous
    if not callable(getattr(module, 'main', None)):
        raise CorrelationError('managed correlation stage has no main entrypoint')
    return module


def cursor_value(connection: sqlite3.Connection, key: str) -> int:
    row = connection.execute(
        'SELECT value FROM agent_state WHERE key = ?',
        (key,),
    ).fetchone()
    if row is None:
        return 0
    try:
        value = int(row[0])
    except (TypeError, ValueError) as exc:
        raise CorrelationError('managed correlation cursor is invalid') from exc
    if value < 0 or str(value) != row[0]:
        raise CorrelationError('managed correlation cursor is invalid')
    return value


def snapshot(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
    try:
        recent_max = connection.execute(
            'SELECT COALESCE(MAX(id), 0) FROM recent_events'
        ).fetchone()[0]
        canonical_max = connection.execute(
            'SELECT COALESCE(MAX(event_id), 0) FROM event_enrichment '
            'WHERE classification_version = 4'
        ).fetchone()[0]
        projection_cursor = cursor_value(connection, PROJECTION_CURSOR)
        incident_cursor = cursor_value(connection, INCIDENT_CURSOR)
        if projection_cursor > recent_max or incident_cursor > canonical_max:
            raise CorrelationError('managed correlation cursor exceeds input')
        return {
            'recent_max': recent_max,
            'projection_cursor': projection_cursor,
            'projection_lag': recent_max - projection_cursor,
            'canonical_rows': connection.execute(
                'SELECT COUNT(*) FROM event_enrichment '
                'WHERE classification_version = 4'
            ).fetchone()[0],
            'canonical_max': canonical_max,
            'incident_cursor': incident_cursor,
            'incident_lag': canonical_max - incident_cursor,
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


def acquire_lock(path: Path):
    descriptor = os.open(
        path,
        os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    details = os.fstat(descriptor)
    if (
        not stat.S_ISREG(details.st_mode)
        or details.st_nlink != 1
        or details.st_uid != os.geteuid()
        or stat.S_IMODE(details.st_mode) != 0o600
    ):
        os.close(descriptor)
        raise CorrelationError('managed correlation lock metadata differs')
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise CorrelationError('managed correlation cycle is already running') from exc
    return descriptor


def emit_summary(state: dict[str, int], duration_ms: int, passes: int) -> None:
    print(
        'MANAGED_CORRELATION '
        'schema=1 '
        f'result=pass passes={passes} duration_ms={duration_ms} '
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
    print('GX10_MANAGED_CORRELATION=PASS')


def main(
    database_path=None,
    projection_path=PROJECTION_PATH,
    incident_path=INCIDENT_PATH,
    lock_path=None,
) -> int:
    selected_database = Path(database_path) if database_path is not None else DB
    if selected_database is None:
        print('ERROR: managed correlation database is unavailable', file=sys.stderr)
        return 1
    projection_path = Path(projection_path)
    incident_path = Path(incident_path)
    selected_lock = (
        Path(lock_path)
        if lock_path is not None
        else selected_database.parent / 'managed-correlation.lock'
    )
    descriptor = None
    started = time.monotonic()
    try:
        validate_stage(projection_path, PROJECTION_SHA256)
        validate_stage(incident_path, INCIDENT_SHA256)
        descriptor = acquire_lock(selected_lock)
        projection = load_stage(
            'gx10_managed_projection',
            projection_path,
            selected_database,
        )
        incident = load_stage(
            'gx10_managed_incident',
            incident_path,
            selected_database,
        )
        passes = 0
        for passes in range(1, MAX_CATCHUP_PASSES + 1):
            if projection.main(selected_database) != 0:
                raise CorrelationError('canonical projection stage failed')
            if incident.main(selected_database) != 0:
                raise CorrelationError('incident stage failed')
            state = snapshot(selected_database)
            if state['projection_lag'] == 0 and state['incident_lag'] == 0:
                break
        else:
            raise CorrelationError('managed correlation did not reach its watermark')
        duration_ms = int((time.monotonic() - started) * 1000)
        emit_summary(state, duration_ms, passes)
        return 0
    except (CorrelationError, OSError, sqlite3.Error) as exc:
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f'{timestamp} ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_CORRELATION=FAIL', file=sys.stderr)
        return 1
    finally:
        if descriptor is not None:
            os.close(descriptor)


if __name__ == '__main__':
    sys.exit(main())
