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


PRODUCER_SCHEMA = 'network-log-ai-result'
PRODUCER_VERSION = 1
RESULT_TYPE = 'incident_assessment'
MAX_FILE_BYTES = 256 * 1024
LOCK_NAME = '.result-outbox.lock'
FINAL_RE = re.compile(r'^ai-result-v1-[0-9a-f]{32}\.jsonl$')
INCIDENT_FINAL_RE = re.compile(
    r'^incident-state-v[12]-[0-9a-f]{32}\.jsonl$'
)
INCIDENT_PARTIAL_RE = re.compile(
    r'^\.incident-state-v[12]-[0-9a-f]{32}\.jsonl\.tmp-[1-9][0-9]*-[0-9]+$'
)
PARTIAL_RE = re.compile(
    r'^\.ai-result-v1-[0-9a-f]{32}\.jsonl\.tmp-[1-9][0-9]*-[0-9]+$'
)
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
EXPECTED_RESULT_KEYS = {
    'schema',
    'schema_version',
    'packet_id',
    'incident_id',
    'disposition',
    'severity',
    'confidence',
    'title',
    'summary',
    'likely_causes',
    'recommended_actions',
    'tags',
}
REQUIRED_TABLES = {
    'reasoning_packets',
    'reasoning_model_versions',
    'reasoning_prompt_versions',
    'reasoning_runs',
    'reasoning_results',
}


class OutboxError(ValueError):
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


def sha256_text(value):
    return sha256_bytes(value.encode('utf-8'))


def parse_canonical_object(value, label):
    if not isinstance(value, str):
        raise OutboxError(f'{label} is invalid')
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise OutboxError(f'{label} is invalid') from exc
    if not isinstance(parsed, dict) or canonical_json(parsed) != value:
        raise OutboxError(f'{label} is not canonical')
    return parsed


def valid_timestamp(value):
    if not isinstance(value, str) or not value or len(value) > 64:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def parse_timestamp(value, label):
    if not valid_timestamp(value):
        raise OutboxError(f'{label} is invalid')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate_string(value, maximum, label, *, required=True):
    if (
        not isinstance(value, str)
        or (required and not value.strip())
        or len(value) > maximum
    ):
        raise OutboxError(f'{label} is invalid')


def validate_result(result, row):
    if set(result) != EXPECTED_RESULT_KEYS:
        raise OutboxError('reasoning result keys differ')
    if (
        result['schema'] != 'gx10-incident-assessment'
        or type(result['schema_version']) is not int
        or result['schema_version'] != row['schema_version']
        or result['packet_id'] != row['packet_id']
        or result['incident_id'] != row['incident_id']
        or result['disposition'] != row['disposition']
        or result['severity'] != row['severity']
        or result['confidence'] != row['confidence']
        or result['title'] != row['title']
        or result['summary'] != row['summary']
    ):
        raise OutboxError('reasoning result columns differ')
    validate_string(result['packet_id'], 256, 'result packet ID')
    validate_string(result['incident_id'], 256, 'result incident ID')
    validate_string(result['disposition'], 64, 'result disposition')
    validate_string(result['severity'], 64, 'result severity')
    validate_string(result['title'], 512, 'result title')
    validate_string(result['summary'], 65536, 'result summary')
    if (
        isinstance(result['confidence'], bool)
        or not isinstance(result['confidence'], int)
        or not 0 <= result['confidence'] <= 100
        or not isinstance(result['likely_causes'], list)
        or not isinstance(result['recommended_actions'], list)
        or not isinstance(result['tags'], list)
        or len(result['tags']) > 64
    ):
        raise OutboxError('reasoning result structure differs')
    for tag in result['tags']:
        validate_string(tag, 128, 'result tag', required=False)


def validate_packet(packet, row):
    incident = packet.get('incident')
    if (
        packet.get('schema') != 'gx10-incident-reasoning-packet'
        or packet.get('packet_id') != row['packet_id']
        or not isinstance(incident, dict)
        or incident.get('incident_id') != row['incident_id']
        or not valid_timestamp(incident.get('first_seen'))
        or not valid_timestamp(incident.get('last_seen'))
        or isinstance(incident.get('occurrence_count'), bool)
        or not isinstance(incident.get('occurrence_count'), int)
        or not 0 <= incident['occurrence_count'] <= 4294967295
    ):
        raise OutboxError('reasoning packet projection fields differ')
    return incident


def incident_device(incident):
    entity_key = incident.get('entity_key')
    validate_string(entity_key, 4096, 'reasoning packet entity key')
    parts = entity_key.split('|')
    if len(parts) < 2:
        raise OutboxError('reasoning packet device projection differs')
    device = parts[1].strip()
    validate_string(device, 256, 'reasoning packet device')
    return device


def output_name(run_id):
    validate_string(run_id, 128, 'reasoning run ID')
    return f'ai-result-v1-{sha256_text(run_id)[:32]}.jsonl'


def map_row(row):
    if row['run_status'] != 'SUCCEEDED':
        raise OutboxError('result run is not successful')
    started_at = parse_timestamp(row['started_at'], 'run start timestamp')
    completed_at = parse_timestamp(row['completed_at'], 'run completion timestamp')
    result_created_at = parse_timestamp(
        row['created_at'], 'result timestamp'
    )
    if (
        sha256_text(row['result_json']) != row['result_sha256']
        or sha256_text(row['packet_json']) != row['packet_sha256']
    ):
        raise OutboxError('result or packet digest differs')
    result = parse_canonical_object(row['result_json'], 'reasoning result')
    packet = parse_canonical_object(row['packet_json'], 'reasoning packet')
    validate_result(result, row)
    incident = validate_packet(packet, row)
    device = incident_device(incident)
    for field, maximum in (
        ('model_version', 256),
        ('provider', 64),
        ('model_reference', 256),
        ('prompt_version', 256),
        ('manifest_sha256', 64),
        ('config_digest', 71),
        ('request_sha256', 64),
        ('system_prompt_sha256', 64),
        ('output_schema_sha256', 64),
    ):
        validate_string(row[field], maximum, f'provenance {field}')
    if (
        row['provider'] != 'ollama'
        or SHA256_RE.fullmatch(row['manifest_sha256']) is None
        or len(row['config_digest']) != 71
        or not row['config_digest'].startswith('sha256:')
        or SHA256_RE.fullmatch(row['config_digest'][7:]) is None
        or SHA256_RE.fullmatch(row['request_sha256']) is None
        or SHA256_RE.fullmatch(row['system_prompt_sha256']) is None
        or SHA256_RE.fullmatch(row['output_schema_sha256']) is None
        or type(row['output_schema_version']) is not int
        or row['output_schema_version'] != row['schema_version']
        or row['run_packet_id'] != row['packet_id']
        or type(row['attempt_number']) is not int
        or row['attempt_number'] < 1
        or row['error_code'] is not None
        or completed_at != result_created_at
        or completed_at < started_at
    ):
        raise OutboxError('reasoning provenance differs')
    diagnostics = parse_canonical_object(
        row['diagnostics_json'], 'reasoning diagnostics'
    )
    record = {
        'body': result['summary'],
        'device': device,
        'first_seen': incident['first_seen'],
        'incident_id': row['incident_id'],
        'last_seen': incident['last_seen'],
        'model': row['model_version'],
        'occurrence_count': incident['occurrence_count'],
        'producer_schema': PRODUCER_SCHEMA,
        'producer_version': PRODUCER_VERSION,
        'provenance': {
            'model_config_digest': row['config_digest'],
            'model_manifest_sha256': row['manifest_sha256'],
            'model_reference': row['model_reference'],
            'output_schema_sha256': row['output_schema_sha256'],
            'output_schema_version': row['output_schema_version'],
            'packet_id': row['packet_id'],
            'packet_sha256': row['packet_sha256'],
            'prompt_version': row['prompt_version'],
            'provider': row['provider'],
            'request_sha256': row['request_sha256'],
            'result_sha256': row['result_sha256'],
            'run_attempt_number': row['attempt_number'],
            'run_completed_at': row['completed_at'],
            'run_diagnostics': diagnostics,
            'run_started_at': row['started_at'],
            'system_prompt_sha256': row['system_prompt_sha256'],
        },
        'result': result,
        'run_id': row['run_id'],
        'severity': result['severity'],
        'status': result['disposition'],
        'tags': result['tags'],
        'timestamp': row['created_at'],
        'title': result['title'],
        'type': RESULT_TYPE,
    }
    data = (canonical_json(record) + '\n').encode('utf-8')
    legacy_record = dict(record)
    del legacy_record['device']
    legacy_data = (canonical_json(legacy_record) + '\n').encode('utf-8')
    if not data or len(data) > MAX_FILE_BYTES:
        raise OutboxError('AI result file size differs')
    return output_name(row['run_id']), (data, legacy_data)


def load_records(database):
    database = Path(database).resolve(strict=True)
    connection = sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise OutboxError('result outbox quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise OutboxError('result outbox foreign_key_check failed')
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not REQUIRED_TABLES <= tables:
            raise OutboxError('result outbox database schema differs')
        mismatch = connection.execute(
            '''
            SELECT COUNT(*) FROM reasoning_runs AS run
            WHERE (run.status = 'SUCCEEDED') != EXISTS (
                SELECT 1 FROM reasoning_results AS result
                WHERE result.run_id = run.run_id
            )
            '''
        ).fetchone()[0]
        if mismatch:
            raise OutboxError('result outbox run/result invariant differs')
        rows = connection.execute(
            '''
            SELECT
                result.run_id,
                result.packet_id,
                result.incident_id,
                result.schema_version,
                result.disposition,
                result.severity,
                result.confidence,
                result.title,
                result.summary,
                result.result_json,
                result.result_sha256,
                result.created_at,
                run.status AS run_status,
                run.packet_id AS run_packet_id,
                run.model_version,
                run.prompt_version,
                run.attempt_number,
                run.request_sha256,
                run.started_at,
                run.completed_at,
                run.error_code,
                run.diagnostics_json,
                packet.packet_json,
                packet.packet_sha256,
                model.provider,
                model.model_reference,
                model.manifest_sha256,
                model.config_digest,
                prompt.system_prompt_sha256,
                prompt.output_schema_sha256,
                prompt.output_schema_version
            FROM reasoning_results AS result
            JOIN reasoning_runs AS run ON run.run_id = result.run_id
            JOIN reasoning_packets AS packet
              ON packet.packet_id = result.packet_id
            JOIN reasoning_model_versions AS model
              ON model.model_version = run.model_version
            JOIN reasoning_prompt_versions AS prompt
              ON prompt.prompt_version = run.prompt_version
            ORDER BY result.created_at, result.run_id
            '''
        ).fetchall()
        records = {}
        for row in rows:
            name, data = map_row(row)
            if name in records:
                raise OutboxError('result outbox filename collision')
            records[name] = data
        return records
    finally:
        connection.close()


def validate_directory(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise OutboxError('result outbox is not a directory')
    details = path.stat()
    if details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) & 0o022:
        raise OutboxError('result outbox directory metadata differs')


def validate_file(path, variants):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise OutboxError('result outbox target is not a regular file')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != os.geteuid()
        or stat.S_IMODE(details.st_mode) != 0o640
        or path.read_bytes() not in variants
    ):
        raise OutboxError('result outbox target differs')


def acquire_lock(directory):
    path = Path(directory) / LOCK_NAME
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
        raise OutboxError('result outbox lock metadata differs')
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise OutboxError('result outbox producer is already running') from exc
    return descriptor


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def recover_partials(directory):
    removed = 0
    for path in sorted(Path(directory).iterdir(), key=lambda item: item.name):
        if not PARTIAL_RE.fullmatch(path.name):
            continue
        if path.is_symlink() or not path.is_file():
            raise OutboxError('result outbox partial is not a regular file')
        details = path.stat()
        if (
            details.st_nlink != 1
            or details.st_uid != os.geteuid()
            or stat.S_IMODE(details.st_mode) not in {0o600, 0o640}
        ):
            raise OutboxError('result outbox partial metadata differs')
        path.unlink()
        removed += 1
    if removed:
        fsync_directory(directory)
    return removed


def inventory_directory(directory, records, *, allow_partials):
    found = set()
    for path in sorted(Path(directory).iterdir(), key=lambda item: item.name):
        if INCIDENT_FINAL_RE.fullmatch(path.name):
            continue
        if allow_partials and INCIDENT_PARTIAL_RE.fullmatch(path.name):
            continue
        if allow_partials and PARTIAL_RE.fullmatch(path.name):
            continue
        if not FINAL_RE.fullmatch(path.name) or path.name not in records:
            raise OutboxError('result outbox contains an unexpected entry')
        validate_file(path, records[path.name])
        found.add(path.name)
    return found


def preflight(ready, delivered, records):
    ready_names = inventory_directory(
        ready, records, allow_partials=True
    )
    delivered_names = inventory_directory(
        delivered, records, allow_partials=False
    )
    if ready_names & delivered_names:
        raise OutboxError('result outbox state is duplicated')
    return ready_names, delivered_names


def publish(directory, name, variants):
    target = Path(directory) / name
    if target.exists() or target.is_symlink():
        validate_file(target, variants)
        return False
    data = variants[0]
    temporary = Path(directory) / (
        f'.{name}.tmp-{os.getpid()}-{time.time_ns()}'
    )
    descriptor = os.open(
        temporary,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, 'O_NOFOLLOW', 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, 'wb', closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists() or target.is_symlink():
            raise OutboxError('result outbox target appeared during publish')
        os.chmod(temporary, 0o640)
        os.replace(temporary, target)
        fsync_directory(directory)
        validate_file(target, variants)
        return True
    finally:
        if temporary.exists():
            temporary.unlink()


def build(database, ready, delivered):
    database = Path(database)
    ready = Path(ready)
    delivered = Path(delivered)
    if database.is_symlink() or not database.is_file():
        raise OutboxError('result outbox database is not a regular file')
    for directory in (ready, delivered):
        if directory.is_symlink() or not directory.is_dir():
            raise OutboxError('result outbox is not a directory')
    database = database.resolve(strict=True)
    ready = ready.resolve(strict=True)
    delivered = delivered.resolve(strict=True)
    if ready == delivered or ready.parent != delivered.parent:
        raise OutboxError('result outbox directory layout differs')
    root = ready.parent
    validate_directory(root)
    validate_directory(ready)
    validate_directory(delivered)
    descriptor = acquire_lock(root)
    try:
        recovered = recover_partials(ready)
        records = load_records(database)
        ready_names, delivered_names = preflight(
            ready, delivered, records
        )
        reused = len(ready_names) + len(delivered_names)
        created = 0
        written_bytes = 0
        for name, variants in sorted(records.items()):
            if name in ready_names or name in delivered_names:
                continue
            if publish(ready, name, variants):
                created += 1
                written_bytes += len(variants[0])
        if created + reused != len(records):
            raise OutboxError('result outbox publication count differs')
        return {
            'total': len(records),
            'created': created,
            'reused': reused,
            'ready': len(ready_names) + created,
            'delivered': len(delivered_names),
            'recovered': recovered,
            'written_bytes': written_bytes,
        }
    finally:
        os.close(descriptor)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Build deterministic local AI-result outbox files'
    )
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--delivered', type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = build(args.database, args.ready, args.delivered)
        print(
            'RESULT_OUTBOX schema=1 '
            f'total={result["total"]} created={result["created"]} '
            f'reused={result["reused"]} '
            f'ready={result["ready"]} '
            f'delivered={result["delivered"]} '
            f'recovered={result["recovered"]} '
            f'written_bytes={result["written_bytes"]}'
        )
        print('GX10_RESULT_OUTBOX=PASS')
        return 0
    except (OSError, sqlite3.Error, OutboxError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_RESULT_OUTBOX=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
