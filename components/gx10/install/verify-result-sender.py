#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import grp
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
LIBEXEC_DIR = Path('/usr/local/libexec/network-log-gx10')
CONFIG_DIR = Path('/etc/network-log-gx10')
SYSTEMD_DIR = Path('/etc/systemd/system')
OUTBOX_CONFIG = CONFIG_DIR / 'result-outbox.json'
SENDER_CONFIG = CONFIG_DIR / 'result-sender.json'
RUNTIME_CONFIG = CONFIG_DIR / 'runtime.json'
SERVICE = 'network-log-gx10-result-sender.service'
TIMER = 'network-log-gx10-result-sender.timer'
OUTBOX_SERVICE = 'network-log-gx10-result-outbox.service'
OUTBOX_TIMER = 'network-log-gx10-result-outbox.timer'
DROPIN_PATH = SYSTEMD_DIR / f'{SERVICE}.d' / '10-runtime.conf'
SSH_KEYGEN = Path('/usr/bin/ssh-keygen')
LEGACY_FETCH_SHA256 = '662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b'
SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_.@-]+$')
ARTIFACTS = (
    (
        GX10_DIR / 'sbin' / 'send-result-outbox.py',
        LIBEXEC_DIR / 'send-result-outbox.py',
        0o755,
    ),
    (
        GX10_DIR / 'sbin' / 'run-result-sender.py',
        LIBEXEC_DIR / 'run-result-sender.py',
        0o755,
    ),
    (
        GX10_DIR / 'systemd' / SERVICE,
        SYSTEMD_DIR / SERVICE,
        0o644,
    ),
    (
        GX10_DIR / 'systemd' / TIMER,
        SYSTEMD_DIR / TIMER,
        0o644,
    ),
)


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def validate_file(path, mode, uid, gid, source=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('managed result sender artifact differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ValueError('managed result sender artifact metadata differs')
    if source is not None and path.read_bytes() != Path(source).read_bytes():
        raise ValueError('managed result sender installed source differs')


def absolute_path(value, label):
    if not isinstance(value, str) or not value.startswith('/'):
        raise ValueError(f'managed result sender {label} differs')
    path = Path(value)
    if '..' in path.parts:
        raise ValueError(f'managed result sender {label} differs')
    return path


def service_identity():
    user = systemctl_value(OUTBOX_SERVICE, 'User')
    group = systemctl_value(OUTBOX_SERVICE, 'Group')
    if SAFE_NAME_RE.fullmatch(user) is None or SAFE_NAME_RE.fullmatch(group) is None:
        raise ValueError('managed result sender identity differs')
    account = pwd.getpwnam(user)
    group_entry = grp.getgrnam(group)
    if account.pw_gid != group_entry.gr_gid:
        raise ValueError('managed result sender identity differs')
    return user, group, account.pw_uid, group_entry.gr_gid, Path(account.pw_dir)


def validate_directory(path, uid, gid, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('managed result sender directory differs')
    details = path.stat()
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise ValueError('managed result sender directory metadata differs')


def runtime_state():
    user, group, uid, gid, home = service_identity()
    validate_file(OUTBOX_CONFIG, 0o640, 0, gid)
    try:
        data = json.loads(OUTBOX_CONFIG.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('managed result outbox configuration differs') from exc
    if not isinstance(data, dict) or set(data) != {
        'database_path',
        'delivered_path',
        'ready_path',
    }:
        raise ValueError('managed result outbox configuration differs')
    database = absolute_path(data['database_path'], 'database path')
    ready = absolute_path(data['ready_path'], 'ready path')
    delivered = absolute_path(data['delivered_path'], 'delivered path')
    if ready == delivered or ready.parent != delivered.parent:
        raise ValueError('managed result outbox layout differs')
    for directory in (ready.parent, ready, delivered):
        validate_directory(directory, uid, gid, 0o700)
    validate_directory(home / '.ssh', uid, gid, 0o700)
    return {
        'user': user,
        'group': group,
        'uid': uid,
        'gid': gid,
        'database': database,
        'root': ready.parent,
        'ready': ready,
        'delivered': delivered,
        'identity': home / '.ssh/result-writer.key',
        'known_hosts': home / '.ssh/result-writer-known_hosts',
    }


def render_dropin(state):
    return (
        '[Service]\n'
        f'User={state["user"]}\n'
        f'Group={state["group"]}\n'
        'ReadWritePaths=\n'
        f'ReadWritePaths={state["root"]}\n'
        'ReadOnlyPaths=\n'
        f'ReadOnlyPaths={SENDER_CONFIG}\n'
        f'ReadOnlyPaths={state["identity"]}\n'
        f'ReadOnlyPaths={state["known_hosts"]}\n'
        'InaccessiblePaths=\n'
        f'InaccessiblePaths={state["database"]}\n'
    ).encode('utf-8')


def validate_units(state):
    for unit in (SERVICE, TIMER):
        if systemctl_value(unit, 'LoadState') != 'loaded':
            raise ValueError('managed result sender unit is not loaded')
        if Path(systemctl_value(unit, 'FragmentPath')) != SYSTEMD_DIR / unit:
            raise ValueError('managed result sender fragment path differs')
    if systemctl_value(SERVICE, 'DropInPaths') != str(DROPIN_PATH):
        raise ValueError('managed result sender drop-in state differs')
    if systemctl_value(TIMER, 'DropInPaths'):
        raise ValueError('managed result sender timer drop-in differs')
    if systemctl_value(SERVICE, 'UnitFileState') != 'static':
        raise ValueError('managed result sender service state differs')
    if systemctl_value(TIMER, 'UnitFileState') != 'disabled':
        raise ValueError('managed result sender timer is not disabled')
    if systemctl_value(TIMER, 'ActiveState') != 'inactive':
        raise ValueError('managed result sender timer is not inactive')
    if systemctl_value(SERVICE, 'ActiveState') != 'inactive':
        raise ValueError('managed result sender service is not inactive')
    if systemctl_value(SERVICE, 'NRestarts') != '0':
        raise ValueError('managed result sender restart count differs')
    if systemctl_value(SERVICE, 'User') != state['user']:
        raise ValueError('managed result sender effective user differs')
    if systemctl_value(SERVICE, 'Group') != state['group']:
        raise ValueError('managed result sender effective group differs')


def verify_public_package():
    state = runtime_state()
    for source, target, mode in ARTIFACTS:
        validate_file(target, mode, 0, 0, source=source)
    validate_file(DROPIN_PATH, 0o644, 0, 0)
    if DROPIN_PATH.read_bytes() != render_dropin(state):
        raise ValueError('managed result sender drop-in differs')
    validate_file('/usr/bin/sftp', 0o755, 0, 0)
    validate_units(state)
    if systemctl_value(OUTBOX_TIMER, 'UnitFileState') != 'enabled':
        raise ValueError('managed result outbox timer is not enabled')
    if systemctl_value(OUTBOX_TIMER, 'ActiveState') != 'active':
        raise ValueError('managed result outbox timer is not active')
    return state


def verify_staged():
    state = verify_public_package()
    for path in (SENDER_CONFIG, state['identity'], state['known_hosts']):
        if Path(path).exists() or Path(path).is_symlink():
            raise ValueError('managed result sender private state exists')
    return state


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
        raise ValueError('managed result sender identity differs')
    return ' '.join(fields[:2])


def assigned_values(tree):
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        if isinstance(node.targets[0], ast.Name):
            values[node.targets[0].id] = node.value
    return values


def constant(values, name):
    node = values.get(name)
    if not isinstance(node, ast.Constant) or not isinstance(node.value, (str, int)):
        raise ValueError('managed result sender legacy runtime differs')
    return node.value


def path_constant(values, name):
    node = values.get(name)
    if (
        not isinstance(node, ast.Call)
        or not isinstance(node.func, ast.Name)
        or node.func.id != 'Path'
        or len(node.args) != 1
        or node.keywords
        or not isinstance(node.args[0], ast.Constant)
        or not isinstance(node.args[0].value, str)
    ):
        raise ValueError('managed result sender legacy runtime differs')
    return absolute_path(node.args[0].value, 'legacy path')


def runtime_inputs(state, runtime_config=RUNTIME_CONFIG, legacy_fetch_source=None):
    if legacy_fetch_source is None:
        validate_file(runtime_config, 0o640, 0, state['gid'])
        try:
            runtime = json.loads(Path(runtime_config).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError('managed result sender runtime configuration differs') from exc
        if not isinstance(runtime, dict) or set(runtime) != {
            'sftp_host',
            'sftp_port',
            'sftp_user',
        }:
            raise ValueError('managed result sender runtime configuration differs')
        reader_identity = state['identity'].parent / 'spool-reader.key'
        source_known_hosts = state['identity'].parent / 'known_hosts'
        host = runtime['sftp_host']
        port = runtime['sftp_port']
    else:
        source = Path(legacy_fetch_source)
        validate_file(source, 0o755, 0, 0)
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != LEGACY_FETCH_SHA256:
            raise ValueError('managed result sender legacy runtime differs')
        try:
            tree = ast.parse(data.decode('utf-8'))
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise ValueError('managed result sender legacy runtime differs') from exc
        values = assigned_values(tree)
        host = constant(values, 'SFTP_HOST')
        port = constant(values, 'SFTP_PORT')
        reader_user = constant(values, 'SFTP_USER')
        if not isinstance(reader_user, str) or not reader_user:
            raise ValueError('managed result sender legacy runtime differs')
        reader_identity = path_constant(values, 'SSH_KEY')
        source_known_hosts = path_constant(values, 'KNOWN_HOSTS')
        if (
            reader_identity.parent != state['identity'].parent
            or source_known_hosts != state['identity'].parent / 'known_hosts'
        ):
            raise ValueError('managed result sender legacy runtime differs')
    validate_file(reader_identity, 0o600, state['uid'], state['gid'])
    validate_file(source_known_hosts, 0o600, state['uid'], state['gid'])
    return {
        'host': host,
        'port': int(port),
        'reader_identity': reader_identity,
        'source_known_hosts': source_known_hosts,
    }


def verify_configured(runtime_config=RUNTIME_CONFIG, legacy_fetch_source=None):
    state = verify_public_package()
    validate_file(SENDER_CONFIG, 0o640, 0, state['gid'])
    validate_file(state['identity'], 0o600, state['uid'], state['gid'])
    validate_file(state['known_hosts'], 0o600, state['uid'], state['gid'])
    if not public_key(state['identity']):
        raise ValueError('managed result sender identity differs')
    runtime = runtime_inputs(state, runtime_config, legacy_fetch_source)
    try:
        configured = json.loads(SENDER_CONFIG.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('managed result sender configuration differs') from exc
    runner_path = LIBEXEC_DIR / 'run-result-sender.py'
    specification = importlib.util.spec_from_file_location(
        'verified_installed_result_sender_runner', runner_path
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    parsed = module.parse_config(configured)
    if (
        parsed['ready'] != state['ready']
        or parsed['delivered'] != state['delivered']
        or parsed['identity'] != state['identity']
        or parsed['known_hosts'] != state['known_hosts']
        or parsed['host'] != runtime['host']
        or parsed['port'] != runtime['port']
        or parsed['user'] != 'ai_results_writer'
    ):
        raise ValueError('managed result sender configured values differ')
    canonical = (
        json.dumps(configured, separators=(',', ':'), sort_keys=True) + '\n'
    ).encode('utf-8')
    if SENDER_CONFIG.read_bytes() != canonical:
        raise ValueError('managed result sender configuration is not canonical')
    lookup = (
        parsed['host']
        if parsed['port'] == 22
        else f'[{parsed["host"]}]:{parsed["port"]}'
    )
    result = subprocess.run(
        [str(SSH_KEYGEN), '-F', lookup, '-f', str(state['known_hosts'])],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError('managed result sender pinned host differs')
    return state


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--staged', action='store_true')
    mode.add_argument('--configured', action='store_true')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--runtime-config', type=Path)
    source.add_argument('--legacy-fetch-source', type=Path)
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError('run the managed result sender verifier as root')
        if args.configured:
            verify_configured(
                args.runtime_config or RUNTIME_CONFIG,
                args.legacy_fetch_source,
            )
        else:
            verify_staged()
        print(
            'MANAGED_RESULT_SENDER_VERIFY schema=1 '
            f'configured={"yes" if args.configured else "no"} '
            f'config_installed={"yes" if args.configured else "no"} '
            'timer_enabled=no service_active=no '
            f'credentials_installed={"yes" if args.configured else "no"}'
        )
        print('GX10_MANAGED_RESULT_SENDER_VERIFY=PASS')
        return 0
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_MANAGED_RESULT_SENDER_VERIFY=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
