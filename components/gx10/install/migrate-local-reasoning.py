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
PACKET_SCHEMA = GX10_DIR / 'sql' / 'reasoning-v1.sql'
INFERENCE_SCHEMA = GX10_DIR / 'sql' / 'inference-v1.sql'
PACKET_BUILDER_SHA256 = (
    '3543ca1dd5b661c628fbef6e0101c79d0bc236997d229ce354ba9dc618fc8145'
)
ARTIFACTS = (
    (
        'caller',
        GX10_DIR / 'sbin' / 'run-local-reasoning.py',
        'e9b894afa16fd5f138cfeec299be58328fd02454db2b53c3e395809e04d58cd0',
        0o755,
    ),
    (
        'configuration',
        GX10_DIR / 'config' / 'reasoning-runtime-v2.json',
        'e7bde8d878e71d8a1b11af01170ff332920aae1df1a65536b516abf5862428f0',
        0o644,
    ),
    (
        'prompt',
        GX10_DIR / 'prompts' / 'incident-assessment-v2.txt',
        'c24a1e4a5af021ea66475cdb77c792b19f023caf93f344f64be4dedf1ebb634c',
        0o644,
    ),
    (
        'output schema',
        GX10_DIR / 'prompts' / 'incident-assessment-output-v2.json',
        '1ec4e28d0d18320c7469d4f1bb26a5c766515ff008c5803d24ce214ded69928a',
        0o644,
    ),
)
INFERENCE_SCHEMA_SHA256 = (
    '6365f99eb834c0561a1246757a4404bbbc7ec831fe910325eff8dcfd92113a90'
)
TARGET_UID = 0
TARGET_GID = 0
APPLY_CONFIRMATION = 'INSTALL-UNSCHEDULED-LOCAL-REASONING-V1'
ROLLBACK_CONFIRMATION = 'ROLLBACK-EMPTY-LOCAL-REASONING-V1'
REFERENCE_ROOTS = (
    Path('/etc/systemd/system'),
    Path('/etc/cron.d'),
    Path('/etc/cron.daily'),
    Path('/etc/cron.hourly'),
    Path('/etc/cron.monthly'),
    Path('/etc/cron.weekly'),
)
INFERENCE_TABLES = (
    'reasoning_model_versions',
    'reasoning_prompt_versions',
    'reasoning_runs',
    'reasoning_results',
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


def require_regular_file(path, label, *, owner=None, group=None, mode=None):
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
        for schema in (BASE_SCHEMA, INCIDENT_SCHEMA, PACKET_SCHEMA):
            connection.executescript(schema.read_text(encoding='utf-8'))
        if migrated:
            connection.executescript(
                INFERENCE_SCHEMA.read_text(encoding='utf-8')
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
        state = 'inference' if migrated else 'reasoning packet'
        raise MigrationError(f'database does not match exact {state} schema')
    expected = sqlite3.connect(':memory:')
    try:
        expected.executescript(BASE_SCHEMA.read_text(encoding='utf-8'))
        suppression = expected.execute(
            'SELECT id, rule_type, pattern, enabled '
            'FROM suppression_rules ORDER BY id'
        ).fetchall()
    finally:
        expected.close()
    actual = connection.execute(
        'SELECT id, rule_type, pattern, enabled '
        'FROM suppression_rules ORDER BY id'
    ).fetchall()
    if actual != suppression:
        raise MigrationError('functional suppression corpus differs')
    if connection.execute('PRAGMA user_version').fetchone()[0] != 0:
        raise MigrationError('unexpected SQLite user_version')
    if connection.execute('PRAGMA application_id').fetchone()[0] != 0:
        raise MigrationError('unexpected SQLite application_id')


def validate_candidates():
    require_regular_file(INFERENCE_SCHEMA, 'repository inference schema')
    if sha256_file(INFERENCE_SCHEMA) != INFERENCE_SCHEMA_SHA256:
        raise MigrationError('repository inference schema hash differs')
    for label, source, digest, _ in ARTIFACTS:
        require_regular_file(source, f'repository {label}')
        if sha256_file(source) != digest:
            raise MigrationError(f'repository {label} hash differs')


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


def artifact_bindings(targets):
    if len(targets) != len(ARTIFACTS):
        raise MigrationError('installed inference artifact target count differs')
    return tuple(
        (label, source, digest, mode, Path(target))
        for (label, source, digest, mode), target in zip(ARTIFACTS, targets)
    )


def validate_target_preflight(bindings):
    resolved = [str(target.absolute()) for *_, target in bindings]
    if len(set(resolved)) != len(resolved):
        raise MigrationError('inference artifact targets are not distinct')
    for label, _, _, _, target in bindings:
        require_protected_parent(target, f'{label} target')
        if target.exists() or target.is_symlink():
            raise MigrationError(f'{label} target already exists')
    caller = bindings[0][-1]
    if reference_count(caller) != 0:
        raise MigrationError('local reasoning caller already has a scheduler reference')


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
    for line in INFERENCE_SCHEMA.read_text(encoding='utf-8').splitlines(True):
        pending += line
        if not sqlite3.complete_statement(pending):
            continue
        statement = pending.strip()
        pending = ''
        normalized = statement.rstrip(';').strip().upper()
        if normalized in {'PRAGMA FOREIGN_KEYS=ON', 'BEGIN IMMEDIATE', 'COMMIT'}:
            continue
        statements.append(statement)
    if pending.strip():
        raise MigrationError('inference schema contains an incomplete statement')
    return statements


def apply_schema(connection):
    for statement in schema_statements():
        connection.execute(statement)


def remove_schema(connection):
    for trigger in (
        'reasoning_results_no_delete',
        'reasoning_results_no_update',
        'reasoning_runs_no_delete',
        'reasoning_runs_guard_update',
        'reasoning_prompt_versions_no_delete',
        'reasoning_prompt_versions_no_update',
        'reasoning_model_versions_no_delete',
        'reasoning_model_versions_no_update',
    ):
        connection.execute(f'DROP TRIGGER {trigger}')
    for table in (
        'reasoning_results',
        'reasoning_runs',
        'reasoning_prompt_versions',
        'reasoning_model_versions',
    ):
        connection.execute(f'DROP TABLE {table}')


def install_one(source, target, mode):
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{target.name}.',
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with source.open('rb') as input_handle, os.fdopen(
            descriptor,
            'wb',
        ) as output_handle:
            for chunk in iter(lambda: input_handle.read(1024 * 1024), b''):
                output_handle.write(chunk)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.chown(temporary, TARGET_UID, TARGET_GID)
        os.chmod(temporary, mode)
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


def validate_packet_builder(packet_builder):
    require_regular_file(
        packet_builder,
        'installed packet builder',
        owner=TARGET_UID,
        group=TARGET_GID,
        mode=0o755,
    )
    if sha256_file(packet_builder) != PACKET_BUILDER_SHA256:
        raise MigrationError('installed packet builder hash differs')
    if reference_count(packet_builder) != 0:
        raise MigrationError('packet builder unexpectedly has a scheduler reference')


def validate_installed_state(database, targets, packet_builder, backup):
    validate_candidates()
    bindings = artifact_bindings(targets)
    validate_packet_builder(packet_builder)
    for label, _, digest, mode, target in bindings:
        require_regular_file(
            target,
            f'installed {label}',
            owner=TARGET_UID,
            group=TARGET_GID,
            mode=mode,
        )
        if sha256_file(target) != digest:
            raise MigrationError(f'installed {label} hash differs')
    if reference_count(bindings[0][-1]) != 0:
        raise MigrationError('local reasoning caller has a scheduler reference')
    validate_backup(backup)
    connection = sqlite3.connect(f'file:{Path(database)}?mode=ro', uri=True)
    try:
        validate_database(connection, migrated=True)
    finally:
        connection.close()


def apply_migration(database, targets, packet_builder, backup):
    database = Path(database)
    bindings = artifact_bindings(targets)
    validate_candidates()
    validate_packet_builder(packet_builder)
    validate_target_preflight(bindings)
    database_details = require_regular_file(database, 'application database')

    connection = sqlite3.connect(database)
    created = []
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        validate_database(connection, migrated=False)
        backup_database(connection, backup)
        connection.execute('BEGIN IMMEDIATE')
        apply_schema(connection)
        validate_database(connection, migrated=True)
        for _, source, _, mode, target in bindings:
            install_one(source, target, mode)
            created.append(target)
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        for target in reversed(created):
            if target.exists() and not target.is_symlink():
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
    validate_installed_state(database, targets, packet_builder, backup)


def rollback_migration(database, targets, packet_builder, backup):
    database = Path(database)
    bindings = artifact_bindings(targets)
    validate_installed_state(database, targets, packet_builder, backup)
    connection = sqlite3.connect(database)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('BEGIN IMMEDIATE')
        if any(
            connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            for table in INFERENCE_TABLES
        ):
            raise MigrationError('rollback refuses nonempty inference state')
        remove_schema(connection)
        validate_database(connection, migrated=False)
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
    for _, _, digest, _, target in reversed(bindings):
        if sha256_file(target) != digest:
            raise MigrationError('installed artifact changed during rollback')
        target.unlink()
        fsync_directory(target.parent)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Guarded unscheduled GX10 local-reasoning migration'
    )
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--packet-builder', type=Path, required=True)
    parser.add_argument('--caller-target', type=Path, required=True)
    parser.add_argument('--config-target', type=Path, required=True)
    parser.add_argument('--prompt-target', type=Path, required=True)
    parser.add_argument('--output-schema-target', type=Path, required=True)
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
            raise MigrationError('run the local-reasoning migration guard as root')
        expected = ROLLBACK_CONFIRMATION if args.rollback else APPLY_CONFIRMATION
        if os.environ.get('GX10_INFERENCE_MIGRATE_CONFIRM') != expected:
            raise MigrationError('local-reasoning migration confirmation is absent')
        database = args.database.resolve(strict=True)
        targets = (
            args.caller_target,
            args.config_target,
            args.prompt_target,
            args.output_schema_target,
        )
        if args.apply:
            apply_migration(database, targets, args.packet_builder, args.backup)
            action = 'applied'
        elif args.rollback:
            rollback_migration(database, targets, args.packet_builder, args.backup)
            action = 'rolled_back'
        else:
            validate_installed_state(
                database,
                targets,
                args.packet_builder,
                args.backup,
            )
            action = 'verified'
        print(f'gx10_local_reasoning_migration={action}')
        print('GX10_LOCAL_REASONING_MIGRATION=PASS')
        return 0
    except (MigrationError, OSError, sqlite3.Error) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
