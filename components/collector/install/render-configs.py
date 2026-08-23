#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import re
import stat
import sys


ROOT = Path(__file__).resolve().parents[3]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require_nonempty(name: str) -> str:
    value = os.environ.get(name)

    if value is None or value == "":
        fail(f"required environment variable is not set: {name}")

    return value


def read_secret(path_text: str, label: str) -> str:
    path = Path(path_text)
    fd = -1

    try:
        fd = os.open(
            path,
            os.O_RDONLY | os.O_CLOEXEC,
        )

        metadata = os.fstat(fd)

        if not stat.S_ISREG(metadata.st_mode):
            fail(
                f"{label} is not a regular file"
            )

        mode = stat.S_IMODE(
            metadata.st_mode
        )

        if mode & 0o077:
            fail(
                f"{label} must not be "
                "group/world accessible"
            )

        handle = os.fdopen(
            fd,
            "r",
            encoding="utf-8",
            errors="strict",
        )
        fd = -1

        with handle:
            value = handle.read()

    except (OSError, UnicodeError) as exc:
        fail(f"cannot read {label}: {exc}")

    finally:
        if fd >= 0:
            os.close(fd)

    value = value.rstrip("\r\n")

    if not value:
        fail(f"{label} is empty")

    if "\x00" in value:
        fail(f"{label} contains a NUL byte")

    return value


def write_private_text(
    destination: Path,
    text: str,
) -> None:
    fd = -1

    try:
        fd = os.open(
            destination,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_TRUNC
            | os.O_CLOEXEC,
            0o600,
        )

        os.fchmod(
            fd,
            0o600,
        )

        handle = os.fdopen(
            fd,
            "w",
            encoding="utf-8",
            errors="strict",
        )
        fd = -1

        with handle:
            handle.write(text)

    except OSError as exc:
        fail(
            "cannot write private rendered file "
            f"{destination}: {exc}"
        )

    finally:
        if fd >= 0:
            os.close(fd)


def replace_required(
    text: str,
    marker: str,
    value: str,
    minimum_count: int,
) -> str:
    if minimum_count < 1:
        fail(
            f"{marker}: minimum occurrence count must be at least 1"
        )

    count = text.count(marker)

    if count < minimum_count:
        fail(
            f"{marker}: expected at least {minimum_count} occurrence(s), "
            f"found {count}"
        )

    return text.replace(marker, value)


def assert_no_markers(text: str, label: str) -> None:
    markers = sorted(
        set(
            re.findall(
                r"__[A-Z0-9_]+__",
                text,
            )
        )
    )

    env_markers = sorted(
        set(
            re.findall(
                r"\$\{[A-Z0-9_]+\}",
                text,
            )
        )
    )

    remaining = markers + env_markers

    if remaining:
        fail(
            f"{label} has unresolved placeholders: "
            + ", ".join(remaining)
        )


def sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render_vector(destination: Path) -> None:
    source = (
        ROOT
        / "components/collector/vector/vector.yaml"
    )

    text = source.read_text(
        encoding="utf-8",
        errors="strict",
    )

    replacements = {
        "${SYSLOG_UDP_ADDRESS}":
            require_nonempty("SYSLOG_UDP_ADDRESS"),
        "${SYSLOG_TCP_ADDRESS}":
            require_nonempty("SYSLOG_TCP_ADDRESS"),
        "${CLICKHOUSE_ENDPOINT}":
            require_nonempty("CLICKHOUSE_ENDPOINT"),
        "${CLICKHOUSE_USER}":
            require_nonempty("CLICKHOUSE_USER"),
    }

    for marker, value in replacements.items():
        text = replace_required(
            text,
            marker,
            value,
            1,
        )

    assert_no_markers(
        text,
        "Vector configuration",
    )

    destination.write_text(
        text,
        encoding="utf-8",
    )


def render_clickhouse_access(destination: Path) -> None:
    source = (
        ROOT
        / "components/collector/clickhouse/"
        "40-access-control.sql.in"
    )

    text = source.read_text(
        encoding="utf-8",
        errors="strict",
    )

    grafana_password = read_secret(
        require_nonempty(
            "GRAFANA_READER_PASSWORD_FILE"
        ),
        "Grafana reader password file",
    )

    vector_password = read_secret(
        require_nonempty(
            "VECTOR_INGEST_PASSWORD_FILE"
        ),
        "Vector ingest password file",
    )

    text = replace_required(
        text,
        "__GRAFANA_READER_PASSWORD__",
        sql_string(grafana_password),
        1,
    )

    text = replace_required(
        text,
        "__VECTOR_INGEST_PASSWORD__",
        sql_string(vector_password),
        1,
    )

    assert_no_markers(
        text,
        "ClickHouse access SQL",
    )

    write_private_text(
        destination,
        text,
    )


def render_grafana_datasources(
    destination: Path,
) -> None:
    source = (
        ROOT
        / "components/collector/grafana/"
        "provisioning/datasources/"
        "clickhouse.yaml.in"
    )

    text = source.read_text(
        encoding="utf-8",
        errors="strict",
    )

    host = require_nonempty(
        "CLICKHOUSE_HOST"
    )

    password = read_secret(
        require_nonempty(
            "GRAFANA_READER_PASSWORD_FILE"
        ),
        "Grafana reader password file",
    )

    text = replace_required(
        text,
        "__CLICKHOUSE_HOST__",
        host,
        text.count("__CLICKHOUSE_HOST__"),
    )

    text = replace_required(
        text,
        "__GRAFANA_READER_PASSWORD__",
        json.dumps(password),
        text.count(
            "__GRAFANA_READER_PASSWORD__"
        ),
    )

    assert_no_markers(
        text,
        "Grafana datasource configuration",
    )

    write_private_text(
        destination,
        text,
    )


def render_grafana_https(destination: Path) -> None:
    source = (
        ROOT
        / "components/collector/grafana/"
        "systemd/grafana-server.service.d/"
        "https.conf.in"
    )

    text = source.read_text(
        encoding="utf-8",
        errors="strict",
    )

    host = require_nonempty(
        "GRAFANA_PUBLIC_HOST"
    )

    text = replace_required(
        text,
        "__GRAFANA_PUBLIC_HOST__",
        host,
        1,
    )

    assert_no_markers(
        text,
        "Grafana HTTPS override",
    )

    destination.write_text(
        text,
        encoding="utf-8",
    )


def render_certbot_hook(destination: Path) -> None:
    source = (
        ROOT
        / "components/collector/certbot/"
        "renewal-hooks/deploy/"
        "10-grafana-cert.in"
    )

    text = source.read_text(
        encoding="utf-8",
        errors="strict",
    )

    cert_name = require_nonempty(
        "CERT_NAME"
    )

    text = replace_required(
        text,
        "__CERT_NAME__",
        cert_name,
        1,
    )

    assert_no_markers(
        text,
        "Certbot deploy hook",
    )

    destination.write_text(
        text,
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    output = args.output_dir

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    render_vector(
        output / "vector.yaml"
    )

    render_clickhouse_access(
        output / "40-access-control.sql"
    )

    render_grafana_datasources(
        output / "clickhouse-datasources.yaml"
    )

    render_grafana_https(
        output / "grafana-https.conf"
    )

    render_certbot_hook(
        output / "10-grafana-cert"
    )

    os.chmod(
        output / "10-grafana-cert",
        0o700,
    )

    print("COLLECTOR_CONFIG_RENDER=PASS")


if __name__ == "__main__":
    main()
