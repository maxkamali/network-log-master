#!/usr/bin/env python3
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time
import types


MANAGED_CONFIG_PATH = Path(
    '/etc/network-log-gx10/managed-reasoning.json'
)
PACKET_BUILDER_PATH = Path(
    '/usr/local/libexec/network-log-gx10/build-reasoning-packets.py'
)
CALLER_PATH = Path(
    '/usr/local/libexec/network-log-gx10/run-local-reasoning.py'
)
RUNTIME_CONFIG_PATH = Path(
    '/etc/network-log-gx10/reasoning-runtime-v2.json'
)
PROMPT_PATH = Path(
    '/etc/network-log-gx10/incident-assessment-v2.txt'
)
OUTPUT_SCHEMA_PATH = Path(
    '/etc/network-log-gx10/incident-assessment-output-v2.json'
)
PACKET_BUILDER_SHA256 = (
    '62bc6c3ca3be60457989f73e6eaced04a1ffd2f16043050c767e7b7c86514326'
)
CALLER_SHA256 = (
    'dac1e176108452c77ea4eb2f7195dd8eb8223576ab8cbdb2cb95a2acbb8fcbe8'
)
RUNTIME_CONFIG_SHA256 = (
    '8a55aeb708a05fafd3eb1d4df206714339deb344588f218f00ecbee5fdd93cd9'
)
PROMPT_SHA256 = (
    'c24a1e4a5af021ea66475cdb77c792b19f023caf93f344f64be4dedf1ebb634c'
)
OUTPUT_SCHEMA_SHA256 = (
    '13083841c44253b326f1294b930acae435bfdddb458b47c31a9fd385b181abd0'
)
MODEL_VERSION = 'ollama-gemma4-c6eb396d-v1'
PROMPT_VERSION = 'incident-assessment-v2-r3'
TERMINAL_FAILURES = (
    'INFERENCE_UNAVAILABLE',
    'INFERENCE_TIMEOUT',
    'TRANSPORT_ERROR',
    'INVALID_RESPONSE',
    'INVALID_OUTPUT',
)


class ManagedReasoningError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_artifact(
    path: Path,
    expected_hash: str,
    expected_mode: int,
) -> None:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ManagedReasoningError(
            'managed reasoning artifact is not a regular file'
        )
    details = path.stat()
    if (
        details.st_nlink != 1
        or stat.S_IMODE(details.st_mode) != expected_mode
    ):
        raise ManagedReasoningError(
            'managed reasoning artifact metadata differs'
        )
    if sha256_file(path) != expected_hash:
        raise ManagedReasoningError(
            'managed reasoning artifact hash differs'
        )


def load_database_path(path=MANAGED_CONFIG_PATH):
    path = Path(path)
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 4096
    ):
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or set(data) != {'database_path'}:
        return None
    value = data['database_path']
    if not isinstance(value, str) or not value.startswith('/'):
        return None
    database = Path(value)
    if '..' in database.parts:
        return None
    return database


def load_stage(name: str, path: Path, database: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ManagedReasoningError(
            'managed reasoning stage cannot be loaded'
        )
    module = importlib.util.module_from_spec(specification)
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
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
        raise ManagedReasoningError(
            'managed reasoning lock metadata differs'
        )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise ManagedReasoningError(
            'managed reasoning cycle is already running'
        ) from exc
    return descriptor


def snapshot(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ManagedReasoningError(
                'managed reasoning quick_check failed'
            )
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ManagedReasoningError(
                'managed reasoning foreign_key_check failed'
            )
        required = {
            'reasoning_packets',
            'reasoning_model_versions',
            'reasoning_prompt_versions',
            'reasoning_runs',
            'reasoning_results',
        }
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not required <= tables:
            raise ManagedReasoningError(
                'managed reasoning database schema differs'
            )
        status_rows = dict(
            connection.execute(
                'SELECT status, COUNT(*) FROM reasoning_runs GROUP BY status'
            )
        )
        allowed_statuses = {'STARTED', 'SUCCEEDED', *TERMINAL_FAILURES}
        if not set(status_rows) <= allowed_statuses:
            raise ManagedReasoningError(
                'managed reasoning run status differs'
            )
        result_mismatches = connection.execute(
            '''
            SELECT COUNT(*) FROM reasoning_runs AS run
            WHERE (run.status = 'SUCCEEDED') != EXISTS (
                SELECT 1 FROM reasoning_results AS result
                WHERE result.run_id = run.run_id
            )
            '''
        ).fetchone()[0]
        if result_mismatches:
            raise ManagedReasoningError(
                'managed reasoning result invariant differs'
            )
        packets = connection.execute(
            'SELECT COUNT(*) FROM reasoning_packets'
        ).fetchone()[0]
        pending = connection.execute(
            '''
            SELECT COUNT(*) FROM reasoning_packets AS packet
            WHERE NOT EXISTS (
                SELECT 1 FROM reasoning_runs AS run
                WHERE run.packet_id = packet.packet_id
                  AND run.model_version = ?
                  AND run.prompt_version = ?
                  AND run.attempt_number = 1
            )
            ''',
            (MODEL_VERSION, PROMPT_VERSION),
        ).fetchone()[0]
        return {
            'packets': packets,
            'pending': pending,
            'model_versions': connection.execute(
                'SELECT COUNT(*) FROM reasoning_model_versions'
            ).fetchone()[0],
            'prompt_versions': connection.execute(
                'SELECT COUNT(*) FROM reasoning_prompt_versions'
            ).fetchone()[0],
            'runs': sum(status_rows.values()),
            'started': status_rows.get('STARTED', 0),
            'succeeded': status_rows.get('SUCCEEDED', 0),
            'failures': sum(
                status_rows.get(status, 0) for status in TERMINAL_FAILURES
            ),
            'results': connection.execute(
                'SELECT COUNT(*) FROM reasoning_results'
            ).fetchone()[0],
        }
    finally:
        connection.close()


def emit_summary(
    state: dict[str, int],
    *,
    result: str,
    duration_ms: int,
    packets_created: int,
    builder_deferred: int,
    invoked: int,
) -> None:
    print(
        'MANAGED_REASONING '
        'schema=1 '
        f'result={result} duration_ms={duration_ms} '
        f'packets_created={packets_created} '
        f'builder_deferred={builder_deferred} invoked={invoked} '
        f'packets={state["packets"]} pending={state["pending"]} '
        f'model_versions={state["model_versions"]} '
        f'prompt_versions={state["prompt_versions"]} '
        f'runs={state["runs"]} started={state["started"]} '
        f'succeeded={state["succeeded"]} failures={state["failures"]} '
        f'results={state["results"]}'
    )


def main(
    database_path=None,
    packet_builder_path=PACKET_BUILDER_PATH,
    caller_path=CALLER_PATH,
    runtime_config_path=RUNTIME_CONFIG_PATH,
    prompt_path=PROMPT_PATH,
    output_schema_path=OUTPUT_SCHEMA_PATH,
    lock_path=None,
    *,
    reasoning_transport=None,
) -> int:
    selected_database = (
        Path(database_path)
        if database_path is not None
        else load_database_path()
    )
    if selected_database is None:
        print(
            'ERROR: managed reasoning database is unavailable',
            file=sys.stderr,
        )
        return 1
    packet_builder_path = Path(packet_builder_path)
    caller_path = Path(caller_path)
    runtime_config_path = Path(runtime_config_path)
    prompt_path = Path(prompt_path)
    output_schema_path = Path(output_schema_path)
    selected_lock = (
        Path(lock_path)
        if lock_path is not None
        else selected_database.parent / 'managed-reasoning.lock'
    )
    descriptor = None
    started_at = time.monotonic()
    packets_created = 0
    builder_deferred = 0
    invoked = 0
    try:
        for path, expected_hash, mode in (
            (packet_builder_path, PACKET_BUILDER_SHA256, 0o755),
            (caller_path, CALLER_SHA256, 0o755),
            (runtime_config_path, RUNTIME_CONFIG_SHA256, 0o644),
            (prompt_path, PROMPT_SHA256, 0o644),
            (output_schema_path, OUTPUT_SCHEMA_SHA256, 0o644),
        ):
            validate_artifact(path, expected_hash, mode)
        descriptor = acquire_lock(selected_lock)
        before = snapshot(selected_database)
        if before['started']:
            raise ManagedReasoningError(
                'managed reasoning has an unreconciled STARTED reservation'
            )
        caller = load_stage(
            'gx10_managed_local_reasoning',
            caller_path,
            selected_database,
        )
        if before['pending']:
            builder_deferred = 1
            after_packets = before
        else:
            packet_builder = load_stage(
                'gx10_managed_reasoning_packets',
                packet_builder_path,
                selected_database,
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(
                io.StringIO()
            ):
                packet_result = packet_builder.run(selected_database)
            if packet_result != 0:
                raise ManagedReasoningError(
                    'reasoning packet stage failed'
                )
            after_packets = snapshot(selected_database)
        packets_created = after_packets['packets'] - before['packets']
        if packets_created < 0:
            raise ManagedReasoningError(
                'reasoning packet count moved backward'
            )
        runs_before = after_packets['runs']
        results_before = after_packets['results']
        caller_arguments = {
            'config_path': runtime_config_path,
            'prompt_path': prompt_path,
            'output_schema_path': output_schema_path,
        }
        if reasoning_transport is not None:
            caller_arguments['transport'] = reasoning_transport
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            reasoning_result = caller.run(
                selected_database,
                **caller_arguments,
            )
        final = snapshot(selected_database)
        new_runs = final['runs'] - runs_before
        new_results = final['results'] - results_before
        if new_runs not in {0, 1} or new_results not in {0, 1}:
            raise ManagedReasoningError(
                'managed reasoning exceeded one inference per cycle'
            )
        invoked = new_runs
        if after_packets['pending'] and new_runs != 1:
            raise ManagedReasoningError(
                'managed reasoning did not reserve one pending packet'
            )
        if not after_packets['pending'] and new_runs != 0:
            raise ManagedReasoningError(
                'managed reasoning reserved without a pending packet'
            )
        if final['started']:
            raise ManagedReasoningError(
                'managed reasoning left a STARTED reservation'
            )
        if before['pending'] and (
            packets_created
            or final['pending'] != before['pending'] - new_runs
        ):
            raise ManagedReasoningError(
                'managed reasoning backlog admission differs'
            )
        duration_ms = int((time.monotonic() - started_at) * 1000)
        if reasoning_result != 0:
            emit_summary(
                final,
                result='safe_failure',
                duration_ms=duration_ms,
                packets_created=packets_created,
                builder_deferred=builder_deferred,
                invoked=invoked,
            )
            print('GX10_MANAGED_REASONING=SAFE_FAILURE', file=sys.stderr)
            return 1
        if new_runs != new_results:
            raise ManagedReasoningError(
                'managed reasoning success result differs'
            )
        emit_summary(
            final,
            result='pass',
            duration_ms=duration_ms,
            packets_created=packets_created,
            builder_deferred=builder_deferred,
            invoked=invoked,
        )
        print('GX10_MANAGED_REASONING=PASS')
        return 0
    except (ManagedReasoningError, OSError, sqlite3.Error, ValueError) as exc:
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f'{timestamp} ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_REASONING=FAIL', file=sys.stderr)
        return 1
    finally:
        if descriptor is not None:
            os.close(descriptor)


if __name__ == '__main__':
    sys.exit(main())
