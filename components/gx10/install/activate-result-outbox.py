#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time


SCRIPT_DIR = Path(__file__).resolve().parent
OUTBOX_SERVICE = 'network-log-gx10-result-outbox.service'
OUTBOX_TIMER = 'network-log-gx10-result-outbox.timer'
REASONING_SERVICE = 'network-log-gx10-reasoning.service'
REASONING_TIMER = 'network-log-gx10-reasoning.timer'
REASONING_TABLES = (
    'reasoning_packets',
    'reasoning_model_versions',
    'reasoning_prompt_versions',
    'reasoning_runs',
    'reasoning_results',
)


class ActivationError(ValueError):
    pass


def load_verifier():
    path = SCRIPT_DIR / 'verify-result-outbox.py'
    specification = importlib.util.spec_from_file_location(
        'result_outbox_activation_verifier', path
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def systemctl_value(unit, property_name):
    return subprocess.run(
        ['systemctl', 'show', unit, f'--property={property_name}', '--value'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def run_systemctl(*arguments):
    subprocess.run(
        ['systemctl', *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_service_inactive(unit, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = systemctl_value(unit, 'ActiveState')
        if state == 'inactive':
            return
        if state == 'failed':
            raise ActivationError('activation dependency service failed')
        time.sleep(0.2)
    raise ActivationError('activation dependency service did not settle')


def reasoning_snapshot(database):
    connection = sqlite3.connect(f'{Path(database).as_uri()}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('BEGIN')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ActivationError('activation quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ActivationError('activation foreign_key_check failed')
        digest = hashlib.sha256()
        counts = {}
        for table in REASONING_TABLES:
            columns = [
                row[1]
                for row in connection.execute(f'PRAGMA table_info({table})')
            ]
            if not columns:
                raise ActivationError('activation reasoning schema differs')
            primary = [
                row[1]
                for row in connection.execute(f'PRAGMA table_info({table})')
                if row[5]
            ]
            order = ','.join(f'"{name}"' for name in (primary or columns))
            rows = connection.execute(
                f'SELECT * FROM "{table}" ORDER BY {order}'
            ).fetchall()
            counts[table] = len(rows)
            digest.update(table.encode('ascii'))
            digest.update(b'\0')
            for row in rows:
                data = json.dumps(
                    list(row),
                    ensure_ascii=False,
                    separators=(',', ':'),
                ).encode('utf-8')
                digest.update(len(data).to_bytes(8, 'big'))
                digest.update(data)
        started = connection.execute(
            "SELECT COUNT(*) FROM reasoning_runs WHERE status='STARTED'"
        ).fetchone()[0]
        failures = connection.execute(
            "SELECT COUNT(*) FROM reasoning_runs WHERE status NOT IN ('STARTED','SUCCEEDED')"
        ).fetchone()[0]
        if started or failures != 1:
            raise ActivationError('activation reasoning terminal state differs')
        return {
            'digest': digest.hexdigest(),
            'packets': counts['reasoning_packets'],
            'runs': counts['reasoning_runs'],
            'results': counts['reasoning_results'],
            'failures': failures,
        }
    finally:
        connection.close()


def activate():
    verifier = load_verifier()
    database = verifier.load_managed_database()
    root = database.parent / 'result-outbox'
    ready = root / 'ready'
    delivered = root / 'delivered'
    initial = verifier.verify(
        database,
        root,
        ready,
        delivered,
        active=False,
        allow_populated_inactive=True,
    )
    if initial['delivered'] or initial['ready'] > initial['results']:
        raise ActivationError('activation initial outbox state differs')
    if (
        systemctl_value(REASONING_TIMER, 'ActiveState') != 'active'
        or systemctl_value(REASONING_TIMER, 'UnitFileState') != 'enabled'
    ):
        raise ActivationError('activation reasoning schedule differs')
    if systemctl_value(REASONING_SERVICE, 'ActiveState') == 'failed':
        raise ActivationError('activation reasoning service differs')
    reasoning_restored = False
    try:
        run_systemctl('disable', '--now', OUTBOX_TIMER)
        run_systemctl('disable', '--now', REASONING_TIMER)
        wait_service_inactive(REASONING_SERVICE)
        before = reasoning_snapshot(database)
        run_systemctl('start', OUTBOX_SERVICE)
        if systemctl_value(OUTBOX_SERVICE, 'Result') != 'success':
            raise ActivationError('activation service result differs')
        after = reasoning_snapshot(database)
        if after != before:
            raise ActivationError('activation changed reasoning state')
        populated = verifier.verify(
            database,
            root,
            ready,
            delivered,
            active=False,
            allow_populated_inactive=True,
        )
        if (
            populated['results'] != before['results']
            or populated['ready'] != before['results']
            or populated['delivered'] != 0
        ):
            raise ActivationError('activation outbox cardinality differs')
        run_systemctl('enable', '--now', OUTBOX_TIMER)
        active = verifier.verify(
            database, root, ready, delivered, active=True
        )
        if active != populated:
            raise ActivationError('activation active verification differs')
        run_systemctl('enable', '--now', REASONING_TIMER)
        reasoning_restored = True
        if (
            systemctl_value(REASONING_TIMER, 'ActiveState') != 'active'
            or systemctl_value(REASONING_TIMER, 'UnitFileState') != 'enabled'
        ):
            raise ActivationError('activation reasoning restore differs')
        return before, active
    except Exception:
        try:
            run_systemctl('disable', '--now', OUTBOX_TIMER)
        except Exception:
            pass
        raise
    finally:
        if not reasoning_restored:
            try:
                run_systemctl('enable', '--now', REASONING_TIMER)
            except Exception:
                pass


def parse_args():
    parser = argparse.ArgumentParser(
        description='Activate the protected local GX10 result outbox'
    )
    parser.add_argument(
        '--confirm-activate-local-result-outbox', action='store_true'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise ActivationError('run the result outbox activator as root')
        if not args.confirm_activate_local_result_outbox:
            raise ActivationError('local result outbox confirmation is absent')
        state, outbox = activate()
        print(
            'RESULT_OUTBOX_ACTIVATION schema=1 '
            f'packets={state["packets"]} runs={state["runs"]} '
            f'results={state["results"]} failures={state["failures"]} '
            f'ready={outbox["ready"]} delivered={outbox["delivered"]} '
            f'reasoning_sha256={state["digest"]} '
            'timer_enabled=yes credentials_installed=no transmission=no'
        )
        print('GX10_RESULT_OUTBOX_LOCAL_ACTIVATION=PASS')
        return 0
    except (OSError, sqlite3.Error, ActivationError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_RESULT_OUTBOX_LOCAL_ACTIVATION=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
