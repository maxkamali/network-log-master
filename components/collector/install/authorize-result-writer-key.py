#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import grp
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys


WRITER_USER = 'ai_results_writer'
WRITER_GROUP = 'ai_results_writer'
AUTHORIZED_KEYS = Path('/var/lib/ai-results-writer/.ssh/authorized_keys')
BACKUP_DIR = Path('/var/backups/network-log')
BACKUP = BACKUP_DIR / 'ai-results-writer.authorized_keys.pre-result-sender-v1'
PUBLIC_KEY_INPUT_DEFAULT = Path('/run/network-log-result-writer.key.pub')
SSH_KEYGEN = Path('/usr/bin/ssh-keygen')
SSHD = Path('/usr/sbin/sshd')


class AuthorizeError(ValueError):
    pass


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_file(path, mode, uid, gid, maximum=256 * 1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise AuthorizeError('result writer authorization artifact differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
        or details.st_size <= 0
        or details.st_size > maximum
    ):
        raise AuthorizeError('result writer authorization metadata differs')


def validate_directory(path, mode, uid, gid):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise AuthorizeError('result writer authorization directory differs')
    details = path.stat()
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise AuthorizeError('result writer authorization directory metadata differs')


def key_pair(line):
    fields = line.split()
    if len(fields) < 2 or fields[0] != 'ssh-ed25519':
        raise AuthorizeError('result writer public key input differs')
    try:
        decoded = base64.b64decode(fields[1], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AuthorizeError('result writer public key input differs') from exc
    if len(decoded) < 32:
        raise AuthorizeError('result writer public key input differs')
    return fields[0], fields[1]


def authorized_key_pairs(data):
    pairs = []
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise AuthorizeError('existing result writer authorization differs') from exc
    for raw in text.splitlines():
        fields = raw.split()
        if not fields or fields[0].startswith('#'):
            continue
        try:
            index = fields.index('ssh-ed25519')
        except ValueError:
            continue
        if index + 1 >= len(fields):
            raise AuthorizeError('existing result writer authorization differs')
        pairs.append((fields[index], fields[index + 1]))
    return pairs


def read_public_key(path):
    path = Path(path)
    validate_file(path, 0o600, 0, 0, maximum=16 * 1024)
    data = path.read_bytes()
    if b'PRIVATE KEY' in data or b'\x00' in data:
        raise AuthorizeError('result writer public key input differs')
    try:
        text = data.decode('ascii')
    except UnicodeDecodeError as exc:
        raise AuthorizeError('result writer public key input differs') from exc
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise AuthorizeError('result writer public key input differs')
    line = lines[0].strip()
    pair = key_pair(line)
    result = subprocess.run(
        [str(SSH_KEYGEN), '-l', '-f', str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise AuthorizeError('result writer public key input differs')
    return line.encode('ascii') + b'\n', pair


def install_new(path, data, mode, uid, gid):
    path = Path(path)
    temporary = path.parent / f'.{path.name}.authorize-{os.getpid()}'
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


def replace(path, data, mode, uid, gid):
    path = Path(path)
    temporary = path.parent / f'.{path.name}.replace-{os.getpid()}'
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
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def ensure_backup_directory():
    created = False
    try:
        BACKUP_DIR.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        pass
    validate_directory(BACKUP_DIR, 0o700, 0, 0)
    return created


def authorize(public_key_input):
    account = pwd.getpwnam(WRITER_USER)
    group = grp.getgrnam(WRITER_GROUP)
    if account.pw_gid != group.gr_gid:
        raise AuthorizeError('result writer account differs')
    validate_file(AUTHORIZED_KEYS, 0o600, account.pw_uid, group.gr_gid)
    original = AUTHORIZED_KEYS.read_bytes()
    line, pair = read_public_key(public_key_input)
    count = authorized_key_pairs(original).count(pair)
    if count > 1:
        raise AuthorizeError('result writer public key is duplicated')
    if count == 1:
        if BACKUP.exists() or BACKUP.is_symlink():
            validate_file(BACKUP, 0o600, 0, 0)
            predecessor = BACKUP.read_bytes()
            separator = b'' if predecessor.endswith(b'\n') else b'\n'
            if original != predecessor + separator + line:
                raise AuthorizeError('result writer authorization differs from backup')
        return {'created': 0, 'reused': 1, 'backup_created': 0}
    if BACKUP.exists() or BACKUP.is_symlink():
        raise AuthorizeError('result writer authorization backup already exists')
    created_directory = ensure_backup_directory()
    backup_created = False
    changed = False
    try:
        backup_created = True
        install_new(BACKUP, original, 0o600, 0, 0)
        validate_file(BACKUP, 0o600, 0, 0)
        if BACKUP.read_bytes() != original:
            raise AuthorizeError('result writer authorization backup differs')
        separator = b'' if original.endswith(b'\n') else b'\n'
        replacement = original + separator + line
        changed = True
        replace(AUTHORIZED_KEYS, replacement, 0o600, account.pw_uid, group.gr_gid)
        validate_file(AUTHORIZED_KEYS, 0o600, account.pw_uid, group.gr_gid)
        if AUTHORIZED_KEYS.read_bytes() != replacement:
            raise AuthorizeError('result writer authorization publication differs')
        if authorized_key_pairs(replacement).count(pair) != 1:
            raise AuthorizeError('result writer authorization publication differs')
        result = subprocess.run(
            [str(SSHD), '-t'],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise AuthorizeError('SSH configuration validation failed')
        return {'created': 1, 'reused': 0, 'backup_created': 1}
    except Exception:
        if changed:
            replace(AUTHORIZED_KEYS, original, 0o600, account.pw_uid, group.gr_gid)
        if backup_created:
            BACKUP.unlink()
            fsync_directory(BACKUP.parent)
        if created_directory:
            try:
                BACKUP_DIR.rmdir()
            except OSError:
                pass
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Append one dedicated GX10 result-writer public key'
    )
    parser.add_argument(
        '--public-key-input',
        type=Path,
        default=PUBLIC_KEY_INPUT_DEFAULT,
    )
    parser.add_argument(
        '--confirm-authorize-dedicated-result-writer',
        action='store_true',
    )
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise AuthorizeError('run the result writer authorizer as root')
        if not args.confirm_authorize_dedicated_result_writer:
            raise AuthorizeError('result writer authorization confirmation is absent')
        result = authorize(args.public_key_input)
        print(
            'RESULT_WRITER_AUTHORIZATION schema=1 '
            f'created={result["created"]} reused={result["reused"]} '
            f'backup_created={result["backup_created"]}'
        )
        print('COLLECTOR_RESULT_WRITER_AUTHORIZATION=PASS')
        return 0
    except (OSError, KeyError, subprocess.SubprocessError, AuthorizeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('COLLECTOR_RESULT_WRITER_AUTHORIZATION=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
