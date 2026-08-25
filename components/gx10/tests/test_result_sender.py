#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
SENDER_PATH = GX10_DIR / 'sbin' / 'send-result-outbox.py'


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SENDER = load_module('result_sender_test', SENDER_PATH)


def canonical_json(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


class ResultSenderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'outbox'
        self.ready = self.root / 'ready'
        self.delivered = self.root / 'delivered'
        self.root.mkdir(mode=0o700)
        self.ready.mkdir(mode=0o700)
        self.delivered.mkdir(mode=0o700)
        self.identity = Path(self.temporary.name) / 'writer-identity'
        self.known_hosts = Path(self.temporary.name) / 'writer-hosts'
        self.identity.write_text('synthetic private input\n', encoding='utf-8')
        self.known_hosts.write_text('synthetic pinned host\n', encoding='utf-8')
        self.identity.chmod(0o600)
        self.known_hosts.chmod(0o600)
        self.transport_calls = []

    def record(
        self,
        run_id,
        timestamp='2026-08-24T08:10:00Z',
        *,
        include_device=True,
    ):
        value = {
            'body': 'Synthetic result summary.',
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
        if include_device:
            value['device'] = 'router.example.invalid'
        return value

    def add_ready(self, run_id, timestamp='2026-08-24T08:10:00Z'):
        name = SENDER.output_name(run_id)
        data = (
            canonical_json(self.record(run_id, timestamp)) + '\n'
        ).encode('utf-8')
        path = self.ready / name
        path.write_bytes(data)
        path.chmod(0o640)
        return path, data

    def incident_record(self, incident_id, timestamp, *, version=2):
        record = {
            'body': 'Deterministic incident lifecycle state.',
            'device': 'router.example.invalid',
            'engine_version': 1,
            'entity_name': 'Ethernet1',
            'entity_type': 'interface',
            'event_family': 'ethport',
            'first_seen': '2026-08-24T08:00:00Z',
            'incident_id': incident_id,
            'interface_flap': True,
            'last_observation_state': 'down',
            'last_seen': timestamp,
            'lifecycle_status': 'OPEN',
            'occurrence_count': 3,
            'opened_at': '2026-08-24T08:00:00Z',
            'producer_schema': 'network-log-incident-state',
            'producer_version': version,
            'protocol': 'ethernet',
            'recovering_at': None,
            'repeat_count_total': 3,
            'resolved_at': None,
            'severity': 'warning',
            'snapshot_id': f'state-v{version}-' + 'a' * 32,
            'snapshot_version': 1787559000000,
            'state_change_count': 2,
            'timestamp': timestamp,
            'title': 'ethport: Ethernet1',
            'type': 'incident_lifecycle',
        }
        if version == 2:
            record['recurrence_count'] = 1
        return record

    def add_incident_batch(self, *, version=2):
        records = [
            self.incident_record(
                'inc-v1-a', '2026-08-24T08:09:00Z', version=version
            ),
            self.incident_record(
                'inc-v1-b', '2026-08-24T08:10:00Z', version=version
            ),
        ]
        data = ''.join(canonical_json(row) + '\n' for row in records).encode()
        name = SENDER.incident_output_name(data)
        path = self.ready / name
        path.write_bytes(data)
        path.chmod(0o640)
        return path, data

    def transport(self, command, batch, timeout):
        self.transport_calls.append((command, batch, timeout))
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    def send(self, **overrides):
        arguments = {
            'ready': self.ready,
            'delivered': self.delivered,
            'host': 'collector.example.invalid',
            'port': 2222,
            'user': 'result-writer',
            'identity': self.identity,
            'known_hosts': self.known_hosts,
            'transport': self.transport,
        }
        arguments.update(overrides)
        return SENDER.send_one(**arguments)

    def test_success_uses_strict_batch_sftp_and_moves_exact_file(self):
        path, data = self.add_ready('run-v1-synthetic-1')

        result = self.send()

        self.assertEqual(result['attempted'], 1)
        self.assertEqual(result['sent'], 1)
        self.assertEqual(result['sent_bytes'], len(data))
        self.assertFalse(path.exists())
        delivered = self.delivered / path.name
        self.assertEqual(delivered.read_bytes(), data)
        command, batch, timeout = self.transport_calls[0]
        self.assertEqual(command[0], '/usr/bin/sftp')
        for option in (
            'BatchMode=yes',
            'IdentitiesOnly=yes',
            'PasswordAuthentication=no',
            'KbdInteractiveAuthentication=no',
            'StrictHostKeyChecking=yes',
            f'UserKnownHostsFile={self.known_hosts}',
            'GlobalKnownHostsFile=/dev/null',
            'ConnectTimeout=10',
            'ConnectionAttempts=1',
            'ServerAliveInterval=5',
            'ServerAliveCountMax=1',
        ):
            self.assertIn(option, command)
        self.assertEqual(batch, f'put {path.resolve()} {path.name}\n')
        self.assertEqual(timeout, 30)

    def test_legacy_record_without_device_remains_sendable(self):
        run_id = 'run-v1-synthetic-legacy'
        name = SENDER.output_name(run_id)
        data = (
            canonical_json(self.record(run_id, include_device=False)) + '\n'
        ).encode('utf-8')
        path = self.ready / name
        path.write_bytes(data)
        path.chmod(0o640)

        result = self.send()

        self.assertEqual(result['sent'], 1)
        self.assertEqual((self.delivered / name).read_bytes(), data)

    def test_canonical_incident_batch_is_sent_unchanged(self):
        path, data = self.add_incident_batch()

        state = self.send()

        self.assertEqual(state['sent'], 1)
        self.assertEqual((self.delivered / path.name).read_bytes(), data)

    def test_legacy_version_1_incident_batch_remains_sendable(self):
        path, data = self.add_incident_batch(version=1)

        state = self.send()

        self.assertEqual(state['sent'], 1)
        self.assertEqual((self.delivered / path.name).read_bytes(), data)

    def test_tampered_incident_batch_is_refused(self):
        path, _ = self.add_incident_batch()
        path.write_bytes(path.read_bytes().replace(b'warning', b'critical'))

        with self.assertRaisesRegex(SENDER.SenderError, 'filename differs'):
            self.send()
        self.assertEqual(self.transport_calls, [])

    def test_each_cycle_sends_exactly_one_file(self):
        paths = [self.add_ready(f'run-v1-synthetic-{value}')[0] for value in range(3)]

        first = self.send()

        self.assertEqual(first['ready'], 2)
        self.assertEqual(first['delivered'], 1)
        self.assertEqual(len(self.transport_calls), 1)
        remaining = {path.name for path in self.ready.iterdir()}
        self.assertEqual(len(remaining), 2)
        self.assertEqual(len(tuple(self.delivered.iterdir())), 1)

    def test_oldest_result_timestamp_is_sent_first(self):
        newer, _ = self.add_ready(
            'run-v1-synthetic-newer',
            '2026-08-24T08:11:00Z',
        )
        older, _ = self.add_ready(
            'run-v1-synthetic-older',
            '2026-08-24T08:09:00Z',
        )

        self.send()

        self.assertTrue(newer.exists())
        self.assertFalse(older.exists())
        self.assertTrue((self.delivered / older.name).exists())

    def test_transport_failure_preserves_ready_without_delivery(self):
        path, data = self.add_ready('run-v1-synthetic-failure')

        def failed_transport(command, batch, timeout):
            return types.SimpleNamespace(
                returncode=1,
                stdout='sensitive remote output',
                stderr='sensitive remote error',
            )

        with self.assertRaisesRegex(SENDER.SenderError, 'transport failed') as caught:
            self.send(transport=failed_transport)
        self.assertNotIn('sensitive', str(caught.exception))
        self.assertEqual(path.read_bytes(), data)
        self.assertEqual(tuple(self.delivered.iterdir()), ())

    def test_interruption_after_transport_retries_same_name_and_bytes(self):
        path, data = self.add_ready('run-v1-synthetic-interrupted')

        def interrupt():
            raise SENDER.SenderError('injected post-transport interruption')

        with self.assertRaisesRegex(SENDER.SenderError, 'injected'):
            self.send(after_transport=interrupt)
        self.assertEqual(path.read_bytes(), data)
        first_batch = self.transport_calls[0][1]

        result = self.send()

        self.assertEqual(result['sent'], 1)
        self.assertEqual(len(self.transport_calls), 2)
        self.assertEqual(self.transport_calls[1][1], first_batch)
        self.assertEqual((self.delivered / path.name).read_bytes(), data)

    def test_empty_ready_is_exact_noop(self):
        result = self.send()

        self.assertEqual(
            result,
            {
                'ready': 0,
                'delivered': 0,
                'attempted': 0,
                'sent': 0,
                'sent_bytes': 0,
            },
        )
        self.assertEqual(self.transport_calls, [])

    def test_duplicate_ready_and_delivered_state_fails_before_transport(self):
        path, data = self.add_ready('run-v1-synthetic-duplicate')
        duplicate = self.delivered / path.name
        duplicate.write_bytes(data)
        duplicate.chmod(0o640)

        with self.assertRaisesRegex(SENDER.SenderError, 'duplicated'):
            self.send()
        self.assertEqual(self.transport_calls, [])

    def test_divergent_filename_or_noncanonical_content_fails_before_transport(self):
        path, _ = self.add_ready('run-v1-synthetic-divergent')
        value = json.loads(path.read_text(encoding='utf-8'))
        value['run_id'] = 'different-run'
        path.write_text(canonical_json(value) + '\n', encoding='utf-8')
        path.chmod(0o640)

        with self.assertRaisesRegex(SENDER.SenderError, 'record differs'):
            self.send()
        self.assertEqual(self.transport_calls, [])

    def test_private_inputs_require_exact_metadata(self):
        self.add_ready('run-v1-synthetic-private')
        self.identity.chmod(0o640)

        with self.assertRaisesRegex(SENDER.SenderError, 'identity metadata'):
            self.send()
        self.assertEqual(self.transport_calls, [])

    def test_shared_outbox_lock_refuses_concurrent_sender(self):
        self.add_ready('run-v1-synthetic-lock')
        lock = self.root / SENDER.LOCK_NAME
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

        with self.assertRaisesRegex(SENDER.SenderError, 'already locked'):
            self.send()
        self.assertEqual(self.transport_calls, [])

    def test_delivered_inventory_is_validated_on_noop(self):
        path, data = self.add_ready('run-v1-synthetic-delivered')
        path.rename(self.delivered / path.name)
        (self.delivered / path.name).write_bytes(data + b'\n')

        with self.assertRaisesRegex(SENDER.SenderError, 'record count'):
            self.send()
        self.assertEqual(self.transport_calls, [])


if __name__ == '__main__':
    unittest.main()
