#!/usr/bin/env python3

from __future__ import annotations

import base64
import ipaddress
import json
from pathlib import Path
import ssl
import stat
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


API_VERSION = "dashboard.grafana.app/v2"
KIND = "Dashboard"


class DashboardApiError(RuntimeError):
    pass


def load_password(path: Path) -> str:
    if not path.is_file():
        raise DashboardApiError(
            f"password file does not exist: {path}"
        )

    mode = stat.S_IMODE(
        path.stat().st_mode
    )

    if mode & 0o077:
        raise DashboardApiError(
            "password file must not be "
            "group/world accessible"
        )

    password = path.read_text(
        encoding="utf-8",
        errors="strict",
    ).rstrip("\r\n")

    if not password:
        raise DashboardApiError(
            "password file is empty"
        )

    if "\n" in password or "\r" in password:
        raise DashboardApiError(
            "password must be one line"
        )

    return password


def validate_base_url(
    base_url: str,
) -> str:
    parsed = urlsplit(base_url)

    if parsed.scheme != "https":
        raise DashboardApiError(
            "Grafana base URL must use HTTPS"
        )

    if parsed.username or parsed.password:
        raise DashboardApiError(
            "credentials must not appear in URL"
        )

    hostname = parsed.hostname or ""

    if hostname != "localhost":
        try:
            address = ipaddress.ip_address(
                hostname
            )
        except ValueError as exc:
            raise DashboardApiError(
                "Grafana API connection must use "
                "localhost or a loopback address"
            ) from exc

        if not address.is_loopback:
            raise DashboardApiError(
                "Grafana API connection must use "
                "a loopback address"
            )

    return base_url.rstrip("/")


def load_captures(
    dashboard_dir: Path,
) -> list[tuple[Path, dict[str, Any]]]:
    captures = []

    for path in sorted(
        dashboard_dir.glob("*.json")
    ):
        document = json.loads(
            path.read_text(
                encoding="utf-8",
                errors="strict",
            )
        )

        if document.get("apiVersion") != API_VERSION:
            raise DashboardApiError(
                f"{path.name}: unexpected apiVersion"
            )

        if document.get("kind") != KIND:
            raise DashboardApiError(
                f"{path.name}: unexpected kind"
            )

        metadata = (
            document.get("metadata")
            or {}
        )

        if not metadata.get("name"):
            raise DashboardApiError(
                f"{path.name}: metadata.name missing"
            )

        if "spec" not in document:
            raise DashboardApiError(
                f"{path.name}: spec missing"
            )

        if "status" not in document:
            raise DashboardApiError(
                f"{path.name}: status missing"
            )

        captures.append(
            (
                path,
                document,
            )
        )

    if not captures:
        raise DashboardApiError(
            "no dashboard captures found"
        )

    return captures


def clean_payload(
    captured: dict[str, Any],
) -> dict[str, Any]:
    metadata = (
        captured.get("metadata")
        or {}
    )

    clean_metadata: dict[str, Any] = {
        "name": metadata["name"],
        "namespace": metadata.get(
            "namespace",
            "default",
        ),
    }

    for key in [
        "annotations",
        "labels",
    ]:
        if key in metadata:
            clean_metadata[key] = metadata[key]

    return {
        "apiVersion": captured["apiVersion"],
        "kind": captured["kind"],
        "metadata": clean_metadata,
        "spec": captured["spec"],
        "status": captured["status"],
    }


def resource_identity(
    captured: dict[str, Any],
) -> tuple[str, str]:
    metadata = (
        captured.get("metadata")
        or {}
    )

    return (
        str(
            metadata.get(
                "namespace",
                "default",
            )
        ),
        str(metadata["name"]),
    )


def collection_path(
    namespace: str,
) -> str:
    return (
        "/apis/dashboard.grafana.app/v2/"
        "namespaces/"
        + quote(
            namespace,
            safe="",
        )
        + "/dashboards"
    )


def resource_path(
    namespace: str,
    name: str,
) -> str:
    return (
        collection_path(namespace)
        + "/"
        + quote(
            name,
            safe="",
        )
    )


def capture_matches(
    live: dict[str, Any],
    captured: dict[str, Any],
) -> tuple[bool, str]:
    if live.get("apiVersion") != \
            captured.get("apiVersion"):
        return (
            False,
            "apiVersion differs",
        )

    if live.get("kind") != \
            captured.get("kind"):
        return (
            False,
            "kind differs",
        )

    live_metadata = (
        live.get("metadata")
        or {}
    )

    captured_metadata = (
        captured.get("metadata")
        or {}
    )

    for key in [
        "name",
        "namespace",
    ]:
        live_value = live_metadata.get(
            key
        )

        captured_value = captured_metadata.get(
            key
        )

        if key == "namespace":
            live_value = (
                live_value
                or "default"
            )

            captured_value = (
                captured_value
                or "default"
            )

        if live_value != captured_value:
            return (
                False,
                f"metadata.{key} differs",
            )

    # Grafana may add server-owned annotations or labels when a
    # native resource is created. A portable capture that omits
    # either field intentionally leaves it server-owned. Captures
    # that include the field still require an exact match.
    for key in [
        "annotations",
        "labels",
    ]:
        if key not in captured_metadata:
            continue

        if live_metadata.get(key) != \
                captured_metadata.get(key):
            return (
                False,
                f"metadata.{key} differs",
            )

    if live.get("spec") != \
            captured.get("spec"):
        return (
            False,
            "spec differs",
        )

    return (
        True,
        "",
    )


class DashboardApi:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        self.base_url = validate_base_url(
            base_url
        )

        if not username:
            raise DashboardApiError(
                "Grafana username is empty"
            )

        raw_auth = (
            username
            + ":"
            + password
        ).encode("utf-8")

        self.authorization = (
            "Basic "
            + base64.b64encode(
                raw_auth
            ).decode("ascii")
        )

        self.context = (
            ssl._create_unverified_context()
        )

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any] | None]:
        headers = {
            "Accept": "application/json",
            "Authorization": self.authorization,
        }

        body = None

        if payload is not None:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

            headers["Content-Type"] = (
                "application/json"
            )

        request = Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(
                request,
                context=self.context,
                timeout=30,
            ) as response:
                status = response.status
                raw = response.read()

        except HTTPError as exc:
            status = exc.code
            raw = exc.read()

        except URLError as exc:
            raise DashboardApiError(
                "Grafana API request failed"
            ) from exc

        if not raw:
            return (
                status,
                None,
            )

        try:
            document = json.loads(
                raw.decode(
                    "utf-8",
                    errors="strict",
                )
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            raise DashboardApiError(
                f"Grafana returned non-JSON "
                f"response with status {status}"
            )

        return (
            status,
            document,
        )
