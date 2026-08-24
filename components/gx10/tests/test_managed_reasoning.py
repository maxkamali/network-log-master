#!/usr/bin/env python3
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
import sqlite3
import tempfile
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = GX10_DIR / 'sbin' / 'run-managed-reasoning.py'


def load_runner():
    specification = importlib.util.spec_from_file_location(
        'managed_reasoning_test_runner', RUNNER_PATH
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ManagedReasoningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / 'events.sqlite3'
        connection = sqlite3.connect(self.database)
        connection.executescript(
            '''
            CREATE TABLE reasoning_packets (packet_id TEXT PRIMARY KEY);
            CREATE TABLE reasoning_model_versions (
                model_version TEXT PRIMARY KEY
            );
            CREATE TABLE reasoning_prompt_versions (
                prompt_version TEXT PRIMARY KEY
            );
            CREATE TABLE reasoning_runs (
                run_id TEXT PRIMARY KEY,
                packet_id TEXT NOT NULL,
                model_version TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE reasoning_results (run_id TEXT PRIMARY KEY);
            '''
        )
        connection.commit()
        connection.close()
        self.runner = load_runner()
        self.packet_builder = self.root / 'packet-builder.py'
        self.caller = self.root / 'caller.py'
        self.runtime_config = self.root / 'runtime.json'
        self.prompt = self.root / 'prompt.txt'
        self.output_schema = self.root / 'schema.json'
        for path, data, mode in (
            (
                self.packet_builder,
                '#!/usr/bin/env python3\ndef run(database):\n    return 0\n',
                0o755,
            ),
            (
                self.caller,
                '#!/usr/bin/env python3\ndef run(database, **kwargs):\n    return 0\n',
                0o755,
            ),
            (self.runtime_config, '{}\n', 0o644),
            (self.prompt, 'prompt\n', 0o644),
            (self.output_schema, '{}\n', 0o644),
        ):
            path.write_text(data)
            path.chmod(mode)
        self.refresh_hashes()
        self.lock = self.root / 'managed-reasoning.lock'

    def refresh_hashes(self):
        self.runner.PACKET_BUILDER_SHA256 = digest(self.packet_builder)
        self.runner.CALLER_SHA256 = digest(self.caller)
        self.runner.RUNTIME_CONFIG_SHA256 = digest(self.runtime_config)
        self.runner.PROMPT_SHA256 = digest(self.prompt)
        self.runner.OUTPUT_SCHEMA_SHA256 = digest(self.output_schema)

    def run_runner(self):
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(
            io.StringIO()
        ) as stderr:
            result = self.runner.main(
                self.database,
                self.packet_builder,
                self.caller,
                self.runtime_config,
                self.prompt,
                self.output_schema,
                self.lock,
            )
        return result, stdout.getvalue(), stderr.getvalue()

    def add_packet(self, packet_id='packet-1'):
        connection = sqlite3.connect(self.database)
        connection.execute(
            'INSERT INTO reasoning_packets VALUES (?)', (packet_id,)
        )
        connection.commit()
        connection.close()

    def test_empty_cycle_is_noop_and_reports_health(self):
        result, output, error = self.run_runner()
        self.assertEqual(result, 0, error)
        self.assertIn('packets_created=0 invoked=0', output)
        self.assertIn('pending=0', output)
        self.assertIn('GX10_MANAGED_REASONING=PASS', output)

    def test_one_pending_packet_allows_exactly_one_success(self):
        self.add_packet()
        self.caller.write_text(
            '#!/usr/bin/env python3\n'
            'import sqlite3\n'
            f'MODEL={self.runner.MODEL_VERSION!r}\n'
            f'PROMPT={self.runner.PROMPT_VERSION!r}\n'
            'def run(database, **kwargs):\n'
            '    c=sqlite3.connect(database)\n'
            "    c.execute('INSERT INTO reasoning_model_versions VALUES (?)',(MODEL,))\n"
            "    c.execute('INSERT INTO reasoning_prompt_versions VALUES (?)',(PROMPT,))\n"
            "    c.execute(\"INSERT INTO reasoning_runs VALUES ('run-1','packet-1',?,?,1,'SUCCEEDED')\",(MODEL,PROMPT))\n"
            "    c.execute(\"INSERT INTO reasoning_results VALUES ('run-1')\")\n"
            '    c.commit()\n'
            '    c.close()\n'
            '    return 0\n'
        )
        self.caller.chmod(0o755)
        self.refresh_hashes()
        result, output, error = self.run_runner()
        self.assertEqual(result, 0, error)
        self.assertIn('invoked=1', output)
        self.assertIn('succeeded=1', output)
        self.assertIn('results=1', output)
        self.assertIn('pending=0', output)

    def test_safe_terminal_failure_is_visible_and_bounded(self):
        self.add_packet()
        self.caller.write_text(
            '#!/usr/bin/env python3\n'
            'import sqlite3\n'
            f'MODEL={self.runner.MODEL_VERSION!r}\n'
            f'PROMPT={self.runner.PROMPT_VERSION!r}\n'
            'def run(database, **kwargs):\n'
            '    c=sqlite3.connect(database)\n'
            "    c.execute('INSERT INTO reasoning_model_versions VALUES (?)',(MODEL,))\n"
            "    c.execute('INSERT INTO reasoning_prompt_versions VALUES (?)',(PROMPT,))\n"
            "    c.execute(\"INSERT INTO reasoning_runs VALUES ('run-1','packet-1',?,?,1,'INFERENCE_UNAVAILABLE')\",(MODEL,PROMPT))\n"
            '    c.commit()\n'
            '    c.close()\n'
            '    return 1\n'
        )
        self.caller.chmod(0o755)
        self.refresh_hashes()
        result, output, error = self.run_runner()
        self.assertEqual(result, 1)
        self.assertIn('result=safe_failure', output)
        self.assertIn('invoked=1', output)
        self.assertIn('failures=1', output)
        self.assertIn('GX10_MANAGED_REASONING=SAFE_FAILURE', error)

    def test_unreconciled_started_reservation_blocks_new_work(self):
        self.add_packet()
        connection = sqlite3.connect(self.database)
        connection.execute(
            'INSERT INTO reasoning_runs VALUES (?, ?, ?, ?, 1, ?)',
            (
                'run-1',
                'packet-1',
                self.runner.MODEL_VERSION,
                self.runner.PROMPT_VERSION,
                'STARTED',
            ),
        )
        connection.commit()
        connection.close()
        result, _, error = self.run_runner()
        self.assertEqual(result, 1)
        self.assertIn('unreconciled STARTED', error)

    def test_lock_contention_prevents_processing(self):
        descriptor = os.open(self.lock, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result, _, error = self.run_runner()
        self.assertEqual(result, 1)
        self.assertIn('already running', error)

    def test_two_new_runs_are_rejected_as_unbounded(self):
        self.add_packet('packet-1')
        self.add_packet('packet-2')
        self.caller.write_text(
            '#!/usr/bin/env python3\n'
            'import sqlite3\n'
            f'MODEL={self.runner.MODEL_VERSION!r}\n'
            f'PROMPT={self.runner.PROMPT_VERSION!r}\n'
            'def run(database, **kwargs):\n'
            '    c=sqlite3.connect(database)\n'
            '    for n in (1,2):\n'
            "        c.execute('INSERT INTO reasoning_runs VALUES (?, ?, ?, ?, 1, ?)',(f'run-{n}',f'packet-{n}',MODEL,PROMPT,'INFERENCE_UNAVAILABLE'))\n"
            '    c.commit()\n'
            '    c.close()\n'
            '    return 1\n'
        )
        self.caller.chmod(0o755)
        self.refresh_hashes()
        result, _, error = self.run_runner()
        self.assertEqual(result, 1)
        self.assertIn('exceeded one inference', error)

    def test_private_database_config_is_strict(self):
        config = self.root / 'managed.json'
        config.write_text(
            json.dumps({'database_path': str(self.database)})
        )
        self.assertEqual(
            self.runner.load_database_path(config), self.database
        )
        config.write_text(json.dumps({'database_path': 'relative.db'}))
        self.assertIsNone(self.runner.load_database_path(config))
        config.write_text(
            json.dumps(
                {'database_path': str(self.database), 'unexpected': True}
            )
        )
        self.assertIsNone(self.runner.load_database_path(config))


if __name__ == '__main__':
    unittest.main()
