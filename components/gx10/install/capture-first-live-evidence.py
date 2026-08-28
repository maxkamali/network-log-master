#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys


OUTBOX_ROOT = Path('/var/lib/network-log-gx10/result-outbox')
INSTALLED_SENDER = Path('/usr/local/libexec/network-log-gx10/send-result-outbox.py')
REPOSITORY_SENDER = Path(__file__).resolve().parents[1] / 'sbin/send-result-outbox.py'
RUNTIME_USER = 'network-log-agent'
SCHEMA = 'network-log-first-live-evidence'
SCHEMA_VERSION = 1
EVIDENCE_MAX_BYTES = 4 * 1024 * 1024
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
FILENAME_RE = re.compile(
    r'^(?:ai-result-v1|incident-state-v[12])-[0-9a-f]{32}\.jsonl$'
)


class EvidenceError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def validate_directory(path, uid, gid, mode, label):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise EvidenceError(f'{label} differs')
    details = path.stat()
    if (
        details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
    ):
        raise EvidenceError(f'{label} metadata differs')


def validate_private_file(path, uid, gid, mode, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise EvidenceError(f'{label} differs')
    details = path.stat()
    if (
        details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != mode
        or details.st_size <= 0
        or details.st_size > EVIDENCE_MAX_BYTES
    ):
        raise EvidenceError(f'{label} metadata differs')


def load_sender(installed, repository, uid, gid):
    if installed.is_symlink() or not installed.is_file():
        raise EvidenceError('installed result sender source differs')
    installed_details = installed.stat()
    if installed_details.st_uid != 0 or stat.S_IMODE(installed_details.st_mode) & 0o022:
        raise EvidenceError('installed result sender source metadata differs')
    if repository.is_symlink() or not repository.is_file():
        raise EvidenceError('repository result sender source differs')
    if stat.S_IMODE(repository.stat().st_mode) & 0o022:
        raise EvidenceError('repository result sender source metadata differs')
    if sha256_file(installed) != sha256_file(repository):
        raise EvidenceError('installed result sender source differs from repository')
    specification = importlib.util.spec_from_file_location(
        'first_live_installed_sender', installed
    )
    if specification is None or specification.loader is None:
        raise EvidenceError('result sender source cannot be loaded')
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def verify_configured_boundary():
    verifier = Path(__file__).resolve().parent / 'verify-result-sender.py'
    result = subprocess.run(
        [
            str(verifier), '--configured',
            '--runtime-config', '/etc/network-log-gx10/runtime.json',
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if (
        result.returncode != 0
        or 'timer_enabled=no' not in result.stdout
        or 'GX10_MANAGED_RESULT_SENDER_VERIFY=PASS' not in result.stdout
    ):
        raise EvidenceError('configured-inactive result sender verification failed')


def acquire_lock(root, uid, gid):
    path = Path(root) / '.result-outbox.lock'
    flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise EvidenceError('result outbox lock differs') from exc
    details = os.fstat(descriptor)
    if (
        not stat.S_ISREG(details.st_mode)
        or details.st_nlink != 1
        or details.st_uid != uid
        or details.st_gid != gid
        or stat.S_IMODE(details.st_mode) != 0o600
    ):
        os.close(descriptor)
        raise EvidenceError('result outbox lock metadata differs')
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise EvidenceError('result outbox is already locked') from exc
    return descriptor


def describe_entry(name, item):
    data = item['data']
    lines = data.decode('utf-8').splitlines()
    records = [json.loads(line) for line in lines]
    route = (
        'incident_updates'
        if all(record.get('type') == 'incident_lifecycle' for record in records)
        else 'ai_updates'
    )
    if route == 'ai_updates' and any(
        record.get('type') == 'incident_lifecycle' for record in records
    ):
        raise EvidenceError('result outbox route is mixed')
    return {
        'filename': name,
        'file_sha256': sha256_bytes(data),
        'line_sha256': [
            sha256_bytes((line + '\n').encode('utf-8')) for line in lines
        ],
        'record_count': len(lines),
        'route': route,
        'size': len(data),
        '_timestamp': item['timestamp'],
    }


def public_entry(entry):
    return {key: value for key, value in entry.items() if key != '_timestamp'}


def compact_entry(entry):
    public = public_entry(entry)
    return {
        key: public[key]
        for key in ('filename', 'file_sha256', 'record_count', 'route', 'size')
    }


def validate_compact_manifest(value, expected_count, label):
    if not isinstance(value, list) or len(value) != expected_count:
        raise EvidenceError(f'{label} inventory differs')
    names = set()
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {
            'filename', 'file_sha256', 'record_count', 'route', 'size'
        }:
            raise EvidenceError(f'{label} inventory shape differs')
        if (
            not isinstance(entry['filename'], str)
            or FILENAME_RE.fullmatch(entry['filename']) is None
            or entry['filename'] in names
            or not isinstance(entry['file_sha256'], str)
            or SHA256_RE.fullmatch(entry['file_sha256']) is None
            or entry['route'] not in {'ai_updates', 'incident_updates'}
            or isinstance(entry['record_count'], bool)
            or not isinstance(entry['record_count'], int)
            or not 1 <= entry['record_count'] <= 100
            or (entry['route'] == 'ai_updates' and entry['record_count'] != 1)
            or isinstance(entry['size'], bool)
            or not isinstance(entry['size'], int)
            or not 1 <= entry['size'] <= 256 * 1024
        ):
            raise EvidenceError(f'{label} inventory values differ')
        names.add(entry['filename'])
    return names


def inventory(sender, directory):
    return {
        name: describe_entry(name, item)
        for name, item in sender.inventory(directory).items()
    }


def inventory_as_runtime(sender, ready, delivered, runtime_uid, runtime_gid):
    original_euid = os.geteuid()
    original_egid = os.getegid()
    original_groups = os.getgroups()
    changed = original_euid == 0 and runtime_uid != 0
    try:
        if changed:
            os.setgroups([runtime_gid])
            os.setegid(runtime_gid)
            os.seteuid(runtime_uid)
        return inventory(sender, ready), inventory(sender, delivered)
    finally:
        if changed:
            os.seteuid(0)
            os.setegid(original_egid)
            os.setgroups(original_groups)


def inventory_digest(entries):
    value = [public_entry(entries[name]) for name in sorted(entries)]
    return sha256_bytes(canonical_json(value).encode('utf-8'))


def write_new_private(path, value, uid, gid):
    path = Path(path)
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise EvidenceError('evidence output must be an absent absolute path')
    validate_directory(path.parent, uid, gid, 0o700, 'evidence parent')
    payload = (canonical_json(value) + '\n').encode('utf-8')
    if len(payload) > EVIDENCE_MAX_BYTES:
        raise EvidenceError('first-live evidence exceeds the private evidence bound')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        try:
            handle = os.fdopen(descriptor, 'wb', closefd=True)
        except Exception:
            os.close(descriptor)
            raise
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(path, uid, gid)
        os.chmod(path, 0o600)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def read_evidence(path, uid, gid, phase):
    validate_private_file(path, uid, gid, 0o600, 'first-live evidence')
    before = Path(path).stat()
    raw = Path(path).read_text(encoding='utf-8')
    after = Path(path).stat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns')
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise EvidenceError('first-live evidence changed during verification')
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceError('first-live evidence JSON differs') from exc
    if (canonical_json(value) + '\n') != raw:
        raise EvidenceError('first-live evidence is not canonical')
    if (
        not isinstance(value, dict)
        or set(value) != {
            'delivered_before', 'delivered_count_before',
            'expected_delivered_digest', 'phase', 'prepared_at',
            'ready_count_before', 'remaining_ready', 'remaining_ready_digest',
            'schema', 'schema_version', 'selected',
        }
        or value.get('schema') != SCHEMA
        or value.get('schema_version') != SCHEMA_VERSION
        or value.get('phase') != phase
    ):
        raise EvidenceError('first-live evidence identity differs')
    selected = value.get('selected')
    if not isinstance(selected, dict) or set(selected) != {
        'filename', 'file_sha256', 'line_sha256', 'record_count', 'route', 'size'
    }:
        raise EvidenceError('first-live selected evidence shape differs')
    if (
        not isinstance(selected['filename'], str)
        or FILENAME_RE.fullmatch(selected['filename']) is None
        or not isinstance(selected['file_sha256'], str)
        or SHA256_RE.fullmatch(selected['file_sha256']) is None
        or selected['route'] not in {'ai_updates', 'incident_updates'}
        or isinstance(selected['record_count'], bool)
        or not isinstance(selected['record_count'], int)
        or not 1 <= selected['record_count'] <= 100
        or isinstance(selected['size'], bool)
        or not isinstance(selected['size'], int)
        or not 1 <= selected['size'] <= 256 * 1024
        or not isinstance(selected['line_sha256'], list)
        or len(selected['line_sha256']) != selected['record_count']
        or any(
            not isinstance(item, str) or SHA256_RE.fullmatch(item) is None
            for item in selected['line_sha256']
        )
        or any(
            not isinstance(value.get(field), str)
            or SHA256_RE.fullmatch(value[field]) is None
            for field in ('expected_delivered_digest', 'remaining_ready_digest')
        )
        or any(
            isinstance(value.get(field), bool)
            or not isinstance(value[field], int)
            or value[field] < 0
            for field in ('ready_count_before', 'delivered_count_before')
        )
        or value['ready_count_before'] < 1
        or not isinstance(value.get('remaining_ready'), list)
        or not isinstance(value.get('delivered_before'), list)
    ):
        raise EvidenceError('first-live evidence values differ')
    remaining_names = validate_compact_manifest(
        value['remaining_ready'], value['ready_count_before'] - 1,
        'remaining ready',
    )
    delivered_names = validate_compact_manifest(
        value['delivered_before'], value['delivered_count_before'],
        'delivered before',
    )
    if (
        selected['filename'] in remaining_names
        or selected['filename'] in delivered_names
        or remaining_names & delivered_names
    ):
        raise EvidenceError('first-live private inventories overlap')
    timestamp = value.get('prepared_at')
    try:
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except (AttributeError, ValueError) as exc:
        raise EvidenceError('first-live evidence timestamp differs') from exc
    if parsed.tzinfo is None:
        raise EvidenceError('first-live evidence timestamp lacks timezone')
    return value, raw.encode('utf-8')


def prepare(root, output, sender, runtime_uid, runtime_gid, evidence_uid, evidence_gid):
    ready = Path(root) / 'ready'
    delivered = Path(root) / 'delivered'
    for path, label in ((root, 'outbox root'), (ready, 'ready directory'), (delivered, 'delivered directory')):
        validate_directory(path, runtime_uid, runtime_gid, 0o700, label)
    descriptor = acquire_lock(root, runtime_uid, runtime_gid)
    try:
        ready_entries, delivered_entries = inventory_as_runtime(
            sender, ready, delivered, runtime_uid, runtime_gid
        )
        if set(ready_entries) & set(delivered_entries):
            raise EvidenceError('result outbox state is duplicated')
        if not ready_entries:
            raise EvidenceError('result outbox has no ready file')
        selected_name = min(
            ready_entries,
            key=lambda name: (ready_entries[name]['_timestamp'], name),
        )
        selected = ready_entries[selected_name]
        remaining = dict(ready_entries)
        del remaining[selected_name]
        expected_delivered = dict(delivered_entries)
        expected_delivered[selected_name] = selected
        evidence = {
            'delivered_count_before': len(delivered_entries),
            'delivered_before': [
                compact_entry(delivered_entries[name])
                for name in sorted(delivered_entries)
            ],
            'expected_delivered_digest': inventory_digest(expected_delivered),
            'phase': 'prepared',
            'prepared_at': now_utc(),
            'ready_count_before': len(ready_entries),
            'remaining_ready': [
                compact_entry(remaining[name]) for name in sorted(remaining)
            ],
            'remaining_ready_digest': inventory_digest(remaining),
            'schema': SCHEMA,
            'schema_version': SCHEMA_VERSION,
            'selected': public_entry(selected),
        }
        write_new_private(output, evidence, evidence_uid, evidence_gid)
        return evidence
    finally:
        os.close(descriptor)


def finalize(root, prepared_path, output, sender, runtime_uid, runtime_gid, evidence_uid, evidence_gid):
    prepared, prepared_bytes = read_evidence(
        prepared_path, evidence_uid, evidence_gid, 'prepared'
    )
    ready = Path(root) / 'ready'
    delivered = Path(root) / 'delivered'
    descriptor = acquire_lock(root, runtime_uid, runtime_gid)
    try:
        ready_entries, delivered_entries = inventory_as_runtime(
            sender, ready, delivered, runtime_uid, runtime_gid
        )
        if set(ready_entries) & set(delivered_entries):
            raise EvidenceError('result outbox state is duplicated')
        selected = prepared['selected']
        name = selected['filename']
        if name in ready_entries or public_entry(delivered_entries.get(name, {})) != selected:
            raise EvidenceError('prepared file did not move unchanged to delivered')
        baseline_ready = {
            entry['filename']: entry for entry in prepared['remaining_ready']
        }
        baseline_delivered = {
            entry['filename']: entry for entry in prepared['delivered_before']
        }
        current_ready = {
            name: compact_entry(entry) for name, entry in ready_entries.items()
        }
        current_delivered = {
            name: compact_entry(entry) for name, entry in delivered_entries.items()
        }
        if any(current_ready.get(name) != entry for name, entry in baseline_ready.items()):
            raise EvidenceError('baseline ready inventory changed')
        expected_delivered = dict(baseline_delivered)
        expected_delivered[name] = compact_entry(delivered_entries[name])
        if current_delivered != expected_delivered:
            raise EvidenceError('delivered inventory changed outside selected transition')
        new_ready = set(current_ready) - set(baseline_ready)
        if name in new_ready:
            raise EvidenceError('selected identity reappeared in ready')
        if len(delivered_entries) != prepared['delivered_count_before'] + 1:
            raise EvidenceError('delivered count transition differs')
        if inventory_digest(delivered_entries) != prepared['expected_delivered_digest']:
            raise EvidenceError('delivered inventory changed outside selected transition')
        evidence = {
            'delivered_count_after': len(delivered_entries),
            'finalized_at': now_utc(),
            'phase': 'finalized',
            'prepared_sha256': sha256_bytes(prepared_bytes),
            'ready_count_after': len(ready_entries),
            'new_ready_count': len(new_ready),
            'schema': SCHEMA,
            'schema_version': SCHEMA_VERSION,
            'selected': selected,
        }
        write_new_private(output, evidence, evidence_uid, evidence_gid)
        return evidence
    finally:
        os.close(descriptor)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Capture private GX10 first-live result-delivery evidence'
    )
    subparsers = parser.add_subparsers(dest='mode', required=True)
    prepare_parser = subparsers.add_parser('prepare')
    prepare_parser.add_argument('--output', type=Path, required=True)
    finalize_parser = subparsers.add_parser('finalize')
    finalize_parser.add_argument('--prepared', type=Path, required=True)
    finalize_parser.add_argument('--output', type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if os.geteuid() != 0:
            raise EvidenceError('run first-live evidence capture as root')
        runtime = pwd.getpwnam(RUNTIME_USER)
        verify_configured_boundary()
        sender = load_sender(
            INSTALLED_SENDER,
            REPOSITORY_SENDER,
            runtime.pw_uid,
            runtime.pw_gid,
        )
        if args.mode == 'prepare':
            evidence = prepare(
                OUTBOX_ROOT, args.output, sender,
                runtime.pw_uid, runtime.pw_gid, 0, 0,
            )
            print(
                'FIRST_LIVE_EVIDENCE_PREPARED schema=1 '
                f'ready={evidence["ready_count_before"]} '
                f'delivered={evidence["delivered_count_before"]} '
                f'records={evidence["selected"]["record_count"]}'
            )
            print('GX10_FIRST_LIVE_EVIDENCE_PREPARE=PASS')
        else:
            evidence = finalize(
                OUTBOX_ROOT, args.prepared, args.output, sender,
                runtime.pw_uid, runtime.pw_gid, 0, 0,
            )
            print(
                'FIRST_LIVE_EVIDENCE_FINALIZED schema=1 '
                f'ready={evidence["ready_count_after"]} '
                f'delivered={evidence["delivered_count_after"]} '
                f'records={evidence["selected"]["record_count"]}'
            )
            print('GX10_FIRST_LIVE_EVIDENCE_FINALIZE=PASS')
        return 0
    except EvidenceError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('GX10_FIRST_LIVE_EVIDENCE=FAIL', file=sys.stderr)
        return 1
    except (OSError, KeyError, ValueError):
        print('ERROR: private first-live evidence operation failed', file=sys.stderr)
        print('GX10_FIRST_LIVE_EVIDENCE=FAIL', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
