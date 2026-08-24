#!/usr/bin/env python3
import grp
import os
import pwd
import sqlite3
import stat
import sys
import tempfile
from pathlib import Path

RUNTIME_USER = 'network-log-agent'
RUNTIME_GROUP = 'network-log-agent'
DATABASE_PATH = Path('/var/lib/network-log-gx10/state/events.sqlite3')
SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SCRIPT_DIR.parent / 'sql' / 'initialize.sql'
INCIDENT_SCHEMA_PATH = SCRIPT_DIR.parent / 'sql' / 'incident-v1.sql'


def validate_parent(path):
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError('database parent is not a real directory')
    details = parent.stat()
    if not stat.S_ISDIR(details.st_mode):
        raise ValueError('database parent is not a directory')


def schema_inventory(connection):
    return connection.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' "
        "AND type IN ('table', 'index', 'trigger') "
        "ORDER BY type, name"
    ).fetchall()


def expected_schema_inventory(schema_paths):
    expected = sqlite3.connect(':memory:')
    try:
        for schema_path in schema_paths:
            expected.executescript(Path(schema_path).read_text(encoding='utf-8'))
        return schema_inventory(expected)
    finally:
        expected.close()


def validate_database(connection, schema_paths):
    quick_check = connection.execute('PRAGMA quick_check').fetchone()[0]
    if quick_check != 'ok':
        raise ValueError('SQLite quick_check failed')

    if schema_inventory(connection) != expected_schema_inventory(schema_paths):
        raise ValueError('unexpected SQLite schema contract')

    suppression = connection.execute(
        'SELECT id, rule_type, pattern, enabled '
        'FROM suppression_rules ORDER BY id'
    ).fetchall()
    expected = [
        (1, 'event_code_exact', 'ICMPV6-3-ND_LOG', 1),
        (2, 'event_code_exact', 'ICMPV6-3-ND_RA_LOG', 1),
    ]
    if suppression != expected:
        raise ValueError('unexpected suppression corpus')


def initialize_database(
    path,
    schema_path,
    uid,
    gid,
    incident_schema_path=INCIDENT_SCHEMA_PATH,
):
    path = Path(path)
    schema_path = Path(schema_path)
    if path.exists() or path.is_symlink():
        raise ValueError('clean-machine initializer refuses an existing database')
    incident_schema_path = Path(incident_schema_path)
    schema_paths = (schema_path, incident_schema_path)
    for source in schema_paths:
        if not source.is_file() or source.is_symlink():
            raise ValueError('schema source is not a real file')
    validate_parent(path)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix='.events.sqlite3.',
        dir=path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)

    try:
        connection = sqlite3.connect(temporary_path)
        try:
            for source in schema_paths:
                connection.executescript(source.read_text(encoding='utf-8'))
            validate_database(connection, schema_paths)
        finally:
            connection.close()

        os.chown(temporary_path, uid, gid)
        os.chmod(temporary_path, 0o640)
        os.link(temporary_path, path, follow_symlinks=False)
        temporary_path.unlink()
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main():
    try:
        if os.geteuid() != 0:
            raise ValueError('run this clean-machine initializer as root')
        if os.environ.get('CLEAN_INSTALL_CONFIRM') != 'YES-CLEAN-GX10':
            raise ValueError('CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-GX10')

        uid = pwd.getpwnam(RUNTIME_USER).pw_uid
        gid = grp.getgrnam(RUNTIME_GROUP).gr_gid
        initialize_database(DATABASE_PATH, SCHEMA_PATH, uid, gid)
        print('GX10_DATABASE_INITIALIZE=PASS')
        return 0
    except (KeyError, OSError, sqlite3.Error, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
