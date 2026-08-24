#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE = 'network-log-gx10-reasoning.service'
TIMER = 'network-log-gx10-reasoning.timer'
CONFIRMATION = 'ENABLE-VERIFIED-MANAGED-REASONING'


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


def validate_backup(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('managed reasoning backup is not a regular file')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != 0
        or details.st_gid != 0
        or stat.S_IMODE(details.st_mode) != 0o600
    ):
        raise ValueError('managed reasoning backup metadata differs')
    connection = sqlite3.connect(
        f'file:{path}?mode=ro&immutable=1', uri=True
    )
    try:
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('managed reasoning backup quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError(
                'managed reasoning backup foreign_key_check failed'
            )
    finally:
        connection.close()


def create_backup(database, backup):
    database = Path(database)
    backup = Path(backup)
    parent = backup.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError('managed reasoning backup parent differs')
    parent_details = parent.stat()
    if (
        parent_details.st_uid != 0
        or stat.S_IMODE(parent_details.st_mode) & 0o022
    ):
        raise ValueError('managed reasoning backup parent is not protected')
    if backup.exists() or backup.is_symlink():
        raise ValueError('managed reasoning backup already exists')
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{backup.name}.', dir=parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        source = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
        destination = sqlite3.connect(temporary)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        os.chown(temporary, 0, 0)
        os.chmod(temporary, 0o600)
        os.link(temporary, backup, follow_symlinks=False)
        temporary.unlink()
        fsync_directory(parent)
        validate_backup(backup)
    finally:
        if temporary.exists():
            temporary.unlink()


def run_verifier(database, mode):
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / 'verify-managed-reasoning.py'),
            mode,
            '--database',
            str(database),
            '--private-runtime',
        ],
        check=True,
    )


def counts(database):
    connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
    try:
        return tuple(
            connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            for table in (
                'reasoning_packets',
                'reasoning_runs',
                'reasoning_results',
            )
        )
    finally:
        connection.close()


def disable_runtime():
    subprocess.run(['systemctl', 'disable', '--now', TIMER], check=False)
    subprocess.run(['systemctl', 'stop', SERVICE], check=False)
    subprocess.run(['systemctl', 'reset-failed', SERVICE], check=False)


def activate(database, backup):
    run_verifier(database, '--installed')
    create_backup(database, backup)
    before = counts(database)
    try:
        subprocess.run(['systemctl', 'start', SERVICE], check=True)
        run_verifier(database, '--installed')
        after = counts(database)
        if (
            after[0] < before[0]
            or after[1] - before[1] not in {0, 1}
            or after[2] - before[2] not in {0, 1}
            or after[2] - before[2] > after[1] - before[1]
        ):
            raise ValueError(
                'managed reasoning activation exceeded its bounded cycle'
            )
        subprocess.run(
            ['systemctl', 'enable', '--now', TIMER], check=True
        )
        run_verifier(database, '--active')
    except (OSError, sqlite3.Error, subprocess.CalledProcessError, ValueError):
        disable_runtime()
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description='Activate the verified GX10 managed reasoning timer'
    )
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError('run the managed reasoning activator as root')
        if os.environ.get('GX10_REASONING_ACTIVATE_CONFIRM') != CONFIRMATION:
            raise ValueError(
                'managed reasoning activation confirmation is absent'
            )
        database = args.database.resolve(strict=True)
        activate(database, args.backup)
        print(f'protected_backup_bytes={args.backup.stat().st_size}')
        print(f'protected_backup_sha256={sha256_file(args.backup)}')
        print('protected_backup_mode=0600')
        print('GX10_MANAGED_REASONING_ACTIVATION=PASS')
        return 0
    except (
        OSError,
        sqlite3.Error,
        subprocess.CalledProcessError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
