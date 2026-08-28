#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import os
from pathlib import Path
import pwd
import grp
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time


LEDGER = Path('/var/spool/ai-results/ready/.accepted-v1.sqlite3')
READY = Path('/var/spool/ai-results/ready')
INCOMING = Path('/var/spool/ai-results/incoming')
CLICKHOUSE_CLIENT = Path('/usr/bin/clickhouse-client')
GATE_USER = 'ai_results_gate'
READY_GROUP = 'vector'
SCHEMA = 'network-log-first-live-evidence'
SCHEMA_VERSION = 1
EVIDENCE_MAX_BYTES = 4 * 1024 * 1024
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
FILENAME_RE = re.compile(
    r'^(?:ai-result-v1|incident-state-v[12])-[0-9a-f]{32}\.jsonl$'
)


class ProvenanceError(ValueError):
    pass


class NotReadyError(ProvenanceError):
    pass


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def validate_private_file(path, uid, gid, modes, label, maximum=256 * 1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ProvenanceError(f'{label} differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) not in modes
        or details.st_size <= 0
        or details.st_size > maximum
    ):
        raise ProvenanceError(f'{label} metadata differs')


def validate_selected(selected):
    if not isinstance(selected, dict) or set(selected) != {
        'filename', 'file_sha256', 'line_sha256', 'record_count', 'route', 'size'
    }:
        raise ProvenanceError('first-live selected evidence shape differs')
    if (
        not isinstance(selected['filename'], str)
        or FILENAME_RE.fullmatch(selected['filename']) is None
        or not isinstance(selected['file_sha256'], str)
        or SHA256_RE.fullmatch(selected['file_sha256']) is None
        or selected['route'] not in {'ai_updates', 'incident_updates'}
        or isinstance(selected['size'], bool)
        or not isinstance(selected['size'], int)
        or not 1 <= selected['size'] <= 256 * 1024
        or isinstance(selected['record_count'], bool)
        or not isinstance(selected['record_count'], int)
        or not 1 <= selected['record_count'] <= 100
        or not isinstance(selected['line_sha256'], list)
        or len(selected['line_sha256']) != selected['record_count']
        or any(
            not isinstance(value, str) or SHA256_RE.fullmatch(value) is None
            for value in selected['line_sha256']
        )
    ):
        raise ProvenanceError('first-live selected evidence values differ')
    if (
        selected['route'] == 'ai_updates'
        and selected['record_count'] != 1
    ):
        raise ProvenanceError('AI first-live evidence record count differs')


def validate_compact_manifest(value, expected_count, label):
    if not isinstance(value, list) or len(value) != expected_count:
        raise ProvenanceError(f'{label} inventory differs')
    names = set()
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {
            'filename', 'file_sha256', 'record_count', 'route', 'size'
        }:
            raise ProvenanceError(f'{label} inventory shape differs')
        if (
            not isinstance(entry['filename'], str)
            or FILENAME_RE.fullmatch(entry['filename']) is None
            or entry['filename'] in names
            or not isinstance(entry['file_sha256'], str)
            or SHA256_RE.fullmatch(entry['file_sha256']) is None
            or entry['route'] not in {'ai_updates', 'incident_updates'}
            or isinstance(entry['record_count'], bool)
            or not isinstance(entry['record_count'], int)
            or not 1 <= entry['record_count'] <= 100
            or (entry['route'] == 'ai_updates' and entry['record_count'] != 1)
            or isinstance(entry['size'], bool)
            or not isinstance(entry['size'], int)
            or not 1 <= entry['size'] <= 256 * 1024
        ):
            raise ProvenanceError(f'{label} inventory values differ')
        names.add(entry['filename'])
    return names


def load_evidence(path, phase, uid=0, gid=0):
    validate_private_file(
        path, uid, gid, {0o600}, 'first-live evidence', maximum=EVIDENCE_MAX_BYTES
    )
    before = Path(path).stat()
    raw = Path(path).read_text(encoding='utf-8')
    after = Path(path).stat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns')
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise ProvenanceError('first-live evidence changed during verification')
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProvenanceError('first-live evidence JSON differs') from exc
    if canonical_json(value) + '\n' != raw:
        raise ProvenanceError('first-live evidence is not canonical')
    common = {'schema', 'schema_version', 'phase', 'selected'}
    expected = (
        common | {
            'delivered_before', 'delivered_count_before',
            'expected_delivered_digest', 'prepared_at', 'ready_count_before',
            'remaining_ready', 'remaining_ready_digest',
        }
        if phase == 'prepared'
        else common | {
            'delivered_count_after', 'finalized_at', 'prepared_sha256',
            'ready_count_after', 'new_ready_count',
        }
    )
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or value.get('schema') != SCHEMA
        or value.get('schema_version') != SCHEMA_VERSION
        or value.get('phase') != phase
    ):
        raise ProvenanceError('first-live evidence identity differs')
    validate_selected(value['selected'])
    for field in (
        ('expected_delivered_digest', 'remaining_ready_digest')
        if phase == 'prepared'
        else ('prepared_sha256',)
    ):
        if not isinstance(value[field], str) or SHA256_RE.fullmatch(value[field]) is None:
            raise ProvenanceError('first-live evidence digest differs')
    count_fields = (
        ('ready_count_before', 'delivered_count_before')
        if phase == 'prepared'
        else ('ready_count_after', 'delivered_count_after', 'new_ready_count')
    )
    for field in count_fields:
        if isinstance(value[field], bool) or not isinstance(value[field], int) or value[field] < 0:
            raise ProvenanceError('first-live evidence count differs')
    if phase == 'prepared' and value['ready_count_before'] < 1:
        raise ProvenanceError('first-live prepared ready count differs')
    if phase == 'prepared' and (
        not isinstance(value['remaining_ready'], list)
        or not isinstance(value['delivered_before'], list)
        or len(value['remaining_ready']) != value['ready_count_before'] - 1
        or len(value['delivered_before']) != value['delivered_count_before']
    ):
        raise ProvenanceError('first-live evidence private inventory differs')
    if phase == 'prepared':
        remaining_names = validate_compact_manifest(
            value['remaining_ready'], value['ready_count_before'] - 1,
            'remaining ready',
        )
        delivered_names = validate_compact_manifest(
            value['delivered_before'], value['delivered_count_before'],
            'delivered before',
        )
        selected_name = value['selected']['filename']
        if (
            selected_name in remaining_names
            or selected_name in delivered_names
            or remaining_names & delivered_names
        ):
            raise ProvenanceError('first-live private inventories overlap')
    timestamp_field = 'prepared_at' if phase == 'prepared' else 'finalized_at'
    timestamp = value.get(timestamp_field)
    if not isinstance(timestamp, str):
        raise ProvenanceError('first-live evidence timestamp differs')
    try:
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ProvenanceError('first-live evidence timestamp differs') from exc
    if parsed.tzinfo is None:
        raise ProvenanceError('first-live evidence timestamp lacks timezone')
    return value, raw.encode('utf-8')


def ledger_row(path, filename, gate_uid, gate_gid, *, allow_absent):
    path = Path(path)
    if path.is_symlink():
        raise ProvenanceError('collector acceptance ledger is a symlink')
    if not path.exists():
        if allow_absent:
            return None
        raise NotReadyError('collector acceptance ledger is absent')
    validate_private_file(
        path, gate_uid, gate_gid, {0o640}, 'collector acceptance ledger',
        maximum=64 * 1024 * 1024,
    )
    connection = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only = ON')
        if connection.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ProvenanceError('collector acceptance ledger quick_check failed')
        if connection.execute('PRAGMA user_version').fetchone() != (1,):
            raise ProvenanceError('collector acceptance ledger version differs')
        columns = tuple(connection.execute('PRAGMA table_info(accepted)'))
        if columns != (
            (0, 'filename', 'TEXT', 1, None, 1),
            (1, 'sha256', 'TEXT', 1, None, 0),
            (2, 'size', 'INTEGER', 1, None, 0),
            (3, 'record_count', 'INTEGER', 1, None, 0),
            (4, 'accepted_at', 'TEXT', 1, None, 0),
        ):
            raise ProvenanceError('collector acceptance ledger schema differs')
        triggers = {
            row[0]: ' '.join(row[1].split())
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'trigger' AND tbl_name = 'accepted'"
            )
        }
        expected_triggers = {
            'accepted_no_update': ' '.join(
                """
                CREATE TRIGGER accepted_no_update
                BEFORE UPDATE ON accepted
                BEGIN
                    SELECT RAISE(ABORT, 'accepted rows are immutable');
                END
                """.split()
            ),
            'accepted_no_delete': ' '.join(
                """
                CREATE TRIGGER accepted_no_delete
                BEFORE DELETE ON accepted
                BEGIN
                    SELECT RAISE(ABORT, 'accepted rows are immutable');
                END
                """.split()
            ),
        }
        if triggers != expected_triggers:
            raise ProvenanceError('collector acceptance ledger triggers differ')
        rows = tuple(
            connection.execute(
                'SELECT sha256, size, record_count FROM accepted WHERE filename = ?',
                (filename,),
            )
        )
        if len(rows) > 1:
            raise ProvenanceError('collector acceptance identity is duplicated')
        return rows[0] if rows else None
    finally:
        connection.close()


def ready_evidence(path, selected, gate_uid, gate_gid):
    path = Path(path) / selected['filename']
    if not path.exists() and not path.is_symlink():
        raise NotReadyError('accepted ready file is absent')
    validate_private_file(path, gate_uid, gate_gid, {0o640}, 'accepted ready file')
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns')
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise ProvenanceError('accepted ready file changed during verification')
    if len(data) != selected['size'] or sha256_bytes(data) != selected['file_sha256']:
        raise ProvenanceError('accepted ready file identity differs')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ProvenanceError('accepted ready file encoding differs') from exc
    if not text.endswith('\n'):
        raise ProvenanceError('accepted ready file framing differs')
    lines = text.splitlines()
    if len(lines) != selected['record_count']:
        raise ProvenanceError('accepted ready file record count differs')
    line_digests = []
    routes = set()
    records = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProvenanceError('accepted ready file JSON differs') from exc
        if canonical_json(record) != line:
            raise ProvenanceError('accepted ready file is not canonical')
        records.append(record)
        routes.add(
            'incident_updates'
            if record.get('type') == 'incident_lifecycle'
            else 'ai_updates'
        )
        line_digests.append(sha256_bytes((line + '\n').encode('utf-8')))
    if routes != {selected['route']} or line_digests != selected['line_sha256']:
        raise ProvenanceError('accepted ready file route or line identity differs')
    return records


class ClickHouseDigestReader:
    def __init__(self, password_file, client=CLICKHOUSE_CLIENT):
        self.password_file = Path(password_file)
        self.client = Path(client)
        self.temporary = None
        self.config = None

    def __enter__(self):
        try:
            resolved_client = self.client.resolve(strict=True)
        except OSError as exc:
            raise ProvenanceError('ClickHouse client differs') from exc
        if not resolved_client.is_file() or not os.access(resolved_client, os.X_OK):
            raise ProvenanceError('ClickHouse client differs')
        details = resolved_client.stat()
        if details.st_uid != 0 or stat.S_IMODE(details.st_mode) & 0o022:
            raise ProvenanceError('ClickHouse client metadata differs')
        validate_private_file(
            self.password_file, 0, 0, {0o400, 0o600},
            'ClickHouse reader password', maximum=8192,
        )
        password = self.password_file.read_text(encoding='utf-8').rstrip('\r\n')
        if not password or '\n' in password or '\r' in password:
            raise ProvenanceError('ClickHouse reader password shape differs')
        try:
            self.temporary = tempfile.TemporaryDirectory(
                prefix='first-live-clickhouse-'
            )
            self.config = Path(self.temporary.name) / 'client.xml'
            payload = (
                '<config>\n'
                '  <host>127.0.0.1</host>\n'
                '  <user>grafana_reader</user>\n'
                f'  <password>{escape(password)}</password>\n'
                '</config>\n'
            ).encode('utf-8')
            descriptor = os.open(
                self.config,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL
                | getattr(os, 'O_NOFOLLOW', 0),
                0o600,
            )
            try:
                handle = os.fdopen(descriptor, 'wb', closefd=True)
            except Exception:
                os.close(descriptor)
                raise
            with handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            if self.temporary is not None:
                self.temporary.cleanup()
            self.temporary = None
            self.config = None
            raise
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.temporary is not None:
            self.temporary.cleanup()

    def rows(self, table, digests):
        if table not in {'ai_updates', 'incident_updates'}:
            raise ProvenanceError('ClickHouse route differs')
        unique = sorted(set(digests))
        if not unique:
            return []
        values = ','.join(f"'{value}'" for value in unique)
        expression = "lower(hex(SHA256(concat(raw_json, char(10)))))"
        columns = (
            'raw_json, toUnixTimestamp64Milli(timestamp) AS timestamp_ms, '
            'incident_id, run_id, device, model, type, status, severity, '
            'ifNull(toUnixTimestamp64Milli(first_seen), -1) AS first_seen_ms, '
            'ifNull(toUnixTimestamp64Milli(last_seen), -1) AS last_seen_ms, '
            'occurrence_count, title, body, tags'
            if table == 'ai_updates'
            else (
                'raw_json, toUnixTimestamp64Milli(timestamp) AS timestamp_ms, '
                'snapshot_id, snapshot_version, incident_id, device, '
                'entity_type, entity_name, event_family, protocol, '
                'lifecycle_status, severity, '
                'toUnixTimestamp64Milli(first_seen) AS first_seen_ms, '
                'toUnixTimestamp64Milli(last_seen) AS last_seen_ms, '
                'ifNull(toUnixTimestamp64Milli(opened_at), -1) AS opened_at_ms, '
                'ifNull(toUnixTimestamp64Milli(recovering_at), -1) AS recovering_at_ms, '
                'ifNull(toUnixTimestamp64Milli(resolved_at), -1) AS resolved_at_ms, '
                'occurrence_count, recurrence_count, repeat_count_total, '
                'state_change_count, last_observation_state, interface_flap, '
                'engine_version, title, body, type, producer_schema, producer_version'
            )
        )
        query = (
            f'SELECT {columns} '
            f'FROM observability.{table} '
            f'WHERE {expression} IN ({values}) '
            'LIMIT 101 FORMAT JSONEachRow\n'
        )
        result = subprocess.run(
            [
                str(self.client), '--config-file', str(self.config),
                '--max_execution_time=30',
            ],
            input=query,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise ProvenanceError('ClickHouse read-only digest query failed')
        observed = []
        for line in result.stdout.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceError('ClickHouse digest response differs') from exc
            if not isinstance(row, dict) or not isinstance(row.get('raw_json'), str):
                raise ProvenanceError('ClickHouse digest response differs')
            observed.append(row)
        return observed


def timestamp_to_milliseconds(value):
    if value is None:
        return -1
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError) as exc:
        raise ProvenanceError('accepted timestamp differs') from exc
    if parsed.tzinfo is None:
        raise ProvenanceError('accepted timestamp lacks timezone')
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = parsed.astimezone(timezone.utc) - epoch
    return (
        delta.days * 86_400_000
        + delta.seconds * 1000
        + delta.microseconds // 1000
    )


def require_clickhouse_rows(rows, records, route):
    expected_raw = Counter(canonical_json(record) for record in records)
    observed_raw = Counter(row['raw_json'] for row in rows)
    if observed_raw != expected_raw:
        raise ProvenanceError('ClickHouse routed raw_json multiset differs')

    for row in rows:
        record = json.loads(row['raw_json'])
        if route == 'ai_updates':
            expected = {
                'timestamp_ms': timestamp_to_milliseconds(record['timestamp']),
                'incident_id': record.get('incident_id', ''),
                'run_id': record.get('run_id', ''),
                'device': record.get('device', ''),
                'model': record.get('model', ''),
                'type': record.get('type', ''),
                'status': record.get('status', ''),
                'severity': record.get('severity', ''),
                'first_seen_ms': timestamp_to_milliseconds(record.get('first_seen')),
                'last_seen_ms': timestamp_to_milliseconds(record.get('last_seen')),
                'occurrence_count': record.get('occurrence_count', 0),
                'title': record['title'],
                'body': record['body'],
                'tags': record.get('tags', []),
            }
        else:
            expected = {
                'timestamp_ms': timestamp_to_milliseconds(record['timestamp']),
                'snapshot_id': record['snapshot_id'],
                'snapshot_version': record['snapshot_version'],
                'incident_id': record['incident_id'],
                'device': record['device'],
                'entity_type': record['entity_type'],
                'entity_name': record['entity_name'],
                'event_family': record['event_family'],
                'protocol': record['protocol'],
                'lifecycle_status': record['lifecycle_status'],
                'severity': record['severity'],
                'first_seen_ms': timestamp_to_milliseconds(record['first_seen']),
                'last_seen_ms': timestamp_to_milliseconds(record['last_seen']),
                'opened_at_ms': timestamp_to_milliseconds(record['opened_at']),
                'recovering_at_ms': timestamp_to_milliseconds(record['recovering_at']),
                'resolved_at_ms': timestamp_to_milliseconds(record['resolved_at']),
                'occurrence_count': record['occurrence_count'],
                'recurrence_count': record.get('recurrence_count', 0),
                'repeat_count_total': record['repeat_count_total'],
                'state_change_count': record['state_change_count'],
                'last_observation_state': record['last_observation_state'],
                'interface_flap': record['interface_flap'],
                'engine_version': record['engine_version'],
                'title': record['title'],
                'body': record['body'],
                'type': record['type'],
                'producer_schema': record['producer_schema'],
                'producer_version': record['producer_version'],
            }
        if any(row.get(field) != value for field, value in expected.items()):
            raise ProvenanceError('ClickHouse thin projection differs')


def preflight(prepared, ledger, ready, incoming, gate_uid, gate_gid, clickhouse):
    selected = prepared['selected']
    if ledger_row(
        ledger, selected['filename'], gate_uid, gate_gid, allow_absent=True
    ) is not None:
        raise ProvenanceError('first-live identity already exists in ledger')
    for directory, label in ((ready, 'ready'), (incoming, 'incoming')):
        candidate = Path(directory) / selected['filename']
        if candidate.exists() or candidate.is_symlink():
            raise ProvenanceError(f'first-live identity already exists in collector {label}')
    for table in ('ai_updates', 'incident_updates'):
        if clickhouse.rows(table, selected['line_sha256']):
            raise ProvenanceError('first-live identity already exists in ClickHouse')


def final_once(prepared, finalized, ledger, ready, incoming, gate_uid, gate_gid, clickhouse):
    selected = finalized['selected']
    row = ledger_row(
        ledger, selected['filename'], gate_uid, gate_gid, allow_absent=False
    )
    expected_row = (
        selected['file_sha256'], selected['size'], selected['record_count']
    )
    if row is None:
        raise NotReadyError('collector acceptance row is not ready')
    if row != expected_row:
        raise ProvenanceError('collector acceptance ledger identity differs')
    incoming_path = Path(incoming) / selected['filename']
    if incoming_path.exists() or incoming_path.is_symlink():
        raise ProvenanceError('first-live identity remains in collector incoming')
    records = ready_evidence(ready, selected, gate_uid, gate_gid)
    other = 'incident_updates' if selected['route'] == 'ai_updates' else 'ai_updates'
    rows = clickhouse.rows(selected['route'], selected['line_sha256'])
    wrong_rows = clickhouse.rows(other, selected['line_sha256'])
    if wrong_rows:
        raise ProvenanceError('first-live identity entered the wrong ClickHouse route')
    if not rows:
        raise NotReadyError('ClickHouse routed rows are not ready')
    require_clickhouse_rows(rows, records, selected['route'])


def validate_final_binding(prepared, prepared_bytes, finalized):
    if (
        finalized['prepared_sha256'] != sha256_bytes(prepared_bytes)
        or finalized['selected'] != prepared['selected']
        or finalized['ready_count_after'] != (
            prepared['ready_count_before'] - 1
            + finalized['new_ready_count']
        )
        or finalized['delivered_count_after']
        != prepared['delivered_count_before'] + 1
    ):
        raise ProvenanceError('finalized evidence does not bind prepared state')


def parse_args():
    parser = argparse.ArgumentParser(
        description='Verify private first-live GX10-to-collector provenance'
    )
    parser.add_argument('--password-file', type=Path, required=True)
    subparsers = parser.add_subparsers(dest='mode', required=True)
    preflight_parser = subparsers.add_parser('preflight')
    preflight_parser.add_argument('--prepared', type=Path, required=True)
    final_parser = subparsers.add_parser('final')
    final_parser.add_argument('--prepared', type=Path, required=True)
    final_parser.add_argument('--finalized', type=Path, required=True)
    final_parser.add_argument('--wait-seconds', type=int, default=300)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise ProvenanceError('run first-live provenance verifier as root')
        gate = pwd.getpwnam(GATE_USER)
        ready_group = grp.getgrnam(READY_GROUP)
        prepared, prepared_bytes = load_evidence(args.prepared, 'prepared')
        with ClickHouseDigestReader(args.password_file) as clickhouse:
            if args.mode == 'preflight':
                preflight(
                    prepared, LEDGER, READY, INCOMING,
                    gate.pw_uid, ready_group.gr_gid, clickhouse,
                )
                print(
                    'COLLECTOR_FIRST_LIVE_PREFLIGHT schema=1 ledger=0 ready=0 '
                    'clickhouse=0 wrong_route=0'
                )
                print('COLLECTOR_FIRST_LIVE_PREFLIGHT=PASS')
                return 0
            if not 0 <= args.wait_seconds <= 900:
                raise ProvenanceError('first-live wait bound differs')
            finalized, _ = load_evidence(args.finalized, 'finalized')
            validate_final_binding(prepared, prepared_bytes, finalized)
            deadline = time.monotonic() + args.wait_seconds
            while True:
                try:
                    final_once(
                        prepared, finalized, LEDGER, READY, INCOMING,
                        gate.pw_uid, ready_group.gr_gid, clickhouse,
                    )
                    break
                except NotReadyError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(5)
            selected = finalized['selected']
            print(
                'COLLECTOR_FIRST_LIVE_PROVENANCE schema=1 ledger=1 ready=1 '
                f'records={selected["record_count"]} '
                f'clickhouse={selected["record_count"]} wrong_route=0'
            )
            print('COLLECTOR_FIRST_LIVE_PROVENANCE=PASS')
            return 0
    except ProvenanceError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('COLLECTOR_FIRST_LIVE_PROVENANCE=FAIL', file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error, KeyError, ValueError):
        print('ERROR: private first-live provenance verification failed', file=sys.stderr)
        print('COLLECTOR_FIRST_LIVE_PROVENANCE=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
