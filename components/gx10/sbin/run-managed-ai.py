#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import stat
import sys
import types


MANAGED_RUNNER_PATH = Path(
    '/usr/local/libexec/network-log-gx10/run-managed-reasoning.py'
)
TRIAGE_PATH = Path(
    '/usr/local/libexec/network-log-gx10/triage-uncovered-events.py'
)
INCIDENT_ENGINE_PATH = Path(
    '/usr/local/libexec/network-log-gx10/incident-engine.py'
)
CONFIG_PATH = Path('/etc/network-log-gx10/triage-runtime-v1.json')
PROMPT_PATH = Path('/etc/network-log-gx10/uncovered-event-triage-v1.txt')
OUTPUT_SCHEMA_PATH = Path(
    '/etc/network-log-gx10/uncovered-event-triage-output-v1.json'
)
MANAGED_CONFIG_PATH = Path('/etc/network-log-gx10/managed-reasoning.json')

# Updated mechanically by the release validation step.
MANAGED_RUNNER_SHA256 = '2b692e0f2be29f717b3085f9efa0fb45605cab9982131dab6dc14375d9f3ad57'
TRIAGE_SHA256 = '374902c89c855a7dc61f155be98d46a42eddf718c066a852eefea1b542b711c5'
INCIDENT_ENGINE_SHA256 = '0e2642d5cc20881cfbd9069f5ef0a36f38aaab5cda6b1522f312eee4443f8527'
CONFIG_SHA256 = '44da2b8835e0dad88da3bc72f185dcc22971443a9c02e0eea42a84f5199e30e6'
PROMPT_SHA256 = '561675daf887b68e10f6988492caa29dd72ed1c4b710d7c0e47102d98c589889'
OUTPUT_SCHEMA_SHA256 = 'c8603b0f6f86d72b4964c4d5d67af3239a4a7cde18c92fda04c2ca1ad733c109'


class ManagedAiError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_artifact(path: Path, expected_hash: str, mode: int) -> None:
    if not expected_hash or len(expected_hash) != 64:
        raise ManagedAiError('managed AI release hash is unavailable')
    if path.is_symlink() or not path.is_file():
        raise ManagedAiError('managed AI artifact is not a regular file')
    details = path.stat()
    if (
        details.st_nlink != 1
        or stat.S_IMODE(details.st_mode) != mode
        or sha256_file(path) != expected_hash
    ):
        raise ManagedAiError('managed AI artifact differs')


def load_module(name: str, path: Path, database: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ManagedAiError('managed AI stage cannot be loaded')
    module = importlib.util.module_from_spec(specification)
    fake = types.ModuleType('runtime_config')
    fake.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake
    try:
        specification.loader.exec_module(module)
    finally:
        if previous is None:
            del sys.modules['runtime_config']
        else:
            sys.modules['runtime_config'] = previous
    return module


def acquire_lock(path: Path):
    descriptor = os.open(
        path,
        os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    details = os.fstat(descriptor)
    if (
        not stat.S_ISREG(details.st_mode)
        or details.st_nlink != 1
        or details.st_uid != os.geteuid()
        or stat.S_IMODE(details.st_mode) != 0o600
    ):
        os.close(descriptor)
        raise ManagedAiError('managed AI lock metadata differs')
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise ManagedAiError('managed AI cycle is already running') from exc
    return descriptor


def main(
    database_path=None,
    *,
    managed_runner_path=MANAGED_RUNNER_PATH,
    triage_path=TRIAGE_PATH,
    incident_engine_path=INCIDENT_ENGINE_PATH,
    config_path=CONFIG_PATH,
    prompt_path=PROMPT_PATH,
    output_schema_path=OUTPUT_SCHEMA_PATH,
    lock_path=None,
    triage_transport=None,
) -> int:
    descriptor = None
    try:
        managed_runner_path = Path(managed_runner_path)
        triage_path = Path(triage_path)
        incident_engine_path = Path(incident_engine_path)
        config_path = Path(config_path)
        prompt_path = Path(prompt_path)
        output_schema_path = Path(output_schema_path)
        for path, expected, mode in (
            (managed_runner_path, MANAGED_RUNNER_SHA256, 0o755),
            (triage_path, TRIAGE_SHA256, 0o755),
            (incident_engine_path, INCIDENT_ENGINE_SHA256, 0o755),
            (config_path, CONFIG_SHA256, 0o644),
            (prompt_path, PROMPT_SHA256, 0o644),
            (output_schema_path, OUTPUT_SCHEMA_SHA256, 0o644),
        ):
            validate_artifact(path, expected, mode)
        managed = load_module(
            'gx10_managed_reasoning_for_ai', managed_runner_path,
            Path(database_path) if database_path is not None else Path('/'),
        )
        database = (
            Path(database_path)
            if database_path is not None
            else managed.load_database_path(MANAGED_CONFIG_PATH)
        )
        if database is None:
            raise ManagedAiError('managed AI database is unavailable')
        descriptor = acquire_lock(
            Path(lock_path) if lock_path else database.parent / 'managed-ai.lock'
        )
        before = managed.snapshot(database)
        if before['pending']:
            return managed.main(database_path=database)
        triage = load_module('gx10_managed_ai_triage', triage_path, database)
        arguments = {
            'config_path': config_path,
            'prompt_path': prompt_path,
            'output_schema_path': output_schema_path,
            'incident_engine_path': incident_engine_path,
            'mode': 'active',
            'learned_coverage': True,
        }
        if triage_transport is not None:
            arguments['transport'] = triage_transport
        result = triage.run(database, **arguments)
        print(
            'MANAGED_AI schema=1 '
            f'result={result["result"]} invoked={result.get("invoked", 0)} '
            f'decisions={result.get("decisions", 0)} '
            f'applied_incidents={result.get("applied_incidents", 0)} '
            f'promoted_rules={result.get("promoted_rules", 0)}'
        )
        if result.get('invoked', 0) == 1:
            print('GX10_MANAGED_AI=PASS')
            return 0
        return managed.main(database_path=database)
    except (ManagedAiError, OSError, sqlite3.Error, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_AI=FAIL', file=sys.stderr)
        return 1
    finally:
        if descriptor is not None:
            os.close(descriptor)


if __name__ == '__main__':
    sys.exit(main())
