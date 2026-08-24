#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dashboard_api import (
    DashboardApi,
    DashboardApiError,
    capture_matches,
    load_captures,
    load_password,
    resource_identity,
    resource_path,
)


EXPECTED_DASHBOARD_COUNT = 5


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dashboard-dir",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "dashboards"
        ),
    )

    parser.add_argument(
        "--base-url",
        default="https://127.0.0.1:443",
    )

    parser.add_argument(
        "--username",
        default="admin",
    )

    parser.add_argument(
        "--password-file",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    captures = load_captures(
        args.dashboard_dir
    )

    if len(captures) != \
            EXPECTED_DASHBOARD_COUNT:
        raise DashboardApiError(
            "expected exactly "
            f"{EXPECTED_DASHBOARD_COUNT} "
            "dashboard captures"
        )

    password = load_password(
        args.password_file
    )

    api = DashboardApi(
        base_url=args.base_url,
        username=args.username,
        password=password,
    )

    for path, captured in captures:
        namespace, name = (
            resource_identity(
                captured
            )
        )

        status, live = api.request(
            "GET",
            resource_path(
                namespace,
                name,
            ),
        )

        if status != 200:
            raise DashboardApiError(
                f"{path.name}: "
                f"GET status={status}"
            )

        if not isinstance(
            live,
            dict,
        ):
            raise DashboardApiError(
                f"{path.name}: "
                "invalid API response"
            )

        matches, reason = capture_matches(
            live,
            captured,
        )

        if not matches:
            raise DashboardApiError(
                f"{path.name}: {reason}"
            )

        print(
            f"{path.name} "
            "api_resource=present "
            "spec_exact_match=yes"
        )

    print(
        "GRAFANA_DASHBOARD_VERIFY=PASS"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DashboardApiError as exc:
        print(
            f"FAIL: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
