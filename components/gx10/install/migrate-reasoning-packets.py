#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
BASE_SCHEMA = GX10_DIR / 'sql' / 'initialize.sql'
INCIDENT_SCHEMA = GX10_DIR / 'sql' / 'incident-v1.sql'
REASONING_SCHEMA = GX10_DIR / 'sql' / 'reasoning-v1.sql'
BUILDER_SOURCE = GX10_DIR / 'sbin' / 'build-reasoning-packets.py'
BUILDER_SHA256 = (
    '3543ca1dd5b661c628fbef6e0101c79d0bc236997d229ce354ba9dc618fc8145'
)
SCHEMA_SHA256 = (
    'bd46f4a51301c225e051aa6b5e27406ad06c651271d7c82fb3b67ac2b21def90'
)
TARGET_UID = 0
TARGET_GID = 0
APPLY_CONFIRMATION = 'INSTALL-UNSCHEDULED-REASONING-PACKETS-V1'
ROLLBACK_CONFIRMATION = 'ROLLBACK-EMPTY-REASONING-PACKETS-V1'
REFERENCE_ROOTS = (
    Path('/etc/systemd/system'),
    Path('/etc/cron.d'),
    Path('/etc/cron.daily'),
    Path('/etc/cron.hourly'),
    Path('/etc/cron.monthly'),
    Path('/etc/cron.weekly'),
)


class MigrationError(ValueError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def require_regular_file(
    path,
    label,
    *,
    owner=None,
    group=None,
    mode=None,
):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise MigrationError(f'{label} is not a real regular file')
    details = path.stat()
    if details.st_nlink != 1:
        raise MigrationError(f'{label} must not be hard-linked')
    if owner is not None and details.st_uid != owner:
        raise MigrationError(f'{label} has unexpected owner')
    if group is not None and details.st_gid != group:
        raise MigrationError(f'{label} has unexpected group')
    if mode is not None and stat.S_IMODE(details.st_mode) != mode:
        raise MigrationError(f'{label} has unexpected mode')
    return details


def require_protected_parent(path, label):
    parent = Path(path).parent
    if parent.is_symlink() or not parent.is_dir():
        raise MigrationError(f'{label} parent is not a real directory')
    details = parent.stat()
    if details.st_uid != TARGET_UID or stat.S_IMODE(details.st_mode) & 0o022:
        raise MigrationError(f'{label} parent is not protected')


def schema_inventory(connection):
    return [
        (kind, name, re.sub(r'\s+', '', sql or '').casefold())
        for kind, name, sql in connection.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' "
            "AND type IN ('table', 'index', 'trigger') "
            'ORDER BY type, name'
        )
    ]


def expected_inventory(migrated):
    connection = sqlite3.connect(':memory:')
    try:
        connection.executescript(BASE_SCHEMA.read_text(encoding='utf-8'))
        connection.executescript(INCIDENT_SCHEMA.read_text(encoding='utf-8'))
        if migrated:
            connection.executescript(
                REASONING_SCHEMA.read_text(encoding='utf-8')
            )
        return schema_inventory(connection)
    finally:
        connection.close()


def validate_database(connection, *, migrated):
    if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise MigrationError('SQLite quick_check failed')
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise MigrationError('SQLite foreign_key_check failed')
    if schema_inventory(connection) != expected_inventory(migrated):
        state = 'reasoning' if migrated else 'incident'
        raise MigrationError(f'database does not match exact {state} schema')
    expected = sqlite3.connect(':memory:')
    try:
        expected.executescript(BASE_SCHEMA.read_text(encoding='utf-8'))
        expected_suppression = expected.execute(
            'SELECT id, rule_type, pattern, enabled '
            'FROM suppression_rules ORDER BY id'
        ).fetchall()
    finally:
        expected.close()
    actual_suppression = connection.execute(
        'SELECT id, rule_type, pattern, enabled '
        'FROM suppression_rules ORDER BY id'
    ).fetchall()
    if actual_suppression != expected_suppression:
        raise MigrationError('functional suppression corpus differs')
    if connection.execute('PRAGMA user_version').fetchone()[0] != 0:
        raise MigrationError('unexpected SQLite user_version')
    if connection.execute('PRAGMA application_id').fetchone()[0] != 0:
        raise MigrationError('unexpected SQLite application_id')


def validate_candidates():
    require_regular_file(BUILDER_SOURCE, 'repository packet builder')
    require_regular_file(REASONING_SCHEMA, 'repository reasoning schema')
    if sha256_file(BUILDER_SOURCE) != BUILDER_SHA256:
        raise MigrationError('repository packet builder hash differs')
    if sha256_file(REASONING_SCHEMA) != SCHEMA_SHA256:
        raise MigrationError('repository reasoning schema hash differs')


def reference_count(target):
    needle = str(target)
    matches = 0
    for root in REFERENCE_ROOTS:
        if root.is_symlink() or not root.is_dir():
            continue
        for path in root.rglob('*'):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                matches += needle in path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
    return matches


def backup_database(connection, backup):
    backup = Path(backup)
    require_protected_parent(backup, 'backup')
    if backup.exists() or backup.is_symlink():
        raise MigrationError('protected database backup already exists')
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{backup.name}.',
        dir=backup.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        destination = sqlite3.connect(temporary)
        try:
            connection.backup(destination)
            validate_database(destination, migrated=False)
        finally:
            destination.close()
        os.chown(temporary, TARGET_UID, TARGET_GID)
        os.chmod(temporary, 0o600)
        os.link(temporary, backup, follow_symlinks=False)
        temporary.unlink()
        fsync_directory(backup.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def schema_statements():
    statements = []
    pending = ''
    for line in REASONING_SCHEMA.read_text(encoding='utf-8').splitlines(True):
        pending += line
        if not sqlite3.complete_statement(pending):
            continue
        statement = pending.strip()
        pending = ''
        normalized = statement.rstrip(';').strip().upper()
        if normalized in {
            'PRAGMA FOREIGN_KEYS=ON',
            'BEGIN IMMEDIATE',
            'COMMIT',
        }:
            continue
        statements.append(statement)
    if pending.strip():
        raise MigrationError('reasoning schema contains an incomplete statement')
    return statements


def apply_schema(connection):
    for statement in schema_statements():
        connection.execute(statement)


def remove_schema(connection):
    connection.execute('DROP TRIGGER reasoning_packets_no_update')
    connection.execute('DROP TRIGGER reasoning_packets_no_delete')
    connection.execute('DROP TABLE reasoning_packets')


def install_builder(target):
    target = Path(target)
    require_protected_parent(target, 'packet builder target')
    if target.exists() or target.is_symlink():
        raise MigrationError('packet builder target already exists')
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{target.name}.',
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with BUILDER_SOURCE.open('rb') as input_handle, os.fdopen(
            descriptor,
            'wb',
        ) as output_handle:
            for chunk in iter(lambda: input_handle.read(1024 * 1024), b''):
                output_handle.write(chunk)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.chown(temporary, TARGET_UID, TARGET_GID)
        os.chmod(temporary, 0o755)
        os.link(temporary, target, follow_symlinks=False)
        temporary.unlink()
        fsync_directory(target.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_backup(backup):
    require_regular_file(
        backup,
        'protected database backup',
        owner=TARGET_UID,
        group=TARGET_GID,
        mode=0o600,
    )
    connection = sqlite3.connect(
        f'file:{Path(backup)}?mode=ro&immutable=1',
        uri=True,
    )
    try:
        validate_database(connection, migrated=False)
    finally:
        connection.close()


def validate_installed_state(database, target, backup):
    validate_candidates()
    require_regular_file(
        target,
        'installed packet builder',
        owner=TARGET_UID,
        group=TARGET_GID,
        mode=0o755,
    )
    if sha256_file(target) != BUILDER_SHA256:
        raise MigrationError('installed packet builder hash differs')
    if reference_count(target) != 0:
        raise MigrationError('packet builder unexpectedly has a scheduler reference')
    validate_backup(backup)
    connection = sqlite3.connect(f'file:{Path(database)}?mode=ro', uri=True)
    try:
        validate_database(connection, migrated=True)
    finally:
        connection.close()


def apply_migration(database, target, backup):
    database = Path(database)
    target = Path(target)
    validate_candidates()
    database_details = require_regular_file(database, 'application database')
    require_protected_parent(target, 'packet builder target')
    if target.exists() or target.is_symlink():
        raise MigrationError('packet builder target already exists')
    if reference_count(target) != 0:
        raise MigrationError('packet builder target already has a scheduler reference')

    connection = sqlite3.connect(database)
    target_created = False
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        validate_database(connection, migrated=False)
        backup_database(connection, backup)
        connection.execute('BEGIN IMMEDIATE')
        apply_schema(connection)
        validate_database(connection, migrated=True)
        install_builder(target)
        target_created = True
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        if target_created and target.exists() and not target.is_symlink():
            if sha256_file(target) == BUILDER_SHA256:
                target.unlink()
                fsync_directory(target.parent)
        raise
    finally:
        connection.close()
    after = database.stat()
    if (
        after.st_uid != database_details.st_uid
        or after.st_gid != database_details.st_gid
        or stat.S_IMODE(after.st_mode) != stat.S_IMODE(database_details.st_mode)
    ):
        raise MigrationError('application database metadata changed')
    validate_installed_state(database, target, backup)


def rollback_migration(database, target, backup):
    database = Path(database)
    target = Path(target)
    validate_installed_state(database, target, backup)
    connection = sqlite3.connect(database)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute(
            'SELECT COUNT(*) FROM reasoning_packets'
        ).fetchone()[0]:
            raise MigrationError('rollback refuses nonempty reasoning packets')
        remove_schema(connection)
        validate_database(connection, migrated=False)
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
    target.unlink()
    fsync_directory(target.parent)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Guarded unscheduled GX10 reasoning-packet migration'
    )
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--builder-target', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--apply', action='store_true')
    action.add_argument('--verify', action='store_true')
    action.add_argument('--rollback', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise MigrationError('run the reasoning migration guard as root')
        expected_confirmation = (
            ROLLBACK_CONFIRMATION if args.rollback else APPLY_CONFIRMATION
        )
        if os.environ.get('GX10_REASONING_MIGRATE_CONFIRM') != expected_confirmation:
            raise MigrationError('reasoning migration confirmation is absent')
        database = args.database.resolve(strict=True)
        if args.apply:
            apply_migration(database, args.builder_target, args.backup)
            action = 'applied'
        elif args.rollback:
            rollback_migration(database, args.builder_target, args.backup)
            action = 'rolled_back'
        else:
            validate_installed_state(
                database,
                args.builder_target,
                args.backup,
            )
            action = 'verified'
        print(f'gx10_reasoning_packet_migration={action}')
        print('GX10_REASONING_PACKET_MIGRATION=PASS')
        return 0
    except (MigrationError, OSError, sqlite3.Error) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
