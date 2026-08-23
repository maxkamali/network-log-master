#!/usr/bin/env python3
import grp
import hashlib
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_SIZE = 35792104
EXPECTED_SHA256 = '26f44ca89143f2326a3aad98b2cb5e8b5af9397aef7001cd8d022e90d6e0b55e'
OLLAMA_USER = 'ollama'
OLLAMA_GROUP = 'ollama'
OLLAMA_HOME = Path('/usr/share/ollama')
OLLAMA_BINARY = Path('/usr/local/bin/ollama')
OLLAMA_UNIT = Path('/etc/systemd/system/ollama.service')
SCRIPT_DIR = Path(__file__).resolve().parent
UNIT_SOURCE = SCRIPT_DIR.parent / 'systemd' / 'ollama.service'


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_binary(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Ollama binary input is not a real regular file')
    if path.stat().st_size != EXPECTED_SIZE:
        raise ValueError('Ollama binary input has unexpected size')
    if file_sha256(path) != EXPECTED_SHA256:
        raise ValueError('Ollama binary input has unexpected hash')


def install_exact(source, target, mode, uid, gid):
    source = Path(source)
    target = Path(target)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file():
            raise ValueError('existing Ollama artifact is not a real regular file')
        if target.stat().st_nlink != 1:
            raise ValueError('existing Ollama artifact must not be hard-linked')
        if source.read_bytes() != target.read_bytes():
            raise ValueError('existing Ollama artifact differs')
        os.chown(target, uid, gid)
        os.chmod(target, mode)
        return

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{target.name}.',
        dir=target.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with source.open('rb') as input_handle, os.fdopen(descriptor, 'wb') as output_handle:
            shutil.copyfileobj(input_handle, output_handle)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.chown(temporary_path, uid, gid)
        os.chmod(temporary_path, mode)
        os.link(temporary_path, target, follow_symlinks=False)
        temporary_path.unlink()
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def ensure_identity():
    try:
        group = grp.getgrnam(OLLAMA_GROUP)
    except KeyError:
        subprocess.run(['groupadd', '--system', OLLAMA_GROUP], check=True)
        group = grp.getgrnam(OLLAMA_GROUP)

    try:
        user = pwd.getpwnam(OLLAMA_USER)
    except KeyError:
        subprocess.run(
            [
                'useradd',
                '--system',
                '--gid',
                OLLAMA_GROUP,
                '--home-dir',
                str(OLLAMA_HOME),
                '--shell',
                '/usr/sbin/nologin',
                '--no-create-home',
                OLLAMA_USER,
            ],
            check=True,
        )
        user = pwd.getpwnam(OLLAMA_USER)

    if user.pw_gid != group.gr_gid or Path(user.pw_dir) != OLLAMA_HOME:
        raise ValueError('existing Ollama identity differs')
    if Path(user.pw_shell).name != 'nologin':
        raise ValueError('existing Ollama identity has unexpected shell')
    return user.pw_uid, group.gr_gid


def ensure_directory(path, uid, gid, mode):
    path = Path(path)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise ValueError('existing Ollama directory is not a real directory')
    else:
        path.mkdir(mode=mode)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def main():
    try:
        if os.geteuid() != 0:
            raise ValueError('run this clean-machine installer as root')
        if os.environ.get('CLEAN_INSTALL_CONFIRM') != 'YES-CLEAN-GX10':
            raise ValueError('CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-GX10')
        binary_input = os.environ.get('OLLAMA_BINARY_FILE')
        if not binary_input:
            raise ValueError('set OLLAMA_BINARY_FILE')

        validate_binary(binary_input)
        if UNIT_SOURCE.is_symlink() or not UNIT_SOURCE.is_file():
            raise ValueError('Ollama unit source is not a real regular file')

        uid, gid = ensure_identity()
        ensure_directory(OLLAMA_HOME, uid, gid, 0o755)
        ollama_state = OLLAMA_HOME / '.ollama'
        ensure_directory(ollama_state, uid, gid, 0o755)
        model_root = OLLAMA_HOME / '.ollama' / 'models'
        ensure_directory(model_root, uid, gid, 0o755)

        install_exact(binary_input, OLLAMA_BINARY, 0o755, 0, 0)
        install_exact(UNIT_SOURCE, OLLAMA_UNIT, 0o644, 0, 0)
        subprocess.run(
            ['systemd-analyze', 'verify', str(OLLAMA_UNIT)],
            check=True,
        )
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        print('GX10_OLLAMA_INSTALL=PASS')
        return 0
    except (
        KeyError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
