#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
GATE_PATH = ROOT / "components/collector/sbin/ai-results-gate"


def load_gate():
    loader = SourceFileLoader("ai_results_gate", str(GATE_PATH))
    spec = importlib.util.spec_from_loader("ai_results_gate", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


GATE = load_gate()


def record(title: str = "synthetic result") -> bytes:
    value = {
        "body": "Synthetic validation body.",
        "run_id": "run-synthetic-1",
        "timestamp": "2026-08-24T12:00:00Z",
        "title": title,
    }
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def incident_record() -> dict:
    return {
        "body": "Deterministic incident lifecycle state.",
        "device": "router.example.invalid",
        "engine_version": 1,
        "entity_name": "Ethernet1",
        "entity_type": "interface",
        "event_family": "ethport",
        "first_seen": "2026-08-24T08:00:00Z",
        "incident_id": "inc-v1-synthetic",
        "interface_flap": True,
        "last_observation_state": "down",
        "last_seen": "2026-08-24T08:05:00Z",
        "lifecycle_status": "OPEN",
        "occurrence_count": 3,
        "opened_at": "2026-08-24T08:00:00Z",
        "producer_schema": "network-log-incident-state",
        "producer_version": 1,
        "protocol": "ethernet",
        "recovering_at": None,
        "repeat_count_total": 3,
        "resolved_at": None,
        "severity": "warning",
        "snapshot_id": "state-v1-" + "a" * 32,
        "snapshot_version": 1787559000000,
        "state_change_count": 2,
        "timestamp": "2026-08-24T08:05:00Z",
        "title": "ethport: Ethernet1",
        "type": "incident_lifecycle",
    }


class AIResultsGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.incoming = self.root / "incoming"
        self.ready = self.root / "ready"
        self.rejected = self.root / "rejected"

        for path in (self.incoming, self.ready, self.rejected):
            path.mkdir(mode=0o750)

        self.patches = (
            mock.patch.object(GATE, "INCOMING", self.incoming),
            mock.patch.object(GATE, "READY", self.ready),
            mock.patch.object(GATE, "REJECTED", self.rejected),
            mock.patch.object(GATE, "SETTLE_SECONDS", 0),
        )

        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()

        self.temporary.cleanup()

    def write_incoming(self, name="result-v1-a.jsonl", payload=None):
        path = self.incoming / name
        path.write_bytes(record() if payload is None else payload)
        return path

    def ledger_rows(self):
        path = self.ready / GATE.LEDGER_NAME
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

        try:
            return connection.execute(
                "SELECT filename, sha256, size, record_count FROM accepted"
            ).fetchall()
        finally:
            connection.close()

    def test_first_acceptance_moves_file_and_records_durable_identity(self):
        source = self.write_incoming()
        expected = source.read_bytes()
        source_inode = source.stat().st_ino

        self.assertEqual(GATE.main(), 0)
        self.assertFalse(source.exists())
        self.assertEqual((self.ready / source.name).read_bytes(), expected)
        self.assertNotEqual((self.ready / source.name).stat().st_ino, source_inode)
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], source.name)
        self.assertEqual(rows[0][2:], (len(expected), 1))

    def test_device_projection_is_bounded_when_present(self):
        value = json.loads(record())
        value["device"] = "router.example.invalid"
        self.assertIsNone(GATE.validate_record(value))
        value["device"] = ""
        self.assertEqual(
            GATE.validate_record(value),
            "device must not be empty",
        )
        value["device"] = "x" * 257
        self.assertEqual(
            GATE.validate_record(value),
            "device exceeds 256 characters",
        )

    def test_incident_lifecycle_record_is_strict_and_bounded(self):
        value = incident_record()
        self.assertIsNone(GATE.validate_record(value))
        value["lifecycle_status"] = "CLOSED"
        self.assertEqual(
            GATE.validate_record(value),
            "incident lifecycle identity differs",
        )
        value = incident_record()
        value["unexpected"] = True
        self.assertEqual(
            GATE.validate_record(value),
            "incident lifecycle record keys differ",
        )

    def test_exact_replay_is_rejected_after_ready_file_is_removed(self):
        source = self.write_incoming()
        payload = source.read_bytes()
        self.assertEqual(GATE.main(), 0)
        (self.ready / source.name).unlink()
        self.write_incoming(source.name, payload)

        self.assertEqual(GATE.main(), 0)
        self.assertFalse((self.ready / source.name).exists())
        self.assertEqual(len(self.ledger_rows()), 1)
        reasons = tuple(self.rejected.glob("*.reason.txt"))
        self.assertEqual(len(reasons), 1)
        self.assertIn("exact filename/content already accepted", reasons[0].read_text())

    def test_divergent_replay_is_rejected_by_durable_identity(self):
        source = self.write_incoming()
        self.assertEqual(GATE.main(), 0)
        (self.ready / source.name).unlink()
        self.write_incoming(source.name, record("different valid result"))

        self.assertEqual(GATE.main(), 0)
        reasons = tuple(self.rejected.glob("*.reason.txt"))
        self.assertEqual(len(reasons), 1)
        self.assertIn("conflicts with durable acceptance", reasons[0].read_text())
        self.assertEqual(len(self.ledger_rows()), 1)

    def test_existing_ready_file_bootstraps_missing_ledger_row(self):
        path = self.ready / "result-v1-existing.jsonl"
        path.write_bytes(record())

        self.assertEqual(GATE.main(), 0)
        self.assertEqual(self.ledger_rows()[0][0], path.name)

    def test_crash_after_ready_publish_is_reconciled_on_next_cycle(self):
        source = self.write_incoming()

        with mock.patch.object(
            GATE,
            "record_acceptance",
            side_effect=GATE.GateError("injected ledger interruption"),
        ):
            self.assertEqual(GATE.main(), 1)

        self.assertFalse(source.exists())
        self.assertTrue((self.ready / source.name).exists())
        self.assertEqual(self.ledger_rows(), [])
        self.assertEqual(GATE.main(), 0)
        self.assertEqual(len(self.ledger_rows()), 1)

    def test_crash_between_link_and_unlink_is_reconciled(self):
        source = self.write_incoming()
        destination = self.ready / source.name
        partial = self.ready / f'.{source.name}.publish-123.jsonl'
        partial.write_bytes(source.read_bytes())
        partial.chmod(0o640)
        os.link(partial, destination)
        self.assertEqual(destination.stat().st_nlink, 2)

        self.assertEqual(GATE.main(), 0)
        self.assertFalse(source.exists())
        self.assertFalse(partial.exists())
        self.assertEqual(destination.stat().st_nlink, 1)
        self.assertEqual(len(self.ledger_rows()), 1)

    def test_malformed_input_is_rejected_without_acceptance(self):
        self.write_incoming(payload=b"not-json\n")

        self.assertEqual(GATE.main(), 0)
        self.assertEqual(self.ledger_rows(), [])
        self.assertEqual(len(tuple(self.rejected.glob("*.jsonl"))), 1)

    def test_accepted_rows_cannot_be_updated_or_deleted(self):
        source = self.write_incoming()
        self.assertEqual(GATE.main(), 0)
        path = self.ready / GATE.LEDGER_NAME
        connection = sqlite3.connect(path)

        try:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                connection.execute(
                    "UPDATE accepted SET size = size + 1 WHERE filename = ?",
                    (source.name,),
                )
            connection.rollback()
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                connection.execute(
                    "DELETE FROM accepted WHERE filename = ?",
                    (source.name,),
                )
        finally:
            connection.close()

    def test_ready_content_divergence_from_ledger_fails_service(self):
        source = self.write_incoming()
        self.assertEqual(GATE.main(), 0)
        (self.ready / source.name).write_bytes(record("tampered valid result"))

        self.assertEqual(GATE.main(), 1)
        self.assertEqual(len(self.ledger_rows()), 1)

    def test_exact_duplicate_while_ready_exists_is_quarantined(self):
        source = self.write_incoming()
        payload = source.read_bytes()
        self.assertEqual(GATE.main(), 0)
        self.write_incoming(source.name, payload)

        self.assertEqual(GATE.main(), 0)
        self.assertTrue((self.ready / source.name).exists())
        self.assertEqual(len(self.ledger_rows()), 1)
        self.assertEqual(len(tuple(self.rejected.glob("*.jsonl"))), 1)

    def test_ledger_mode_tamper_fails_before_input_processing(self):
        self.assertEqual(GATE.main(), 0)
        ledger = self.ready / GATE.LEDGER_NAME
        ledger.chmod(0o600)
        source = self.write_incoming()

        self.assertEqual(GATE.main(), 1)
        self.assertTrue(source.exists())


if __name__ == "__main__":
    unittest.main()
