#!/usr/bin/env python3
import argparse
import grp
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

RUNTIME_GROUP = 'network-log-agent'
OUTPUT_PATH = Path('/etc/network-log-gx10/runtime.json')
EXPECTED_ENV = ('GX10_SFTP_HOST', 'GX10_SFTP_PORT', 'GX10_SFTP_USER')
HOST_RE = re.compile(r'^[A-Za-z0-9.-]+$')
USER_RE = re.compile(r'^[A-Za-z0-9._-]+$')


def build_payload(environ):
    missing = [name for name in EXPECTED_ENV if not environ.get(name)]
    if missing:
        raise ValueError('missing required runtime configuration input')

    host = environ['GX10_SFTP_HOST']
    user = environ['GX10_SFTP_USER']
    port_text = environ['GX10_SFTP_PORT']

    if not HOST_RE.fullmatch(host):
        raise ValueError('invalid SFTP host')
    if not USER_RE.fullmatch(user):
        raise ValueError('invalid SFTP user')
    if not port_text.isdigit():
        raise ValueError('invalid SFTP port')

    port = int(port_text)
    if port < 1 or port > 65535:
        raise ValueError('invalid SFTP port')

    return {
        'sftp_host': host,
        'sftp_port': port,
        'sftp_user': user,
    }


def encoded_payload(payload):
    return (json.dumps(payload, indent=2, sort_keys=True) + '\n').encode('utf-8')


def verify_existing(path, expected, gid):
    if path.is_symlink():
        raise ValueError('existing runtime configuration must not be a symbolic link')
    details = path.stat()
    if not stat.S_ISREG(details.st_mode):
        raise ValueError('existing runtime configuration is not a regular file')
    if details.st_nlink != 1:
        raise ValueError('existing runtime configuration must not be hard-linked')
    if path.read_bytes() != expected:
        raise ValueError('existing runtime configuration differs')
    os.chown(path, 0, gid)
    os.chmod(path, 0o640)


def install_payload(path, content, gid):
    if path.exists() or path.is_symlink():
        verify_existing(path, content, gid)
        return

    if not path.parent.is_dir():
        raise ValueError('runtime configuration directory is missing')

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix='.runtime.json.',
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary_path, 0, gid)
        os.chmod(temporary_path, 0o640)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--check',
        action='store_true',
        help='validate operator inputs without writing configuration',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        payload = build_payload(os.environ)
        content = encoded_payload(payload)

        if args.check:
            print('GX10_RUNTIME_CONFIG_INPUT=PASS')
            return 0

        if os.geteuid() != 0:
            raise ValueError('run this clean-machine renderer as root')

        gid = grp.getgrnam(RUNTIME_GROUP).gr_gid
        install_payload(OUTPUT_PATH, content, gid)
        print('GX10_RUNTIME_CONFIG_RENDER=PASS')
        return 0
    except (KeyError, OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
