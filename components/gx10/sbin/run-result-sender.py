#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys


CONFIG_PATH = Path('/etc/network-log-gx10/result-sender.json')
SENDER_PATH = Path('/usr/local/libexec/network-log-gx10/send-result-outbox.py')
SENDER_SHA256 = '7895e1fa43f4cb796ac50d8b7f2c2beea8489a392d37a85d20280eb8cfbcbf4d'
HOST_RE = re.compile(r'^[A-Za-z0-9.-]+$')
USER_RE = re.compile(r'^[A-Za-z0-9._-]+$')
EXPECTED_KEYS = {
    'delivered_path',
    'identity_path',
    'known_hosts_path',
    'ready_path',
    'schema_version',
    'sftp_host',
    'sftp_port',
    'sftp_user',
}


class ManagedSenderError(ValueError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_regular(path, mode, uid, gid):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ManagedSenderError('managed result sender artifact differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ManagedSenderError('managed result sender artifact metadata differs')


def absolute_path(value, label):
    if not isinstance(value, str) or not value.startswith('/'):
        raise ManagedSenderError(f'managed result sender {label} differs')
    path = Path(value)
    if '..' in path.parts:
        raise ManagedSenderError(f'managed result sender {label} differs')
    return path


def parse_config(data):
    if not isinstance(data, dict) or set(data) != EXPECTED_KEYS:
        raise ManagedSenderError('managed result sender configuration keys differ')
    if data['schema_version'] != 1:
        raise ManagedSenderError('managed result sender schema version differs')
    host = data['sftp_host']
    user = data['sftp_user']
    port = data['sftp_port']
    if not isinstance(host, str) or HOST_RE.fullmatch(host) is None:
        raise ManagedSenderError('managed result sender host differs')
    if not isinstance(user, str) or USER_RE.fullmatch(user) is None:
        raise ManagedSenderError('managed result sender user differs')
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ManagedSenderError('managed result sender port differs')
    ready = absolute_path(data['ready_path'], 'ready path')
    delivered = absolute_path(data['delivered_path'], 'delivered path')
    identity = absolute_path(data['identity_path'], 'identity path')
    known_hosts = absolute_path(data['known_hosts_path'], 'known-hosts path')
    if (
        ready == delivered
        or ready.parent != delivered.parent
        or identity.name != 'result-writer.key'
        or known_hosts.name != 'result-writer-known_hosts'
        or identity.parent != known_hosts.parent
    ):
        raise ManagedSenderError('managed result sender path layout differs')
    return {
        'ready': ready,
        'delivered': delivered,
        'identity': identity,
        'known_hosts': known_hosts,
        'host': host,
        'port': port,
        'user': user,
    }


def load_config(path=CONFIG_PATH):
    path = Path(path)
    validate_regular(path, 0o640, 0, os.getegid())
    if path.stat().st_size > 8192:
        raise ManagedSenderError('managed result sender configuration is too large')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedSenderError('managed result sender configuration is invalid') from exc
    return parse_config(data)


def load_sender(path=SENDER_PATH):
    validate_regular(path, 0o755, 0, 0)
    if sha256_file(path) != SENDER_SHA256:
        raise ManagedSenderError('managed result sender source hash differs')
    specification = importlib.util.spec_from_file_location(
        'installed_result_sender', path
    )
    if specification is None or specification.loader is None:
        raise ManagedSenderError('managed result sender source cannot be loaded')
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run(config_path=CONFIG_PATH, sender_path=SENDER_PATH):
    try:
        config = load_config(config_path)
        sender = load_sender(sender_path)
        result = sender.send_one(
            config['ready'],
            config['delivered'],
            config['host'],
            config['port'],
            config['user'],
            config['identity'],
            config['known_hosts'],
        )
        print(
            'MANAGED_RESULT_SENDER schema=1 '
            f'ready={result["ready"]} delivered={result["delivered"]} '
            f'attempted={result["attempted"]} sent={result["sent"]} '
            f'sent_bytes={result["sent_bytes"]}'
        )
        print('GX10_MANAGED_RESULT_SENDER=PASS')
        return 0
    except (OSError, ManagedSenderError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_RESULT_SENDER=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if os.geteuid() == 0:
        print('ERROR: managed result sender must run as its service user', file=sys.stderr)
        sys.exit(1)
    sys.exit(run())
