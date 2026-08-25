#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time


PRODUCER_SCHEMA = 'network-log-incident-state'
PRODUCER_VERSION = 1
RECORD_TYPE = 'incident_lifecycle'
LEDGER_NAME = '.incident-export-v1.sqlite3'
LOCK_NAME = '.result-outbox.lock'
MAX_FILE_BYTES = 256 * 1024
MAX_RECORDS = 100
FINAL_RE = re.compile(r'^incident-state-v1-[0-9a-f]{32}\.jsonl$')
PARTIAL_RE = re.compile(
    r'^\.incident-state-v1-[0-9a-f]{32}\.jsonl\.tmp-[1-9][0-9]*-[0-9]+$'
)
STATUSES = {'CANDIDATE', 'OPEN', 'RECOVERING', 'RESOLVED'}
REQUIRED_COLUMNS = {
    'incident_id',
    'status',
    'event_family',
    'protocol',
    'entity_type',
    'entity_key',
    'severity',
    'first_seen',
    'last_seen',
    'occurrence_count',
    'repeat_count_total',
    'observation_state_changes',
    'last_observation_state',
    'opened_at',
    'recovering_at',
    'resolved_at',
    'engine_version',
    'updated_at',
}
RECORD_KEYS = {
    'body',
    'device',
    'engine_version',
    'entity_name',
    'entity_type',
    'event_family',
    'first_seen',
    'incident_id',
    'interface_flap',
    'last_observation_state',
    'last_seen',
    'lifecycle_status',
    'occurrence_count',
    'opened_at',
    'producer_schema',
    'producer_version',
    'protocol',
    'recovering_at',
    'repeat_count_total',
    'resolved_at',
    'severity',
    'snapshot_id',
    'snapshot_version',
    'state_change_count',
    'timestamp',
    'title',
    'type',
}


class IncidentOutboxError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    )


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def valid_timestamp(value, *, nullable=False):
    if nullable and value is None:
        return True
    if not isinstance(value, str) or not value or len(value) > 64:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def timestamp_version(value):
    if not valid_timestamp(value):
        raise IncidentOutboxError('incident update timestamp is invalid')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return int(parsed.timestamp() * 1000)


def bounded_text(value, maximum, label, *, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise IncidentOutboxError(f'{label} is invalid')


def entity_parts(entity_key):
    bounded_text(entity_key, 4096, 'incident entity key')
    parts = [part.strip() for part in entity_key.split('|')]
    if len(parts) < 2 or not parts[1]:
        raise IncidentOutboxError('incident device projection differs')
    device = parts[1]
    entity_name = '|'.join(part for part in parts[2:] if part)
    return device, entity_name


def map_incident(row):
    for field in REQUIRED_COLUMNS:
        if field not in row.keys():
            raise IncidentOutboxError('incident schema differs')
    status = row['status']
    if status not in STATUSES:
        raise IncidentOutboxError('incident lifecycle status differs')
    for field, maximum in (
        ('incident_id', 256),
        ('event_family', 128),
        ('protocol', 128),
        ('entity_type', 128),
        ('severity', 64),
    ):
        bounded_text(row[field], maximum, f'incident {field}')
    for field in ('first_seen', 'last_seen', 'updated_at'):
        if not valid_timestamp(row[field]):
            raise IncidentOutboxError(f'incident {field} is invalid')
    for field in ('opened_at', 'recovering_at', 'resolved_at'):
        if not valid_timestamp(row[field], nullable=True):
            raise IncidentOutboxError(f'incident {field} is invalid')
    if (status == 'RESOLVED') != (row['resolved_at'] is not None):
        raise IncidentOutboxError('incident resolution timestamp differs')
    if status == 'RECOVERING' and row['recovering_at'] is None:
        raise IncidentOutboxError('incident recovery timestamp differs')
    for field in (
        'occurrence_count',
        'repeat_count_total',
        'observation_state_changes',
        'engine_version',
    ):
        value = row[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise IncidentOutboxError(f'incident {field} is invalid')
    if row['occurrence_count'] < 1 or row['repeat_count_total'] < 1:
        raise IncidentOutboxError('incident counters differ')
    device, entity_name = entity_parts(row['entity_key'])
    bounded_text(device, 256, 'incident device')
    if len(entity_name) > 512:
        raise IncidentOutboxError('incident entity name is invalid')
    last_state = row['last_observation_state']
    if last_state is not None:
        bounded_text(last_state, 128, 'incident observation state')
    source = {
        field: row[field]
        for field in sorted(REQUIRED_COLUMNS)
    }
    snapshot_digest = sha256_bytes(canonical_json(source).encode('utf-8'))
    label = entity_name or row['entity_type']
    title = f'{row["event_family"]}: {label}'
    record = {
        'body': 'Deterministic incident lifecycle state.',
        'device': device,
        'engine_version': row['engine_version'],
        'entity_name': entity_name,
        'entity_type': row['entity_type'],
        'event_family': row['event_family'],
        'first_seen': row['first_seen'],
        'incident_id': row['incident_id'],
        'interface_flap': (
            row['entity_type'].casefold() == 'interface'
            and row['observation_state_changes'] > 0
        ),
        'last_observation_state': last_state or '',
        'last_seen': row['last_seen'],
        'lifecycle_status': status,
        'occurrence_count': row['occurrence_count'],
        'opened_at': row['opened_at'],
        'producer_schema': PRODUCER_SCHEMA,
        'producer_version': PRODUCER_VERSION,
        'protocol': row['protocol'],
        'recovering_at': row['recovering_at'],
        'repeat_count_total': row['repeat_count_total'],
        'resolved_at': row['resolved_at'],
        'severity': row['severity'],
        'snapshot_id': f'state-v1-{snapshot_digest[:32]}',
        'snapshot_version': timestamp_version(row['updated_at']),
        'state_change_count': row['observation_state_changes'],
        'timestamp': row['updated_at'],
        'title': title[:512],
        'type': RECORD_TYPE,
    }
    validate_record(record)
    data = (canonical_json(record) + '\n').encode('utf-8')
    return snapshot_digest, data


def validate_record(record):
    if not isinstance(record, dict) or set(record) != RECORD_KEYS:
        raise IncidentOutboxError('incident lifecycle record keys differ')
    if (
        record['producer_schema'] != PRODUCER_SCHEMA
        or record['producer_version'] != PRODUCER_VERSION
        or record['type'] != RECORD_TYPE
        or record['lifecycle_status'] not in STATUSES
        or type(record['interface_flap']) is not bool
    ):
        raise IncidentOutboxError('incident lifecycle record identity differs')
    for field, maximum in (
        ('body', 65536),
        ('device', 256),
        ('entity_type', 128),
        ('event_family', 128),
        ('incident_id', 256),
        ('lifecycle_status', 64),
        ('protocol', 128),
        ('severity', 64),
        ('snapshot_id', 64),
        ('title', 512),
    ):
        bounded_text(record[field], maximum, f'lifecycle {field}')
    for field, maximum in (
        ('entity_name', 512),
        ('last_observation_state', 128),
    ):
        value = record[field]
        if not isinstance(value, str) or len(value) > maximum:
            raise IncidentOutboxError(f'lifecycle {field} is invalid')
    for field in ('timestamp', 'first_seen', 'last_seen'):
        if not valid_timestamp(record[field]):
            raise IncidentOutboxError(f'lifecycle {field} is invalid')
    for field in ('opened_at', 'recovering_at', 'resolved_at'):
        if not valid_timestamp(record[field], nullable=True):
            raise IncidentOutboxError(f'lifecycle {field} is invalid')
    if (
        (record['lifecycle_status'] == 'RESOLVED')
        != (record['resolved_at'] is not None)
    ):
        raise IncidentOutboxError('lifecycle resolution timestamp differs')
    if (
        record['lifecycle_status'] == 'RECOVERING'
        and record['recovering_at'] is None
    ):
        raise IncidentOutboxError('lifecycle recovery timestamp differs')
    for field in (
        'engine_version',
        'occurrence_count',
        'repeat_count_total',
        'snapshot_version',
        'state_change_count',
    ):
        value = record[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise IncidentOutboxError(f'lifecycle {field} is invalid')
    if record['occurrence_count'] < 1 or record['repeat_count_total'] < 1:
        raise IncidentOutboxError('lifecycle counters differ')


def load_incidents(database):
    database = Path(database).resolve(strict=True)
    connection = sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise IncidentOutboxError('incident outbox quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise IncidentOutboxError('incident outbox foreign_key_check failed')
        columns = {
            row[1]
            for row in connection.execute('PRAGMA table_info(incidents)')
        }
        if not REQUIRED_COLUMNS <= columns:
            raise IncidentOutboxError('incident outbox database schema differs')
        records = {}
        for row in connection.execute(
            'SELECT * FROM incidents ORDER BY incident_id'
        ):
            digest, data = map_incident(row)
            if row['incident_id'] in records:
                raise IncidentOutboxError('incident identity is duplicated')
            records[row['incident_id']] = (digest, data)
        return records
    finally:
        connection.close()


def validate_directory(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise IncidentOutboxError('incident outbox is not a directory')
    details = path.stat()
    if details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) & 0o022:
        raise IncidentOutboxError('incident outbox directory metadata differs')


def acquire_lock(root):
    path = Path(root) / LOCK_NAME
    descriptor = os.open(
        path,
        os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0),
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
        raise IncidentOutboxError('incident outbox lock metadata differs')
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise IncidentOutboxError('result outbox is already locked') from exc
    return descriptor


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_ledger(path):
    details = Path(path).lstat()
    if (
        not stat.S_ISREG(details.st_mode)
        or details.st_nlink != 1
        or details.st_uid != os.geteuid()
        or stat.S_IMODE(details.st_mode) != 0o600
    ):
        raise IncidentOutboxError('incident export ledger metadata differs')


def open_ledger(root):
    path = Path(root) / LEDGER_NAME
    try:
        validate_ledger(path)
    except FileNotFoundError:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
            0o600,
        )
        os.close(descriptor)
        fsync_directory(root)
        validate_ledger(path)
    connection = sqlite3.connect(path, timeout=0)
    connection.execute('PRAGMA busy_timeout=0')
    connection.execute('PRAGMA journal_mode=DELETE')
    connection.execute('PRAGMA synchronous=FULL')
    connection.executescript(
        '''
        CREATE TABLE IF NOT EXISTS current_exports (
            incident_id TEXT PRIMARY KEY,
            snapshot_digest TEXT NOT NULL,
            exported_at TEXT NOT NULL
        ) WITHOUT ROWID;
        '''
    )
    if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        connection.close()
        raise IncidentOutboxError('incident export ledger quick_check failed')
    return connection


def output_name(data):
    return f'incident-state-v1-{sha256_bytes(data)[:32]}.jsonl'


def validate_file(path, *, expected_uid=None):
    path = Path(path)
    if expected_uid is None:
        expected_uid = os.geteuid()
    if path.is_symlink() or not path.is_file() or not FINAL_RE.fullmatch(path.name):
        raise IncidentOutboxError('incident outbox file differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != expected_uid
        or stat.S_IMODE(details.st_mode) != 0o640
        or details.st_size <= 0
        or details.st_size > MAX_FILE_BYTES
    ):
        raise IncidentOutboxError('incident outbox file metadata differs')
    data = path.read_bytes()
    if output_name(data) != path.name:
        raise IncidentOutboxError('incident outbox filename digest differs')
    lines = data.decode('utf-8').splitlines()
    if not 1 <= len(lines) <= MAX_RECORDS or data.count(b'\n') != len(lines):
        raise IncidentOutboxError('incident outbox record count differs')
    incident_ids = set()
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IncidentOutboxError('incident outbox JSON differs') from exc
        if canonical_json(record) != line:
            raise IncidentOutboxError('incident outbox JSON is not canonical')
        validate_record(record)
        if record['incident_id'] in incident_ids:
            raise IncidentOutboxError('incident outbox batch duplicates an incident')
        incident_ids.add(record['incident_id'])
    return data


def inventory(directory, *, allow_partials):
    names = set()
    for path in sorted(Path(directory).iterdir(), key=lambda item: item.name):
        if allow_partials and PARTIAL_RE.fullmatch(path.name):
            continue
        if FINAL_RE.fullmatch(path.name):
            validate_file(path)
            names.add(path.name)
    return names


def recover_partials(directory):
    removed = 0
    for path in sorted(Path(directory).iterdir(), key=lambda item: item.name):
        if not PARTIAL_RE.fullmatch(path.name):
            continue
        details = path.lstat()
        if (
            not stat.S_ISREG(details.st_mode)
            or details.st_nlink != 1
            or details.st_uid != os.geteuid()
            or stat.S_IMODE(details.st_mode) not in {0o600, 0o640}
        ):
            raise IncidentOutboxError('incident outbox partial metadata differs')
        path.unlink()
        removed += 1
    if removed:
        fsync_directory(directory)
    return removed


def batches(changed):
    result = []
    current = []
    current_size = 0
    for incident_id, digest, data in changed:
        if len(data) > MAX_FILE_BYTES:
            raise IncidentOutboxError('incident lifecycle record is too large')
        if current and (
            len(current) >= MAX_RECORDS
            or current_size + len(data) > MAX_FILE_BYTES
        ):
            result.append(current)
            current = []
            current_size = 0
        current.append((incident_id, digest, data))
        current_size += len(data)
    if current:
        result.append(current)
    return result


def publish(directory, data):
    name = output_name(data)
    target = Path(directory) / name
    if target.exists() or target.is_symlink():
        if validate_file(target) != data:
            raise IncidentOutboxError('incident outbox target differs')
        return name, False
    temporary = Path(directory) / (
        f'.{name}.tmp-{os.getpid()}-{time.time_ns()}'
    )
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
        os.chmod(temporary, 0o640)
        os.replace(temporary, target)
        fsync_directory(directory)
        validate_file(target)
        return name, True
    finally:
        if temporary.exists():
            temporary.unlink()


def build(database, ready, delivered):
    database = Path(database)
    ready = Path(ready)
    delivered = Path(delivered)
    if database.is_symlink() or not database.is_file():
        raise IncidentOutboxError('incident outbox database differs')
    for directory in (ready, delivered):
        validate_directory(directory)
    database = database.resolve(strict=True)
    ready = ready.resolve(strict=True)
    delivered = delivered.resolve(strict=True)
    if ready == delivered or ready.parent != delivered.parent:
        raise IncidentOutboxError('incident outbox directory layout differs')
    root = ready.parent
    validate_directory(root)
    descriptor = acquire_lock(root)
    ledger = None
    try:
        recovered = recover_partials(ready)
        ready_names = inventory(ready, allow_partials=True)
        delivered_names = inventory(delivered, allow_partials=False)
        if ready_names & delivered_names:
            raise IncidentOutboxError('incident outbox state is duplicated')
        incidents = load_incidents(database)
        ledger = open_ledger(root)
        exported = dict(
            ledger.execute(
                'SELECT incident_id, snapshot_digest FROM current_exports'
            )
        )
        unknown = set(exported) - set(incidents)
        if unknown:
            raise IncidentOutboxError('incident export ledger has unknown incidents')
        changed = [
            (incident_id, digest, data)
            for incident_id, (digest, data) in incidents.items()
            if exported.get(incident_id) != digest
        ]
        built_batches = batches(changed)
        ledger.execute('BEGIN IMMEDIATE')
        created = 0
        reused = 0
        written_bytes = 0
        for batch in built_batches:
            data = b''.join(item[2] for item in batch)
            name, was_created = publish(ready, data)
            created += int(was_created)
            reused += int(not was_created)
            written_bytes += len(data) if was_created else 0
            if name in delivered_names:
                raise IncidentOutboxError('incident batch already delivered before ledger update')
        exported_at = datetime.now().astimezone().isoformat()
        ledger.executemany(
            '''
            INSERT INTO current_exports (
                incident_id, snapshot_digest, exported_at
            ) VALUES (?, ?, ?)
            ON CONFLICT(incident_id) DO UPDATE SET
                snapshot_digest=excluded.snapshot_digest,
                exported_at=excluded.exported_at
            ''',
            [
                (incident_id, digest, exported_at)
                for incident_id, digest, _ in changed
            ],
        )
        ledger.commit()
        return {
            'incidents': len(incidents),
            'changed': len(changed),
            'batches': len(built_batches),
            'created': created,
            'reused': reused,
            'ready': len(ready_names) + created,
            'delivered': len(delivered_names),
            'recovered': recovered,
            'written_bytes': written_bytes,
        }
    except Exception:
        if ledger is not None:
            ledger.rollback()
        raise
    finally:
        if ledger is not None:
            ledger.close()
        os.close(descriptor)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Build deterministic incident-lifecycle outbox batches'
    )
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--delivered', type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        state = build(args.database, args.ready, args.delivered)
        print(
            'INCIDENT_OUTBOX schema=1 '
            f'incidents={state["incidents"]} changed={state["changed"]} '
            f'batches={state["batches"]} created={state["created"]} '
            f'reused={state["reused"]} ready={state["ready"]} '
            f'delivered={state["delivered"]} recovered={state["recovered"]} '
            f'written_bytes={state["written_bytes"]}'
        )
        print('GX10_INCIDENT_OUTBOX=PASS')
        return 0
    except (OSError, sqlite3.Error, IncidentOutboxError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_INCIDENT_OUTBOX=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
