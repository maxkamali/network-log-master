#!/usr/bin/env python3
import hashlib
import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_application_contract import load_application

GX10_DIR = Path(__file__).resolve().parents[1]
INITIALIZER_PATH = GX10_DIR / 'install' / 'initialize-database.py'
SCHEMA_PATH = GX10_DIR / 'sql' / 'initialize.sql'
SPEC = importlib.util.spec_from_file_location('initialize_database', INITIALIZER_PATH)
INITIALIZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INITIALIZER)

EXPECTED_TABLE_HASHES = {
    'agent_state': '8488a9c5f878e1979979c6bdb7868e6f6dffc9ba29592c02f3046fb55e83f3f2',
    'event_enrichment': '1a3d2819432ce6a4fbbbff6a9c1bbfb657f58ebe48f325358fd75f04fce83bf6',
    'recent_events': '5e1c4e91a37f75421d445f75bae0830244a132f0193908e7f996bf90bf552e9e',
    'source_files': '0b6219e204290200b2856b0afc34661ebadb31836ebb3f531de7fac23024d781',
    'suppression_rules': '1262051a43077190c96ae1b6549dd3683bed38375d102319c96431b3f60366ec',
}


class DatabaseInitializationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'events.sqlite3'
        INITIALIZER.initialize_database(
            self.database,
            SCHEMA_PATH,
            os.getuid(),
            os.getgid(),
        )

    def connect(self):
        connection = sqlite3.connect(self.database)
        self.addCleanup(connection.close)
        connection.execute('PRAGMA foreign_keys=ON')
        return connection

    def test_recovered_base_schema_is_preserved_with_incident_extension(self):
        with self.connect() as connection:
            objects = connection.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' "
                "AND type IN ('table', 'index', 'trigger') "
                "ORDER BY type, name"
            ).fetchall()
            self.assertEqual(len(objects), 30)
            self.assertEqual(
                sum(1 for kind, _, _ in objects if kind == 'table'),
                8,
            )
            self.assertEqual(
                sum(1 for kind, _, _ in objects if kind == 'index'),
                18,
            )
            self.assertEqual(
                sum(1 for kind, _, _ in objects if kind == 'trigger'),
                4,
            )

            tables = {
                name: sql
                for kind, name, sql in objects
                if kind == 'table'
            }
            for name, expected_hash in EXPECTED_TABLE_HASHES.items():
                self.assertEqual(
                    hashlib.sha256(tables[name].encode()).hexdigest(),
                    expected_hash,
                    name,
                )

    def test_foreign_keys_match_recovered_contract(self):
        with self.connect() as connection:
            relationships = set()
            for table in (
                'event_enrichment',
                'recent_events',
                'incidents',
                'incident_evidence',
                'incident_transitions',
            ):
                for row in connection.execute(f'PRAGMA foreign_key_list({table})'):
                    relationships.add((table, row[3], row[2], row[4]))
            self.assertEqual(
                relationships,
                {
                    ('event_enrichment', 'event_id', 'recent_events', 'id'),
                    (
                        'event_enrichment',
                        'suppression_rule_id',
                        'suppression_rules',
                        'id',
                    ),
                    ('recent_events', 'source_file', 'source_files', 'remote_path'),
                    ('incidents', 'last_event_id', 'recent_events', 'id'),
                    ('incident_evidence', 'event_id', 'recent_events', 'id'),
                    ('incident_evidence', 'incident_id', 'incidents', 'incident_id'),
                    ('incident_transitions', 'event_id', 'recent_events', 'id'),
                    ('incident_transitions', 'incident_id', 'incidents', 'incident_id'),
                },
            )

    def test_functional_suppression_corpus_is_exact(self):
        with self.connect() as connection:
            rows = connection.execute(
                'SELECT id, rule_type, pattern, enabled '
                'FROM suppression_rules ORDER BY id'
            ).fetchall()
            self.assertEqual(
                rows,
                [
                    (1, 'event_code_exact', 'ICMPV6-3-ND_LOG', 1),
                    (2, 'event_code_exact', 'ICMPV6-3-ND_RA_LOG', 1),
                ],
            )

    def test_database_integrity_mode_and_empty_application_state(self):
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o640)
        with self.connect() as connection:
            self.assertEqual(connection.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 0)
            self.assertEqual(connection.execute('PRAGMA application_id').fetchone()[0], 0)
            for table in (
                'agent_state',
                'source_files',
                'recent_events',
                'event_enrichment',
                'incidents',
                'incident_evidence',
                'incident_transitions',
            ):
                self.assertEqual(
                    connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],
                    0,
                )

    def test_existing_database_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'refuses an existing database'):
            INITIALIZER.initialize_database(
                self.database,
                SCHEMA_PATH,
                os.getuid(),
                os.getgid(),
            )

    def test_ingest_migrator_and_projection_validator_preserve_schema(self):
        with self.connect() as connection:
            before = connection.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' "
                "AND type IN ('table', 'index', 'trigger') "
                "ORDER BY type, name"
            ).fetchall()

            load_application('ingest').ensure_schema(connection)
            load_application('projection').validate_database_contract(
                connection
            )
            load_application('incident').validate_database_contract(
                connection
            )

            after = connection.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' "
                "AND type IN ('table', 'index', 'trigger') "
                "ORDER BY type, name"
            ).fetchall()
            self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()
