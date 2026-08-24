#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

from dashboard_api import DashboardApi, DashboardApiError, load_password


DATASOURCE_TYPE = "grafana-clickhouse-datasource"


def query_payload(
    panel_query: dict[str, Any],
    start_ms: int,
    end_ms: int,
) -> tuple[str, dict[str, Any]]:
    query = panel_query["spec"]["query"]
    datasource_uid = query["datasource"]["name"]
    ref_id = panel_query["spec"]["refId"]
    plugin_spec = dict(query["spec"])
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
        elements = (document.get("spec") or {}).get("elements")
        if not isinstance(elements, dict) or not elements:
            raise DashboardApiError(f"{dashboard.name}: dashboard has no panels")
        for panel_name in sorted(elements):
            queries = elements[panel_name]["spec"]["data"]["spec"]["queries"]
            if len(queries) != 1:
                raise DashboardApiError(
                    f"{dashboard.name}/{panel_name}: expected one query"
                )
            ref_id, payload = query_payload(queries[0], start_ms, end_ms)
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
