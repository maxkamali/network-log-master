#!/usr/bin/env python3
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = GX10_DIR / 'sbin' / 'run-correlation.py'
PROJECTION_PATH = GX10_DIR / 'sbin' / 'enrich-events.py'
INCIDENT_PATH = GX10_DIR / 'sbin' / 'incident-engine.py'
BASE_SCHEMA = GX10_DIR / 'sql' / 'initialize.sql'
INCIDENT_SCHEMA = GX10_DIR / 'sql' / 'incident-v1.sql'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runner(database):
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        spec = importlib.util.spec_from_file_location(
            'gx10_managed_correlation_test',
            RUNNER_PATH,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules['runtime_config']
        else:
            sys.modules['runtime_config'] = previous


def iso(epoch_ms):
    return datetime.fromtimestamp(
        epoch_ms / 1000,
        tz=timezone.utc,
    ).isoformat()


class ManagedCorrelationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / 'events.sqlite3'
        self.lock = self.root / 'managed-correlation.lock'
        connection = sqlite3.connect(self.database)
        connection.executescript(BASE_SCHEMA.read_text())
        connection.executescript(INCIDENT_SCHEMA.read_text())
        connection.execute(
            """
            INSERT INTO source_files (remote_path, status, discovered_at)
            VALUES (?, 'processed', ?)
            """,
            ('/spool/2026/08/24/06/syslog-20260824-0612.jsonl.zst', iso(1)),
        )
        connection.commit()
        connection.close()
        self.runner = load_runner(self.database)

    def normalized_event(self, epoch_ms, state='down'):
        return {
            'schema_version': 1,
            'timestamp': iso(epoch_ms),
            'ingest_timestamp': iso(epoch_ms + 1),
            'device_timestamp': None,
            'hostname': 'router-a.example.invalid',
            'source_ip': '192.0.2.10',
            'source_port': 514,
            'facility': 'local7',
            'severity': 'warning',
            'appname': 'syslog',
            'message': 'synthetic normalized observation',
            'raw_message': 'synthetic normalized observation',
            'parse_status': 'parsed',
            'vendor': 'arista',
            'os_family': 'eos',
            'event_code': 'BGP-5-ADJCHANGE',
            'event_family': 'bgp',
            'protocol': 'bgp',
            'signal_type': (
                'recovery' if state == 'established' else 'state_transition'
            ),
            'entity_type': 'bgp_peer',
            'entity_key': 'BGP|router-a.example.invalid|default|192.0.2.20',
            'state': state,
            'repeat_count': 1,
            'attention_eligible': True,
            'suppression_rule_id': None,
            'attributes': {'normalization_path': 'parser'},
        }

    def add_event(self, epoch_ms, state='down'):
        event = self.normalized_event(epoch_ms, state)
        connection = sqlite3.connect(self.database)
        record_number = connection.execute(
            'SELECT COUNT(*) + 1 FROM recent_events'
        ).fetchone()[0]
        cursor = connection.execute(
            """
            INSERT INTO recent_events (
                source_file,
                record_number,
                timestamp,
                timestamp_epoch_ms,
                severity,
                message,
                event_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                '/spool/2026/08/24/06/syslog-20260824-0612.jsonl.zst',
                record_number,
                event['timestamp'],
                epoch_ms,
                event['severity'],
                event['message'],
                json.dumps(event, separators=(',', ':'), sort_keys=True),
            ),
        )
        connection.commit()
        connection.close()
        return cursor.lastrowid

    def run_runner(self, projection=PROJECTION_PATH, incident=INCIDENT_PATH):
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(
            io.StringIO()
        ) as stderr:
            result = self.runner.main(
                self.database,
                projection,
                incident,
                self.lock,
            )
        return result, stdout.getvalue(), stderr.getvalue()

    def engine_rows(self):
        connection = sqlite3.connect(self.database)
        result = tuple(
            tuple(connection.execute(f'SELECT * FROM {table} ORDER BY rowid'))
            for table in (
                'event_enrichment',
                'incidents',
                'incident_evidence',
                'incident_transitions',
                'agent_state',
            )
        )
        connection.close()
        return result

    def test_projection_precedes_incident_and_repeat_is_noop(self):
        event_id = self.add_event(1787551200000)
        result, output, error = self.run_runner()
        self.assertEqual(result, 0, error)
        self.assertIn('GX10_NORMALIZED_PROJECTION=PASS', output)
        self.assertIn('GX10_INCIDENT_ENGINE=PASS', output)
        self.assertIn('GX10_MANAGED_CORRELATION=PASS', output)
        connection = sqlite3.connect(self.database)
        self.assertEqual(
            connection.execute(
                'SELECT classification_version FROM event_enrichment '
                'WHERE event_id = ?',
                (event_id,),
            ).fetchone(),
            (4,),
        )
        self.assertEqual(
            connection.execute('SELECT status FROM incidents').fetchone(),
            ('OPEN',),
        )
        connection.close()
        snapshot = self.engine_rows()
        result, output, error = self.run_runner()
        self.assertEqual(result, 0, error)
        self.assertIn('scanned=0', output)
        self.assertEqual(self.engine_rows(), snapshot)

    def test_new_input_advances_both_watermarks(self):
        self.add_event(1787551200000)
        self.assertEqual(self.run_runner()[0], 0)
        second = self.add_event(1787551260000, state='established')
        self.assertEqual(self.run_runner()[0], 0)
        connection = sqlite3.connect(self.database)
        cursors = dict(
            connection.execute(
                'SELECT key, value FROM agent_state WHERE key IN (?, ?)',
                (self.runner.PROJECTION_CURSOR, self.runner.INCIDENT_CURSOR),
            )
        )
        connection.close()
        self.assertEqual(set(map(int, cursors.values())), {second})

    def test_projection_failure_prevents_incident_stage(self):
        projection = self.root / 'projection.py'
        incident = self.root / 'incident.py'
        marker = self.root / 'incident-ran'
        projection.write_text(
            '#!/usr/bin/env python3\ndef main(database):\n    return 1\n'
        )
        incident.write_text(
            '#!/usr/bin/env python3\n'
            'from pathlib import Path\n'
            f'MARKER = Path({str(marker)!r})\n'
            'def main(database):\n    MARKER.write_text("ran")\n    return 0\n'
        )
        projection.chmod(0o755)
        incident.chmod(0o755)
        self.runner.PROJECTION_SHA256 = digest(projection)
        self.runner.INCIDENT_SHA256 = digest(incident)
        result, _, error = self.run_runner(projection, incident)
        self.assertEqual(result, 1)
        self.assertIn('canonical projection stage failed', error)
        self.assertFalse(marker.exists())

    def test_lock_contention_fails_without_processing(self):
        self.add_event(1787551200000)
        descriptor = os.open(self.lock, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result, _, error = self.run_runner()
        self.assertEqual(result, 1)
        self.assertIn('already running', error)
        connection = sqlite3.connect(self.database)
        self.assertEqual(
            connection.execute(
                'SELECT COUNT(*) FROM event_enrichment'
            ).fetchone()[0],
            0,
        )
        connection.close()

    def test_private_database_config_is_strict_fallback_only(self):
        config = self.root / 'correlation.json'
        original = self.runner.load_runtime_config
        self.runner.load_runtime_config = None
        self.addCleanup(
            setattr,
            self.runner,
            'load_runtime_config',
            original,
        )
        config.write_text(
            json.dumps({'database_path': str(self.database)})
        )
        self.assertEqual(
            self.runner.load_database_path(config),
            self.database,
        )
        config.write_text(json.dumps({'database_path': 'relative.sqlite3'}))
        self.assertIsNone(self.runner.load_database_path(config))
        config.write_text(
            json.dumps(
                {
                    'database_path': str(self.database),
                    'unexpected': True,
                }
            )
        )
        self.assertIsNone(self.runner.load_database_path(config))


if __name__ == '__main__':
    unittest.main()
