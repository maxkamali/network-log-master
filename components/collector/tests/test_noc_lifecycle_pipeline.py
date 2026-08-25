from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
COLLECTOR = ROOT / 'components/collector'


class NocLifecyclePipelineTests(unittest.TestCase):
    def test_clickhouse_contract_is_append_only_latest_state_projection(self):
        sql = (
            COLLECTOR / 'clickhouse/25-incident-updates.sql'
        ).read_text(encoding='utf-8')
        self.assertIn('CREATE TABLE observability.incident_updates', sql)
        self.assertIn('ENGINE = ReplacingMergeTree(snapshot_version)', sql)
        self.assertIn('ORDER BY incident_id', sql)
        for column in (
            'snapshot_id', 'snapshot_version', 'incident_id', 'device',
            'entity_type', 'entity_name', 'event_family', 'protocol',
            'lifecycle_status', 'resolved_at', 'occurrence_count',
            'recurrence_count', 'state_change_count', 'interface_flap',
            'raw_json',
        ):
            self.assertIn(f'`{column}`', sql)
        migration = (
            COLLECTOR / 'clickhouse/26-incident-recurrence.sql'
        ).read_text(encoding='utf-8')
        self.assertIn('ADD COLUMN IF NOT EXISTS `recurrence_count`', migration)
        self.assertIn('UInt32 DEFAULT 0', migration)

    def test_vector_routes_lifecycle_away_from_ai_assessments(self):
        config = (COLLECTOR / 'vector/vector.yaml').read_text(encoding='utf-8')
        self.assertIn('select_ai_assessments:', config)
        self.assertIn("condition: '.type != \"incident_lifecycle\"'", config)
        self.assertIn('select_incident_updates:', config)
        self.assertIn("condition: '.type == \"incident_lifecycle\"'", config)
        self.assertIn('clickhouse_incident_updates:', config)
        self.assertIn('table: incident_updates', config)
        ai_sink = config.split('clickhouse_ai_updates:', 1)[1].split(
            'clickhouse_incident_updates:', 1
        )[0]
        self.assertIn('- select_ai_assessments', ai_sink)
        self.assertNotIn('- prepare_ai_updates', ai_sink)

    def test_clean_installer_and_access_contract_include_lifecycle_table(self):
        installer = (
            COLLECTOR / 'install/install-runtime.sh'
        ).read_text(encoding='utf-8')
        verifier = (
            COLLECTOR / 'install/verify-runtime.sh'
        ).read_text(encoding='utf-8')
        grants = (
            COLLECTOR / 'clickhouse/40-access-control.sql.in'
        ).read_text(encoding='utf-8')
        self.assertGreaterEqual(installer.count('25-incident-updates.sql'), 2)
        self.assertGreaterEqual(installer.count('26-incident-recurrence.sql'), 2)
        self.assertIn('"incident_updates": "ReplacingMergeTree"', verifier)
        self.assertIn(
            'GRANT SELECT ON observability.incident_updates\nTO grafana_reader;',
            grants,
        )
        self.assertIn(
            'GRANT INSERT ON observability.incident_updates\nTO vector_ingest;',
            grants,
        )


if __name__ == '__main__':
    unittest.main()
