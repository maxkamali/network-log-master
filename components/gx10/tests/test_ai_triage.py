#!/usr/bin/env python3
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
SCHEMAS = tuple(
    GX10_DIR / 'sql' / name
    for name in (
        'initialize.sql', 'incident-v1.sql', 'reasoning-v1.sql',
        'inference-v1.sql', 'triage-v1.sql',
    )
)
CONFIG = GX10_DIR / 'config' / 'triage-runtime-v1.json'
PROMPT = GX10_DIR / 'prompts' / 'uncovered-event-triage-v1.txt'
OUTPUT_SCHEMA = GX10_DIR / 'prompts' / 'uncovered-event-triage-output-v1.json'
INCIDENT_ENGINE = GX10_DIR / 'sbin' / 'incident-engine.py'


def iso(epoch_ms):
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()


def load_triage(database):
    fake_config = types.ModuleType('runtime_config')
    fake_config.load_runtime_config = lambda: types.SimpleNamespace(
        database_path=database,
    )
    previous = sys.modules.get('runtime_config')
    sys.modules['runtime_config'] = fake_config
    try:
        path = GX10_DIR / 'sbin' / 'triage-uncovered-events.py'
        specification = importlib.util.spec_from_file_location(
            'gx10_ai_triage_test', path
        )
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules['runtime_config']
        else:
            sys.modules['runtime_config'] = previous


class AiTriageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
        connection = sqlite3.connect(self.database)
        for schema in SCHEMAS:
            connection.executescript(schema.read_text(encoding='utf-8'))
        connection.execute(
            "INSERT INTO source_files(remote_path,status,discovered_at) "
            "VALUES('/spool/synthetic','processed','2026-08-26T00:00:00+00:00')"
        )
        connection.commit()
        connection.close()
        self.triage = load_triage(self.database)
        self.record_number = 0

    def add_event(
        self,
        epoch_ms,
        *,
        code='TAHUSD-SLOT1-4-BUFFER_THRESHOLD_EXCEEDED',
        message='Pool-group buffer 90 percent threshold is exceeded',
        severity='warning',
        attention=1,
        device='switch-a.example.invalid',
    ):
        self.record_number += 1
        connection = sqlite3.connect(self.database)
        event_json = json.dumps({'os_family': 'nx-os'}, sort_keys=True)
        event_id = connection.execute(
            '''
            INSERT INTO recent_events(
                source_file,record_number,timestamp,timestamp_epoch_ms,
                severity,message,event_json
            ) VALUES('/spool/synthetic',?,?,?,?,?,?)
            ''',
            (
                self.record_number, iso(epoch_ms), epoch_ms, severity,
                message, event_json,
            ),
        ).lastrowid
        connection.execute(
            '''
            INSERT INTO event_enrichment(
                event_id,event_code,family,device,entity_type,entity_key,state,
                attention_eligible,classified_at,repeat_count,
                classification_version,vendor_hint,protocol,signal_type,
                attributes_json
            ) VALUES(?,?, 'unknown', ?,NULL,NULL,NULL,?,?,1,4,'cisco','','observation','{}')
            ''',
            (event_id, code, device, attention, iso(epoch_ms)),
        )
        connection.execute(
            '''
            INSERT INTO agent_state(key,value,updated_at)
            VALUES('incident_engine_v1_last_event_id',?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at
            ''',
            (str(event_id), iso(epoch_ms)),
        )
        connection.commit()
        connection.close()
        return event_id

    def run_triage(self, transport, now_value, *, mode='active', learned=False):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.triage.run(
                self.database,
                config_path=CONFIG,
                prompt_path=PROMPT,
                output_schema_path=OUTPUT_SCHEMA,
                incident_engine_path=INCIDENT_ENGINE,
                transport=transport,
                now=lambda: now_value,
                mode=mode,
                learned_coverage=learned,
            )

    def response(self, request_json, decision='incident'):
        request = json.loads(request_json)
        packet = json.loads(request['messages'][1]['content'])['packet']
        decisions = []
        for signature in sorted(packet['signatures'], key=lambda item: item['signature_id']):
            decisions.append(
                {
                    'signature_id': signature['signature_id'],
                    'decision': decision,
                    'confidence': 88,
                    'category': 'capacity',
                    'title': 'ASIC buffer pressure detected',
                    'summary': 'The switch reported sustained ASIC buffer pressure.',
                    'reason': 'A hardware buffer threshold was exceeded.',
                }
            )
        result = {
            'schema': 'gx10-uncovered-event-triage',
            'schema_version': 1,
            'batch_id': packet['batch_id'],
            'decisions': decisions,
        }
        return json.dumps(
            {
                'model': self.triage.MODEL_REFERENCE,
                'done': True,
                'message': {'role': 'assistant', 'content': json.dumps(result)},
            }
        ).encode()

    def scalar(self, statement, parameters=()):
        connection = sqlite3.connect(self.database)
        try:
            return connection.execute(statement, parameters).fetchone()[0]
        finally:
            connection.close()

    def test_positive_decision_becomes_open_ordinary_incident(self):
        self.add_event(1787716800000)
        result = self.run_triage(self.response, '2026-08-26T04:05:00+00:00')
        self.assertEqual(result['result'], 'pass')
        self.assertEqual(result['applied_incidents'], 1)
        connection = sqlite3.connect(self.database)
        row = connection.execute(
            '''
            SELECT i.status,i.entity_type,s.title,s.summary,o.source_type
            FROM incidents i
            JOIN triage_incident_summaries s ON s.incident_id=i.incident_id
            JOIN incident_evidence e ON e.incident_id=i.incident_id
            JOIN event_detection_overrides o ON o.event_id=e.event_id
            '''
        ).fetchone()
        connection.close()
        self.assertEqual(
            row,
            (
                'OPEN', 'event_signature', 'ASIC buffer pressure detected',
                'The switch reported sustained ASIC buffer pressure.',
                'ai_decision',
            ),
        )

    def test_unavailable_model_waits_without_incident_or_cursor_advance(self):
        self.add_event(1787716800000)

        def unavailable(_request):
            raise self.triage.InferenceFailure('INFERENCE_UNAVAILABLE')

        result = self.run_triage(unavailable, '2026-08-26T04:05:00+00:00')
        self.assertEqual(result['result'], 'waiting')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM incidents'), 0)
        self.assertEqual(
            self.scalar(
                "SELECT value FROM agent_state WHERE key='ai_triage_v1_last_event_id'"
            ) if self.scalar(
                "SELECT COUNT(*) FROM agent_state WHERE key='ai_triage_v1_last_event_id'"
            ) else '0',
            '0',
        )
        self.assertEqual(
            self.scalar("SELECT status FROM triage_runs"),
            'INFERENCE_UNAVAILABLE',
        )

    def test_ignore_advances_and_does_not_create_incident(self):
        event_id = self.add_event(1787716800000)
        result = self.run_triage(
            lambda request: self.response(request, decision='ignore'),
            '2026-08-26T04:05:00+00:00',
        )
        self.assertEqual(result['result'], 'pass')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM incidents'), 0)
        self.assertEqual(
            self.scalar(
                "SELECT value FROM agent_state WHERE key='ai_triage_v1_last_event_id'"
            ),
            str(event_id),
        )

    def test_learned_rule_bypasses_model_for_future_error(self):
        connection = sqlite3.connect(self.database)
        connection.execute(
            '''
            INSERT INTO learned_detection_rules(
                rule_id,rule_version,event_code,maximum_severity_number,
                category,title,summary,status,evidence_json,created_at,revoked_at
            ) VALUES(
                'rule-1',1,'TAHUSD-SLOT1-4-BUFFER_THRESHOLD_EXCEEDED',3,
                'capacity','Known buffer pressure','Known capacity threshold.',
                'ACTIVE','{}','2026-08-26T03:00:00+00:00',NULL
            )
            '''
        )
        connection.commit()
        connection.close()
        self.add_event(1787716800000, severity='error')

        def forbidden(_request):
            self.fail('learned coverage must not invoke the model')

        result = self.run_triage(
            forbidden, '2026-08-26T04:05:00+00:00', learned=True
        )
        self.assertEqual(result['result'], 'idle')
        self.assertEqual(result['invoked'], 0)
        self.assertEqual(result['applied_incidents'], 1)
        self.assertEqual(
            self.scalar('SELECT source_type FROM event_detection_overrides'),
            'learned_rule',
        )


if __name__ == '__main__':
    unittest.main()
