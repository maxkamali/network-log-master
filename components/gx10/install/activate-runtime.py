#!/usr/bin/env python3
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ACTIVATION_UNITS = ('ollama.service', 'network-log-gx10.timer')
OLLAMA_PREACTIVATION_ARGS = ('--offline', '--hash-blobs')


def require_authorization(euid, environ):
    if euid != 0:
        raise ValueError('run this clean-machine activator as root')
    if environ.get('CLEAN_INSTALL_CONFIRM') != 'YES-CLEAN-GX10':
        raise ValueError('CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-GX10')
    if environ.get('GX10_ACTIVATE_CONFIRM') != 'ENABLE-VERIFIED-GX10':
        raise ValueError('GX10_ACTIVATE_CONFIRM must equal ENABLE-VERIFIED-GX10')


def run_script(name, *arguments, quiet=False, check=True):
    streams = {}
    if quiet:
        streams = {
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL,
        }
    return subprocess.run(
        [sys.executable, str(SCRIPT_DIR / name), *arguments],
        check=check,
        **streams,
    )


def wait_for_ollama(attempts=30):
    for _ in range(attempts):
        result = run_script('verify-ollama.py', quiet=True, check=False)
        if result.returncode == 0:
            return
        time.sleep(1)
    run_script('verify-ollama.py')


def rollback(units):
    if 'network-log-gx10.timer' in units:
        subprocess.run(
            ['systemctl', 'stop', 'network-log-gx10.service'],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    for unit in reversed(units):
        subprocess.run(
            ['systemctl', 'disable', '--now', unit],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def activate():
    require_authorization(os.geteuid(), os.environ)
    run_script('verify-platform.py')
    run_script('verify-runtime.py', '--preactivation')
    run_script('verify-ollama.py', *OLLAMA_PREACTIVATION_ARGS)

    changed_units = []
    try:
        changed_units.append(ACTIVATION_UNITS[0])
        subprocess.run(
            ['systemctl', 'enable', '--now', ACTIVATION_UNITS[0]],
            check=True,
        )
        wait_for_ollama()

        changed_units.append(ACTIVATION_UNITS[1])
        subprocess.run(
            ['systemctl', 'enable', '--now', ACTIVATION_UNITS[1]],
            check=True,
        )
        run_script('verify-runtime.py', '--active')
        run_script('verify-ollama.py')
    except (OSError, subprocess.CalledProcessError, ValueError):
        rollback(changed_units)
        raise


def main():
    try:
        activate()
        print('GX10_RUNTIME_ACTIVATION=PASS')
        return 0
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
