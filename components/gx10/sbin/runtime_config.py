#!/usr/bin/env python3
import json
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path('/etc/network-log-gx10/runtime.json')
EXPECTED_KEYS = {'sftp_host', 'sftp_port', 'sftp_user'}
HOST_RE = re.compile(r'^[A-Za-z0-9.-]+$')
USER_RE = re.compile(r'^[A-Za-z0-9._-]+$')


@dataclass(frozen=True)
class RuntimeConfig:
    sftp_host: str
    sftp_port: str
    sftp_user: str
    database_path: Path = Path('/var/lib/network-log-gx10/state/events.sqlite3')
    incoming_dir: Path = Path('/var/spool/network-log-gx10/incoming')
    processed_dir: Path = Path('/var/spool/network-log-gx10/processed')
    temp_dir: Path = Path('/var/spool/network-log-gx10/tmp')
    private_key_path: Path = Path('/var/lib/network-log-gx10/.ssh/spool-reader.key')
    known_hosts_path: Path = Path('/var/lib/network-log-gx10/.ssh/known_hosts')


def _require_string(data, key, pattern):
    value = data.get(key)
    if not isinstance(value, str) or not value or not pattern.fullmatch(value):
        raise ValueError(f'invalid {key}')
    return value


def load_runtime_config(path=DEFAULT_CONFIG_PATH):
    path = Path(path)
    if not path.is_file():
        raise ValueError('runtime configuration is not a regular file')
    if path.stat().st_size > 16384:
        raise ValueError('runtime configuration is too large')

    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)

    if not isinstance(data, dict) or set(data) != EXPECTED_KEYS:
        raise ValueError('runtime configuration keys are invalid')

    host = _require_string(data, 'sftp_host', HOST_RE)
    user = _require_string(data, 'sftp_user', USER_RE)
    port = data.get('sftp_port')

    if isinstance(port, int):
        port_number = port
    elif isinstance(port, str) and port.isdigit():
        port_number = int(port)
    else:
        raise ValueError('invalid sftp_port')

    if port_number < 1 or port_number > 65535:
        raise ValueError('invalid sftp_port')

    return RuntimeConfig(
        sftp_host=host,
        sftp_port=str(port_number),
        sftp_user=user,
    )
