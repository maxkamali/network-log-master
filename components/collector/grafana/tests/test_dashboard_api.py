#!/usr/bin/env python3
"""Safety tests for portable native Grafana dashboard captures."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


GRAFANA_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = GRAFANA_ROOT / "scripts" / "dashboard_api.py"
SPEC = importlib.util.spec_from_file_location(
    "dashboard_api",
    MODULE_PATH,
)
DASHBOARD_API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DASHBOARD_API)
sys.modules["dashboard_api"] = DASHBOARD_API
NOC_BUILDER_PATH = (
    GRAFANA_ROOT / "scripts" / "build-noc-organization-captures.py"
)
NOC_SPEC = importlib.util.spec_from_file_location(
    "build_noc_organization_captures",
    NOC_BUILDER_PATH,
)
NOC_BUILDER = importlib.util.module_from_spec(NOC_SPEC)
NOC_SPEC.loader.exec_module(NOC_BUILDER)
QUERY_VERIFIER_PATH = (
    GRAFANA_ROOT / "scripts" / "verify-ai-dashboard-queries.py"
)
QUERY_SPEC = importlib.util.spec_from_file_location(
    "verify_ai_dashboard_queries",
    QUERY_VERIFIER_PATH,
)
QUERY_VERIFIER = importlib.util.module_from_spec(QUERY_SPEC)
QUERY_SPEC.loader.exec_module(QUERY_VERIFIER)


def capture(metadata: dict | None = None, status: dict | None = None) -> dict:
    return {
        "apiVersion": DASHBOARD_API.API_VERSION,
        "kind": DASHBOARD_API.KIND,
        "metadata": metadata or {
            "name": "portable-dashboard",
            "namespace": "default",
        },
        "spec": {"title": "Portable dashboard"},
        "status": {} if status is None else status,
    }


class DashboardApiMetadataTests(unittest.TestCase):
    def write_capture(self, directory: Path, document: dict) -> None:
        (directory / "dashboard.json").write_text(
            json.dumps(document),
            encoding="utf-8",
        )

    def test_repository_captures_contain_only_portable_metadata(self):
        captures = DASHBOARD_API.load_captures(
            GRAFANA_ROOT / "dashboards"
        )
        self.assertTrue(captures)
        for path, document in captures:
            with self.subTest(path=path.name):
                self.assertEqual(
                    set(document["metadata"]),
                    DASHBOARD_API.PORTABLE_METADATA_KEYS,
                )
                self.assertEqual(document["status"], {})

    def test_load_refuses_server_owned_metadata(self):
        document = capture()
        document["metadata"]["annotations"] = {
            "grafana.app/createdBy": "server-account"
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_capture(root, document)
            with self.assertRaisesRegex(
                DASHBOARD_API.DashboardApiError,
                "server-owned metadata",
            ):
                DASHBOARD_API.load_captures(root)

    def test_load_refuses_server_owned_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_capture(root, capture(status={"generation": 7}))
            with self.assertRaisesRegex(
                DASHBOARD_API.DashboardApiError,
                "server-owned status",
            ):
                DASHBOARD_API.load_captures(root)

    def test_clean_payload_strips_server_owned_fields(self):
        document = capture()
        document["metadata"].update({
            "uid": "server-object-identity",
            "annotations": {"createdBy": "server-account"},
            "labels": {"internalID": "server-internal-id"},
        })
        document["status"] = {"generation": 7}
        cleaned = DASHBOARD_API.clean_payload(document)
        self.assertEqual(
            cleaned["metadata"],
            {
                "name": "portable-dashboard",
                "namespace": "default",
            },
        )
        self.assertEqual(cleaned["status"], {})

    def test_live_server_metadata_does_not_change_semantic_match(self):
        document = capture()
        live = capture()
        live["metadata"].update({
            "uid": "server-object-identity",
            "annotations": {"createdBy": "server-account"},
            "labels": {"internalID": "server-internal-id"},
        })
        self.assertEqual(
            DASHBOARD_API.capture_matches(live, document),
            (True, ""),
        )

    def test_noc_builder_scopes_namespace_and_links(self):
        document = capture()
        document["spec"] = {
            "links": [
                "/explore?orgId=1",
                {"nested": "/d/example?orgId=1&view=one"},
            ],
        }
        prepared, changes = NOC_BUILDER.build_capture(document, 7)
        self.assertEqual(changes, 2)
        self.assertEqual(prepared["metadata"], {
            "name": "portable-dashboard",
            "namespace": "org-7",
        })
        self.assertNotIn("orgId=1", json.dumps(prepared))
        self.assertIn("orgId=7", json.dumps(prepared))

    def test_noc_builder_does_not_rewrite_longer_org_ids(self):
        rewritten, changes = NOC_BUILDER.rewrite_org_links(
            "/explore?orgId=10&view=one",
            1,
            7,
        )
        self.assertEqual(rewritten, "/explore?orgId=10&view=one")
        self.assertEqual(changes, 0)

    def test_noc_builder_refuses_main_org_or_unscoped_dashboard(self):
        with self.assertRaisesRegex(
            DASHBOARD_API.DashboardApiError,
            "greater than one",
        ):
            NOC_BUILDER.build_capture(capture(), 1)
        with self.assertRaisesRegex(
            DASHBOARD_API.DashboardApiError,
            "no main-organization drilldown",
        ):
            NOC_BUILDER.build_capture(capture(), 2)

    def test_query_verifier_supports_named_and_indexed_row_fields(self):
        query = {
            "rawSql": (
                "SELECT * WHERE level = '${__data.fields.severity}' "
                "AND device = '${__data.fields[0]}'"
            )
        }
        self.assertEqual(
            QUERY_VERIFIER.row_field_markers(query),
            (
                ("${__data.fields.severity}", "severity"),
                ("${__data.fields[0]}", 0),
            ),
        )

    def test_query_verifier_refuses_unresolved_indexed_row_field(self):
        query = {
            "refId": "A",
            "rawSql": (
                "SELECT '${__data.fields.incident_id}', "
                "'${__data.fields[0]}'"
            ),
        }
        with self.assertRaisesRegex(
            DASHBOARD_API.DashboardApiError,
            "unresolved row-field marker",
        ):
            QUERY_VERIFIER.drilldown_payload(
                query,
                {"${__data.fields.incident_id}": "incident-example"},
                1,
                2,
            )


if __name__ == "__main__":
    unittest.main()
