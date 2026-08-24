#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = Path('/etc/network-log-gx10')
SENDER_CONFIG = CONFIG_DIR / 'result-sender.json'
RUNTIME_CONFIG = CONFIG_DIR / 'runtime.json'
IDENTITY_INPUT_DEFAULT = Path('/run/network-log-result-writer.key')
SSH_KEYGEN = Path('/usr/bin/ssh-keygen')
TIMER = 'network-log-gx10-result-sender.timer'
SERVICE = 'network-log-gx10-result-sender.service'


class ConfigureError(ValueError):
    pass


def load_verifier():
    path = SCRIPT_DIR / 'verify-result-sender.py'
    specification = importlib.util.spec_from_file_location(
        'result_sender_configure_verifier', path
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def require_inactive():
    if systemctl_value(TIMER, 'UnitFileState') != 'disabled':
        raise ConfigureError('result sender timer is not disabled')
    if systemctl_value(TIMER, 'ActiveState') != 'inactive':
        raise ConfigureError('result sender timer is not inactive')
    if systemctl_value(SERVICE, 'ActiveState') != 'inactive':
        raise ConfigureError('result sender service is not inactive')


def public_key(path):
    result = subprocess.run(
        [str(SSH_KEYGEN), '-y', '-P', '', '-f', str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    fields = result.stdout.strip().split()
    if (
        result.returncode != 0
        or len(fields) < 2
        or fields[0] != 'ssh-ed25519'
        or len(fields[1]) < 32
    ):
        raise ConfigureError('result writer identity input differs')
    return ' '.join(fields[:2])


def validate_identity_input(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ConfigureError('result writer identity input differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != 0
        or stat.S_IMODE(details.st_mode) not in {0o400, 0o600}
        or details.st_size <= 0
        or details.st_size > 64 * 1024
    ):
        raise ConfigureError('result writer identity input metadata differs')
    return public_key(path)


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def install_bytes(path, data, mode, uid, gid):
    path = Path(path)
    temporary = path.parent / f'.{path.name}.configure-{os.getpid()}'
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, 'wb', closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
        fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def expected_configuration(verifier, state):
    verifier.validate_file(RUNTIME_CONFIG, 0o640, 0, state['gid'])
    try:
        runtime = json.loads(RUNTIME_CONFIG.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigureError('result sender runtime configuration differs') from exc
    if not isinstance(runtime, dict) or set(runtime) != {
        'sftp_host',
        'sftp_port',
        'sftp_user',
    }:
        raise ConfigureError('result sender runtime configuration differs')
    data = {
        'delivered_path': str(state['delivered']),
        'identity_path': str(state['identity']),
        'known_hosts_path': str(state['known_hosts']),
        'ready_path': str(state['ready']),
        'schema_version': 1,
        'sftp_host': runtime['sftp_host'],
        'sftp_port': int(runtime['sftp_port']),
        'sftp_user': 'ai_results_writer',
    }
    return (json.dumps(data, separators=(',', ':'), sort_keys=True) + '\n').encode(
        'utf-8'
    )


def configure(identity_input):
    require_inactive()
    verifier = load_verifier()
    state = verifier.runtime_state()
    supplied_public = validate_identity_input(identity_input)
    reader_identity = state['identity'].parent / 'spool-reader.key'
    verifier.validate_file(reader_identity, 0o600, state['uid'], state['gid'])
    if supplied_public == public_key(reader_identity):
        raise ConfigureError('result writer identity is not role-separated')
    source_known_hosts = state['identity'].parent / 'known_hosts'
    verifier.validate_file(source_known_hosts, 0o600, state['uid'], state['gid'])
    expected_config = expected_configuration(verifier, state)
    targets = (state['identity'], state['known_hosts'], SENDER_CONFIG)
    present = tuple(path.exists() or path.is_symlink() for path in targets)
    if any(present):
        if not all(present):
            raise ConfigureError('result sender private state is partial')
        verifier.verify_configured()
        if (
            public_key(state['identity']) != supplied_public
            or state['known_hosts'].read_bytes() != source_known_hosts.read_bytes()
            or SENDER_CONFIG.read_bytes() != expected_config
        ):
            raise ConfigureError('result sender existing private state differs')
        return {'created': 0, 'reused': 3}
    verifier.verify_staged()
    created = []
    try:
        install_bytes(
            state['identity'],
            Path(identity_input).read_bytes(),
            0o600,
            state['uid'],
            state['gid'],
        )
        created.append(state['identity'])
        install_bytes(
            state['known_hosts'],
            source_known_hosts.read_bytes(),
            0o600,
            state['uid'],
            state['gid'],
        )
        created.append(state['known_hosts'])
        install_bytes(
            SENDER_CONFIG,
            expected_config,
            0o640,
            0,
            state['gid'],
        )
        created.append(SENDER_CONFIG)
        require_inactive()
        verifier.verify_configured()
        require_inactive()
        return {'created': 3, 'reused': 0}
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
                fsync_directory(path.parent)
            except FileNotFoundError:
                pass
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Configure the disabled managed GX10 result sender'
    )
    parser.add_argument(
        '--identity-input',
        type=Path,
        default=IDENTITY_INPUT_DEFAULT,
    )
    parser.add_argument(
        '--confirm-configure-disabled-result-sender',
        action='store_true',
    )
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise ConfigureError('run the result sender configurator as root')
        if not args.confirm_configure_disabled_result_sender:
            raise ConfigureError('disabled result sender confirmation is absent')
        result = configure(args.identity_input)
        print(
            'RESULT_SENDER_CONFIGURE schema=1 '
            f'created={result["created"]} reused={result["reused"]} '
            'timer_enabled=no service_active=no sftp_invoked=no'
        )
        print('GX10_RESULT_SENDER_CONFIGURED_INACTIVE=PASS')
        return 0
    except (OSError, subprocess.CalledProcessError, ConfigureError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_RESULT_SENDER_CONFIGURED_INACTIVE=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
