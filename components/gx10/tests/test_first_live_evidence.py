#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


GX10_DIR = Path(__file__).resolve().parents[1]
HELPER_PATH = GX10_DIR / 'install/capture-first-live-evidence.py'
SENDER_PATH = GX10_DIR / 'sbin/send-result-outbox.py'


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


HELPER = load_module('first_live_evidence_test', HELPER_PATH)
SENDER = load_module('first_live_evidence_sender_test', SENDER_PATH)


def canonical_json(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def ai_record(run_id, timestamp='2026-08-24T08:10:00Z'):
    return {
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
        'run_id': run_id,
        'severity': 'medium',
        'status': 'action_required',
        'tags': ['synthetic'],
        'timestamp': timestamp,
        'title': 'Synthetic result',
        'type': 'incident_assessment',
    }


def incident_record(identity, timestamp):
    return {
        'body': 'Synthetic lifecycle state.',
        'device': 'router.example.invalid',
        'engine_version': 1,
        'entity_name': 'Ethernet1',
        'entity_type': 'interface',
        'event_family': 'ethport',
        'first_seen': '2026-08-24T08:00:00Z',
        'incident_id': identity,
        'interface_flap': True,
        'last_observation_state': 'down',
        'last_seen': timestamp,
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
        'snapshot_id': 'state-v2-' + hashlib.sha256(identity.encode()).hexdigest()[:32],
        'snapshot_version': 1787559000000,
        'state_change_count': 2,
        'timestamp': timestamp,
        'title': 'ethport: Ethernet1',
        'type': 'incident_lifecycle',
    }


class FirstLiveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.root = base / 'outbox'
        self.ready = self.root / 'ready'
        self.delivered = self.root / 'delivered'
        self.private = base / 'private'
        for directory in (self.root, self.ready, self.delivered, self.private):
            directory.mkdir(mode=0o700)
            directory.chmod(0o700)
        self.lock = self.root / '.result-outbox.lock'
        self.lock.write_bytes(b'')
        self.lock.chmod(0o600)
        self.uid = os.geteuid()
        self.gid = os.getegid()

    def add_ai(self, run_id, timestamp='2026-08-24T08:10:00Z'):
        data = (canonical_json(ai_record(run_id, timestamp)) + '\n').encode()
        path = self.ready / SENDER.output_name(run_id)
        path.write_bytes(data)
        path.chmod(0o640)
        return path

    def add_incidents(self):
        records = [
            incident_record('inc-v1-a', '2026-08-24T08:08:00Z'),
            incident_record('inc-v1-b', '2026-08-24T08:09:00Z'),
        ]
        data = ''.join(canonical_json(row) + '\n' for row in records).encode()
        path = self.ready / SENDER.incident_output_name(data)
        path.write_bytes(data)
        path.chmod(0o640)
        return path

    def prepare(self):
        output = self.private / 'prepared.json'
        evidence = HELPER.prepare(
            self.root, output, SENDER,
            self.uid, self.gid, self.uid, self.gid,
        )
        return output, evidence

    def finalize(self, prepared):
        output = self.private / 'finalized.json'
        evidence = HELPER.finalize(
            self.root, prepared, output, SENDER,
            self.uid, self.gid, self.uid, self.gid,
        )
        return output, evidence

    def test_ai_prepare_and_finalize_bind_exact_transition(self):
        selected = self.add_ai('run-v1-a')
        self.add_ai('run-v1-b', '2026-08-24T08:11:00Z')
        prepared_path, prepared = self.prepare()
        self.assertEqual(prepared['selected']['filename'], selected.name)
        self.assertEqual(prepared['selected']['route'], 'ai_updates')
        selected.rename(self.delivered / selected.name)
        finalized_path, finalized = self.finalize(prepared_path)
        self.assertTrue(finalized_path.is_file())
        self.assertEqual(finalized['selected'], prepared['selected'])
        self.assertEqual(finalized['ready_count_after'], 1)

    def test_lifecycle_batch_retains_all_line_digests(self):
        selected = self.add_incidents()
        prepared_path, prepared = self.prepare()
        self.assertEqual(prepared['selected']['route'], 'incident_updates')
        self.assertEqual(prepared['selected']['record_count'], 2)
        self.assertEqual(len(prepared['selected']['line_sha256']), 2)
        selected.rename(self.delivered / selected.name)
        _, finalized = self.finalize(prepared_path)
        self.assertEqual(finalized['selected']['record_count'], 2)

    def test_finalize_rejects_an_extra_transition(self):
        first = self.add_ai('run-v1-a')
        second = self.add_ai('run-v1-b', '2026-08-24T08:11:00Z')
        prepared_path, _ = self.prepare()
        first.rename(self.delivered / first.name)
        second.rename(self.delivered / second.name)
        with self.assertRaisesRegex(HELPER.EvidenceError, 'baseline ready inventory'):
            self.finalize(prepared_path)

    def test_finalize_allows_new_ready_work_without_weakening_delivery_proof(self):
        selected = self.add_ai('run-v1-a')
        self.add_ai('run-v1-b', '2026-08-24T08:11:00Z')
        prepared_path, _ = self.prepare()
        selected.rename(self.delivered / selected.name)
        self.add_ai('run-v1-c', '2026-08-24T08:12:00Z')
        _, finalized = self.finalize(prepared_path)
        self.assertEqual(finalized['new_ready_count'], 1)
        self.assertEqual(finalized['ready_count_after'], 2)

    def test_finalize_rejects_ready_delivered_identity_overlap(self):
        selected = self.add_ai('run-v1-a')
        remaining = self.add_ai('run-v1-b', '2026-08-24T08:11:00Z')
        prepared_path, _ = self.prepare()
        selected.rename(self.delivered / selected.name)
        duplicate = self.delivered / remaining.name
        duplicate.write_bytes(remaining.read_bytes())
        duplicate.chmod(0o640)
        with self.assertRaisesRegex(HELPER.EvidenceError, 'duplicated'):
            self.finalize(prepared_path)

    def test_private_evidence_size_is_rejected_before_creation(self):
        output = self.private / 'oversize.json'
        value = {'payload': 'x' * HELPER.EVIDENCE_MAX_BYTES}
        with self.assertRaisesRegex(HELPER.EvidenceError, 'exceeds'):
            HELPER.write_new_private(output, value, self.uid, self.gid)
        self.assertFalse(output.exists())

    def test_unexpected_error_does_not_echo_private_path(self):
        marker = 'private-path-marker-should-not-appear'
        arguments = SimpleNamespace(mode='prepare', output=Path('/') / marker)
        runtime = SimpleNamespace(pw_uid=self.uid, pw_gid=self.gid)
        stderr = io.StringIO()
        with (
            mock.patch.object(HELPER, 'parse_args', return_value=arguments),
            mock.patch.object(HELPER.os, 'geteuid', return_value=0),
            mock.patch.object(HELPER.pwd, 'getpwnam', return_value=runtime),
            mock.patch.object(HELPER, 'verify_configured_boundary'),
            mock.patch.object(HELPER, 'load_sender', return_value=SENDER),
            mock.patch.object(HELPER, 'prepare', side_effect=OSError(marker)),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(HELPER.main(), 1)
        self.assertNotIn(marker, stderr.getvalue())
        self.assertIn('GX10_FIRST_LIVE_EVIDENCE=FAIL', stderr.getvalue())

    def test_runtime_privileges_are_restored_after_inventory_failure(self):
        with (
            mock.patch.object(HELPER.os, 'geteuid', return_value=0),
            mock.patch.object(HELPER.os, 'getegid', return_value=41),
            mock.patch.object(HELPER.os, 'getgroups', return_value=[41, 42]),
            mock.patch.object(HELPER.os, 'setgroups') as setgroups,
            mock.patch.object(HELPER.os, 'setegid') as setegid,
            mock.patch.object(HELPER.os, 'seteuid') as seteuid,
            mock.patch.object(
                HELPER, 'inventory', side_effect=OSError('synthetic failure')
            ),
            self.assertRaises(OSError),
        ):
            HELPER.inventory_as_runtime(
                SENDER, self.ready, self.delivered, 1001, 1002
            )
        self.assertEqual(setgroups.call_args_list, [mock.call([1002]), mock.call([41, 42])])
        self.assertEqual(setegid.call_args_list, [mock.call(1002), mock.call(41)])
        self.assertEqual(seteuid.call_args_list, [mock.call(1001), mock.call(0)])

    def test_prepare_refuses_existing_output_and_hardlinked_entry(self):
        selected = self.add_ai('run-v1-a')
        os.link(selected, self.private / 'extra-link')
        with self.assertRaises(HELPER.SenderError if hasattr(HELPER, 'SenderError') else ValueError):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
