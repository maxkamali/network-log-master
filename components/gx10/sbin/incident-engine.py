#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import sys

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
ENGINE_VERSION = 3
PROJECTION_VERSION = 4
CURSOR_KEY = "incident_engine_v1_last_event_id"
BATCH_SIZE = 1000
CANDIDATE_WINDOW_MS = 15 * 60 * 1000
RECOVERY_QUIET_MS = 5 * 60 * 1000
TRIAGE_RECOVERY_CONFIRM_MS = 15 * 60 * 1000
PROTOCOL_MONITORING_MS = 24 * 60 * 60 * 1000
MONITORED_PROTOCOLS = {"bgp", "ospf", "ospfv3"}
CONTEXT_WINDOWS_MS = {
    "60m": 60 * 60 * 1000,
    "180m": 180 * 60 * 1000,
    "24h": 24 * 60 * 60 * 1000,
}
STATUSES = {"CANDIDATE", "OPEN", "RECOVERING", "RESOLVED"}
ADVERSE_SIGNALS = {
    "state_transition",
    "degradation",
    "protocol_notification",
}
RECOVERY_STATES = {
    "up",
    "established",
    "normal",
    "operational",
    "resolved",
}
IMMEDIATE_OPEN_STATES = {
    "down",
    "disabled",
    "failed",
    "idle",
}
SEVERITY_RANK = {
    "debug": 0,
    "informational": 1,
    "info": 1,
    "notice": 2,
    "warning": 3,
    "warn": 3,
    "error": 4,
    "err": 4,
    "critical": 5,
    "crit": 5,
    "alert": 6,
    "emergency": 7,
    "emerg": 7,
}
ALLOWED_TRANSITIONS = {
    (None, "CANDIDATE"),
    ("CANDIDATE", "OPEN"),
    ("CANDIDATE", "RECOVERING"),
    ("CANDIDATE", "RESOLVED"),
    ("OPEN", "RECOVERING"),
    ("RECOVERING", "OPEN"),
    ("RECOVERING", "RESOLVED"),
}

REQUIRED_COLUMNS = {
    "agent_state": {"key", "value", "updated_at"},
    "recent_events": {
        "id",
        "source_file",
        "record_number",
        "timestamp",
        "timestamp_epoch_ms",
        "severity",
    },
    "event_enrichment": {
        "event_id",
        "event_code",
        "family",
        "entity_type",
        "entity_key",
        "state",
        "attention_eligible",
        "repeat_count",
        "classification_version",
        "protocol",
        "signal_type",
        "attributes_json",
    },
    "incidents": {
        "incident_id",
        "correlation_key",
        "status",
        "event_family",
        "protocol",
        "entity_type",
        "entity_key",
        "severity",
        "first_seen",
        "first_seen_epoch_ms",
        "last_seen",
        "last_seen_epoch_ms",
        "occurrence_count",
        "repeat_count_total",
        "observation_state_changes",
        "last_observation_state",
        "opened_at",
        "recovering_at",
        "resolved_at",
        "last_event_id",
        "context_json",
        "engine_version",
        "created_at",
        "updated_at",
    },
    "incident_evidence": {
        "incident_id",
        "evidence_sequence",
        "event_id",
        "evidence_kind",
        "observed_at",
        "observed_at_epoch_ms",
        "event_code",
        "signal_type",
        "observation_state",
        "repeat_count",
        "attributes_json",
    },
    "incident_transitions": {
        "incident_id",
        "transition_sequence",
        "from_status",
        "to_status",
        "event_id",
        "reason",
        "occurred_at",
        "occurred_at_epoch_ms",
    },
}


class IncidentError(ValueError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def iso_from_epoch(epoch_ms: int) -> str:
    return datetime.fromtimestamp(
        epoch_ms / 1000,
        tz=timezone.utc,
    ).isoformat()


def epoch_from_iso(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise IncidentError("incident recovery timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise IncidentError("incident recovery timestamp is invalid")
    return int(parsed.timestamp() * 1000)


def uses_protocol_monitoring(current: sqlite3.Row) -> bool:
    return any(
        (current[field] or "").casefold() in MONITORED_PROTOCOLS
        for field in ("protocol", "event_family")
    )


def recovery_deadline(current: sqlite3.Row) -> tuple[int, str]:
    if (current["entity_type"] or "").casefold() == "event_signature":
        if not current["recovering_at"]:
            raise IncidentError("triage incident lacks recovery timestamp")
        return (
            epoch_from_iso(current["recovering_at"])
            + TRIAGE_RECOVERY_CONFIRM_MS,
            "triage_recovery_confirmation",
        )
    if uses_protocol_monitoring(current):
        if not current["recovering_at"]:
            raise IncidentError("monitored incident lacks recovery timestamp")
        return (
            epoch_from_iso(current["recovering_at"])
            + PROTOCOL_MONITORING_MS,
            "protocol_monitoring_period",
        )
    return (
        current["last_seen_epoch_ms"] + RECOVERY_QUIET_MS,
        "recovery_quiet_period",
    )


def validate_database_contract(connection: sqlite3.Connection) -> None:
    for table, expected in REQUIRED_COLUMNS.items():
        columns = {
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if not expected <= columns:
            raise IncidentError("incident database schema differs")


def cursor_value(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT value FROM agent_state WHERE key = ?",
        (CURSOR_KEY,),
    ).fetchone()
    if row is None:
        return 0
    try:
        value = int(row[0])
    except (TypeError, ValueError) as exc:
        raise IncidentError("incident cursor is invalid") from exc
    if value < 0 or str(value) != row[0]:
        raise IncidentError("incident cursor is invalid")
    return value


def event_kind(signal_type: str, state: str | None) -> str:
    normalized_state = (state or "").casefold()
    if signal_type == "recovery" or normalized_state in RECOVERY_STATES:
        return "recovery"
    if signal_type in ADVERSE_SIGNALS:
        return "adverse"
    return "supporting"


def correlation_key(row: sqlite3.Row) -> str:
    material = canonical_json(
        [
            "incident-correlation-v1",
            row["family"],
            row["protocol"],
            row["entity_type"],
            row["entity_key"],
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def incident_id(row: sqlite3.Row, key: str) -> str:
    material = canonical_json(
        [
            "incident-instance-v1",
            key,
            row["source_file"],
            row["record_number"],
        ]
    )
    return "inc-v1-" + hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()[:32]


def normalized_severity(value: str | None) -> str:
    text = (value or "").strip().casefold()
    return text if text else "unknown"


def stronger_severity(current: str, candidate: str) -> str:
    current_rank = SEVERITY_RANK.get(current.casefold(), -1)
    candidate_rank = SEVERITY_RANK.get(candidate.casefold(), -1)
    return candidate if candidate_rank > current_rank else current


def validate_event(row: sqlite3.Row) -> None:
    if row["classification_version"] != PROJECTION_VERSION:
        raise IncidentError("incident input projection version differs")
    if not isinstance(row["timestamp_epoch_ms"], int):
        raise IncidentError("incident input timestamp is invalid")
    if not isinstance(row["timestamp"], str) or not row["timestamp"]:
        raise IncidentError("incident input timestamp is invalid")
    try:
        parsed_timestamp = datetime.fromisoformat(
            row["timestamp"].replace("Z", "+00:00")
        )
        if parsed_timestamp.tzinfo is None:
            raise ValueError("timestamp lacks timezone")
        parsed_epoch_ms = int(parsed_timestamp.timestamp() * 1000)
    except (OverflowError, ValueError) as exc:
        raise IncidentError("incident input timestamp is invalid") from exc
    if parsed_epoch_ms != row["timestamp_epoch_ms"]:
        raise IncidentError("incident input timestamp differs from epoch")
    if not isinstance(row["source_file"], str) or not row["source_file"]:
        raise IncidentError("incident source identity is invalid")
    if not isinstance(row["record_number"], int) or row["record_number"] < 1:
        raise IncidentError("incident source identity is invalid")
    if row["severity"] is not None and not isinstance(row["severity"], str):
        raise IncidentError("incident severity is invalid")
    if row["attention_eligible"] not in (0, 1):
        raise IncidentError("incident attention policy is invalid")
    if not isinstance(row["repeat_count"], int) or row["repeat_count"] < 1:
        raise IncidentError("incident repeat count is invalid")
    for field in (
        "event_code",
        "family",
        "protocol",
        "signal_type",
    ):
        if not isinstance(row[field], str):
            raise IncidentError("incident projected text field is invalid")
    if row["entity_type"] is not None and not isinstance(
        row["entity_type"], str
    ):
        raise IncidentError("incident entity type is invalid")
    if row["entity_key"] is not None and not isinstance(
        row["entity_key"], str
    ):
        raise IncidentError("incident entity key is invalid")
    if row["state"] is not None and not isinstance(row["state"], str):
        raise IncidentError("incident state is invalid")
    if not isinstance(row["attributes_json"], str):
        raise IncidentError("incident attributes are invalid")
    try:
        attributes = json.loads(row["attributes_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise IncidentError("incident attributes are invalid") from exc
    if not isinstance(attributes, dict):
        raise IncidentError("incident attributes are invalid")


def active_incident(
    connection: sqlite3.Connection,
    key: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM incidents
        WHERE correlation_key = ?
          AND status != 'RESOLVED'
        """,
        (key,),
    ).fetchone()


def append_transition(
    connection: sqlite3.Connection,
    incident: str,
    from_status: str | None,
    to_status: str,
    event_id: int | None,
    reason: str,
    occurred_at: str,
    occurred_at_epoch_ms: int,
) -> None:
    if (from_status, to_status) not in ALLOWED_TRANSITIONS:
        raise IncidentError("contradictory incident transition")
    sequence = connection.execute(
        """
        SELECT COALESCE(MAX(transition_sequence), 0) + 1
        FROM incident_transitions
        WHERE incident_id = ?
        """,
        (incident,),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO incident_transitions (
            incident_id,
            transition_sequence,
            from_status,
            to_status,
            event_id,
            reason,
            occurred_at,
            occurred_at_epoch_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident,
            sequence,
            from_status,
            to_status,
            event_id,
            reason,
            occurred_at,
            occurred_at_epoch_ms,
        ),
    )


def append_evidence(
    connection: sqlite3.Connection,
    incident: str,
    row: sqlite3.Row,
    kind: str,
) -> None:
    sequence = connection.execute(
        """
        SELECT COALESCE(MAX(evidence_sequence), 0) + 1
        FROM incident_evidence
        WHERE incident_id = ?
        """,
        (incident,),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO incident_evidence (
            incident_id,
            evidence_sequence,
            event_id,
            evidence_kind,
            observed_at,
            observed_at_epoch_ms,
            event_code,
            signal_type,
            observation_state,
            repeat_count,
            attributes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident,
            sequence,
            row["id"],
            kind,
            row["timestamp"],
            row["timestamp_epoch_ms"],
            row["event_code"],
            row["signal_type"],
            row["state"],
            row["repeat_count"],
            row["attributes_json"],
        ),
    )


def build_context(
    connection: sqlite3.Connection,
    current: sqlite3.Row,
) -> dict:
    windows = {}
    for name, duration in CONTEXT_WINDOWS_MS.items():
        cutoff = current["last_seen_epoch_ms"] - duration
        row = connection.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(repeat_count), 0),
                COALESCE(SUM(evidence_kind = 'adverse'), 0),
                COALESCE(SUM(evidence_kind = 'recovery'), 0),
                COALESCE(SUM(evidence_kind = 'supporting'), 0),
                MIN(observed_at_epoch_ms),
                MAX(observed_at_epoch_ms)
            FROM incident_evidence
            WHERE incident_id = ?
              AND observed_at_epoch_ms >= ?
            """,
            (current["incident_id"], cutoff),
        ).fetchone()
        windows[name] = {
            "evidence_count": row[0],
            "repeat_count_total": row[1],
            "adverse_count": row[2],
            "recovery_count": row[3],
            "supporting_count": row[4],
            "first_seen_epoch_ms": row[5],
            "last_seen_epoch_ms": row[6],
        }
    return {
        "schema_version": 1,
        "incident_id": current["incident_id"],
        "status": current["status"],
        "as_of_event_id": current["last_event_id"],
        "first_seen": current["first_seen"],
        "last_seen": current["last_seen"],
        "occurrence_count": current["occurrence_count"],
        "repeat_count_total": current["repeat_count_total"],
        "last_observation_state": current["last_observation_state"],
        "windows": windows,
    }


def refresh_context(connection: sqlite3.Connection, incident: str) -> None:
    current = connection.execute(
        "SELECT * FROM incidents WHERE incident_id = ?",
        (incident,),
    ).fetchone()
    if current is None:
        raise IncidentError("incident disappeared during context refresh")
    context = build_context(connection, current)
    connection.execute(
        "UPDATE incidents SET context_json = ? WHERE incident_id = ?",
        (canonical_json(context), incident),
    )


def create_incident(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    key: str,
    kind: str,
) -> tuple[str, int]:
    identifier = incident_id(row, key)
    severity = normalized_severity(row["severity"])
    connection.execute(
        """
        INSERT INTO incidents (
            incident_id,
            correlation_key,
            status,
            event_family,
            protocol,
            entity_type,
            entity_key,
            severity,
            first_seen,
            first_seen_epoch_ms,
            last_seen,
            last_seen_epoch_ms,
            occurrence_count,
            repeat_count_total,
            observation_state_changes,
            last_observation_state,
            opened_at,
            recovering_at,
            resolved_at,
            last_event_id,
            context_json,
            engine_version,
            created_at,
            updated_at
        ) VALUES (
            ?, ?, 'CANDIDATE', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0, ?,
            NULL, NULL, NULL, ?, '{}', ?, ?, ?
        )
        """,
        (
            identifier,
            key,
            row["family"],
            row["protocol"],
            row["entity_type"],
            row["entity_key"],
            severity,
            row["timestamp"],
            row["timestamp_epoch_ms"],
            row["timestamp"],
            row["timestamp_epoch_ms"],
            row["repeat_count"],
            row["state"],
            row["id"],
            ENGINE_VERSION,
            row["timestamp"],
            row["timestamp"],
        ),
    )
    append_transition(
        connection,
        identifier,
        None,
        "CANDIDATE",
        row["id"],
        "first_adverse_evidence",
        row["timestamp"],
        row["timestamp_epoch_ms"],
    )
    append_evidence(connection, identifier, row, kind)
    transitions = 1
    if (
        (
            row["signal_type"] == "state_transition"
            and (row["state"] or "").casefold() in IMMEDIATE_OPEN_STATES
        )
        or (
            row["entity_type"] == "event_signature"
            and row["signal_type"] == "degradation"
            and row["state"] == "detected"
        )
    ):
        append_transition(
            connection,
            identifier,
            "CANDIDATE",
            "OPEN",
            row["id"],
            "explicit_adverse_state",
            row["timestamp"],
            row["timestamp_epoch_ms"],
        )
        connection.execute(
            """
            UPDATE incidents
            SET status = 'OPEN', opened_at = ?, updated_at = ?
            WHERE incident_id = ?
            """,
            (row["timestamp"], row["timestamp"], identifier),
        )
        transitions += 1
    refresh_context(connection, identifier)
    return identifier, transitions


def update_incident_with_evidence(
    connection: sqlite3.Connection,
    current: sqlite3.Row,
    row: sqlite3.Row,
    kind: str,
) -> int:
    incident = current["incident_id"]
    append_evidence(connection, incident, row, kind)
    state = row["state"]
    state_changes = current["observation_state_changes"]
    if (
        state
        and current["last_observation_state"]
        and state != current["last_observation_state"]
    ):
        state_changes += 1
    severity = stronger_severity(
        current["severity"],
        normalized_severity(row["severity"]),
    )
    connection.execute(
        """
        UPDATE incidents
        SET
            severity = ?,
            last_seen = ?,
            last_seen_epoch_ms = ?,
            occurrence_count = occurrence_count + 1,
            repeat_count_total = repeat_count_total + ?,
            observation_state_changes = ?,
            last_observation_state = COALESCE(?, last_observation_state),
            last_event_id = ?,
            engine_version = ?,
            updated_at = ?
        WHERE incident_id = ?
        """,
        (
            severity,
            row["timestamp"],
            row["timestamp_epoch_ms"],
            row["repeat_count"],
            state_changes,
            state,
            row["id"],
            ENGINE_VERSION,
            row["timestamp"],
            incident,
        ),
    )

    transitions = 0
    status = current["status"]
    updated = connection.execute(
        "SELECT * FROM incidents WHERE incident_id = ?",
        (incident,),
    ).fetchone()
    if status == "CANDIDATE" and kind == "adverse":
        if updated["occurrence_count"] >= 2:
            append_transition(
                connection,
                incident,
                "CANDIDATE",
                "OPEN",
                row["id"],
                "repeated_adverse_evidence",
                row["timestamp"],
                row["timestamp_epoch_ms"],
            )
            connection.execute(
                """
                UPDATE incidents
                SET status = 'OPEN', opened_at = ?, updated_at = ?
                WHERE incident_id = ?
                """,
                (row["timestamp"], row["timestamp"], incident),
            )
            transitions += 1
    elif status == "CANDIDATE" and kind == "recovery":
        if uses_protocol_monitoring(updated):
            append_transition(
                connection,
                incident,
                "CANDIDATE",
                "RECOVERING",
                row["id"],
                "protocol_candidate_recovery_monitoring",
                row["timestamp"],
                row["timestamp_epoch_ms"],
            )
            connection.execute(
                """
                UPDATE incidents
                SET
                    status = 'RECOVERING',
                    recovering_at = ?,
                    engine_version = ?,
                    updated_at = ?
                WHERE incident_id = ?
                """,
                (
                    row["timestamp"],
                    ENGINE_VERSION,
                    row["timestamp"],
                    incident,
                ),
            )
        else:
            append_transition(
                connection,
                incident,
                "CANDIDATE",
                "RESOLVED",
                row["id"],
                "recovered_before_open",
                row["timestamp"],
                row["timestamp_epoch_ms"],
            )
            connection.execute(
                """
                UPDATE incidents
                SET
                    status = 'RESOLVED',
                    resolved_at = ?,
                    engine_version = ?,
                    updated_at = ?
                WHERE incident_id = ?
                """,
                (
                    row["timestamp"],
                    ENGINE_VERSION,
                    row["timestamp"],
                    incident,
                ),
            )
        transitions += 1
    elif status == "OPEN" and kind == "recovery":
        append_transition(
            connection,
            incident,
            "OPEN",
            "RECOVERING",
            row["id"],
            "recovery_evidence",
            row["timestamp"],
            row["timestamp_epoch_ms"],
        )
        connection.execute(
            """
            UPDATE incidents
            SET status = 'RECOVERING', recovering_at = ?, updated_at = ?
            WHERE incident_id = ?
            """,
            (row["timestamp"], row["timestamp"], incident),
        )
        transitions += 1
    elif status == "RECOVERING" and kind == "adverse":
        append_transition(
            connection,
            incident,
            "RECOVERING",
            "OPEN",
            row["id"],
            "adverse_relapse",
            row["timestamp"],
            row["timestamp_epoch_ms"],
        )
        connection.execute(
            """
            UPDATE incidents
            SET
                status = 'OPEN',
                recovering_at = NULL,
                updated_at = ?
            WHERE incident_id = ?
            """,
            (row["timestamp"], incident),
        )
        transitions += 1
    refresh_context(connection, incident)
    return transitions


def resolve_at_deadline(
    connection: sqlite3.Connection,
    current: sqlite3.Row,
    reason: str,
    deadline_ms: int,
) -> None:
    occurred_at = iso_from_epoch(deadline_ms)
    append_transition(
        connection,
        current["incident_id"],
        current["status"],
        "RESOLVED",
        None,
        reason,
        occurred_at,
        deadline_ms,
    )
    connection.execute(
        """
        UPDATE incidents
        SET status = 'RESOLVED', resolved_at = ?, engine_version = ?,
            updated_at = ?
        WHERE incident_id = ?
        """,
        (occurred_at, ENGINE_VERSION, occurred_at, current["incident_id"]),
    )
    refresh_context(connection, current["incident_id"])


def sweep_timeouts(
    connection: sqlite3.Connection,
    watermark_ms: int,
) -> int:
    transitions = 0
    for current in connection.execute(
        """
        SELECT * FROM incidents
        WHERE status IN ('CANDIDATE', 'RECOVERING')
        ORDER BY first_seen_epoch_ms, incident_id
        """
    ).fetchall():
        if current["status"] == "CANDIDATE":
            deadline = current["first_seen_epoch_ms"] + CANDIDATE_WINDOW_MS
            reason = "candidate_timeout"
        else:
            deadline, reason = recovery_deadline(current)
        if deadline <= watermark_ms:
            if (
                current["status"] == "CANDIDATE"
                and uses_protocol_monitoring(current)
            ):
                occurred_at = iso_from_epoch(deadline)
                append_transition(
                    connection,
                    current["incident_id"],
                    "CANDIDATE",
                    "RECOVERING",
                    None,
                    "protocol_candidate_monitoring",
                    occurred_at,
                    deadline,
                )
                connection.execute(
                    """
                    UPDATE incidents
                    SET
                        status = 'RECOVERING',
                        recovering_at = ?,
                        engine_version = ?,
                        updated_at = ?
                    WHERE incident_id = ?
                    """,
                    (
                        occurred_at,
                        ENGINE_VERSION,
                        occurred_at,
                        current["incident_id"],
                    ),
                )
                refresh_context(connection, current["incident_id"])
            else:
                resolve_at_deadline(connection, current, reason, deadline)
            transitions += 1
    return transitions


def process_event(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> tuple[int, int]:
    validate_event(row)
    if connection.execute(
        "SELECT 1 FROM incident_evidence WHERE event_id = ?",
        (row["id"],),
    ).fetchone() is not None:
        return 0, 0
    if not row["attention_eligible"]:
        return 0, 0
    if not row["entity_type"] or not row["entity_key"]:
        return 0, 0
    kind = event_kind(row["signal_type"], row["state"])
    key = correlation_key(row)
    current = active_incident(connection, key)
    if current is None:
        if kind != "adverse":
            return 0, 0
        _, transitions = create_incident(connection, row, key, kind)
        return 1, transitions

    transitions = update_incident_with_evidence(
        connection,
        current,
        row,
        kind,
    )
    return 0, transitions


def process_batch(
    connection: sqlite3.Connection,
) -> tuple[int, int, int, int]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        cursor = cursor_value(connection)
        rows = connection.execute(
            """
            SELECT
                r.id,
                r.source_file,
                r.record_number,
                r.timestamp,
                r.timestamp_epoch_ms,
                r.severity,
                e.event_code,
                e.family,
                e.entity_type,
                e.entity_key,
                e.state,
                e.attention_eligible,
                e.repeat_count,
                e.classification_version,
                e.protocol,
                e.signal_type,
                e.attributes_json
            FROM recent_events AS r
            JOIN event_enrichment AS e ON e.event_id = r.id
            WHERE r.id > ?
              AND e.classification_version = ?
            ORDER BY r.id
            LIMIT ?
            """,
            (cursor, PROJECTION_VERSION, BATCH_SIZE),
        ).fetchall()
        if not rows:
            connection.commit()
            return 0, 0, 0, 0
        incidents_created = 0
        transitions = 0
        watermark = 0
        for row in rows:
            watermark = max(watermark, row["timestamp_epoch_ms"])
            transitions += sweep_timeouts(connection, watermark)
            created, event_transitions = process_event(connection, row)
            incidents_created += created
            transitions += event_transitions
        updated_at = iso_from_epoch(watermark)
        connection.execute(
            """
            INSERT INTO agent_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (CURSOR_KEY, str(rows[-1]["id"]), updated_at),
        )
        connection.commit()
        return len(rows), incidents_created, transitions, watermark
    except Exception:
        connection.rollback()
        raise


def verify_engine_state(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise IncidentError("SQLite quick_check failed")
    duplicate_active = connection.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT correlation_key
            FROM incidents
            WHERE status != 'RESOLVED'
            GROUP BY correlation_key
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    if duplicate_active:
        raise IncidentError("duplicate active incident identity")
    missing_initial = connection.execute(
        """
        SELECT COUNT(*)
        FROM incidents AS i
        WHERE NOT EXISTS (
            SELECT 1
            FROM incident_transitions AS t
            WHERE t.incident_id = i.incident_id
              AND t.transition_sequence = 1
              AND t.from_status IS NULL
              AND t.to_status = 'CANDIDATE'
        )
        """
    ).fetchone()[0]
    if missing_initial:
        raise IncidentError("incident lacks initial transition")
    transition_mismatch = connection.execute(
        """
        SELECT COUNT(*)
        FROM incidents AS i
        WHERE i.status != (
            SELECT t.to_status
            FROM incident_transitions AS t
            WHERE t.incident_id = i.incident_id
            ORDER BY t.transition_sequence DESC
            LIMIT 1
        )
        """
    ).fetchone()[0]
    if transition_mismatch:
        raise IncidentError("incident status differs from transition history")
    sequence_mismatch = connection.execute(
        """
        SELECT COUNT(*)
        FROM incidents AS i
        WHERE i.occurrence_count != (
            SELECT COALESCE(MAX(e.evidence_sequence), 0)
            FROM incident_evidence AS e
            WHERE e.incident_id = i.incident_id
        )
           OR (
            SELECT COUNT(*)
            FROM incident_transitions AS t
            WHERE t.incident_id = i.incident_id
           ) != (
            SELECT COALESCE(MAX(t.transition_sequence), 0)
            FROM incident_transitions AS t
            WHERE t.incident_id = i.incident_id
           )
        """
    ).fetchone()[0]
    if sequence_mismatch:
        raise IncidentError("incident append sequence is not contiguous")
    mismatched_counts = connection.execute(
        """
        SELECT COUNT(*)
        FROM incidents AS i
        WHERE i.occurrence_count != (
            SELECT COUNT(*)
            FROM incident_evidence AS e
            WHERE e.incident_id = i.incident_id
        )
           OR i.repeat_count_total != (
            SELECT COALESCE(SUM(e.repeat_count), 0)
            FROM incident_evidence AS e
            WHERE e.incident_id = i.incident_id
        )
        """
    ).fetchone()[0]
    if mismatched_counts:
        raise IncidentError("incident aggregate differs from evidence")
    for current in connection.execute("SELECT * FROM incidents"):
        context_text = current["context_json"]
        try:
            context = json.loads(context_text)
        except json.JSONDecodeError as exc:
            raise IncidentError("incident context is invalid") from exc
        if (
            not isinstance(context, dict)
            or context.get("schema_version") != 1
            or context.get("incident_id") != current["incident_id"]
            or set(context.get("windows", {})) != set(CONTEXT_WINDOWS_MS)
            or canonical_json(context) != canonical_json(
                build_context(connection, current)
            )
        ):
            raise IncidentError("incident context contract differs")


def main(database_path=None) -> int:
    selected_database = database_path if database_path is not None else DB
    if selected_database is None:
        print(
            "ERROR: database path requires runtime_config or explicit input",
            file=sys.stderr,
        )
        return 1
    connection = sqlite3.connect(selected_database)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        validate_database_contract(connection)
        scanned = 0
        created = 0
        transitions = 0
        watermark = 0
        while True:
            batch = process_batch(connection)
            if batch[0] == 0:
                break
            scanned += batch[0]
            created += batch[1]
            transitions += batch[2]
            watermark = max(watermark, batch[3])
        verify_engine_state(connection)
        incidents = connection.execute(
            "SELECT COUNT(*) FROM incidents"
        ).fetchone()[0]
        active = connection.execute(
            "SELECT COUNT(*) FROM incidents WHERE status != 'RESOLVED'"
        ).fetchone()[0]
        evidence = connection.execute(
            "SELECT COUNT(*) FROM incident_evidence"
        ).fetchone()[0]
        print(
            "INCIDENT_ENGINE "
            f"scanned={scanned} "
            f"created={created} "
            f"transitions={transitions} "
            f"incidents={incidents} "
            f"active={active} "
            f"evidence={evidence} "
            f"watermark_ms={watermark} "
            f"version={ENGINE_VERSION}"
        )
        print("GX10_INCIDENT_ENGINE=PASS")
        return 0
    except (IncidentError, OSError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
