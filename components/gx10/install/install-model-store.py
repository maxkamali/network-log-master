#!/usr/bin/env python3
import grp
import importlib.util
import os
import pwd
import shutil
import stat
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VERIFIER_PATH = SCRIPT_DIR / 'verify-ollama.py'
TARGET_ROOT = Path('/usr/share/ollama/.ollama/models')
OLLAMA_USER = 'ollama'
OLLAMA_GROUP = 'ollama'


def load_verifier():
    specification = importlib.util.spec_from_file_location(
        'verify_ollama_model_store',
        VERIFIER_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def validate_distinct_roots(source_root, target_root):
    source = Path(source_root)
    target = Path(target_root)
    if source.is_symlink() or not source.is_dir():
        raise ValueError('offline model-store source is not a real directory')
    if target.is_symlink() or not target.is_dir():
        raise ValueError('installed model root is not a real directory')
    source_resolved = source.resolve()
    target_resolved = target.resolve()
    if source_resolved == target_resolved:
        raise ValueError('offline model-store source equals installed target')
    if source_resolved in target_resolved.parents:
        raise ValueError('installed target is inside offline model-store source')
    if target_resolved in source_resolved.parents:
        raise ValueError('offline model-store source is inside installed target')


def ensure_directory(path, uid, gid):
    path = Path(path)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise ValueError('model-store destination parent is not a real directory')
    else:
        path.mkdir()
    os.chown(path, uid, gid)
    os.chmod(path, 0o755)


def prepare_parents(path, root, uid, gid):
    relative = Path(path).relative_to(root)
    current = Path(root)
    for part in relative.parts[:-1]:
        current = current / part
        ensure_directory(current, uid, gid)


def preflight_file(source, target):
    source = Path(source)
    target = Path(target)
    if source.is_symlink() or not source.is_file():
        raise ValueError('offline model-store artifact is not a real file')
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file():
            raise ValueError('installed model-store artifact is not a real file')
        if target.stat().st_nlink != 1:
            raise ValueError('installed model-store artifact must not be hard-linked')
        if source.stat().st_size != target.stat().st_size:
            raise ValueError('installed model-store artifact differs')
        with source.open('rb') as source_handle, target.open('rb') as target_handle:
            while True:
                source_chunk = source_handle.read(1024 * 1024)
                target_chunk = target_handle.read(1024 * 1024)
                if source_chunk != target_chunk:
                    raise ValueError('installed model-store artifact differs')
                if not source_chunk:
                    break


def install_file(source, target, uid, gid):
    source = Path(source)
    target = Path(target)
    if target.exists():
        if source.stat().st_size <= 1024 * 1024:
            if source.read_bytes() != target.read_bytes():
                raise ValueError('installed model-store artifact differs')
        os.chown(target, uid, gid)
        os.chmod(target, 0o644)
        return

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{target.name}.',
        dir=target.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with source.open('rb') as input_handle, os.fdopen(descriptor, 'wb') as output_handle:
            shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.chown(temporary_path, uid, gid)
        os.chmod(temporary_path, 0o644)
        os.link(temporary_path, target, follow_symlinks=False)
        temporary_path.unlink()
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def relative_inventory(paths, root):
    return {Path(path).relative_to(root) for path in paths}


def reject_unexpected_target_files(target_root, expected):
    target_root = Path(target_root)
    observed = set()
    for path in target_root.rglob('*'):
        if path.is_symlink():
            raise ValueError('installed model root contains a symbolic link')
        if path.is_file():
            observed.add(path.relative_to(target_root))
    if observed - expected:
        raise ValueError('installed model root contains unexpected files')


def install_model_store(source_root, target_root, uid, gid, verifier):
    source_root = Path(source_root)
    target_root = Path(target_root)
    validate_distinct_roots(source_root, target_root)
    manifests, blobs = verifier.verify_model_store(source_root, hash_blobs=True)
    source_paths = (*blobs, *manifests)
    relative_paths = relative_inventory(source_paths, source_root)
    reject_unexpected_target_files(target_root, relative_paths)

    for source in source_paths:
        target = target_root / source.relative_to(source_root)
        preflight_file(source, target)

    for source in source_paths:
        target = target_root / source.relative_to(source_root)
        prepare_parents(target, target_root, uid, gid)
        install_file(source, target, uid, gid)

    verifier.verify_model_store(target_root, hash_blobs=True)


def main():
    try:
        if os.geteuid() != 0:
            raise ValueError('run this clean-machine installer as root')
        if os.environ.get('CLEAN_INSTALL_CONFIRM') != 'YES-CLEAN-GX10':
            raise ValueError('CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-GX10')
        source_value = os.environ.get('OLLAMA_MODEL_STORE_DIR')
        if not source_value:
            raise ValueError('set OLLAMA_MODEL_STORE_DIR')

        user = pwd.getpwnam(OLLAMA_USER)
        group = grp.getgrnam(OLLAMA_GROUP)
        target_details = TARGET_ROOT.stat()
        if target_details.st_uid != user.pw_uid or target_details.st_gid != group.gr_gid:
            raise ValueError('installed model root has unexpected ownership')
        if stat.S_IMODE(target_details.st_mode) != 0o755:
            raise ValueError('installed model root has unexpected mode')

        install_model_store(
            source_value,
            TARGET_ROOT,
            user.pw_uid,
            group.gr_gid,
            load_verifier(),
        )
        print('GX10_OLLAMA_MODEL_INSTALL=PASS')
        return 0
    except (KeyError, OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
