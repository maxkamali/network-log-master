#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import time


REQUIRED_TABLES = {
    'incidents',
    'incident_transitions',
    'reasoning_packets',
    'reasoning_model_versions',
    'reasoning_prompt_versions',
    'reasoning_runs',
    'reasoning_results',
}
OPTIONAL_TABLES = {
    'learned_detection_rules',
    'triage_decisions',
    'triage_incident_summaries',
}
PROJECTION_TABLES = tuple(sorted(REQUIRED_TABLES | OPTIONAL_TABLES))
TRANSIENT_ERRORS = (
    'database is busy',
    'database is locked',
    'database table is locked',
    'unable to open database file',
)


class SnapshotError(ValueError):
    pass


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_regular(path, label, *, mode=None, uid=None, gid=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise SnapshotError(f'{label} is not a regular file')
    details = path.stat()
    if details.st_nlink != 1:
        raise SnapshotError(f'{label} link count differs')
    if mode is not None and stat.S_IMODE(details.st_mode) != mode:
        raise SnapshotError(f'{label} mode differs')
    if uid is not None and details.st_uid != uid:
        raise SnapshotError(f'{label} owner differs')
    if gid is not None and details.st_gid != gid:
        raise SnapshotError(f'{label} group differs')
    return details


def validate_directory(path, uid, gid):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise SnapshotError('snapshot directory differs')
    details = path.stat()
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != 0o700
    ):
        raise SnapshotError('snapshot directory metadata differs')


def database_state(connection):
    if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise SnapshotError('snapshot quick_check failed')
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise SnapshotError('snapshot foreign_key_check failed')
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if not REQUIRED_TABLES <= tables:
        raise SnapshotError('snapshot database schema differs')
    results, succeeded, started, incidents = connection.execute(
        '''
        SELECT
          (SELECT COUNT(*) FROM reasoning_results),
          (SELECT COUNT(*) FROM reasoning_runs WHERE status='SUCCEEDED'),
          (SELECT COUNT(*) FROM reasoning_runs WHERE status='STARTED'),
          (SELECT COUNT(*) FROM incidents)
        '''
    ).fetchone()
    if results != succeeded or started:
        raise SnapshotError('snapshot reasoning state differs')
    return {'results': results, 'incidents': incidents}


def is_transient(exc):
    message = str(exc).casefold()
    return any(fragment in message for fragment in TRANSIENT_ERRORS)


def remove_temporary_files(temporary):
    temporary = Path(temporary)
    for candidate in (
        Path(f'{temporary}-wal'),
        Path(f'{temporary}-shm'),
        temporary,
    ):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def quote_identifier(value):
    return '"' + str(value).replace('"', '""') + '"'


def copy_table(source, destination, table):
    columns = [
        row[1]
        for row in source.execute(
            f'PRAGMA table_info({quote_identifier(table)})'
        )
    ]
    if not columns:
        raise SnapshotError('snapshot database schema differs')
    quoted_columns = ','.join(quote_identifier(column) for column in columns)
    destination.execute(
        f'CREATE TABLE {quote_identifier(table)} '
        f'({quoted_columns})'
    )
    placeholders = ','.join('?' for _ in columns)
    select = source.execute(
        f'SELECT {quoted_columns} FROM {quote_identifier(table)}'
    )
    total = 0
    while True:
        rows = select.fetchmany(1000)
        if not rows:
            break
        destination.executemany(
            f'INSERT INTO {quote_identifier(table)} '
            f'({quoted_columns}) VALUES ({placeholders})',
            rows,
        )
        total += len(rows)
    return total


def snapshot_once(source, temporary):
    source_uri = f'{Path(source).as_uri()}?mode=ro'
    source_connection = sqlite3.connect(
        source_uri,
        uri=True,
        timeout=5,
    )
    destination_connection = sqlite3.connect(temporary, timeout=5)
    try:
        source_connection.execute('PRAGMA query_only=ON')
        source_connection.execute('BEGIN')
        if source_connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise SnapshotError('snapshot source quick_check failed')
        if source_connection.execute(
            'PRAGMA foreign_key_check'
        ).fetchone() is not None:
            raise SnapshotError('snapshot source foreign_key_check failed')
        source_tables = {
            row[0]
            for row in source_connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not REQUIRED_TABLES <= source_tables:
            raise SnapshotError('snapshot source schema differs')
        optional = OPTIONAL_TABLES & source_tables
        if optional and optional != OPTIONAL_TABLES:
            raise SnapshotError('snapshot optional schema differs')
        destination_connection.execute('BEGIN IMMEDIATE')
        for table in PROJECTION_TABLES:
            if table in source_tables:
                copy_table(source_connection, destination_connection, table)
        destination_connection.commit()
        journal_mode = destination_connection.execute(
            'PRAGMA journal_mode=DELETE'
        ).fetchone()[0]
        if journal_mode.casefold() != 'delete':
            raise SnapshotError('snapshot journal mode differs')
        destination_connection.execute('PRAGMA query_only=ON')
        return database_state(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def create_snapshot(source, target, *, attempts=4, retry_delay=0.25):
    source = Path(source)
    target = Path(target)
    if attempts < 1 or attempts > 10:
        raise SnapshotError('snapshot attempt bound differs')
    if retry_delay < 0 or retry_delay > 2:
        raise SnapshotError('snapshot retry delay differs')
    if not source.is_absolute() or not target.is_absolute():
        raise SnapshotError('snapshot path is not absolute')
    if '..' in source.parts or '..' in target.parts or source == target:
        raise SnapshotError('snapshot path differs')

    uid = os.geteuid()
    gid = os.getegid()
    validate_regular(source, 'snapshot source', uid=uid, gid=gid)
    validate_directory(target.parent, uid, gid)
    if target.exists() or target.is_symlink():
        validate_regular(
            target,
            'published snapshot',
            mode=0o600,
            uid=uid,
            gid=gid,
        )

    lock_path = target.parent / '.outbox-snapshot.lock'
    lock_flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    lock_descriptor = os.open(lock_path, lock_flags, 0o600)
    try:
        os.fchmod(lock_descriptor, 0o600)
        lock_details = os.fstat(lock_descriptor)
        if (
            not stat.S_ISREG(lock_details.st_mode)
            or lock_details.st_nlink != 1
            or lock_details.st_uid != uid
            or lock_details.st_gid != gid
        ):
            raise SnapshotError('snapshot lock metadata differs')
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)

        last_error = None
        for attempt in range(1, attempts + 1):
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f'.{target.name}.partial-',
                dir=target.parent,
            )
            temporary = Path(temporary_name)
            os.close(descriptor)
            try:
                os.chmod(temporary, 0o600)
                state = snapshot_once(source, temporary)
                for sidecar in (
                    Path(f'{temporary}-wal'),
                    Path(f'{temporary}-shm'),
                ):
                    if sidecar.exists() or sidecar.is_symlink():
                        validate_regular(
                            sidecar,
                            'temporary snapshot sidecar',
                            uid=uid,
                            gid=gid,
                        )
                        sidecar.unlink()
                descriptor = os.open(
                    temporary,
                    os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0),
                )
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                validate_regular(
                    temporary,
                    'temporary snapshot',
                    mode=0o600,
                    uid=uid,
                    gid=gid,
                )
                os.replace(temporary, target)
                fsync_directory(target.parent)
                details = validate_regular(
                    target,
                    'published snapshot',
                    mode=0o600,
                    uid=uid,
                    gid=gid,
                )
                return {
                    **state,
                    'attempts': attempt,
                    'bytes': details.st_size,
                }
            except sqlite3.OperationalError as exc:
                last_error = exc
                if not is_transient(exc) or attempt == attempts:
                    raise
                time.sleep(retry_delay * attempt)
            finally:
                remove_temporary_files(temporary)
        raise SnapshotError('snapshot retry bound exhausted') from last_error
    finally:
        os.close(lock_descriptor)
