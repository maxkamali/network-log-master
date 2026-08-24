#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dashboard_api import (
    DashboardApi,
    DashboardApiError,
    capture_matches,
    clean_payload,
    collection_path,
    load_captures,
    load_password,
    resource_identity,
    resource_path,
)


EXPECTED_DASHBOARD_COUNT = 6


def require_matching_response(
    label: str,
    response: object,
    captured: dict,
) -> None:
    if not isinstance(
        response,
        dict,
    ):
        raise DashboardApiError(
            f"{label}: invalid API response"
        )

    matches, reason = capture_matches(
        response,
        captured,
    )

    if not matches:
        raise DashboardApiError(
            f"{label}: API response {reason}"
        )


def verify_persisted(
    api: DashboardApi,
    path: Path,
    captured: dict,
) -> None:
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
            f"post-restore GET status={status}"
        )

    require_matching_response(
        path.name,
        live,
        captured,
    )


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

    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "replace an existing dashboard "
            "only when its captured contract differs"
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "use Grafana dryRun=All for API writes"
        ),
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

        resource = resource_path(
            namespace,
            name,
        )

        status, live = api.request(
            "GET",
            resource,
        )

        if status == 200:
            if not isinstance(
                live,
                dict,
            ):
                raise DashboardApiError(
                    f"{path.name}: "
                    "invalid GET response"
                )

            matches, reason = (
                capture_matches(
                    live,
                    captured,
                )
            )

            if matches:
                print(
                    f"{path.name} "
                    "action=unchanged "
                    "spec_exact_match=yes"
                )
                continue

            if not args.replace:
                raise DashboardApiError(
                    f"{path.name}: "
                    f"existing dashboard differs: "
                    f"{reason}; "
                    "refusing replacement without "
                    "--replace"
                )

            payload = clean_payload(
                captured
            )

            put_path = resource

            if args.dry_run:
                put_path += "?dryRun=All"

            put_status, response = (
                api.request(
                    "PUT",
                    put_path,
                    payload,
                )
            )

            if put_status not in {
                200,
                201,
            }:
                raise DashboardApiError(
                    f"{path.name}: "
                    "PUT status="
                    f"{put_status}"
                )

            require_matching_response(
                path.name,
                response,
                captured,
            )

            if args.dry_run:
                after_status, after = (
                    api.request(
                        "GET",
                        resource,
                    )
                )

                if after_status != 200:
                    raise DashboardApiError(
                        f"{path.name}: "
                        "resource disappeared "
                        "after dry-run PUT"
                    )

                if not isinstance(
                    after,
                    dict,
                ):
                    raise DashboardApiError(
                        f"{path.name}: "
                        "invalid post-dry-run "
                        "GET response"
                    )

                after_matches, _ = (
                    capture_matches(
                        after,
                        live,
                    )
                )

                if not after_matches:
                    raise DashboardApiError(
                        f"{path.name}: "
                        "dry-run PUT altered "
                        "persisted resource"
                    )

                print(
                    f"{path.name} "
                    "action=dryrun-replace "
                    "persisted_change=no"
                )
            else:
                verify_persisted(
                    api,
                    path,
                    captured,
                )

                print(
                    f"{path.name} "
                    "action=replaced "
                    "spec_exact_match=yes"
                )

            continue

        if status != 404:
            raise DashboardApiError(
                f"{path.name}: "
                f"GET status={status}"
            )

        payload = clean_payload(
            captured
        )

        post_path = collection_path(
            namespace
        )

        if args.dry_run:
            post_path += "?dryRun=All"

        post_status, response = (
            api.request(
                "POST",
                post_path,
                payload,
            )
        )

        if post_status not in {
            200,
            201,
            202,
        }:
            raise DashboardApiError(
                f"{path.name}: "
                "POST status="
                f"{post_status}"
            )

        require_matching_response(
            path.name,
            response,
            captured,
        )

        if args.dry_run:
            after_status, _ = api.request(
                "GET",
                resource,
            )

            if after_status != 404:
                raise DashboardApiError(
                    f"{path.name}: "
                    "dry-run create persisted"
                )

            print(
                f"{path.name} "
                "action=dryrun-create "
                "persisted_change=no"
            )
        else:
            verify_persisted(
                api,
                path,
                captured,
            )

            print(
                f"{path.name} "
                "action=created "
                "spec_exact_match=yes"
            )

    if args.dry_run:
        print(
            "GRAFANA_DASHBOARD_RESTORE_DRYRUN=PASS"
        )
    else:
        print(
            "GRAFANA_DASHBOARD_RESTORE=PASS"
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
