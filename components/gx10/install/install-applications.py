#!/usr/bin/env python3
import os
import pwd
import grp
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

RUNTIME_USER = 'network-log-agent'
RUNTIME_GROUP = 'network-log-agent'
SCRIPT_DIR = Path(__file__).resolve().parent
GX10_DIR = SCRIPT_DIR.parent
LIBEXEC_DIR = Path('/usr/local/libexec/network-log-gx10')
SYSTEMD_DIR = Path('/etc/systemd/system')
DATABASE_PATH = Path('/var/lib/network-log-gx10/state/events.sqlite3')
RUNTIME_CONFIG_PATH = Path('/etc/network-log-gx10/runtime.json')
REASONING_CONFIG_DIR = Path('/etc/network-log-gx10')

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
        GX10_DIR / 'config' / 'reasoning-runtime-v1.json',
        REASONING_CONFIG_DIR / 'reasoning-runtime-v1.json',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'incident-assessment-v1.txt',
        REASONING_CONFIG_DIR / 'incident-assessment-v1.txt',
        0o644,
    ),
    (
        GX10_DIR / 'prompts' / 'incident-assessment-output-v1.json',
        REASONING_CONFIG_DIR / 'incident-assessment-output-v1.json',
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


def validate_regular_file(path, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'{label} is not a real regular file')


def validate_runtime_file(path, label, uid, gid, mode):
    validate_regular_file(path, label)
    details = path.stat()
    if details.st_nlink != 1:
        raise ValueError(f'{label} must not be hard-linked')
    if details.st_uid != uid or details.st_gid != gid:
        raise ValueError(f'{label} has unexpected ownership')
    if stat.S_IMODE(details.st_mode) != mode:
        raise ValueError(f'{label} has unexpected mode')


def preflight_target(source, target):
    validate_regular_file(source, 'repository artifact')
    if target.exists() or target.is_symlink():
        validate_regular_file(target, 'existing installed artifact')
        details = target.stat()
        if details.st_nlink != 1:
            raise ValueError('existing installed artifact must not be hard-linked')
        if source.read_bytes() != target.read_bytes():
            raise ValueError('existing installed artifact differs')
    elif not target.parent.is_dir() or target.parent.is_symlink():
        raise ValueError('installed artifact parent is not a real directory')


def install_one(source, target, mode, uid, gid):
    preflight_target(source, target)
    if target.exists():
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


def main():
    try:
        if os.geteuid() != 0:
            raise ValueError('run this clean-machine installer as root')
        if os.environ.get('CLEAN_INSTALL_CONFIRM') != 'YES-CLEAN-GX10':
            raise ValueError('CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-GX10')

        runtime_uid = pwd.getpwnam(RUNTIME_USER).pw_uid
        runtime_gid = grp.getgrnam(RUNTIME_GROUP).gr_gid
        validate_runtime_file(
            DATABASE_PATH,
            'application database',
            runtime_uid,
            runtime_gid,
            0o640,
        )
        validate_runtime_file(
            RUNTIME_CONFIG_PATH,
            'runtime configuration',
            0,
            runtime_gid,
            0o640,
        )

        for source, target, _ in ARTIFACTS:
            preflight_target(source, target)

        for source, target, mode in ARTIFACTS:
            install_one(source, target, mode, 0, 0)

        subprocess.run(
            [
                'systemd-analyze',
                'verify',
                str(SYSTEMD_DIR / 'network-log-gx10.service'),
                str(SYSTEMD_DIR / 'network-log-gx10.timer'),
                str(
                    SYSTEMD_DIR
                    / 'network-log-gx10-correlation.service'
                ),
                str(
                    SYSTEMD_DIR
                    / 'network-log-gx10-correlation.timer'
                ),
            ],
            check=True,
        )
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        print('GX10_APPLICATION_INSTALL=PASS')
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
