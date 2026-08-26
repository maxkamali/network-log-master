#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA = SCRIPT_DIR.parent / 'sql' / 'triage-v1.sql'
SERVICE = 'network-log-gx10-reasoning.service'
CURSOR_KEY = 'ai_triage_v1_last_event_id'
CONFIRMATION = 'APPLY-AI-TRIAGE-V1'
REQUIRED_BASE_TABLES = {
    'agent_state', 'recent_events', 'event_enrichment', 'incidents',
    'incident_evidence', 'incident_transitions', 'reasoning_model_versions',
    'reasoning_prompt_versions',
}
TRIAGE_TABLES = {
    'triage_signatures', 'triage_batches', 'triage_batch_members',
    'triage_runs', 'triage_decisions', 'event_detection_overrides',
    'triage_incident_summaries', 'learned_detection_rules',
}


class MigrationError(ValueError):
    pass


def schema_statements():
    statements = []
    pending = ''
    for line in SCHEMA.read_text(encoding='utf-8').splitlines(True):
        pending += line
        if not sqlite3.complete_statement(pending):
            continue
        statement = pending.strip()
        pending = ''
        if statement.rstrip(';').strip().upper() not in {
            'PRAGMA FOREIGN_KEYS=ON', 'BEGIN IMMEDIATE', 'COMMIT'
        }:
            statements.append(statement)
    if pending.strip():
        raise MigrationError('triage schema contains an incomplete statement')
    return statements


def table_names(connection):
    return {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def validate(connection, *, migrated):
    if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise MigrationError('AI triage database quick_check failed')
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise MigrationError('AI triage database foreign_key_check failed')
    tables = table_names(connection)
    if not REQUIRED_BASE_TABLES <= tables:
        raise MigrationError('AI triage prerequisite schema differs')
    present = TRIAGE_TABLES <= tables
    if present != migrated or (tables & TRIAGE_TABLES and not present):
        raise MigrationError('AI triage schema state differs')
    if migrated:
        cursor = connection.execute(
            'SELECT value FROM agent_state WHERE key=?', (CURSOR_KEY,)
        ).fetchone()
        if cursor is None or not cursor[0].isdigit():
            raise MigrationError('AI triage cursor is unavailable')


def backup_database(connection, backup: Path):
    if backup.exists() or backup.is_symlink():
        raise MigrationError('AI triage backup already exists')
    parent = backup.parent
    if parent.is_symlink() or not parent.is_dir():
        raise MigrationError('AI triage backup parent differs')
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{backup.name}.', dir=parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        destination = sqlite3.connect(temporary)
        try:
            connection.backup(destination)
            validate(destination, migrated=False)
        finally:
            destination.close()
        os.chown(temporary, 0, 0)
        os.chmod(temporary, 0o600)
        os.link(temporary, backup, follow_symlinks=False)
        temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()


def migrate(database: Path, backup: Path, now_ms: int):
    if database.is_symlink() or not database.is_file():
        raise MigrationError('AI triage database differs')
    if stat.S_IMODE(database.stat().st_mode) != 0o640:
        raise MigrationError('AI triage database mode differs')
    if subprocess.run(
        ['systemctl', 'is-active', '--quiet', SERVICE], check=False
    ).returncode == 0:
        raise MigrationError('stop the managed reasoning service before migration')
    connection = sqlite3.connect(database)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        validate(connection, migrated=False)
        backup_database(connection, backup)
        connection.execute('BEGIN IMMEDIATE')
        for statement in schema_statements():
            connection.execute(statement)
        incident_cursor = connection.execute(
            "SELECT COALESCE(CAST(value AS INTEGER),0) FROM agent_state "
            "WHERE key='incident_engine_v1_last_event_id'"
        ).fetchone()
        upper = incident_cursor[0] if incident_cursor else 0
        first = connection.execute(
            'SELECT MIN(id) FROM recent_events WHERE timestamp_epoch_ms>=? AND id<=?',
            (now_ms - 24 * 60 * 60 * 1000, upper),
        ).fetchone()[0]
        floor = max(0, (first - 1) if first is not None else upper)
        timestamp = datetime.fromtimestamp(
            now_ms / 1000, tz=timezone.utc
        ).isoformat()
        connection.execute(
            'INSERT INTO agent_state(key,value,updated_at) VALUES(?,?,?)',
            (CURSOR_KEY, str(floor), timestamp),
        )
        validate(connection, migrated=True)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        if os.geteuid() != 0 or not args.apply:
            raise MigrationError('AI triage migration requires root --apply')
        if os.environ.get('GX10_AI_TRIAGE_MIGRATION_CONFIRM') != CONFIRMATION:
            raise MigrationError('AI triage migration confirmation is absent')
        migrate(
            args.database.resolve(strict=True),
            args.backup,
            int(datetime.now(timezone.utc).timestamp() * 1000),
        )
        print('GX10_AI_TRIAGE_MIGRATION=PASS')
        return 0
    except (OSError, sqlite3.Error, MigrationError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
