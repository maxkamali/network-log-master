import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_PATH = ROOT / 'components/collector/grafana/dashboards/noc-view.json'
LINKED_PANELS = {
    'panel-4': 'piechart',
    'panel-5': 'barchart',
    'panel-8': 'barchart',
    'panel-9': 'barchart',
}


class NocViewDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(DASHBOARD_PATH.read_text(encoding='utf-8'))
        cls.elements = cls.document['spec']['elements']

    def test_linked_panels_open_explore_directly_in_compact_mode(self):
        self.assertEqual(self.document['spec']['title'], 'NOC View')
        for panel_name, visualization in LINKED_PANELS.items():
            panel = self.elements[panel_name]
            self.assertEqual(panel['spec']['vizConfig']['group'], visualization)
            defaults = panel['spec']['vizConfig']['spec']['fieldConfig']['defaults']
            self.assertEqual(len(defaults['links']), 1)
            link = defaults['links'][0]
            self.assertIs(link['oneClick'], True)
            self.assertIs(link['targetBlank'], True)

            parsed = urlsplit(link['url'])
            self.assertEqual(parsed.path, '/explore')
            parameters = parse_qs(parsed.query)
            self.assertEqual(parameters['schemaVersion'], ['1'])
            self.assertEqual(parameters['orgId'], ['1'])
            panes = json.loads(parameters['panes'][0])
            self.assertEqual(len(panes), 1)
            pane = next(iter(panes.values()))
            self.assertIs(pane['compact'], True)
            self.assertEqual(len(pane['queries']), 1)
            self.assertNotRegex(
                pane['queries'][0]['rawSql'],
                r'(?i)\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE)\b',
            )


if __name__ == '__main__':
    unittest.main()
