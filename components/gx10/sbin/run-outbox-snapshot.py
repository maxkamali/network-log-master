#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys


CONFIG_PATH = Path('/etc/network-log-gx10/outbox-snapshot.json')
PRODUCER_PATH = Path(
    '/usr/local/libexec/network-log-gx10/create-outbox-snapshot.py'
)
PRODUCER_SHA256 = (
    '2b6f508e24ebc78d4be6d38c963eedf871001ff136bde86287c7bd976010a82d'
)


class ManagedSnapshotError(ValueError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_regular(path, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ManagedSnapshotError(
            'managed outbox snapshot artifact is not a regular file'
        )
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != 0
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ManagedSnapshotError(
            'managed outbox snapshot artifact metadata differs'
        )


def load_config(path=CONFIG_PATH):
    validate_regular(path, 0o640)
    path = Path(path)
    if path.stat().st_size > 4096:
        raise ManagedSnapshotError(
            'managed outbox snapshot configuration is too large'
        )
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedSnapshotError(
            'managed outbox snapshot configuration is invalid'
        ) from exc
    if not isinstance(data, dict) or set(data) != {
        'snapshot_database_path',
        'source_database_path',
    }:
        raise ManagedSnapshotError(
            'managed outbox snapshot configuration keys differ'
        )
    paths = {}
    for key, value in data.items():
        if not isinstance(value, str) or not value.startswith('/'):
            raise ManagedSnapshotError(
                'managed outbox snapshot configuration path differs'
            )
        candidate = Path(value)
        if '..' in candidate.parts:
            raise ManagedSnapshotError(
                'managed outbox snapshot configuration path differs'
            )
        paths[key] = candidate
    if paths['source_database_path'] == paths['snapshot_database_path']:
        raise ManagedSnapshotError(
            'managed outbox snapshot configuration layout differs'
        )
    return paths


def load_producer(path=PRODUCER_PATH):
    validate_regular(path, 0o755)
    if sha256_file(path) != PRODUCER_SHA256:
        raise ManagedSnapshotError(
            'managed outbox snapshot producer hash differs'
        )
    specification = importlib.util.spec_from_file_location(
        'installed_outbox_snapshot_producer', path
    )
    if specification is None or specification.loader is None:
        raise ManagedSnapshotError(
            'managed outbox snapshot producer cannot be loaded'
        )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run(config_path=CONFIG_PATH, producer_path=PRODUCER_PATH):
    try:
        config = load_config(config_path)
        producer = load_producer(producer_path)
        result = producer.create_snapshot(
            config['source_database_path'],
            config['snapshot_database_path'],
        )
        print(
            'MANAGED_OUTBOX_SNAPSHOT schema=1 '
            f'results={result["results"]} incidents={result["incidents"]} '
            f'bytes={result["bytes"]} attempts={result["attempts"]}'
        )
        print('GX10_MANAGED_OUTBOX_SNAPSHOT=PASS')
        return 0
    except (
        OSError,
        sqlite3.Error,
        ManagedSnapshotError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_OUTBOX_SNAPSHOT=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if os.geteuid() == 0:
        print(
            'ERROR: managed outbox snapshot must run as its service user',
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(run())
