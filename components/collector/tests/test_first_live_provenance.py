#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from datetime import datetime
from unittest import mock


COLLECTOR_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = COLLECTOR_DIR.parents[1]
HELPER_PATH = COLLECTOR_DIR / 'sbin/verify-first-live-provenance.py'
GX_HELPER_PATH = (
    REPOSITORY_ROOT / 'components/gx10/install/capture-first-live-evidence.py'
)
GX_SENDER_PATH = REPOSITORY_ROOT / 'components/gx10/sbin/send-result-outbox.py'


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


HELPER = load_module('first_live_provenance_test', HELPER_PATH)
GX_HELPER = load_module('cross_component_first_live_evidence_test', GX_HELPER_PATH)
GX_SENDER = load_module('cross_component_result_sender_test', GX_SENDER_PATH)


def canonical_json(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


class FakeClickHouse:
    def __init__(self, rows=None):
        self.observed = rows or {}

    def rows(self, table, digests):
        return list(self.observed.get(table, []))


class FirstLiveProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.ready = base / 'ready'
        self.incoming = base / 'incoming'
        self.private = base / 'private'
        for directory in (self.ready, self.incoming, self.private):
            directory.mkdir(mode=0o700)
            directory.chmod(0o700)
        self.ledger = self.ready / '.accepted-v1.sqlite3'
        self.uid = os.geteuid()
        self.gid = os.getegid()

    def record(self, identity='run-v1-a'):
        return {
            'body': 'Synthetic result summary.',
            'device': 'router.example.invalid',
            'incident_id': 'inc-v1-a',
            'run_id': identity,
            'timestamp': '2026-08-24T08:10:00Z',
            'title': 'Synthetic result',
            'type': 'incident_assessment',
        }

    def selected(self, records, route='ai_updates'):
        data = ''.join(canonical_json(record) + '\n' for record in records).encode()
        prefix = 'ai-result-v1' if route == 'ai_updates' else 'incident-state-v2'
        name = f'{prefix}-{hashlib.sha256(data).hexdigest()[:32]}.jsonl'
        return {
            'filename': name,
            'file_sha256': hashlib.sha256(data).hexdigest(),
            'line_sha256': [
                hashlib.sha256((canonical_json(record) + '\n').encode()).hexdigest()
                for record in records
            ],
            'record_count': len(records),
            'route': route,
            'size': len(data),
        }, data

    def create_ledger(self, selected=None):
        connection = sqlite3.connect(self.ledger)
        connection.executescript(
            """
            CREATE TABLE accepted (
                filename TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                size INTEGER NOT NULL,
                record_count INTEGER NOT NULL,
                accepted_at TEXT NOT NULL
            ) WITHOUT ROWID;
            CREATE TRIGGER accepted_no_update
            BEFORE UPDATE ON accepted
            BEGIN
                SELECT RAISE(ABORT, 'accepted rows are immutable');
            END;
            CREATE TRIGGER accepted_no_delete
            BEFORE DELETE ON accepted
            BEGIN
                SELECT RAISE(ABORT, 'accepted rows are immutable');
            END;
            PRAGMA user_version = 1;
            """
        )
        if selected is not None:
            connection.execute(
                'INSERT INTO accepted VALUES (?, ?, ?, ?, ?)',
                (
                    selected['filename'], selected['file_sha256'],
                    selected['size'], selected['record_count'],
                    '2026-08-24T08:15:00Z',
                ),
            )
        connection.commit()
        connection.close()
        self.ledger.chmod(0o640)

    def create_ready(self, selected, data):
        path = self.ready / selected['filename']
        path.write_bytes(data)
        path.chmod(0o640)
        return path

    def test_final_ai_proves_ledger_ready_rows_and_projection(self):
        record = self.record()
        selected, data = self.selected([record])
        self.create_ledger(selected)
        self.create_ready(selected, data)
        clickhouse = FakeClickHouse({
            'ai_updates': [{
                'raw_json': canonical_json(record),
                'timestamp_ms': int(datetime.fromisoformat(
                    record['timestamp'].replace('Z', '+00:00')
                ).timestamp() * 1000),
                'run_id': record['run_id'],
                'incident_id': record['incident_id'],
                'device': record['device'],
                'model': '',
                'type': record['type'],
                'status': '',
                'severity': '',
                'first_seen_ms': -1,
                'last_seen_ms': -1,
                'occurrence_count': 0,
                'title': record['title'],
                'body': record['body'],
                'tags': [],
            }],
        })
        HELPER.final_once(
            {}, {'selected': selected}, self.ledger, self.ready,
            self.incoming, self.uid, self.gid, clickhouse,
        )

    def test_final_lifecycle_requires_complete_multiset(self):
        records = []
        for index in range(2):
            records.append({
                'body': 'Synthetic lifecycle state.',
                'device': 'router.example.invalid',
                'engine_version': 1,
                'entity_name': 'Ethernet1',
                'entity_type': 'interface',
                'event_family': 'ethport',
                'first_seen': '2026-08-24T08:00:00Z',
                'incident_id': f'inc-v1-{index}',
                'interface_flap': True,
                'last_observation_state': 'down',
                'last_seen': '2026-08-24T08:10:00Z',
                'lifecycle_status': 'OPEN',
                'occurrence_count': 3,
                'opened_at': '2026-08-24T08:00:00Z',
                'producer_schema': 'network-log-incident-state',
                'producer_version': 2,
                'protocol': 'ethernet',
                'recovering_at': None,
                'recurrence_count': 1,
                'repeat_count_total': 3,
                'resolved_at': None,
                'severity': 'warning',
                'snapshot_id': f'state-v2-{index:032x}',
                'snapshot_version': index + 1,
                'state_change_count': 2,
                'timestamp': '2026-08-24T08:10:00Z',
                'title': 'ethport: Ethernet1',
                'type': 'incident_lifecycle',
            })
        selected, data = self.selected(records, 'incident_updates')
        self.create_ledger(selected)
        self.create_ready(selected, data)
        rows = []
        for record in records:
            timestamp_ms = int(datetime.fromisoformat(
                record['timestamp'].replace('Z', '+00:00')
            ).timestamp() * 1000)
            first_seen_ms = int(datetime.fromisoformat(
                record['first_seen'].replace('Z', '+00:00')
            ).timestamp() * 1000)
            rows.append({
                'raw_json': canonical_json(record),
                'timestamp_ms': timestamp_ms,
                'snapshot_id': record['snapshot_id'],
                'snapshot_version': record['snapshot_version'],
                'incident_id': record['incident_id'],
                'device': record['device'],
                'entity_type': record['entity_type'],
                'entity_name': record['entity_name'],
                'event_family': record['event_family'],
                'protocol': record['protocol'],
                'lifecycle_status': record['lifecycle_status'],
                'severity': record['severity'],
                'first_seen_ms': first_seen_ms,
                'last_seen_ms': timestamp_ms,
                'opened_at_ms': first_seen_ms,
                'recovering_at_ms': -1,
                'resolved_at_ms': -1,
                'occurrence_count': record['occurrence_count'],
                'recurrence_count': record['recurrence_count'],
                'repeat_count_total': record['repeat_count_total'],
                'state_change_count': record['state_change_count'],
                'last_observation_state': record['last_observation_state'],
                'interface_flap': record['interface_flap'],
                'engine_version': record['engine_version'],
                'title': record['title'],
                'body': record['body'],
                'type': record['type'],
                'producer_schema': record['producer_schema'],
                'producer_version': record['producer_version'],
            })
        HELPER.final_once(
            {}, {'selected': selected}, self.ledger, self.ready,
            self.incoming, self.uid, self.gid,
            FakeClickHouse({'incident_updates': rows}),
        )

    def test_duplicate_clickhouse_row_is_rejected(self):
        record = self.record()
        selected, data = self.selected([record])
        self.create_ledger(selected)
        self.create_ready(selected, data)
        row = dict(record, raw_json=canonical_json(record))
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'multiset'):
            HELPER.final_once(
                {}, {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid,
                FakeClickHouse({'ai_updates': [row, row]}),
            )

    def test_zero_and_wrong_route_clickhouse_rows_are_rejected(self):
        record = self.record()
        selected, data = self.selected([record])
        self.create_ledger(selected)
        self.create_ready(selected, data)
        with self.assertRaises(HELPER.NotReadyError):
            HELPER.final_once(
                {}, {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid, FakeClickHouse(),
            )
        wrong = {'raw_json': canonical_json(record)}
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'wrong ClickHouse route'):
            HELPER.final_once(
                {}, {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid,
                FakeClickHouse({'incident_updates': [wrong]}),
            )

    def test_divergent_raw_json_and_projection_are_rejected(self):
        record = self.record()
        selected, data = self.selected([record])
        self.create_ledger(selected)
        self.create_ready(selected, data)
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'multiset'):
            HELPER.final_once(
                {}, {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid,
                FakeClickHouse({'ai_updates': [{
                    'raw_json': canonical_json(dict(record, title='Divergent')),
                }]}),
            )
        row = {
            'raw_json': canonical_json(record),
            'timestamp_ms': HELPER.timestamp_to_milliseconds(record['timestamp']),
            'run_id': record['run_id'],
            'incident_id': record['incident_id'],
            'device': record['device'],
            'model': '',
            'type': record['type'],
            'status': '',
            'severity': '',
            'first_seen_ms': -1,
            'last_seen_ms': -1,
            'occurrence_count': 0,
            'title': 'Divergent projection',
            'body': record['body'],
            'tags': [],
        }
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'thin projection'):
            HELPER.final_once(
                {}, {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid,
                FakeClickHouse({'ai_updates': [row]}),
            )

    def test_ledger_and_ready_identity_mismatch_are_rejected(self):
        record = self.record()
        selected, data = self.selected([record])
        self.create_ledger(selected)
        self.create_ready(selected, data)
        altered = dict(selected, file_sha256='0' * 64)
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'ledger identity'):
            HELPER.final_once(
                {}, {'selected': altered}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid, FakeClickHouse(),
            )
        ready_path = self.ready / selected['filename']
        ready_path.write_bytes(data + b' ')
        ready_path.chmod(0o640)
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'ready file identity'):
            HELPER.final_once(
                {}, {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid, FakeClickHouse(),
            )

    def test_preflight_rejects_preaccepted_identity(self):
        selected, _ = self.selected([self.record()])
        self.create_ledger(selected)
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'already exists in ledger'):
            HELPER.preflight(
                {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid, FakeClickHouse(),
            )

    def test_private_credential_metadata_is_fail_closed(self):
        credential_file = self.private / 'reader-credential-metadata'
        generated_value = hashlib.sha256(
            str(credential_file).encode('utf-8')
        ).hexdigest()
        credential_file.write_text(generated_value + '\n', encoding='utf-8')
        credential_file.chmod(0o644)
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'metadata'):
            HELPER.validate_private_file(
                credential_file, self.uid, self.gid, {0o400, 0o600},
                'ClickHouse reader password', maximum=8192,
            )

    def test_preflight_rejects_dangling_ledger_and_incoming_symlinks(self):
        selected, _ = self.selected([self.record()])
        self.ledger.symlink_to(self.ready / 'missing-ledger')
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'symlink'):
            HELPER.preflight(
                {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid, FakeClickHouse(),
            )
        self.ledger.unlink()
        (self.incoming / selected['filename']).symlink_to(
            self.incoming / 'missing-input'
        )
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'incoming'):
            HELPER.preflight(
                {'selected': selected}, self.ledger, self.ready,
                self.incoming, self.uid, self.gid, FakeClickHouse(),
            )

    def test_clickhouse_query_uses_stdin_and_never_final(self):
        source = HELPER_PATH.read_text(encoding='utf-8')
        self.assertIn('input=query', source)
        self.assertIn('FORMAT JSONEachRow', source)
        self.assertNotIn(' FINAL ', source)
        self.assertNotIn('--pass' + 'word=', source)

    def test_cross_component_evidence_schema_and_concurrent_ready_binding(self):
        root = Path(self.temporary.name) / 'outbox'
        ready = root / 'ready'
        delivered = root / 'delivered'
        evidence = Path(self.temporary.name) / 'evidence'
        for directory in (root, ready, delivered, evidence):
            directory.mkdir(mode=0o700)
            directory.chmod(0o700)
        lock = root / '.result-outbox.lock'
        lock.write_bytes(b'')
        lock.chmod(0o600)

        record = {
            'body': 'Synthetic result summary.',
            'device': 'router.example.invalid',
            'first_seen': '2026-08-24T08:00:00Z',
            'incident_id': 'inc-v1-synthetic',
            'last_seen': '2026-08-24T08:05:00Z',
            'model': 'synthetic-model',
            'occurrence_count': 2,
            'producer_schema': 'network-log-ai-result',
            'producer_version': 1,
            'provenance': {'packet_id': 'pkt-v1-synthetic'},
            'result': {'schema': 'gx10-incident-assessment'},
            'run_id': 'run-v1-cross-component',
            'severity': 'medium',
            'status': 'action_required',
            'tags': ['synthetic'],
            'timestamp': '2026-08-24T08:10:00Z',
            'title': 'Synthetic result',
            'type': 'incident_assessment',
        }
        data = (canonical_json(record) + '\n').encode()
        selected_path = ready / GX_SENDER.output_name(record['run_id'])
        selected_path.write_bytes(data)
        selected_path.chmod(0o640)
        prepared_path = evidence / 'prepared.json'
        prepared = GX_HELPER.prepare(
            root, prepared_path, GX_SENDER,
            self.uid, self.gid, self.uid, self.gid,
        )
        selected_path.rename(delivered / selected_path.name)

        later = dict(record, run_id='run-v1-cross-component-later')
        later_data = (canonical_json(later) + '\n').encode()
        later_path = ready / GX_SENDER.output_name(later['run_id'])
        later_path.write_bytes(later_data)
        later_path.chmod(0o640)
        finalized_path = evidence / 'finalized.json'
        finalized = GX_HELPER.finalize(
            root, prepared_path, finalized_path, GX_SENDER,
            self.uid, self.gid, self.uid, self.gid,
        )

        loaded_prepared, prepared_bytes = HELPER.load_evidence(
            prepared_path, 'prepared', self.uid, self.gid
        )
        loaded_finalized, _ = HELPER.load_evidence(
            finalized_path, 'finalized', self.uid, self.gid
        )
        HELPER.validate_final_binding(
            loaded_prepared, prepared_bytes, loaded_finalized
        )
        self.assertEqual(loaded_prepared['selected'], prepared['selected'])
        self.assertEqual(loaded_finalized['selected'], finalized['selected'])
        self.assertEqual(loaded_finalized['new_ready_count'], 1)

    def test_evidence_manifest_rejects_duplicate_filename(self):
        selected, _ = self.selected([self.record()])
        compact = {
            key: selected[key]
            for key in ('filename', 'file_sha256', 'record_count', 'route', 'size')
        }
        with self.assertRaisesRegex(HELPER.ProvenanceError, 'values'):
            HELPER.validate_compact_manifest([compact, compact], 2, 'synthetic')

    def test_clickhouse_temp_config_is_cleaned_if_enter_fails(self):
        credential_file = self.private / 'reader-credential'
        generated_value = hashlib.sha256(
            str(credential_file).encode('utf-8')
        ).hexdigest()
        credential_file.write_text(generated_value + '\n', encoding='utf-8')
        credential_file.chmod(0o600)
        real_temporary = tempfile.TemporaryDirectory
        observed = {}

        def tracking_temporary(*args, **kwargs):
            value = real_temporary(*args, **kwargs)
            observed['path'] = Path(value.name)
            return value

        reader = HELPER.ClickHouseDigestReader(credential_file, Path('/bin/sh'))
        with (
            mock.patch.object(HELPER, 'validate_private_file'),
            mock.patch.object(
                HELPER.tempfile, 'TemporaryDirectory',
                side_effect=tracking_temporary,
            ),
            mock.patch.object(
                HELPER.os, 'fsync', side_effect=OSError('private-config-marker')
            ),
            self.assertRaises(OSError),
        ):
            reader.__enter__()
        self.assertFalse(observed['path'].exists())
        self.assertIsNone(reader.temporary)
        self.assertIsNone(reader.config)

    def test_fractional_timestamp_uses_integer_millisecond_truncation(self):
        self.assertEqual(
            HELPER.timestamp_to_milliseconds('1970-01-01T00:00:00.123999Z'),
            123,
        )
        self.assertEqual(
            HELPER.timestamp_to_milliseconds('1969-12-31T23:59:59.999999Z'),
            -1,
        )

    def test_unexpected_error_does_not_echo_private_path(self):
        marker = 'private-path-marker-should-not-appear'
        arguments = SimpleNamespace(
            mode='preflight', password_file=Path('/') / marker,
            prepared=Path('/') / 'prepared.json',
        )
        account = SimpleNamespace(pw_uid=self.uid)
        group = SimpleNamespace(gr_gid=self.gid)
        stderr = io.StringIO()
        with (
            mock.patch.object(HELPER, 'parse_args', return_value=arguments),
            mock.patch.object(HELPER.os, 'geteuid', return_value=0),
            mock.patch.object(HELPER.pwd, 'getpwnam', return_value=account),
            mock.patch.object(HELPER.grp, 'getgrnam', return_value=group),
            mock.patch.object(HELPER, 'load_evidence', side_effect=OSError(marker)),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(HELPER.main(), 1)
        self.assertNotIn(marker, stderr.getvalue())
        self.assertIn('COLLECTOR_FIRST_LIVE_PROVENANCE=FAIL', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
