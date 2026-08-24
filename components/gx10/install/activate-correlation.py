#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE = 'network-log-gx10-correlation.service'
TIMER = 'network-log-gx10-correlation.timer'
CONFIRMATION = 'ENABLE-VERIFIED-CORRELATION'


def run_verifier(database, mode):
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / 'verify-correlation.py'),
            mode,
            '--database',
            str(database),
            '--private-runtime',
        ],
        check=True,
    )


def disable_runtime():
    subprocess.run(['systemctl', 'disable', '--now', TIMER], check=False)
    subprocess.run(['systemctl', 'stop', SERVICE], check=False)


def activate(database):
    run_verifier(database, '--installed')
    try:
        subprocess.run(['systemctl', 'start', SERVICE], check=True)
        run_verifier(database, '--installed')
        subprocess.run(
            ['systemctl', 'enable', '--now', TIMER],
            check=True,
        )
        run_verifier(database, '--active')
    except (OSError, subprocess.CalledProcessError, ValueError):
        disable_runtime()
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description='Activate the verified GX10 correlation timer'
    )
    parser.add_argument('--database', type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError('run the correlation activator as root')
        if os.environ.get('GX10_CORRELATION_ACTIVATE_CONFIRM') != CONFIRMATION:
            raise ValueError('managed correlation activation confirmation is absent')
        activate(args.database.resolve(strict=True))
        print('GX10_MANAGED_CORRELATION_ACTIVATION=PASS')
        return 0
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
