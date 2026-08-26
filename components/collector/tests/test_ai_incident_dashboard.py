import json
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_DIR = ROOT / "components/collector/grafana/dashboards"
DASHBOARD_PATH = DASHBOARD_DIR / "ai-incident-analysis.json"
DATASOURCE_UID = "efvaztlrk8ow0a"


def load_dashboard_api():
    path = ROOT / "components/collector/grafana/scripts/dashboard_api.py"
    spec = importlib.util.spec_from_file_location("dashboard_api_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_query_verifier():
    scripts = ROOT / "components/collector/grafana/scripts"
    sys.path.insert(0, str(scripts))
    try:
        path = scripts / "verify-ai-dashboard-queries.py"
        spec = importlib.util.spec_from_file_location("ai_query_verifier_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


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
        self.assertEqual(len(tuple(DASHBOARD_DIR.glob("*.json"))), 6)

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

    def test_server_owned_metadata_is_ignored_only_when_omitted(self):
        api = load_dashboard_api()
        live = json.loads(json.dumps(self.document))
        live["metadata"]["annotations"] = {"grafana.app/createdBy": "server-owned"}
        live["metadata"]["labels"] = {"grafana.app/deprecatedInternalID": "server-owned"}
        self.assertEqual(api.capture_matches(live, self.document), (True, ""))

        captured_with_annotations = json.loads(json.dumps(self.document))
        captured_with_annotations["metadata"]["annotations"] = {"stable": "value"}
        matched, reason = api.capture_matches(live, captured_with_annotations)
        self.assertFalse(matched)
        self.assertEqual(reason, "metadata.annotations differs")

    def test_datasource_query_payload_and_redacted_response_counts(self):
        verifier = load_query_verifier()
        panel_query = self.elements["panel-7"]["spec"]["data"]["spec"]["queries"][0]
        ref_id, payload = verifier.query_payload(panel_query, 1000, 2000)
        self.assertEqual(ref_id, "A")
        self.assertEqual(payload["from"], "1000")
        self.assertEqual(payload["to"], "2000")
        self.assertEqual(len(payload["queries"]), 1)
        query = payload["queries"][0]
        self.assertEqual(query["datasource"], {
            "type": "grafana-clickhouse-datasource",
            "uid": DATASOURCE_UID,
        })
        self.assertNotIn("body", json.dumps(payload.get("results", {})))

        response = {
            "results": {
                "A": {
                    "frames": [
                        {"data": {"values": [[1, 2], ["private", "private"]]}}
                    ]
                }
            }
        }
        self.assertEqual(verifier.response_counts(response, "A"), (1, 2))

    def test_drilldown_payload_uses_selected_incident_without_exposing_rows(self):
        verifier = load_query_verifier()
        response = {
            "results": {
                "A": {
                    "frames": [{
                        "schema": {"fields": [
                            {"name": "Device"},
                            {"name": "incident_id"},
                        ]},
                        "data": {"values": [
                            ["private-device"],
                            ["inc-v1-private"],
                        ]},
                    }]
                }
            }
        }
        self.assertEqual(
            verifier.response_field_values(response, "A", "incident_id"),
            ["inc-v1-private"],
        )
        query = {
            "refId": "A",
            "datasource": {
                "type": "grafana-clickhouse-datasource",
                "uid": "logs",
            },
            "rawSql": (
                "SELECT 1 WHERE incident_id = "
                "'${__data.fields.incident_id}'"
            ),
        }
        ref_id, payload = verifier.drilldown_payload(
            query,
            "inc-v1-'safe",
            1000,
            2000,
        )
        self.assertEqual(ref_id, "A")
        self.assertEqual(payload["from"], "1000")
        self.assertEqual(payload["to"], "2000")
        self.assertIn("inc-v1-''safe", payload["queries"][0]["rawSql"])
        self.assertNotIn("${__data.fields", payload["queries"][0]["rawSql"])

    def test_clean_machine_installer_restores_and_queries_dashboard(self):
        installer = (
            ROOT / "components/collector/install/install-runtime.sh"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"$GRAFANA_DIR/dashboards/ai-incident-analysis.json"',
            installer,
        )
        self.assertIn(
            '"$GRAFANA_DIR/dashboards/ai-incident-analysis-enhanced.json"',
            installer,
        )
        self.assertIn(
            '"$GRAFANA_DIR/scripts/verify-ai-dashboard-queries.py"',
            installer,
        )
        self.assertIn("=== VERIFY AI DASHBOARD QUERIES ===", installer)


if __name__ == "__main__":
    unittest.main()
