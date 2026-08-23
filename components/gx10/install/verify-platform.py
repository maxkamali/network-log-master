#!/usr/bin/env python3
import os
import platform
import sqlite3
import subprocess
import sys
from pathlib import Path

EXPECTED_PACKAGES = {
    'python3.12-minimal': '3.12.3-1ubuntu0.15',
    'openssh-client': '1:9.6p1-3ubuntu13.18',
    'zstd': '1.5.5+dfsg2-2build1.1',
}
CUDA_COMPILER = Path('/usr/local/cuda/bin/nvcc')


def read_os_release(path=Path('/etc/os-release')):
    values = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        if '=' not in raw or raw.startswith('#'):
            continue
        key, value = raw.split('=', 1)
        values[key] = value.strip().strip('"')
    return values


def package_version(name):
    result = subprocess.run(
        ['dpkg-query', '-W', '-f=${Version}', name],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def main():
    try:
        os_release = read_os_release()
        if os_release.get('ID') != 'ubuntu':
            raise ValueError('unexpected operating system')
        if not os_release.get('VERSION_ID', '').startswith('24.04'):
            raise ValueError('unexpected operating-system version')
        if platform.machine() not in ('aarch64', 'arm64'):
            raise ValueError('unexpected architecture')

        for package, expected in EXPECTED_PACKAGES.items():
            if package_version(package) != expected:
                raise ValueError(f'unexpected package version: {package}')

        if sys.version_info[:3] != (3, 12, 3):
            raise ValueError('unexpected Python version')
        if sqlite3.sqlite_version != '3.45.1':
            raise ValueError('unexpected Python SQLite runtime')
        if not Path('/usr/bin/sftp').is_file():
            raise ValueError('SFTP executable missing')
        if not Path('/usr/bin/zstd').is_file():
            raise ValueError('Zstandard executable missing')

        kernel = platform.release()
        if kernel != '6.17.0-1029-nvidia':
            raise ValueError('unexpected kernel')

        driver = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=driver_version',
                '--format=csv,noheader',
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.splitlines()
        if not driver or any(value.strip() != '580.173.02' for value in driver):
            raise ValueError('unexpected NVIDIA driver')

        if not CUDA_COMPILER.is_file():
            raise ValueError('CUDA compiler missing')
        nvcc = subprocess.run(
            [CUDA_COMPILER, '--version'],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        if 'V13.0.88' not in nvcc:
            raise ValueError('unexpected CUDA compiler build')

        print('GX10_PLATFORM_VERIFY=PASS')
        return 0
    except (
        OSError,
        subprocess.CalledProcessError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
