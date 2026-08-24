import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_DIR = ROOT / "components/collector/grafana/dashboards"
DASHBOARD_PATH = DASHBOARD_DIR / "ai-incident-analysis.json"
DATASOURCE_UID = "efvaztlrk8ow0a"


class AiIncidentDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
        cls.spec = cls.document["spec"]
        cls.elements = cls.spec["elements"]

    def test_resource_identity_and_dashboard_count(self):
        self.assertEqual(self.document["kind"], "Dashboard")
        self.assertEqual(self.document["apiVersion"], "dashboard.grafana.app/v2")
        self.assertEqual(self.document["metadata"], {
            "name": "ai-incident-analysis",
            "namespace": "default",
        })
        self.assertEqual(self.document["status"], {})
        self.assertEqual(self.spec["title"], "AI Incident Analysis")
        self.assertEqual(len(tuple(DASHBOARD_DIR.glob("*.json"))), 5)

    def test_panel_and_layout_contract(self):
        self.assertEqual(len(self.elements), 7)
        references = {
            item["spec"]["element"]["name"]
            for item in self.spec["layout"]["spec"]["items"]
        }
        self.assertEqual(references, set(self.elements))
        self.assertEqual(self.spec["timeSettings"]["from"], "now-7d")
        self.assertEqual(self.spec["timeSettings"]["autoRefresh"], "1m")
        self.assertTrue(self.spec["editable"])

    def test_every_query_uses_read_only_ai_updates_boundary(self):
        for panel in self.elements.values():
            queries = panel["spec"]["data"]["spec"]["queries"]
            self.assertEqual(len(queries), 1)
            query = queries[0]["spec"]["query"]
            self.assertEqual(query["datasource"]["name"], DATASOURCE_UID)
            raw_sql = query["spec"]["rawSql"]
            self.assertIn("FROM observability.ai_updates", raw_sql)
            self.assertIn("$__fromTime", raw_sql)
            self.assertIn("$__toTime", raw_sql)
            self.assertNotIn("raw_json", raw_sql)
            self.assertNotRegex(raw_sql, r"(?i)\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE)\b")

    def test_high_priority_and_detail_queries(self):
        important_sql = self.elements["panel-2"]["spec"]["data"]["spec"]["queries"][0]["spec"]["query"]["spec"]["rawSql"]
        self.assertIn("severity IN ('critical', 'high')", important_sql)

        detail_sql = self.elements["panel-7"]["spec"]["data"]["spec"]["queries"][0]["spec"]["query"]["spec"]["rawSql"]
        for field in (
            "timestamp",
            "severity",
            "status",
            "title",
            "body",
            "occurrence_count",
            "tags",
            "model",
            "incident_id",
            "run_id",
        ):
            self.assertIn(field, detail_sql)
        self.assertIn("ORDER BY timestamp DESC", detail_sql)
        self.assertIn("LIMIT 200", detail_sql)

    def test_visualization_mix(self):
        groups = {
            panel["spec"]["vizConfig"]["group"]
            for panel in self.elements.values()
        }
        self.assertEqual(groups, {"stat", "timeseries", "piechart", "table"})


if __name__ == "__main__":
    unittest.main()
