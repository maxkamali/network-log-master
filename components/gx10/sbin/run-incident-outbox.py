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


CONFIG_PATH = Path('/etc/network-log-gx10/result-outbox.json')
PRODUCER_PATH = Path(
    '/usr/local/libexec/network-log-gx10/build-incident-outbox.py'
)
PRODUCER_SHA256 = (
    'f87f65fd92e407efa6e3521aa219e41e869f8786db6a8921091ae0fa0027e9a1'
)


class ManagedIncidentOutboxError(ValueError):
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
        raise ManagedIncidentOutboxError(
            'managed incident outbox artifact is not a regular file'
        )
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != 0
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ManagedIncidentOutboxError(
            'managed incident outbox artifact metadata differs'
        )


def load_config(path=CONFIG_PATH):
    validate_regular(path, 0o640)
    path = Path(path)
    if path.stat().st_size > 4096:
        raise ManagedIncidentOutboxError(
            'managed incident outbox configuration is too large'
        )
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedIncidentOutboxError(
            'managed incident outbox configuration is invalid'
        ) from exc
    if not isinstance(data, dict) or set(data) != {
        'database_path',
        'ready_path',
        'delivered_path',
    }:
        raise ManagedIncidentOutboxError(
            'managed incident outbox configuration keys differ'
        )
    paths = {}
    for key, value in data.items():
        if not isinstance(value, str) or not value.startswith('/'):
            raise ManagedIncidentOutboxError(
                'managed incident outbox configuration path differs'
            )
        candidate = Path(value)
        if '..' in candidate.parts:
            raise ManagedIncidentOutboxError(
                'managed incident outbox configuration path differs'
            )
        paths[key] = candidate
    if (
        paths['ready_path'] == paths['delivered_path']
        or paths['ready_path'].parent != paths['delivered_path'].parent
    ):
        raise ManagedIncidentOutboxError(
            'managed incident outbox configuration layout differs'
        )
    return paths


def load_producer(path=PRODUCER_PATH):
    validate_regular(path, 0o755)
    if sha256_file(path) != PRODUCER_SHA256:
        raise ManagedIncidentOutboxError(
            'managed incident outbox producer hash differs'
        )
    specification = importlib.util.spec_from_file_location(
        'installed_incident_outbox_producer', path
    )
    if specification is None or specification.loader is None:
        raise ManagedIncidentOutboxError(
            'managed incident outbox producer cannot be loaded'
        )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run(config_path=CONFIG_PATH, producer_path=PRODUCER_PATH):
    try:
        config = load_config(config_path)
        producer = load_producer(producer_path)
        state = producer.build(
            config['database_path'],
            config['ready_path'],
            config['delivered_path'],
        )
        print(
            'MANAGED_INCIDENT_OUTBOX schema=1 '
            f'incidents={state["incidents"]} changed={state["changed"]} '
            f'batches={state["batches"]} created={state["created"]} '
            f'reused={state["reused"]} ready={state["ready"]} '
            f'delivered={state["delivered"]} '
            f'recovered={state["recovered"]} '
            f'written_bytes={state["written_bytes"]}'
        )
        print('GX10_MANAGED_INCIDENT_OUTBOX=PASS')
        return 0
    except (
        OSError,
        sqlite3.Error,
        ManagedIncidentOutboxError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_INCIDENT_OUTBOX=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if os.geteuid() == 0:
        print(
            'ERROR: managed incident outbox must run as its service user',
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(run())
