#!/usr/bin/env python3
import io
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from runtime_config import load_runtime_config
_CONFIG = load_runtime_config()
DB = _CONFIG.database_path
INCOMING = _CONFIG.incoming_dir
PROCESSED = _CONFIG.processed_dir
MAX_LINE_BYTES = 1024 * 1024
os.umask(23)

def log(message):
    print(f'{datetime.now(timezone.utc).isoformat()} {message}', flush=True)

def parse_epoch_ms(value):
    if not isinstance(value, str):
        raise ValueError('timestamp is not a string')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp has no timezone')
    return int(parsed.timestamp() * 1000)

def ensure_schema(conn):
    columns = {row[1] for row in conn.execute('PRAGMA table_info(recent_events)')}
    if 'timestamp_epoch_ms' not in columns:
        conn.execute('\n            ALTER TABLE recent_events\n            ADD COLUMN timestamp_epoch_ms INTEGER\n            ')
    source_columns = {row[1] for row in conn.execute('PRAGMA table_info(source_files)')}
    if 'record_count' not in source_columns:
        conn.execute('\n            ALTER TABLE source_files\n            ADD COLUMN record_count INTEGER\n            ')
    conn.execute('\n        CREATE INDEX IF NOT EXISTS\n            idx_recent_events_epoch\n        ON recent_events(timestamp_epoch_ms)\n        ')
    conn.execute('\n        CREATE INDEX IF NOT EXISTS\n            idx_recent_events_device_epoch\n        ON recent_events(hostname, timestamp_epoch_ms)\n        ')
    conn.commit()

def reconcile_processed(conn):
    rows = conn.execute("\n        SELECT remote_path, local_path\n        FROM source_files\n        WHERE status = 'processed'\n          AND local_path IS NOT NULL\n        ").fetchall()
    for remote_path, local_path in rows:
        source = Path(local_path)
        if source.parent == INCOMING and source.exists():
            destination = PROCESSED / source.name
            os.replace(source, destination)
            conn.execute('\n                UPDATE source_files\n                SET local_path = ?\n                WHERE remote_path = ?\n                ', (str(destination), remote_path))
    conn.commit()

def process_file(conn, remote_path, local_path):
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f'local spool file missing: {path}')
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("\n        UPDATE source_files\n        SET\n            status = 'processing',\n            error = NULL\n        WHERE remote_path = ?\n        ", (remote_path,))
    conn.commit()
    process = subprocess.Popen(['/usr/bin/zstd', '-dc', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stream = io.TextIOWrapper(process.stdout, encoding='utf-8', errors='strict')
    record_count = 0
    try:
        conn.execute('BEGIN IMMEDIATE')
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            if len(line.encode('utf-8')) > MAX_LINE_BYTES:
                raise ValueError(f'line {line_number} exceeds {MAX_LINE_BYTES} bytes')
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError(f'line {line_number} is not a JSON object')
            timestamp = event.get('timestamp')
            message = event.get('message')
            if not isinstance(timestamp, str):
                raise ValueError(f'line {line_number}: timestamp missing/invalid')
            if not isinstance(message, str):
                raise ValueError(f'line {line_number}: message missing/invalid')
            timestamp_epoch_ms = parse_epoch_ms(timestamp)
            source_port = event.get('source_port')
            if source_port is not None:
                try:
                    source_port = int(source_port)
                except (TypeError, ValueError):
                    source_port = None
            conn.execute('\n                INSERT OR IGNORE INTO recent_events\n                (\n                    source_file,\n                    record_number,\n                    timestamp,\n                    timestamp_epoch_ms,\n                    device_timestamp,\n                    hostname,\n                    source_ip,\n                    source_port,\n                    facility,\n                    severity,\n                    message,\n                    raw_message,\n                    parse_status,\n                    parser,\n                    event_json\n                )\n                VALUES\n                (\n                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?\n                )\n                ', (remote_path, line_number, timestamp, timestamp_epoch_ms, event.get('device_timestamp'), event.get('hostname'), event.get('source_ip'), source_port, event.get('facility'), event.get('severity'), message, event.get('raw_message'), event.get('parse_status'), event.get('parser'), line.rstrip('\n')))
            record_count += 1
        stderr = process.stderr.read().decode('utf-8', errors='replace')
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError('zstd decompression failed: ' + stderr.strip())
        conn.execute("\n            UPDATE source_files\n            SET\n                status = 'processed',\n                processed_at = ?,\n                record_count = ?,\n                error = NULL\n            WHERE remote_path = ?\n            ", (now, record_count, remote_path))
        conn.commit()
    except Exception:
        conn.rollback()
        try:
            process.kill()
        except Exception:
            pass
        process.wait()
        raise
    destination = PROCESSED / path.name
    os.replace(path, destination)
    conn.execute('\n        UPDATE source_files\n        SET local_path = ?\n        WHERE remote_path = ?\n        ', (str(destination), remote_path))
    conn.commit()
    return record_count

def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    ensure_schema(conn)
    reconcile_processed(conn)
    rows = conn.execute("\n        SELECT remote_path, local_path\n        FROM source_files\n        WHERE status IN ('downloaded', 'processing')\n        ORDER BY remote_path\n        ").fetchall()
    log(f'QUEUE {len(rows)} source file(s)')
    files_processed = 0
    records_processed = 0
    failures = 0
    for remote_path, local_path in rows:
        name = Path(remote_path).name
        try:
            count = process_file(conn, remote_path, local_path)
            files_processed += 1
            records_processed += count
            log(f'PROCESSED {name}: {count} record(s)')
        except Exception as exc:
            failures += 1
            conn.execute("\n                UPDATE source_files\n                SET\n                    status = 'failed',\n                    error = ?\n                WHERE remote_path = ?\n                ", (str(exc)[:2048], remote_path))
            conn.commit()
            log(f'ERROR {name}: {exc}')
    reconcile_processed(conn)
    total_events = conn.execute('SELECT COUNT(*) FROM recent_events').fetchone()[0]
    log(f'DONE files={files_processed} records={records_processed} failed={failures} database_events={total_events}')
    conn.close()
    return 0 if failures == 0 else 2
if __name__ == '__main__':
    sys.exit(main())
