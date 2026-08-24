#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone

try:
    from runtime_config import load_runtime_config
except ModuleNotFoundError as exc:
    if exc.name != "runtime_config":
        raise
    load_runtime_config = None


DB = (
    load_runtime_config().database_path
    if load_runtime_config is not None
    else None
)
PROJECTION_VERSION = 4
CURSOR_KEY = "normalized_projection_v1_last_event_id"
BATCH_SIZE = 5000

EXPECTED_KEYS = frozenset(
    {
        "schema_version",
        "timestamp",
        "ingest_timestamp",
        "device_timestamp",
        "hostname",
        "source_ip",
        "source_port",
        "facility",
        "severity",
        "appname",
        "message",
        "raw_message",
        "parse_status",
        "vendor",
        "os_family",
        "event_code",
        "event_family",
        "protocol",
        "signal_type",
        "entity_type",
        "entity_key",
        "state",
        "repeat_count",
        "attention_eligible",
        "suppression_rule_id",
        "attributes",
    }
)

TEXT_FIELDS = frozenset(
    {
        "timestamp",
        "ingest_timestamp",
        "hostname",
        "source_ip",
        "facility",
        "severity",
        "appname",
        "message",
        "raw_message",
        "parse_status",
        "vendor",
        "os_family",
        "event_code",
        "event_family",
        "protocol",
        "signal_type",
        "entity_type",
        "entity_key",
        "state",
    }
)

REQUIRED_TABLE_COLUMNS = {
    "agent_state": {"key", "value", "updated_at"},
    "recent_events": {"id", "event_json"},
    "suppression_rules": {
        "id",
        "rule_type",
        "pattern",
        "enabled",
    },
    "event_enrichment": {
        "event_id",
        "event_code",
        "family",
        "device",
        "entity_type",
        "entity_key",
        "state",
        "attention_eligible",
        "suppression_rule_id",
        "classified_at",
        "repeat_count",
        "classification_version",
        "vendor_hint",
        "protocol",
        "signal_type",
        "attributes_json",
    },
}


class ProjectionError(ValueError):
    pass


def validate_database_contract(connection: sqlite3.Connection) -> None:
    for table, expected in REQUIRED_TABLE_COLUMNS.items():
        observed = {
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if not expected <= observed:
            raise ProjectionError("GX10 database projection schema differs")


def load_suppression_rules(
    connection: sqlite3.Connection,
) -> list[tuple[int, str, str, re.Pattern[str] | None]]:
    rules = []
    for rule_id, rule_type, pattern in connection.execute(
        """
        SELECT id, rule_type, pattern
        FROM suppression_rules
        WHERE enabled = 1
        ORDER BY id
        """
    ):
        if (
            not isinstance(rule_id, int)
            or rule_type
            not in {
                "event_code_exact",
                "event_code_prefix",
                "message_regex",
            }
            or not isinstance(pattern, str)
        ):
            raise ProjectionError("invalid enabled suppression rule")
        try:
            compiled = (
                re.compile(pattern)
                if rule_type == "message_regex"
                else None
            )
        except re.error as exc:
            raise ProjectionError(
                "invalid enabled suppression regular expression"
            ) from exc
        rules.append((rule_id, rule_type, pattern, compiled))
    return rules


def validate_normalized_event(value: object) -> dict | None:
    if not isinstance(value, dict):
        raise ProjectionError("event_json is not a JSON object")

    if "schema_version" not in value:
        return None

    if value.get("schema_version") != 1:
        raise ProjectionError("unsupported normalized schema version")

    if set(value) != EXPECTED_KEYS:
        raise ProjectionError("normalized event key contract differs")

    if any(not isinstance(value.get(field), str) for field in TEXT_FIELDS):
        raise ProjectionError("normalized text field has invalid type")

    device_timestamp = value.get("device_timestamp")
    if device_timestamp is not None and not isinstance(
        device_timestamp, str
    ):
        raise ProjectionError("normalized device timestamp has invalid type")

    source_port = value.get("source_port")
    if (
        not isinstance(source_port, int)
        or isinstance(source_port, bool)
        or not 0 <= source_port <= 65535
    ):
        raise ProjectionError("normalized source port is invalid")

    repeat_count = value.get("repeat_count")
    if (
        not isinstance(repeat_count, int)
        or isinstance(repeat_count, bool)
        or repeat_count < 1
    ):
        raise ProjectionError("normalized repeat count is invalid")

    if not isinstance(value.get("attention_eligible"), bool):
        raise ProjectionError("normalized attention policy is invalid")

    suppression_rule_id = value.get("suppression_rule_id")
    if suppression_rule_id is not None and not isinstance(
        suppression_rule_id, str
    ):
        raise ProjectionError(
            "normalized suppression identifier has invalid type"
        )

    if not isinstance(value.get("attributes"), dict):
        raise ProjectionError("normalized attributes field is invalid")

    return value


def local_suppression_rule(
    event: dict,
    rules: list[tuple[int, str, str, re.Pattern[str] | None]],
) -> int | None:
    event_code = event["event_code"]
    message = event["message"]
    for rule_id, rule_type, pattern, compiled in rules:
        if rule_type == "event_code_exact" and event_code == pattern:
            return rule_id
        if rule_type == "event_code_prefix" and event_code.startswith(
            pattern
        ):
            return rule_id
        if (
            rule_type == "message_regex"
            and compiled is not None
            and compiled.search(message)
        ):
            return rule_id
    return None


def project_normalized_event(
    event: dict,
    rules: list[tuple[int, str, str, re.Pattern[str] | None]],
    projected_at: str,
) -> dict:
    local_rule_id = local_suppression_rule(event, rules)
    attention_eligible = bool(event["attention_eligible"])
    if local_rule_id is not None:
        attention_eligible = False

    attributes = dict(event["attributes"])
    upstream_rule_id = event["suppression_rule_id"]
    if upstream_rule_id is not None:
        reserved = "upstream_suppression_rule_id"
        if reserved in attributes:
            raise ProjectionError(
                "normalized attributes use a reserved projection key"
            )
        attributes[reserved] = upstream_rule_id

    return {
        "event_code": event["event_code"],
        "family": event["event_family"],
        "device": event["hostname"] or event["source_ip"] or "unknown",
        "entity_type": (
            None
            if event["entity_type"] in {"", "unknown"}
            else event["entity_type"]
        ),
        "entity_key": event["entity_key"] or None,
        "state": event["state"] or None,
        "attention_eligible": int(attention_eligible),
        "suppression_rule_id": local_rule_id,
        "classified_at": projected_at,
        "repeat_count": event["repeat_count"],
        "classification_version": PROJECTION_VERSION,
        "vendor_hint": event["vendor"],
        "protocol": event["protocol"],
        "signal_type": event["signal_type"],
        "attributes_json": json.dumps(
            attributes,
            separators=(",", ":"),
            sort_keys=True,
        ),
    }


def current_cursor(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT value FROM agent_state WHERE key = ?",
        (CURSOR_KEY,),
    ).fetchone()
    if row is None:
        return 0
    try:
        value = int(row[0])
    except (TypeError, ValueError) as exc:
        raise ProjectionError("normalized projection cursor is invalid") from exc
    if value < 0 or str(value) != row[0]:
        raise ProjectionError("normalized projection cursor is invalid")
    return value


def project_batch(
    connection: sqlite3.Connection,
    rules: list[tuple[int, str, str, re.Pattern[str] | None]],
) -> tuple[int, int, int]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        cursor = current_cursor(connection)
        rows = connection.execute(
            """
            SELECT id, event_json
            FROM recent_events
            WHERE id > ?
            ORDER BY id
            LIMIT ?
            """,
            (cursor, BATCH_SIZE),
        ).fetchall()
        if not rows:
            connection.commit()
            return 0, 0, 0

        projected_at = datetime.now(timezone.utc).isoformat()
        projected = 0
        suppressed = 0
        for event_id, event_json in rows:
            try:
                decoded = json.loads(event_json)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ProjectionError("event_json is invalid") from exc
            event = validate_normalized_event(decoded)
            if event is None:
                continue
            values = project_normalized_event(
                event,
                rules,
                projected_at,
            )
            statement = connection.execute(
                """
                INSERT INTO event_enrichment (
                    event_id,
                    event_code,
                    family,
                    device,
                    entity_type,
                    entity_key,
                    state,
                    attention_eligible,
                    suppression_rule_id,
                    classified_at,
                    repeat_count,
                    classification_version,
                    vendor_hint,
                    protocol,
                    signal_type,
                    attributes_json
                ) VALUES (
                    :event_id,
                    :event_code,
                    :family,
                    :device,
                    :entity_type,
                    :entity_key,
                    :state,
                    :attention_eligible,
                    :suppression_rule_id,
                    :classified_at,
                    :repeat_count,
                    :classification_version,
                    :vendor_hint,
                    :protocol,
                    :signal_type,
                    :attributes_json
                )
                ON CONFLICT(event_id) DO UPDATE SET
                    event_code = excluded.event_code,
                    family = excluded.family,
                    device = excluded.device,
                    entity_type = excluded.entity_type,
                    entity_key = excluded.entity_key,
                    state = excluded.state,
                    attention_eligible = excluded.attention_eligible,
                    suppression_rule_id = excluded.suppression_rule_id,
                    classified_at = excluded.classified_at,
                    repeat_count = excluded.repeat_count,
                    classification_version = excluded.classification_version,
                    vendor_hint = excluded.vendor_hint,
                    protocol = excluded.protocol,
                    signal_type = excluded.signal_type,
                    attributes_json = excluded.attributes_json
                WHERE event_enrichment.classification_version <=
                    excluded.classification_version
                """,
                {"event_id": event_id, **values},
            )
            if statement.rowcount != 1:
                raise ProjectionError(
                    "newer enrichment state blocks canonical projection"
                )
            projected += 1
            suppressed += values["attention_eligible"] == 0

        last_event_id = rows[-1][0]
        connection.execute(
            """
            INSERT INTO agent_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (CURSOR_KEY, str(last_event_id), projected_at),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return len(rows), projected, suppressed


def main(database_path=None) -> int:
    selected_database = database_path if database_path is not None else DB
    if selected_database is None:
        print(
            "ERROR: database path requires runtime_config or explicit input",
            file=sys.stderr,
        )
        return 1
    connection = sqlite3.connect(selected_database)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        validate_database_contract(connection)
        rules = load_suppression_rules(connection)
        scanned = 0
        projected = 0
        suppressed = 0
        while True:
            batch_scanned, batch_projected, batch_suppressed = (
                project_batch(connection, rules)
            )
            if batch_scanned == 0:
                break
            scanned += batch_scanned
            projected += batch_projected
            suppressed += batch_suppressed
        print(
            "NORMALIZED_PROJECTION "
            f"scanned={scanned} "
            f"projected={projected} "
            f"suppressed={suppressed} "
            f"version={PROJECTION_VERSION}"
        )
        print("GX10_NORMALIZED_PROJECTION=PASS")
        return 0
    except (OSError, ProjectionError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
