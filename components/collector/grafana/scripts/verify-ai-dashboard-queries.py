#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from dashboard_api import DashboardApi, DashboardApiError, load_password


DATASOURCE_TYPE = "grafana-clickhouse-datasource"


def query_payload(
    panel_query: dict[str, Any],
    start_ms: int,
    end_ms: int,
    variables: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    query = panel_query["spec"]["query"]
    datasource_uid = query["datasource"]["name"]
    ref_id = panel_query["spec"]["refId"]
    plugin_spec = dict(query["spec"])
    raw_sql = plugin_spec.get("rawSql")
    if variables and isinstance(raw_sql, str):
        for name, value in variables.items():
            literal = "'" + value.replace("'", "''") + "'"
            raw_sql = raw_sql.replace(
                "${" + name + ":sqlstring}", literal
            )
        if "${" in raw_sql:
            raise DashboardApiError(
                "dashboard query has an unresolved template variable"
            )
        plugin_spec["rawSql"] = raw_sql
    plugin_spec.update(
        {
            "datasource": {
                "type": DATASOURCE_TYPE,
                "uid": datasource_uid,
            },
            "intervalMs": 60_000,
            "maxDataPoints": 1_000,
            "refId": ref_id,
        }
    )
    return ref_id, {
        "from": str(start_ms),
        "to": str(end_ms),
        "queries": [plugin_spec],
    }


def response_counts(response: object, ref_id: str) -> tuple[int, int]:
    if not isinstance(response, dict):
        raise DashboardApiError("datasource response is not an object")
    results = response.get("results")
    if not isinstance(results, dict):
        raise DashboardApiError("datasource response has no results object")
    result = results.get(ref_id)
    if not isinstance(result, dict):
        raise DashboardApiError("datasource response is missing the panel result")
    if result.get("error"):
        raise DashboardApiError("datasource response reports a query error")
    frames = result.get("frames")
    if not isinstance(frames, list):
        raise DashboardApiError("datasource response has no frames array")

    row_count = 0
    for frame in frames:
        if not isinstance(frame, dict):
            raise DashboardApiError("datasource response frame is invalid")
        data = frame.get("data") or {}
        values = data.get("values") or []
        if values:
            if not isinstance(values[0], list):
                raise DashboardApiError("datasource response values are invalid")
            row_count = max(row_count, len(values[0]))
    return len(frames), row_count


def response_field_values(
    response: object,
    ref_id: str,
    field_name: str,
) -> list[str]:
    if not isinstance(response, dict):
        raise DashboardApiError("datasource response is not an object")
    result = (response.get("results") or {}).get(ref_id)
    if not isinstance(result, dict):
        raise DashboardApiError("datasource response is missing the panel result")
    values: list[str] = []
    for frame in result.get("frames") or []:
        fields = ((frame.get("schema") or {}).get("fields") or [])
        columns = ((frame.get("data") or {}).get("values") or [])
        for index, field in enumerate(fields):
            if field.get("name") != field_name:
                continue
            if index >= len(columns) or not isinstance(columns[index], list):
                raise DashboardApiError("datasource response field values are invalid")
            values.extend(
                str(value)
                for value in columns[index]
                if value is not None and str(value)
            )
    return values


def drilldown_queries(panel: dict[str, Any]) -> list[dict[str, Any]]:
    defaults = (
        panel.get("spec", {})
        .get("vizConfig", {})
        .get("spec", {})
        .get("fieldConfig", {})
        .get("defaults", {})
    )
    links = defaults.get("links") or []
    queries: list[dict[str, Any]] = []
    for link in links:
        parsed = urlsplit(link.get("url", ""))
        parameters = parse_qs(parsed.query)
        panes_values = parameters.get("panes") or []
        if parsed.path != "/explore" or len(panes_values) != 1:
            raise DashboardApiError("dashboard data link is not a single Explore target")
        panes = json.loads(panes_values[0])
        for pane in panes.values():
            pane_queries = pane.get("queries") or []
            if not isinstance(pane_queries, list):
                raise DashboardApiError("Explore data link queries are invalid")
            queries.extend(pane_queries)
    return queries


def drilldown_payload(
    query: dict[str, Any],
    incident_id: str,
    start_ms: int,
    end_ms: int,
) -> tuple[str, dict[str, Any]]:
    prepared = copy.deepcopy(query)
    ref_id = prepared.get("refId", "A")
    raw_sql = prepared.get("rawSql")
    if not isinstance(raw_sql, str):
        raise DashboardApiError("Explore data link has no SQL")
    marker = "${__data.fields.incident_id}"
    if marker not in raw_sql:
        raise DashboardApiError("Explore data link has no incident-ID marker")
    prepared["rawSql"] = raw_sql.replace(
        marker,
        incident_id.replace("'", "''"),
    )
    prepared.update({
        "intervalMs": 60_000,
        "maxDataPoints": 1_000,
        "refId": ref_id,
    })
    return ref_id, {
        "from": str(start_ms),
        "to": str(end_ms),
        "queries": [prepared],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dashboard",
        action="append",
        dest="dashboards",
        type=Path,
        help=(
            "dashboard capture to verify; repeat for multiple AI dashboards"
        ),
    )
    parser.add_argument("--base-url", default="https://127.0.0.1:443")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password-file", required=True, type=Path)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    if args.days < 1 or args.days > 366:
        raise DashboardApiError("days must be between 1 and 366")

    end_ms = int(time.time() * 1_000)
    start_ms = end_ms - args.days * 24 * 60 * 60 * 1_000
    api = DashboardApi(
        base_url=args.base_url,
        username=args.username,
        password=load_password(args.password_file),
    )

    dashboards = args.dashboards or [
        Path(__file__).resolve().parents[1]
        / "dashboards/ai-incident-analysis.json"
    ]
    for dashboard in dashboards:
        document = json.loads(dashboard.read_text(encoding="utf-8"))
        variables = {}
        for variable in (document.get("spec") or {}).get("variables") or []:
            spec = variable.get("spec") or {}
            name = spec.get("name")
            current = spec.get("current") or {}
            value = current.get("value")
            if isinstance(name, str) and isinstance(value, str):
                variables[name] = value
        elements = (document.get("spec") or {}).get("elements")
        if not isinstance(elements, dict) or not elements:
            raise DashboardApiError(f"{dashboard.name}: dashboard has no panels")
        linked_panels = 0
        verified_drilldowns = 0
        for panel_name in sorted(elements):
            panel = elements[panel_name]
            queries = panel["spec"]["data"]["spec"]["queries"]
            if len(queries) != 1:
                raise DashboardApiError(
                    f"{dashboard.name}/{panel_name}: expected one query"
                )
            ref_id, payload = query_payload(
                queries[0], start_ms, end_ms, variables
            )
            status, response = api.request("POST", "/api/ds/query", payload)
            if status != 200:
                raise DashboardApiError(
                    f"{dashboard.name}/{panel_name}: datasource status={status}"
                )
            frame_count, row_count = response_counts(response, ref_id)
            print(
                f"{dashboard.name}/{panel_name} frames={frame_count} "
                f"rows={row_count} query=PASS"
            )
            links = drilldown_queries(panel)
            if not links:
                continue
            linked_panels += 1
            incident_ids = response_field_values(response, ref_id, "incident_id")
            if not incident_ids:
                print(f"{dashboard.name}/{panel_name} drilldown=SKIP_EMPTY")
                continue
            for link_query in links:
                link_ref_id, link_payload = drilldown_payload(
                    link_query,
                    incident_ids[0],
                    start_ms,
                    end_ms,
                )
                link_status, link_response = api.request(
                    "POST", "/api/ds/query", link_payload
                )
                if link_status != 200:
                    raise DashboardApiError(
                        f"{dashboard.name}/{panel_name}: drilldown status={link_status}"
                    )
                link_frames, link_rows = response_counts(
                    link_response, link_ref_id
                )
                verified_drilldowns += 1
                print(
                    f"{dashboard.name}/{panel_name} "
                    f"drilldown_frames={link_frames} "
                    f"drilldown_rows={link_rows} drilldown=PASS"
                )
        if linked_panels and not verified_drilldowns:
            raise DashboardApiError(
                f"{dashboard.name}: linked panels have no sample incident"
            )

    print(
        "GRAFANA_AI_DASHBOARD_QUERIES=PASS "
        f"dashboards={len(dashboards)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DashboardApiError, KeyError, TypeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
