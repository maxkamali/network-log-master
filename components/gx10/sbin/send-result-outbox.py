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
import stat
import subprocess
import sys


MAX_FILE_BYTES = 256 * 1024
LOCK_NAME = '.result-outbox.lock'
FINAL_RE = re.compile(r'^ai-result-v1-[0-9a-f]{32}\.jsonl$')
INCIDENT_FINAL_RE = re.compile(
    r'^incident-state-v1-[0-9a-f]{32}\.jsonl$'
)
HOST_RE = re.compile(r'^[A-Za-z0-9.-]+$')
USER_RE = re.compile(r'^[A-Za-z0-9._-]+$')
SAFE_PATH_RE = re.compile(r'^[A-Za-z0-9_./-]+$')
SFTP_PATH = Path('/usr/bin/sftp')
EXPECTED_RECORD_KEYS = {
    'body',
    'first_seen',
    'incident_id',
    'last_seen',
    'model',
    'occurrence_count',
    'producer_schema',
    'producer_version',
    'provenance',
    'result',
    'run_id',
    'severity',
    'status',
    'tags',
    'timestamp',
    'title',
    'type',
}
DEVICE_RECORD_KEYS = EXPECTED_RECORD_KEYS | {'device'}
INCIDENT_RECORD_KEYS = {
    'body', 'device', 'engine_version', 'entity_name', 'entity_type',
    'event_family', 'first_seen', 'incident_id', 'interface_flap',
    'last_observation_state', 'last_seen', 'lifecycle_status',
    'occurrence_count', 'opened_at', 'producer_schema', 'producer_version',
    'protocol', 'recovering_at', 'repeat_count_total', 'resolved_at',
    'severity', 'snapshot_id', 'snapshot_version', 'state_change_count',
    'timestamp', 'title', 'type',
}
INCIDENT_STATUSES = {'CANDIDATE', 'OPEN', 'RECOVERING', 'RESOLVED'}


class SenderError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    )


def valid_timestamp(value):
    if not isinstance(value, str) or not value or len(value) > 64:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def output_name(run_id):
    if not isinstance(run_id, str) or not run_id or len(run_id) > 128:
        raise SenderError('result sender run identity differs')
    digest = hashlib.sha256(run_id.encode('utf-8')).hexdigest()
    return f'ai-result-v1-{digest[:32]}.jsonl'


def incident_output_name(data):
    digest = hashlib.sha256(data).hexdigest()
    return f'incident-state-v1-{digest[:32]}.jsonl'


def validate_directory(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise SenderError('result sender outbox is not a directory')
    details = path.stat()
    if (
        details.st_uid != os.geteuid()
        or details.st_gid != os.getegid()
        or stat.S_IMODE(details.st_mode) & 0o022
    ):
        raise SenderError('result sender outbox metadata differs')


def validate_sftp_binary(path=SFTP_PATH):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise SenderError('result sender SFTP executable differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != 0
        or stat.S_IMODE(details.st_mode) & 0o022
        or not os.access(path, os.X_OK)
    ):
        raise SenderError('result sender SFTP executable metadata differs')
    return path


def validate_private_file(path, label):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise SenderError(f'result sender {label} differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != os.geteuid()
        or details.st_gid != os.getegid()
        or stat.S_IMODE(details.st_mode) != 0o600
        or details.st_size <= 0
        or details.st_size > 64 * 1024
    ):
        raise SenderError(f'result sender {label} metadata differs')
    return path


def validate_incident_record(record):
    if (
        not isinstance(record, dict)
        or set(record) != INCIDENT_RECORD_KEYS
        or record.get('producer_schema') != 'network-log-incident-state'
        or record.get('producer_version') != 1
        or record.get('type') != 'incident_lifecycle'
        or record.get('lifecycle_status') not in INCIDENT_STATUSES
        or type(record.get('interface_flap')) is not bool
    ):
        raise SenderError('incident sender record identity differs')
    for field, maximum in (
        ('body', 65536), ('device', 256), ('entity_type', 128),
        ('event_family', 128), ('incident_id', 256), ('protocol', 128),
        ('severity', 64), ('snapshot_id', 64), ('title', 512),
    ):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise SenderError(f'incident sender {field} differs')
    for field, maximum in (
        ('entity_name', 512), ('last_observation_state', 128),
    ):
        value = record.get(field)
        if not isinstance(value, str) or len(value) > maximum:
            raise SenderError(f'incident sender {field} differs')
    for field in ('timestamp', 'first_seen', 'last_seen'):
        if not valid_timestamp(record.get(field)):
            raise SenderError(f'incident sender {field} differs')
    for field in ('opened_at', 'recovering_at', 'resolved_at'):
        value = record.get(field)
        if value is not None and not valid_timestamp(value):
            raise SenderError(f'incident sender {field} differs')
    if (
        (record['lifecycle_status'] == 'RESOLVED')
        != (record['resolved_at'] is not None)
    ):
        raise SenderError('incident sender resolution timestamp differs')
    if (
        record['lifecycle_status'] == 'RECOVERING'
        and record['recovering_at'] is None
    ):
        raise SenderError('incident sender recovery timestamp differs')
    for field in (
        'engine_version', 'occurrence_count', 'repeat_count_total',
        'snapshot_version', 'state_change_count',
    ):
        value = record.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SenderError(f'incident sender {field} differs')
    if record['occurrence_count'] < 1 or record['repeat_count_total'] < 1:
        raise SenderError('incident sender counters differ')


def validate_incident_batch(name, data):
    if incident_output_name(data) != name:
        raise SenderError('incident sender filename differs')
    try:
        lines = data.decode('utf-8').splitlines()
    except UnicodeDecodeError as exc:
        raise SenderError('incident sender file JSON differs') from exc
    if not 1 <= len(lines) <= 100 or data.count(b'\n') != len(lines):
        raise SenderError('incident sender record count differs')
    records = []
    incidents = set()
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SenderError('incident sender file JSON differs') from exc
        if canonical_json(record) != line:
            raise SenderError('incident sender file is not canonical')
        validate_incident_record(record)
        if record['incident_id'] in incidents:
            raise SenderError('incident sender batch duplicates an incident')
        incidents.add(record['incident_id'])
        records.append(record)
    return min(records, key=lambda item: item['timestamp'])


def validate_record(name, data):
    if not data or len(data) > MAX_FILE_BYTES or not data.endswith(b'\n'):
        raise SenderError('result sender file bounds differ')
    if INCIDENT_FINAL_RE.fullmatch(name):
        return validate_incident_batch(name, data)
    if data.count(b'\n') != 1:
        raise SenderError('result sender file record count differs')
    try:
        text = data.decode('utf-8')
        record = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SenderError('result sender file JSON differs') from exc
    if (
        not isinstance(record, dict)
        or frozenset(record) not in {
            frozenset(EXPECTED_RECORD_KEYS),
            frozenset(DEVICE_RECORD_KEYS),
        }
        or (canonical_json(record) + '\n').encode('utf-8') != data
        or record.get('producer_schema') != 'network-log-ai-result'
        or record.get('producer_version') != 1
        or record.get('type') != 'incident_assessment'
        or output_name(record.get('run_id')) != name
        or not valid_timestamp(record.get('timestamp'))
        or not valid_timestamp(record.get('first_seen'))
        or not valid_timestamp(record.get('last_seen'))
        or not isinstance(record.get('title'), str)
        or not record['title'].strip()
        or len(record['title']) > 512
        or not isinstance(record.get('body'), str)
        or not record['body'].strip()
        or len(record['body']) > 65536
        or not isinstance(record.get('provenance'), dict)
        or not isinstance(record.get('result'), dict)
        or isinstance(record.get('occurrence_count'), bool)
        or not isinstance(record.get('occurrence_count'), int)
        or not 0 <= record['occurrence_count'] <= 4294967295
        or not isinstance(record.get('tags'), list)
        or len(record['tags']) > 64
    ):
        raise SenderError('result sender record differs')
    if 'device' in record and (
        not isinstance(record['device'], str)
        or not record['device'].strip()
        or len(record['device']) > 256
    ):
        raise SenderError('result sender device projection differs')
    return record


def validate_outbox_file(path):
    path = Path(path)
    if (
        path.is_symlink()
        or not path.is_file()
        or not (
            FINAL_RE.fullmatch(path.name)
            or INCIDENT_FINAL_RE.fullmatch(path.name)
        )
    ):
        raise SenderError('result sender outbox entry differs')
    before = path.stat()
    if (
        before.st_nlink != 1
        or before.st_uid != os.geteuid()
        or before.st_gid != os.getegid()
        or stat.S_IMODE(before.st_mode) != 0o640
        or before.st_size <= 0
        or before.st_size > MAX_FILE_BYTES
    ):
        raise SenderError('result sender outbox file metadata differs')
    data = path.read_bytes()
    after = path.stat()
    stable = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns')
    if any(getattr(before, field) != getattr(after, field) for field in stable):
        raise SenderError('result sender outbox file changed')
    record = validate_record(path.name, data)
    return {
        'data': data,
        'timestamp': datetime.fromisoformat(
            record['timestamp'].replace('Z', '+00:00')
        ),
    }


def inventory(directory):
    found = {}
    for path in sorted(Path(directory).iterdir(), key=lambda item: item.name):
        data = validate_outbox_file(path)
        found[path.name] = data
    return found


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
        or details.st_gid != os.getegid()
        or stat.S_IMODE(details.st_mode) != 0o600
    ):
        os.close(descriptor)
        raise SenderError('result sender lock metadata differs')
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise SenderError('result outbox is already locked') from exc
    return descriptor


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def sftp_command(host, port, user, identity, known_hosts, sftp_path=SFTP_PATH):
    if not isinstance(host, str) or HOST_RE.fullmatch(host) is None:
        raise SenderError('result sender host differs')
    if not isinstance(user, str) or USER_RE.fullmatch(user) is None:
        raise SenderError('result sender user differs')
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise SenderError('result sender port differs')
    executable = validate_sftp_binary(sftp_path)
    identity = validate_private_file(identity, 'identity')
    known_hosts = validate_private_file(known_hosts, 'known-hosts')
    return [
        str(executable),
        '-q',
        '-P',
        str(port),
        '-i',
        str(identity),
        '-o',
        'BatchMode=yes',
        '-o',
        'IdentitiesOnly=yes',
        '-o',
        'PasswordAuthentication=no',
        '-o',
        'KbdInteractiveAuthentication=no',
        '-o',
        'StrictHostKeyChecking=yes',
        '-o',
        f'UserKnownHostsFile={known_hosts}',
        '-o',
        'GlobalKnownHostsFile=/dev/null',
        '-o',
        'ConnectTimeout=10',
        '-o',
        'ConnectionAttempts=1',
        '-o',
        'ServerAliveInterval=5',
        '-o',
        'ServerAliveCountMax=1',
        '-b',
        '-',
        f'{user}@{host}',
    ]


def default_transport(command, batch, timeout):
    try:
        return subprocess.run(
            command,
            input=batch,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SenderError('result sender transport failed') from exc


def send_one(
    ready,
    delivered,
    host,
    port,
    user,
    identity,
    known_hosts,
    *,
    transport=default_transport,
    sftp_path=SFTP_PATH,
    timeout=30,
    after_transport=None,
):
    ready = Path(ready)
    delivered = Path(delivered)
    for directory in (ready, delivered):
        validate_directory(directory)
    ready = ready.resolve(strict=True)
    delivered = delivered.resolve(strict=True)
    if (
        ready == delivered
        or ready.parent != delivered.parent
        or SAFE_PATH_RE.fullmatch(str(ready)) is None
    ):
        raise SenderError('result sender outbox layout differs')
    root = ready.parent
    validate_directory(root)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 120:
        raise SenderError('result sender timeout differs')
    command = sftp_command(
        host,
        port,
        user,
        identity,
        known_hosts,
        sftp_path=sftp_path,
    )
    descriptor = acquire_lock(root)
    try:
        ready_files = inventory(ready)
        delivered_files = inventory(delivered)
        if set(ready_files) & set(delivered_files):
            raise SenderError('result sender outbox state is duplicated')
        if not ready_files:
            return {
                'ready': 0,
                'delivered': len(delivered_files),
                'attempted': 0,
                'sent': 0,
                'sent_bytes': 0,
            }
        name = min(
            ready_files,
            key=lambda candidate: (
                ready_files[candidate]['timestamp'],
                candidate,
            ),
        )
        data = ready_files[name]['data']
        source = ready / name
        destination = delivered / name
        if destination.exists() or destination.is_symlink():
            raise SenderError('result sender delivered target exists')
        batch = f'put {source} {name}\n'
        result = transport(command, batch, timeout)
        if not hasattr(result, 'returncode') or result.returncode != 0:
            raise SenderError('result sender transport failed')
        if after_transport is not None:
            after_transport()
        if validate_outbox_file(source)['data'] != data:
            raise SenderError('result sender source changed after transport')
        if destination.exists() or destination.is_symlink():
            raise SenderError('result sender delivered target appeared')
        os.rename(source, destination)
        fsync_directory(delivered)
        fsync_directory(ready)
        if validate_outbox_file(destination)['data'] != data:
            raise SenderError('result sender delivered file differs')
        return {
            'ready': len(ready_files) - 1,
            'delivered': len(delivered_files) + 1,
            'attempted': 1,
            'sent': 1,
            'sent_bytes': len(data),
        }
    finally:
        os.close(descriptor)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Send one deterministic AI-result outbox file'
    )
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--delivered', type=Path, required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--known-hosts', type=Path, required=True)
    return parser.parse_args()


def main():
    if os.geteuid() == 0:
        print('ERROR: result sender must run as its service user', file=sys.stderr)
        return 1
    args = parse_args()
    try:
        result = send_one(
            args.ready,
            args.delivered,
            args.host,
            args.port,
            args.user,
            args.identity,
            args.known_hosts,
        )
        print(
            'RESULT_SENDER schema=1 '
            f'ready={result["ready"]} delivered={result["delivered"]} '
            f'attempted={result["attempted"]} sent={result["sent"]} '
            f'sent_bytes={result["sent_bytes"]}'
        )
        print('GX10_RESULT_SENDER=PASS')
        return 0
    except (OSError, SenderError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_RESULT_SENDER=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
