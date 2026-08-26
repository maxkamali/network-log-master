import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_DIR = ROOT / 'components/collector/grafana/dashboards'
ORIGINAL_PATH = DASHBOARD_DIR / 'ai-incident-analysis.json'
ENHANCED_PATH = DASHBOARD_DIR / 'ai-incident-analysis-enhanced.json'
BUILDER_PATH = ROOT / 'components/collector/grafana/scripts/build-noc-lifecycle-dashboard.py'
DATASOURCE_UID = 'efvaztlrk8ow0a'
LOGS_DATASOURCE_UID = 'bfvik20ilwoaof'
ORIGINAL_SHA256 = '794719f7cf112babb37c716df16959e631b0f63b81bbe9e503d243ffb36b83e5'


def load_builder():
    specification = importlib.util.spec_from_file_location(
        'noc_lifecycle_dashboard_builder_test', BUILDER_PATH
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def panel_query(panel):
    return panel['spec']['data']['spec']['queries'][0]['spec']['query']


def override(panel, field):
    overrides = panel['spec']['vizConfig']['spec']['fieldConfig']['overrides']
    return next(item for item in overrides if item['matcher']['options'] == field)


class EnhancedAiIncidentDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(ORIGINAL_PATH.read_text(encoding='utf-8'))
        cls.document = json.loads(ENHANCED_PATH.read_text(encoding='utf-8'))
        cls.spec = cls.document['spec']
        cls.elements = cls.spec['elements']

    def test_original_dashboard_remains_exact(self):
        self.assertEqual(
            hashlib.sha256(ORIGINAL_PATH.read_bytes()).hexdigest(),
            ORIGINAL_SHA256,
        )
        self.assertEqual(self.original['spec']['title'], 'AI Incident Analysis')

    def test_enhanced_resource_is_distinct_and_reproducible(self):
        self.assertEqual(
            self.document['metadata'],
            {'name': 'ai-incident-analysis-enhanced', 'namespace': 'default'},
        )
        self.assertEqual(self.spec['title'], 'AI Incident Analysis - Enhanced')
        self.assertTrue(self.spec['editable'])
        self.assertIn('original AI dashboard remains', self.spec['description'])
        self.assertEqual(load_builder().build_document(), self.document)

    def test_search_and_severity_controls_are_server_side_variables(self):
        variables = {item['spec']['name']: item for item in self.spec['variables']}
        self.assertEqual(
            set(variables),
            {'active_search', 'flap_search', 'resolved_search', 'severity_filter'},
        )
        for name in ('active_search', 'flap_search', 'resolved_search'):
            self.assertEqual(variables[name]['kind'], 'TextVariable')
            self.assertEqual(variables[name]['spec']['current']['value'], '')
        self.assertEqual(variables['severity_filter']['kind'], 'CustomVariable')
        self.assertEqual(variables['severity_filter']['spec']['current']['value'], 'all')

    def test_layout_has_three_counts_and_three_operational_windows(self):
        self.assertEqual(len(self.elements), 6)
        self.assertEqual(
            [self.elements[f'panel-{number}']['spec']['title'] for number in range(1, 7)],
            ['Active Events', 'Interface Flaps', 'Resolved', 'Active Events', 'Interface Flaps', 'Resolved Events'],
        )
        references = {
            item['spec']['element']['name']
            for item in self.spec['layout']['spec']['items']
        }
        self.assertEqual(references, set(self.elements))

    def test_every_query_is_read_only_and_lifecycle_authoritative(self):
        for name, panel in self.elements.items():
            query = panel_query(panel)
            self.assertEqual(query['datasource']['name'], DATASOURCE_UID)
            sql = query['spec']['rawSql']
            self.assertIn('FROM observability.incident_updates', sql)
            self.assertIn('argMax(', sql)
            if name == 'panel-4':
                self.assertIn('FROM observability.ai_updates', sql)
                self.assertIn('LEFT JOIN latest_ai USING incident_id', sql)
            else:
                self.assertNotIn('observability.ai_updates', sql)
            self.assertNotIn('recommended_actions', sql)
            self.assertNotRegex(sql, r'(?i)\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE)\b')

    def test_active_queue_persists_and_excludes_flaps(self):
        sql = panel_query(self.elements['panel-4'])['spec']['rawSql']
        self.assertIn("lifecycle_status IN ('CANDIDATE', 'OPEN', 'RECOVERING')", sql)
        self.assertIn("entity_type != 'interface'", sql)
        self.assertIn('${active_search:sqlstring}', sql)
        self.assertIn('${severity_filter:sqlstring}', sql)
        self.assertIn('ai_description', sql)
        self.assertIn('AS "Event Details"', sql)
        self.assertIn('deterministic_detail', sql)
        self.assertIn("lowerUTF8(protocol) IN ('bgp', 'ospf', 'ospfv3')", sql)
        self.assertIn("'MONITORING'", sql)
        self.assertIn('recurrence_count + 1 AS "Occurrences"', sql)
        self.assertNotIn('$__fromTime', sql)
        self.assertNotIn('$__toTime', sql)
        self.assertNotIn('Model', sql)
        self.assertNotIn('Recommendation', sql)

    def test_flap_queue_is_exclusive_and_searchable(self):
        sql = panel_query(self.elements['panel-5'])['spec']['rawSql']
        self.assertIn("entity_type = 'interface'", sql)
        self.assertIn('${flap_search:sqlstring}', sql)
        self.assertIn('state_change_count AS "Flaps"', sql)
        self.assertNotIn('$__fromTime', sql)
        self.assertNotIn('$__toTime', sql)

    def test_resolved_queue_uses_resolved_time_range_and_search(self):
        count_sql = panel_query(self.elements['panel-3'])['spec']['rawSql']
        self.assertIn('count() AS "Resolved"', count_sql)
        self.assertNotIn('Resolved in Range', count_sql)
        sql = panel_query(self.elements['panel-6'])['spec']['rawSql']
        self.assertIn("lifecycle_status = 'RESOLVED'", sql)
        self.assertIn('resolved_at >= $__fromTime', sql)
        self.assertIn('resolved_at <= $__toTime', sql)
        self.assertIn('${resolved_search:sqlstring}', sql)
        self.assertIn('${severity_filter:sqlstring}', sql)
        self.assertIn('recurrence_count + 1 AS "Occurrences"', sql)

    def test_tables_keep_operator_focused_theme_and_filters(self):
        for name in ('panel-4', 'panel-5', 'panel-6'):
            panel = self.elements[name]
            options = panel['spec']['vizConfig']['spec']['options']
            defaults = panel['spec']['vizConfig']['spec']['fieldConfig']['defaults']
            self.assertEqual(options['cellHeight'], 'md')
            self.assertTrue(options['enablePagination'])
            self.assertEqual(options['frozenColumns'], {'left': 2})
            self.assertTrue(defaults['custom']['filterable'])
        severity = override(self.elements['panel-4'], 'Severity')['properties']
        self.assertTrue(any(item['id'] == 'mappings' for item in severity))
        details = override(self.elements['panel-4'], 'Event Details')['properties']
        self.assertIn({'id': 'custom.wrapText', 'value': True}, details)

    def test_every_event_row_links_to_incident_scoped_matching_logs(self):
        for name in ('panel-4', 'panel-5', 'panel-6'):
            panel = self.elements[name]
            defaults = panel['spec']['vizConfig']['spec']['fieldConfig']['defaults']
            self.assertEqual(len(defaults['links']), 1)
            link = defaults['links'][0]
            self.assertTrue(link['targetBlank'])
            self.assertEqual(link['title'], 'View matching logs')
            self.assertIn('${__data.fields.incident_id}', link['url'])
            self.assertIn('${__from}', link['url'])
            self.assertIn('${__to}', link['url'])
            self.assertNotIn('%24%7B__data', link['url'])

            parsed = urlsplit(link['url'])
            self.assertEqual(parsed.path, '/explore')
            parameters = parse_qs(parsed.query)
            self.assertEqual(parameters['schemaVersion'], ['1'])
            self.assertEqual(parameters['orgId'], ['1'])
            panes = json.loads(parameters['panes'][0])
            self.assertEqual(set(panes), {'incident'})
            pane = panes['incident']
            self.assertEqual(pane['datasource'], LOGS_DATASOURCE_UID)
            self.assertEqual(len(pane['queries']), 1)
            query = pane['queries'][0]
            self.assertEqual(query['datasource']['uid'], LOGS_DATASOURCE_UID)
            self.assertEqual(query['queryType'], 'logs')
            sql = query['rawSql']
            self.assertIn('${__data.fields.incident_id}', sql)
            self.assertIn('FROM observability.incident_updates', sql)
            self.assertIn('FROM observability.grafana_logs AS logs', sql)
            self.assertIn('incident.first_seen - INTERVAL 15 MINUTE', sql)
            self.assertIn('ifNull(incident.resolved_at, incident.last_seen)', sql)
            self.assertIn('lowerUTF8(logs.device) = lowerUTF8(incident.device)', sql)
            self.assertIn('positionCaseInsensitiveUTF8(logs.body, incident.entity_name)', sql)
            self.assertIn('positionCaseInsensitiveUTF8(logs.body, incident.protocol)', sql)
            self.assertIn('positionCaseInsensitiveUTF8(logs.body, incident.event_family)', sql)
            self.assertIn('LIMIT 1000', sql)
            self.assertNotRegex(sql, r'(?i)\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE)\b')
            self.assertIn('Click any row cell', panel['spec']['description'])
            incident_id = override(panel, 'incident_id')['properties']
            self.assertIn({'id': 'displayName', 'value': 'Incident ID'}, incident_id)


if __name__ == '__main__':
    unittest.main()
