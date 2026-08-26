#!/usr/bin/env python3
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest


GX10_DIR = Path(__file__).resolve().parents[1]
APPLICATION = GX10_DIR / 'sbin' / 'run-managed-ai.py'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ManagedAiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / 'events.sqlite3'
        sqlite3.connect(self.database).close()
        specification = importlib.util.spec_from_file_location(
            'managed_ai_test', APPLICATION
        )
        self.runner = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(self.runner)
        self.managed = self.root / 'managed.py'
        self.triage = self.root / 'triage.py'
        self.engine = self.root / 'engine.py'
        self.config = self.root / 'config.json'
        self.prompt = self.root / 'prompt.txt'
        self.schema = self.root / 'schema.json'
        self.lock = self.root / 'managed-ai.lock'
        self.engine.write_text('# engine\n')
        self.config.write_text('{}\n')
        self.prompt.write_text('prompt\n')
        self.schema.write_text('{}\n')
        for path in (self.engine,):
            path.chmod(0o755)
        for path in (self.config, self.prompt, self.schema):
            path.chmod(0o644)

    def install_modules(self, *, pending, triage_invoked):
        self.managed.write_text(
            '#!/usr/bin/env python3\n'
            f'PENDING={pending}\n'
            'def snapshot(database):\n'
            "    return {'pending':PENDING}\n"
            'def main(database_path=None):\n'
            "    print('MANAGED_CALLED')\n"
            '    return 0\n'
        )
        self.triage.write_text(
            '#!/usr/bin/env python3\n'
            f'INVOKED={triage_invoked}\n'
            'def run(database, **kwargs):\n'
            "    return {'result':'pass' if INVOKED else 'idle','invoked':INVOKED,'decisions':INVOKED,'applied_incidents':INVOKED,'promoted_rules':0}\n"
        )
        self.managed.chmod(0o755)
        self.triage.chmod(0o755)
        self.runner.MANAGED_RUNNER_SHA256 = digest(self.managed)
        self.runner.TRIAGE_SHA256 = digest(self.triage)
        self.runner.INCIDENT_ENGINE_SHA256 = digest(self.engine)
        self.runner.CONFIG_SHA256 = digest(self.config)
        self.runner.PROMPT_SHA256 = digest(self.prompt)
        self.runner.OUTPUT_SCHEMA_SHA256 = digest(self.schema)

    def invoke(self):
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(
            io.StringIO()
        ) as stderr:
            result = self.runner.main(
                self.database,
                managed_runner_path=self.managed,
                triage_path=self.triage,
                incident_engine_path=self.engine,
                config_path=self.config,
                prompt_path=self.prompt,
                output_schema_path=self.schema,
                lock_path=self.lock,
            )
        return result, stdout.getvalue(), stderr.getvalue()

    def test_triage_inference_owns_cycle_and_defers_incident_reasoning(self):
        self.install_modules(pending=0, triage_invoked=1)
        result, output, error = self.invoke()
        self.assertEqual(result, 0, error)
        self.assertIn('invoked=1', output)
        self.assertNotIn('MANAGED_CALLED', output)

    def test_existing_incident_reasoning_backlog_has_priority(self):
        self.install_modules(pending=1, triage_invoked=1)
        result, output, error = self.invoke()
        self.assertEqual(result, 0, error)
        self.assertIn('MANAGED_CALLED', output)
        self.assertNotIn('MANAGED_AI schema=1', output)

    def test_idle_triage_delegates_to_incident_reasoning(self):
        self.install_modules(pending=0, triage_invoked=0)
        result, output, error = self.invoke()
        self.assertEqual(result, 0, error)
        self.assertIn('MANAGED_AI schema=1 result=idle invoked=0', output)
        self.assertIn('MANAGED_CALLED', output)


if __name__ == '__main__':
    unittest.main()
