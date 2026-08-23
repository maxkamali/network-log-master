#!/usr/bin/env python3
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from runtime_config import load_runtime_config
_CONFIG = load_runtime_config()
DB = _CONFIG.database_path
TMP_DIR = _CONFIG.temp_dir
INCOMING_DIR = _CONFIG.incoming_dir
SFTP_HOST = _CONFIG.sftp_host
SFTP_PORT = _CONFIG.sftp_port
SFTP_USER = _CONFIG.sftp_user
SSH_KEY = _CONFIG.private_key_path
KNOWN_HOSTS = _CONFIG.known_hosts_path
BOOTSTRAP_HOURS = 2
OVERLAP_HOURS = 1
MAX_CATCHUP_HOURS = 24
SETTLE_SECONDS = 120
FILE_RE = re.compile('^syslog-(\\d{8})-(\\d{4})\\.jsonl\\.zst$')
os.umask(23)

def log(message):
    print(f'{datetime.now(timezone.utc).isoformat()} {message}', flush=True)

def sftp_base_command():
    return ['/usr/bin/sftp', '-q', '-P', SFTP_PORT, '-i', str(SSH_KEY), '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={KNOWN_HOSTS}', '-b', '-', f'{SFTP_USER}@{SFTP_HOST}']

def run_sftp(batch):
    result = subprocess.run(sftp_base_command(), input=batch, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result

def list_remote_hour(hour):
    remote_dir = hour.strftime('/spool/%Y/%m/%d/%H')
    result = run_sftp(f'ls -1 {remote_dir}\n')
    combined = result.stdout + '\n' + result.stderr
    if result.returncode != 0:
        if 'No such file' in combined or 'not found' in combined.lower():
            return []
        raise RuntimeError(f'SFTP listing failed for {remote_dir}: {combined.strip()}')
    files = []
    for line in result.stdout.splitlines():
        name = Path(line.strip()).name
        if FILE_RE.match(name):
            files.append(f'{remote_dir}/{name}')
    return sorted(set(files))

def timestamp_from_filename(remote_path):
    name = Path(remote_path).name
    match = FILE_RE.match(name)
    if not match:
        return None
    value = match.group(1) + match.group(2)
    return datetime.strptime(value, '%Y%m%d%H%M').replace(tzinfo=timezone.utc)

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def verify_zstd(path):
    result = subprocess.run(['/usr/bin/zstd', '-t', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'zstd integrity test failed: {result.stderr.strip()}')

def download(remote_path, final_path):
    tmp_path = TMP_DIR / (final_path.name + '.part')
    tmp_path.unlink(missing_ok=True)
    result = run_sftp(f'get {remote_path} {tmp_path}\n')
    if result.returncode != 0:
        raise RuntimeError('SFTP download failed: ' + (result.stdout + '\n' + result.stderr).strip())
    verify_zstd(tmp_path)
    size = tmp_path.stat().st_size
    digest = sha256_file(tmp_path)
    os.replace(tmp_path, final_path)
    return (size, digest)

def get_state(conn, key):
    row = conn.execute('\n        SELECT value\n        FROM agent_state\n        WHERE key = ?\n        ', (key,)).fetchone()
    return row[0] if row else None

def set_state(conn, key, value):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute('\n        INSERT INTO agent_state\n            (key, value, updated_at)\n        VALUES (?, ?, ?)\n\n        ON CONFLICT(key) DO UPDATE SET\n            value = excluded.value,\n            updated_at = excluded.updated_at\n        ', (key, value, now))

def floor_hour(value):
    return value.replace(minute=0, second=0, microsecond=0)

def main():
    for path in (DB, SSH_KEY, KNOWN_HOSTS):
        if not path.exists():
            log(f'FATAL missing required path: {path}')
            return 1
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute('\n        CREATE TABLE IF NOT EXISTS agent_state\n        (\n            key         TEXT PRIMARY KEY,\n            value       TEXT NOT NULL,\n            updated_at  TEXT NOT NULL\n        )\n        ')
    now = datetime.now(timezone.utc)
    previous = get_state(conn, 'last_remote_scan_utc')
    if previous:
        previous_dt = datetime.fromisoformat(previous)
        scan_start = floor_hour(previous_dt - timedelta(hours=OVERLAP_HOURS))
    else:
        scan_start = floor_hour(now - timedelta(hours=BOOTSTRAP_HOURS))
    maximum_end = scan_start + timedelta(hours=MAX_CATCHUP_HOURS)
    scan_end = min(floor_hour(now), maximum_end)
    log(f'SCAN {scan_start.isoformat()} through {scan_end.isoformat()}')
    hour = scan_start
    discovered = []
    while hour <= scan_end:
        files = list_remote_hour(hour)
        discovered.extend(files)
        hour += timedelta(hours=1)
    cutoff = now - timedelta(seconds=SETTLE_SECONDS)
    eligible = []
    for remote_path in sorted(set(discovered)):
        event_time = timestamp_from_filename(remote_path)
        if event_time is None:
            continue
        if event_time <= cutoff:
            eligible.append(remote_path)
    log(f'DISCOVERED {len(discovered)} file(s); {len(eligible)} settled')
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0
    for remote_path in eligible:
        name = Path(remote_path).name
        local_path = INCOMING_DIR / name
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute("\n            INSERT OR IGNORE INTO source_files\n            (\n                remote_path,\n                status,\n                discovered_at\n            )\n            VALUES (?, 'discovered', ?)\n            ", (remote_path, now_iso))
        row = conn.execute('\n            SELECT status, local_path\n            FROM source_files\n            WHERE remote_path = ?\n            ', (remote_path,)).fetchone()
        status = row[0]
        recorded_local = row[1]
        if status == 'processed':
            skipped_count += 1
            continue
        if status == 'processing':
            skipped_count += 1
            continue
        if status == 'downloaded':
            candidate = Path(recorded_local) if recorded_local else local_path
            if candidate.exists():
                skipped_count += 1
                continue
        try:
            size, digest = download(remote_path, local_path)
            conn.execute("\n                UPDATE source_files\n                SET\n                    local_path = ?,\n                    size_bytes = ?,\n                    sha256 = ?,\n                    status = 'downloaded',\n                    downloaded_at = ?,\n                    error = NULL\n                WHERE remote_path = ?\n                ", (str(local_path), size, digest, now_iso, remote_path))
            conn.commit()
            downloaded_count += 1
            log(f'DOWNLOADED {name} {size} bytes sha256={digest[:12]}...')
        except Exception as exc:
            failed_count += 1
            conn.execute("\n                UPDATE source_files\n                SET\n                    status = 'failed',\n                    error = ?\n                WHERE remote_path = ?\n                ", (str(exc)[:2048], remote_path))
            conn.commit()
            log(f'ERROR {name}: {exc}')
    set_state(conn, 'last_remote_scan_utc', scan_end.isoformat())
    conn.commit()
    log(f'DONE downloaded={downloaded_count} skipped={skipped_count} failed={failed_count}')
    conn.close()
    return 0 if failed_count == 0 else 2
if __name__ == '__main__':
    sys.exit(main())
