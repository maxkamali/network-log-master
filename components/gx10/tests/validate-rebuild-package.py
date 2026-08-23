#!/usr/bin/env python3
import ipaddress
import os
import re
import subprocess
import sys
from pathlib import Path

GX10_DIR = Path(__file__).resolve().parents[1]
ROOT = GX10_DIR.parents[1]
PRIVATE_PATH_RE = re.compile(r'/(?:Users|home)/')
IPV4_RE = re.compile(
    r'(?<![0-9])'
    r'(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})'
    r'(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}'
    r'(?![0-9])'
)
PRIVATE_KEY_MARKERS = (
    '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----',
    '-----BEGIN ' + 'RSA PRIVATE KEY-----',
    '-----BEGIN ' + 'EC PRIVATE KEY-----',
    '-----BEGIN ' + 'PRIVATE KEY-----',
)
FORBIDDEN_BASENAMES = {'known_hosts', 'operator-inputs.env', 'token.txt'}
FORBIDDEN_SUFFIXES = {'.db', '.key', '.pyc', '.sqlite', '.sqlite3'}
ALLOWED_IPV4_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        '0.0.0.0/32',
        '127.0.0.0/8',
        '192.0.2.0/24',
        '198.51.100.0/24',
        '203.0.113.0/24',
    )
)


def repository_files():
    result = subprocess.run(
        [
            'git',
            'ls-files',
            '--cached',
            '--others',
            '--exclude-standard',
            '-z',
            'components/gx10',
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    return tuple(
        ROOT / value.decode('utf-8')
        for value in result.stdout.split(b'\0')
        if value
    )


def is_allowed_address(value):
    address = ipaddress.ip_address(value)
    return any(address in network for network in ALLOWED_IPV4_NETWORKS)


def validate_public_files(files):
    for path in files:
        relative = path.relative_to(ROOT)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'non-regular package artifact: {relative}')
        if path.name in FORBIDDEN_BASENAMES or path.suffix in FORBIDDEN_SUFFIXES:
            raise ValueError(f'forbidden generated/private artifact: {relative}')
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError(f'unexpected binary package artifact: {relative}') from exc
        if PRIVATE_PATH_RE.search(text):
            raise ValueError(f'private workstation path in package: {relative}')
        if any(marker in text for marker in PRIVATE_KEY_MARKERS):
            raise ValueError(f'private key material in package: {relative}')
        for match in IPV4_RE.finditer(text):
            if not is_allowed_address(match.group(0)):
                raise ValueError(f'non-public IPv4 literal in package: {relative}')


def validate_sources(files):
    for path in files:
        if path.suffix == '.py':
            source = path.read_text(encoding='utf-8')
            compile(source, str(path), 'exec')
        elif path.suffix == '.sh':
            subprocess.run(['bash', '-n', str(path)], check=True)


def validate_executable_modes(files):
    for path in files:
        relative = path.relative_to(GX10_DIR)
        if relative.parts[0] not in {'install', 'sbin', 'tests'}:
            continue
        if path.suffix not in {'.py', '.sh'}:
            continue
        if not path.read_bytes().startswith(b'#!'):
            raise ValueError(f'executable script has no shebang: {relative}')
        if not os.access(path, os.X_OK):
            raise ValueError(f'package script is not executable: {relative}')


def run_tests():
    subprocess.run(
        [
            sys.executable,
            '-m',
            'unittest',
            'discover',
            '-s',
            str(GX10_DIR / 'tests'),
            '-p',
            'test_*.py',
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [str(GX10_DIR / 'tests' / 'validate-filesystem-contract.sh')],
        cwd=ROOT,
        check=True,
    )


def main():
    try:
        files = repository_files()
        if not files:
            raise ValueError('GX10 package inventory is empty')
        validate_public_files(files)
        validate_sources(files)
        validate_executable_modes(files)
        run_tests()
        print('GX10_REBUILD_PACKAGE_VALIDATION=PASS')
        return 0
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
