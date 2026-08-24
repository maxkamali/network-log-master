#!/usr/bin/env python3
import argparse
import grp
import json
import os
import platform
import pwd
import re
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

RUNTIME_USER = 'network-log-agent'
RUNTIME_GROUP = 'network-log-agent'
RUNTIME_HOME = Path('/var/lib/network-log-gx10')
CONFIG_DIR = Path('/etc/network-log-gx10')
RUNTIME_CONFIG = CONFIG_DIR / 'runtime.json'
SSH_DIR = RUNTIME_HOME / '.ssh'
PRIVATE_KEY = SSH_DIR / 'spool-reader.key'
KNOWN_HOSTS = SSH_DIR / 'known_hosts'
STATE_DIR = RUNTIME_HOME / 'state'
DATABASE = STATE_DIR / 'events.sqlite3'
SPOOL_DIR = Path('/var/spool/network-log-gx10')
INCOMING_DIR = SPOOL_DIR / 'incoming'
PROCESSED_DIR = SPOOL_DIR / 'processed'
TEMP_DIR = SPOOL_DIR / 'tmp'
LIBEXEC_DIR = Path('/usr/local/libexec/network-log-gx10')
SYSTEMD_DIR = Path('/etc/systemd/system')
SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
SCHEMA_PATH = GX10_DIR / 'sql' / 'initialize.sql'
INCIDENT_SCHEMA_PATH = GX10_DIR / 'sql' / 'incident-v1.sql'
REASONING_SCHEMA_PATH = GX10_DIR / 'sql' / 'reasoning-v1.sql'
INFERENCE_SCHEMA_PATH = GX10_DIR / 'sql' / 'inference-v1.sql'
HOST_RE = re.compile(r'^[A-Za-z0-9.-]+$')
USER_RE = re.compile(r'^[A-Za-z0-9._-]+$')

ARTIFACTS = (
    (GX10_DIR / 'sbin' / 'fetch-spool.py', LIBEXEC_DIR / 'fetch-spool.py', 0o755),
    (GX10_DIR / 'sbin' / 'ingest-spool.py', LIBEXEC_DIR / 'ingest-spool.py', 0o755),
    (GX10_DIR / 'sbin' / 'enrich-events.py', LIBEXEC_DIR / 'enrich-events.py', 0o755),
    (GX10_DIR / 'sbin' / 'incident-engine.py', LIBEXEC_DIR / 'incident-engine.py', 0o755),
    (GX10_DIR / 'sbin' / 'run-correlation.py', LIBEXEC_DIR / 'run-correlation.py', 0o755),
    (
        GX10_DIR / 'sbin' / 'build-reasoning-packets.py',
        LIBEXEC_DIR / 'build-reasoning-packets.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-local-reasoning.py',
        LIBEXEC_DIR / 'run-local-reasoning.py',
        0o755,
    ),
    (GX10_DIR / 'sbin' / 'runtime_config.py', LIBEXEC_DIR / 'runtime_config.py', 0o644),
    (
        GX10_DIR / 'config' / 'reasoning-runtime-v2.json',
        CONFIG_DIR / 'reasoning-runtime-v2.json',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'incident-assessment-v2.txt',
        CONFIG_DIR / 'incident-assessment-v2.txt',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'incident-assessment-output-v2.json',
        CONFIG_DIR / 'incident-assessment-output-v2.json',
        0o644,
    ),
    (
        GX10_DIR / 'systemd' / 'network-log-gx10.service',
        SYSTEMD_DIR / 'network-log-gx10.service',
        0o644,
    ),
    (
        GX10_DIR / 'systemd' / 'network-log-gx10.timer',
        SYSTEMD_DIR / 'network-log-gx10.timer',
        0o644,
    ),
    (
        GX10_DIR / 'systemd' / 'network-log-gx10-correlation.service',
        SYSTEMD_DIR / 'network-log-gx10-correlation.service',
        0o644,
    ),
    (
        GX10_DIR / 'systemd' / 'network-log-gx10-correlation.timer',
        SYSTEMD_DIR / 'network-log-gx10-correlation.timer',
        0o644,
    ),
)

UNITS = {
    'network-log-gx10.service': SYSTEMD_DIR / 'network-log-gx10.service',
    'network-log-gx10.timer': SYSTEMD_DIR / 'network-log-gx10.timer',
    'network-log-gx10-correlation.service': (
        SYSTEMD_DIR / 'network-log-gx10-correlation.service'
    ),
    'network-log-gx10-correlation.timer': (
        SYSTEMD_DIR / 'network-log-gx10-correlation.timer'
    ),
    'ollama.service': SYSTEMD_DIR / 'ollama.service',
}


def validate_directory(path, uid, gid, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('required runtime directory is not a real directory')
    details = path.stat()
    if details.st_uid != uid or details.st_gid != gid:
        raise ValueError('required runtime directory has unexpected ownership')
    if stat.S_IMODE(details.st_mode) != mode:
        raise ValueError('required runtime directory has unexpected mode')


def validate_file(path, uid, gid, mode, source=None, require_nonempty=False):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('required runtime file is not a real regular file')
    details = path.stat()
    if details.st_nlink != 1:
        raise ValueError('required runtime file must not be hard-linked')
    if details.st_uid != uid or details.st_gid != gid:
        raise ValueError('required runtime file has unexpected ownership')
    if stat.S_IMODE(details.st_mode) != mode:
        raise ValueError('required runtime file has unexpected mode')
    if require_nonempty and details.st_size == 0:
        raise ValueError('required private runtime file is empty')
    if source is not None and Path(source).read_bytes() != path.read_bytes():
        raise ValueError('installed runtime artifact differs from repository source')


def validate_runtime_config(path=RUNTIME_CONFIG):
    path = Path(path)
    if path.stat().st_size > 16384:
        raise ValueError('runtime configuration is too large')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {
        'sftp_host',
        'sftp_port',
        'sftp_user',
    }:
        raise ValueError('runtime configuration keys are invalid')
    host = data.get('sftp_host')
    user = data.get('sftp_user')
    port = data.get('sftp_port')
    if not isinstance(host, str) or not HOST_RE.fullmatch(host):
        raise ValueError('runtime SFTP host is invalid')
    if not isinstance(user, str) or not USER_RE.fullmatch(user):
        raise ValueError('runtime SFTP user is invalid')
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError('runtime SFTP port is invalid')


def database_connection(path):
    return sqlite3.connect(f'file:{Path(path)}?mode=ro&immutable=1', uri=True)


def schema_inventory(connection):
    return connection.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' "
        "AND type IN ('table', 'index', 'trigger') "
        "ORDER BY type, name"
    ).fetchall()


def expected_database_contract(
    schema_path=SCHEMA_PATH,
    incident_schema_path=INCIDENT_SCHEMA_PATH,
    reasoning_schema_path=REASONING_SCHEMA_PATH,
    inference_schema_path=INFERENCE_SCHEMA_PATH,
):
    schema_path = Path(schema_path)
    if schema_path.is_symlink() or not schema_path.is_file():
        raise ValueError('database schema source is not a real file')
    incident_schema_path = Path(incident_schema_path)
    if incident_schema_path.is_symlink() or not incident_schema_path.is_file():
        raise ValueError('incident schema source is not a real file')
    reasoning_schema_path = Path(reasoning_schema_path)
    if reasoning_schema_path.is_symlink() or not reasoning_schema_path.is_file():
        raise ValueError('reasoning schema source is not a real file')
    inference_schema_path = Path(inference_schema_path)
    if inference_schema_path.is_symlink() or not inference_schema_path.is_file():
        raise ValueError('inference schema source is not a real file')
    connection = sqlite3.connect(':memory:')
    try:
        connection.executescript(schema_path.read_text(encoding='utf-8'))
        connection.executescript(
            incident_schema_path.read_text(encoding='utf-8')
        )
        connection.executescript(
            reasoning_schema_path.read_text(encoding='utf-8')
        )
        connection.executescript(
            inference_schema_path.read_text(encoding='utf-8')
        )
        return (
            schema_inventory(connection),
            connection.execute(
                'SELECT * FROM suppression_rules ORDER BY id'
            ).fetchall(),
        )
    finally:
        connection.close()


def validate_database(
    path=DATABASE,
    require_empty=False,
    schema_path=SCHEMA_PATH,
    incident_schema_path=INCIDENT_SCHEMA_PATH,
    reasoning_schema_path=REASONING_SCHEMA_PATH,
    inference_schema_path=INFERENCE_SCHEMA_PATH,
):
    expected_schema, expected_suppression = expected_database_contract(
        schema_path,
        incident_schema_path,
        reasoning_schema_path,
        inference_schema_path,
    )
    connection = database_connection(path)
    try:
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite quick_check failed')
        if schema_inventory(connection) != expected_schema:
            raise ValueError('installed database schema differs')
        suppression = connection.execute(
            'SELECT * FROM suppression_rules ORDER BY id'
        ).fetchall()
        if suppression != expected_suppression:
            raise ValueError('installed suppression corpus differs')
        if connection.execute('PRAGMA user_version').fetchone()[0] != 0:
            raise ValueError('unexpected SQLite user_version')
        if connection.execute('PRAGMA application_id').fetchone()[0] != 0:
            raise ValueError('unexpected SQLite application_id')
        if require_empty:
            for table in (
                'agent_state',
                'source_files',
                'recent_events',
                'event_enrichment',
                'incidents',
                'incident_evidence',
                'incident_transitions',
                'reasoning_packets',
                'reasoning_model_versions',
                'reasoning_prompt_versions',
                'reasoning_runs',
                'reasoning_results',
            ):
                if connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:
                    raise ValueError('clean activation refuses nonempty application state')
    finally:
        connection.close()


def require_empty_directory(path):
    if any(Path(path).iterdir()):
        raise ValueError('clean activation refuses preexisting spool content')


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def validate_systemd_state(active):
    for unit, fragment in UNITS.items():
        if systemctl_value(unit, 'LoadState') != 'loaded':
            raise ValueError('required systemd unit is not loaded')
        if Path(systemctl_value(unit, 'FragmentPath')) != fragment:
            raise ValueError('required systemd unit has unexpected fragment path')
        if systemctl_value(unit, 'DropInPaths'):
            raise ValueError('required systemd unit has unexpected drop-in configuration')

    expected_states = {
        'network-log-gx10.service': 'static',
        'network-log-gx10.timer': 'enabled' if active else 'disabled',
        'network-log-gx10-correlation.service': 'static',
        'network-log-gx10-correlation.timer': 'disabled',
        'ollama.service': 'enabled' if active else 'disabled',
    }
    for unit, expected in expected_states.items():
        if systemctl_value(unit, 'UnitFileState') != expected:
            raise ValueError('required systemd unit has unexpected enablement state')

    ollama_state = systemctl_value('ollama.service', 'ActiveState')
    timer_state = systemctl_value('network-log-gx10.timer', 'ActiveState')
    pipeline_state = systemctl_value('network-log-gx10.service', 'ActiveState')
    correlation_service_state = systemctl_value(
        'network-log-gx10-correlation.service',
        'ActiveState',
    )
    correlation_timer_state = systemctl_value(
        'network-log-gx10-correlation.timer',
        'ActiveState',
    )
    if correlation_service_state != 'inactive' or correlation_timer_state != 'inactive':
        raise ValueError('managed correlation must remain inactive before its gate')
    if active:
        if ollama_state != 'active' or timer_state != 'active':
            raise ValueError('required runtime unit is not active')
        if pipeline_state == 'failed':
            raise ValueError('pipeline service is failed')
    elif any(state != 'inactive' for state in (ollama_state, timer_state, pipeline_state)):
        raise ValueError('clean activation requires all runtime units inactive')

    if systemctl_value('ollama.service', 'LimitNOFILE') != '524288':
        raise ValueError('unexpected Ollama effective file-descriptor limit')
    if systemctl_value('ollama.service', 'LimitNOFILESoft') != '1024':
        raise ValueError('unexpected Ollama effective soft file-descriptor limit')


def validate_runtime(active):
    if os.geteuid() != 0:
        raise ValueError('run this clean-machine verifier as root')

    runtime_user = pwd.getpwnam(RUNTIME_USER)
    runtime_group = grp.getgrnam(RUNTIME_GROUP)
    if runtime_user.pw_gid != runtime_group.gr_gid:
        raise ValueError('runtime identity has unexpected primary group')
    if Path(runtime_user.pw_dir) != RUNTIME_HOME:
        raise ValueError('runtime identity has unexpected home')
    if Path(runtime_user.pw_shell).name != 'nologin':
        raise ValueError('runtime identity has unexpected shell')
    if set(os.getgrouplist(RUNTIME_USER, runtime_user.pw_gid)) != {runtime_group.gr_gid}:
        raise ValueError('runtime identity has unexpected supplementary groups')
    password_state = subprocess.run(
        ['passwd', '--status', RUNTIME_USER],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.split()
    if len(password_state) < 2 or password_state[1] != 'L':
        raise ValueError('runtime identity is not locked')

    runtime_uid = runtime_user.pw_uid
    runtime_gid = runtime_group.gr_gid
    validate_directory(LIBEXEC_DIR, 0, 0, 0o755)
    validate_directory(CONFIG_DIR, 0, runtime_gid, 0o750)
    validate_directory(RUNTIME_HOME, runtime_uid, runtime_gid, 0o750)
    validate_directory(SSH_DIR, runtime_uid, runtime_gid, 0o700)
    validate_directory(STATE_DIR, runtime_uid, runtime_gid, 0o750)
    validate_directory(SPOOL_DIR, runtime_uid, runtime_gid, 0o750)
    for path in (INCOMING_DIR, PROCESSED_DIR, TEMP_DIR):
        validate_directory(path, runtime_uid, runtime_gid, 0o750)

    validate_file(PRIVATE_KEY, runtime_uid, runtime_gid, 0o600, require_nonempty=True)
    validate_file(KNOWN_HOSTS, runtime_uid, runtime_gid, 0o600, require_nonempty=True)
    validate_file(RUNTIME_CONFIG, 0, runtime_gid, 0o640)
    validate_runtime_config()
    validate_file(DATABASE, runtime_uid, runtime_gid, 0o640)
    validate_database(require_empty=not active)

    for source, target, mode in ARTIFACTS:
        validate_file(target, 0, 0, mode, source=source)

    if not active:
        for path in (INCOMING_DIR, PROCESSED_DIR, TEMP_DIR):
            require_empty_directory(path)
        for suffix in ('-journal', '-wal', '-shm'):
            if Path(f'{DATABASE}{suffix}').exists():
                raise ValueError('clean activation refuses SQLite sidecar state')

    if platform.system() != 'Linux':
        raise ValueError('runtime verification requires Linux')
    validate_systemd_state(active)


def parse_args():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--preactivation', action='store_true')
    group.add_argument('--active', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        validate_runtime(active=args.active)
        label = 'ACTIVE' if args.active else 'PREACTIVATION'
        print(f'GX10_RUNTIME_{label}_VERIFY=PASS')
        return 0
    except (
        KeyError,
        OSError,
        sqlite3.Error,
        subprocess.CalledProcessError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
