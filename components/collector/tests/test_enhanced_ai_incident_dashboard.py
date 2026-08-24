import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_DIR = ROOT / "components/collector/grafana/dashboards"
ORIGINAL_PATH = DASHBOARD_DIR / "ai-incident-analysis.json"
ENHANCED_PATH = DASHBOARD_DIR / "ai-incident-analysis-enhanced.json"
DATASOURCE_UID = "efvaztlrk8ow0a"
ORIGINAL_SHA256 = "794719f7cf112babb37c716df16959e631b0f63b81bbe9e503d243ffb36b83e5"


def query(panel):
    return panel["spec"]["data"]["spec"]["queries"][0]["spec"]["query"]


def override(panel, field):
    overrides = panel["spec"]["vizConfig"]["spec"]["fieldConfig"]["overrides"]
    return next(item for item in overrides if item["matcher"]["options"] == field)


def property_value(panel, field, property_id):
    properties = override(panel, field)["properties"]
    return next(item["value"] for item in properties if item["id"] == property_id)


class EnhancedAiIncidentDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(ORIGINAL_PATH.read_text(encoding="utf-8"))
        cls.document = json.loads(ENHANCED_PATH.read_text(encoding="utf-8"))
        cls.spec = cls.document["spec"]
        cls.elements = cls.spec["elements"]

    def test_original_dashboard_remains_exact(self):
        self.assertEqual(
            hashlib.sha256(ORIGINAL_PATH.read_bytes()).hexdigest(),
            ORIGINAL_SHA256,
        )
        self.assertEqual(self.original["metadata"]["name"], "ai-incident-analysis")
        self.assertEqual(self.original["spec"]["title"], "AI Incident Analysis")

    def test_enhanced_resource_is_a_distinct_editable_copy(self):
        self.assertEqual(self.document["kind"], "Dashboard")
        self.assertEqual(self.document["apiVersion"], "dashboard.grafana.app/v2")
        self.assertEqual(self.document["metadata"], {
            "name": "ai-incident-analysis-enhanced",
            "namespace": "default",
        })
        self.assertEqual(self.spec["title"], "AI Incident Analysis - Enhanced")
        self.assertIn("original dashboard remains available", self.spec["description"])
        self.assertTrue(self.spec["editable"])
        self.assertEqual(self.spec["timeSettings"], self.original["spec"]["timeSettings"])

    def test_summary_panels_preserve_original_queries(self):
        for panel_name in ("panel-1", "panel-2", "panel-3", "panel-4", "panel-5", "panel-6"):
            self.assertEqual(
                query(self.elements[panel_name])["spec"]["rawSql"],
                query(self.original["spec"]["elements"][panel_name])["spec"]["rawSql"],
            )

    def test_layout_references_all_eight_panels(self):
        self.assertEqual(len(self.elements), 8)
        references = {
            item["spec"]["element"]["name"]
            for item in self.spec["layout"]["spec"]["items"]
        }
        self.assertEqual(references, set(self.elements))
        detail = next(
            item for item in self.spec["layout"]["spec"]["items"]
            if item["spec"]["element"]["name"] == "panel-8"
        )
        self.assertEqual(detail["spec"]["width"], 24)

    def test_every_query_is_bounded_read_only_ai_data(self):
        for panel in self.elements.values():
            panel_query = query(panel)
            self.assertEqual(panel_query["datasource"]["name"], DATASOURCE_UID)
            sql = panel_query["spec"]["rawSql"]
            self.assertIn("FROM observability.ai_updates", sql)
            self.assertIn("$__fromTime", sql)
            self.assertIn("$__toTime", sql)
            self.assertNotIn("raw_json", sql)
            self.assertNotRegex(
                sql,
                r"(?i)\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE)\b",
            )

    def test_latest_feed_is_one_deterministic_latest_row_per_incident(self):
        panel = self.elements["panel-7"]
        sql = query(panel)["spec"]["rawSql"]
        self.assertEqual(panel["spec"]["title"], "Latest AI Assessment per Incident")
        self.assertIn("argMax(severity, tuple(timestamp, run_id))", sql)
        self.assertIn("GROUP BY incident_id", sql)
        self.assertIn('ORDER BY "Time" DESC', sql)
        self.assertIn("LIMIT 100", sql)
        self.assertNotIn("body", sql)
        self.assertNotIn("model AS", sql)
        self.assertNotIn("run_id AS", sql)

    def test_feed_uses_operator_focused_table_styling(self):
        panel = self.elements["panel-7"]
        options = panel["spec"]["vizConfig"]["spec"]["options"]
        defaults = panel["spec"]["vizConfig"]["spec"]["fieldConfig"]["defaults"]
        self.assertEqual(options["cellHeight"], "md")
        self.assertTrue(options["enablePagination"])
        self.assertEqual(options["frozenColumns"], {"left": 1})
        self.assertTrue(defaults["custom"]["filterable"])
        self.assertEqual(property_value(panel, "Time", "unit"), "dateTimeFromNow")
        self.assertEqual(
            property_value(panel, "Tags", "custom.cellOptions"),
            {"type": "pill"},
        )
        for field in ("Severity", "Assessment"):
            self.assertEqual(
                property_value(panel, field, "custom.cellOptions")["type"],
                "color-background",
            )
            mappings = property_value(panel, field, "mappings")[0]["options"]
            self.assertGreaterEqual(len(mappings), 5)

    def test_full_detail_panel_retains_explanation_and_provenance(self):
        panel = self.elements["panel-8"]
        sql = query(panel)["spec"]["rawSql"]
        self.assertEqual(panel["spec"]["title"], "Full Assessment Details")
        for field in (
            "body",
            "model",
            "incident_id",
            "run_id",
            "occurrence_count",
            "tags",
        ):
            self.assertIn(field, sql)
        self.assertIn("ORDER BY timestamp DESC", sql)
        self.assertIn("LIMIT 200", sql)
        self.assertTrue(
            property_value(panel, "Explanation", "custom.wrapText")
        )
        self.assertEqual(
            property_value(panel, "Tags", "custom.cellOptions"),
            {"type": "pill"},
        )


if __name__ == "__main__":
    unittest.main()
