#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import socket
import sqlite3
import sys
import types
import urllib.error
import urllib.parse
import urllib.request

try:
    from runtime_config import load_runtime_config
except ModuleNotFoundError as exc:
    if exc.name != "runtime_config":
        raise
    load_runtime_config = None


DB = load_runtime_config().database_path if load_runtime_config else None
CONFIG_PATH = Path("/etc/network-log-gx10/triage-runtime-v1.json")
PROMPT_PATH = Path("/etc/network-log-gx10/uncovered-event-triage-v1.txt")
OUTPUT_SCHEMA_PATH = Path(
    "/etc/network-log-gx10/uncovered-event-triage-output-v1.json"
)
INCIDENT_ENGINE_PATH = Path(
    "/usr/local/libexec/network-log-gx10/incident-engine.py"
)
OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/chat"
CURSOR_KEY = "ai_triage_v1_last_event_id"
POLICY_VERSION = 1
SIGNATURE_VERSION = 1
OUTPUT_SCHEMA_VERSION = 1
MODEL_REFERENCE = "gemma4:latest"
MODEL_VERSION = "ollama-gemma4-c6eb396d-triage-v1"
PROMPT_VERSION = "uncovered-event-triage-v1-r2"
MODEL_MANIFEST_SHA256 = (
    "c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb"
)
MODEL_CONFIG_DIGEST = (
    "sha256:f0988ff50a2458c598ff6b1b87b94d0f5c44d73061c2795391878b00b2285e11"
)
MODEL_VERSION_CREATED_AT = "2026-08-26T04:43:00+00:00"
PROMPT_VERSION_CREATED_AT = "2026-08-26T06:20:00+00:00"
MAX_BATCH_SIGNATURES = 24
MAX_PACKET_BYTES = 32 * 1024
MAX_TEMPLATE_BYTES = 768
MAX_RESPONSE_BYTES = 128 * 1024
MAX_RESULT_BYTES = 48 * 1024
MAX_SCAN_ROWS = 10000
REQUEST_TIMEOUT_SECONDS = 120
NEGATIVE_CACHE_MS = 60 * 60 * 1000
NOTICE_REPEAT_MS = 15 * 60 * 1000
NOTICE_REPEAT_COUNT = 3
NOTICE_DEVICE_COUNT = 2
TRIAGE_OPEN_QUIET_MS = 60 * 60 * 1000
TRIAGE_RECOVERY_CONFIRM_MS = 15 * 60 * 1000
PROMOTION_MIN_CONFIDENCE = 70
PROMOTION_MIN_DECISIONS = 3
PROMOTION_MIN_SPAN_MS = 30 * 60 * 1000
PROMOTION_MAX_SEVERITY = 3
RETRY_BACKOFF_MS = (5 * 60 * 1000, 15 * 60 * 1000, 30 * 60 * 1000, 60 * 60 * 1000)

SEVERITY_NUMBER = {
    "emergency": 0,
    "emerg": 0,
    "alert": 1,
    "critical": 2,
    "crit": 2,
    "error": 3,
    "err": 3,
    "warning": 4,
    "warn": 4,
    "notice": 5,
    "informational": 6,
    "info": 6,
    "debug": 7,
}
NUMBER_SEVERITY = {
    0: "emergency",
    1: "alert",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notice",
}
CATEGORIES = {
    "capacity",
    "configuration",
    "hardware",
    "protocol",
    "security",
    "service",
    "software",
    "unknown",
}
DECISIONS = {"incident", "ignore", "insufficient_evidence"}
FAILURE_CODES = {
    "INFERENCE_UNAVAILABLE": "inference_unavailable",
    "INFERENCE_TIMEOUT": "inference_timeout",
    "TRANSPORT_ERROR": "transport_error",
    "INVALID_RESPONSE": "invalid_response",
    "INVALID_OUTPUT": "invalid_output",
}
EVENT_CODE_RE = re.compile(r"^[A-Z0-9_.-]{1,160}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_RE = re.compile(r"\b[0-9a-f]{0,4}:(?:[0-9a-f]{0,4}:){1,6}[0-9a-f]{0,4}\b", re.IGNORECASE)
MAC_RE = re.compile(r"\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b|\b[0-9a-f]{4}(?:\.[0-9a-f]{4}){2}\b", re.IGNORECASE)
HEX_RE = re.compile(r"\b0x[0-9a-f]+\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d+\b")
SPACE_RE = re.compile(r"\s+")

REQUIRED_TABLE_COLUMNS = {
    "agent_state": {"key", "value", "updated_at"},
    "recent_events": {
        "id", "source_file", "record_number", "timestamp",
        "timestamp_epoch_ms", "severity", "message", "event_json",
    },
    "event_enrichment": {
        "event_id", "event_code", "family", "device", "entity_type",
        "entity_key", "state", "attention_eligible", "repeat_count",
        "classification_version", "vendor_hint", "protocol",
        "signal_type", "attributes_json",
    },
    "incident_evidence": {"event_id"},
    "triage_signatures": {
        "signature_id", "signature_version", "vendor_hint", "os_family",
        "event_code", "event_family", "template_text", "template_sha256",
        "created_at",
    },
    "triage_batches": {
        "batch_id", "scan_start_event_id", "scan_end_event_id",
        "priority_severity", "status", "packet_json", "packet_sha256",
        "created_at", "completed_at",
    },
    "triage_batch_members": {
        "batch_id", "signature_id", "event_id", "device",
        "severity_number",
    },
    "triage_runs": {
        "run_id", "batch_id", "model_version", "prompt_version",
        "attempt_number", "request_sha256", "status", "started_at",
        "completed_at", "error_code", "diagnostics_json",
    },
    "triage_decisions": {
        "decision_id", "run_id", "batch_id", "signature_id", "decision",
        "confidence", "category", "title", "summary", "reason",
        "result_json", "result_sha256", "created_at",
    },
    "event_detection_overrides": {
        "event_id", "signature_id", "source_type", "source_id",
        "entity_type", "entity_key", "state", "signal_type",
        "attributes_json", "created_at",
    },
    "triage_incident_summaries": {
        "incident_id", "source_id", "signature_id", "title", "summary",
        "confidence", "created_at",
    },
    "learned_detection_rules": {
        "rule_id", "event_code", "maximum_severity_number", "category",
        "title", "summary", "status", "evidence_json", "created_at",
        "revoked_at",
    },
}


class TriageError(ValueError):
    pass


class InferenceFailure(TriageError):
    def __init__(self, status: str, diagnostics: dict | None = None):
        if status not in FAILURE_CODES:
            raise ValueError("invalid triage inference status")
        super().__init__(status)
        self.status = status
        self.diagnostics = diagnostics or {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def epoch_ms(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise TriageError("triage timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise TriageError("triage timestamp lacks timezone")
    return int(parsed.timestamp() * 1000)


def iso_from_epoch(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def bounded_text(value: object, maximum: int, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise TriageError(f"{label} is invalid")
    return value


def validate_database_contract(connection: sqlite3.Connection) -> None:
    for table, expected in REQUIRED_TABLE_COLUMNS.items():
        observed = {
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if not expected <= observed:
            raise TriageError(f"triage database contract differs: {table}")


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024:
        raise TriageError("triage JSON artifact is invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TriageError("triage JSON artifact is invalid") from exc
    if not isinstance(value, dict):
        raise TriageError("triage JSON artifact is not an object")
    return value


def load_artifacts(config_path: Path, prompt_path: Path, schema_path: Path):
    config = read_json(config_path)
    expected_config = {
        "config_version", "model_config_digest", "model_manifest_sha256",
        "model_reference", "model_version", "prompt_version", "provider",
        "request_options",
    }
    if (
        set(config) != expected_config
        or config["config_version"] != 1
        or config["provider"] != "ollama"
        or config["model_reference"] != MODEL_REFERENCE
        or config["model_version"] != MODEL_VERSION
        or config["prompt_version"] != PROMPT_VERSION
        or config["model_manifest_sha256"] != MODEL_MANIFEST_SHA256
        or config["model_config_digest"] != MODEL_CONFIG_DIGEST
    ):
        raise TriageError("triage runtime configuration differs")
    options = config["request_options"]
    if (
        not isinstance(options, dict)
        or set(options) != {"num_ctx", "num_predict", "seed", "temperature"}
        or options.get("temperature") != 0
        or type(options.get("num_ctx")) is not int
        or not 1024 <= options["num_ctx"] <= 32768
        or type(options.get("num_predict")) is not int
        or not 128 <= options["num_predict"] <= 4096
        or type(options.get("seed")) is not int
    ):
        raise TriageError("triage request options differ")
    if prompt_path.is_symlink() or not prompt_path.is_file() or prompt_path.stat().st_size > 64 * 1024:
        raise TriageError("triage prompt is invalid")
    prompt = prompt_path.read_text(encoding="utf-8")
    schema = read_json(schema_path)
    if (
        schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or set(schema.get("required", ())) != {"schema", "schema_version", "batch_id", "decisions"}
    ):
        raise TriageError("triage output schema differs")
    return config, prompt, schema, sha256_text(prompt), sha256_bytes(schema_path.read_bytes())


def register_versions(connection, config, prompt_sha256, schema_sha256):
    options_json = canonical_json(config["request_options"])
    connection.execute(
        """
        INSERT OR IGNORE INTO reasoning_model_versions (
            model_version, provider, model_reference, manifest_sha256,
            config_digest, request_options_json, created_at
        ) VALUES (?, 'ollama', ?, ?, ?, ?, ?)
        """,
        (
            MODEL_VERSION, MODEL_REFERENCE, MODEL_MANIFEST_SHA256,
            MODEL_CONFIG_DIGEST, options_json, MODEL_VERSION_CREATED_AT,
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO reasoning_prompt_versions (
            prompt_version, system_prompt_sha256, output_schema_sha256,
            output_schema_version, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            PROMPT_VERSION, prompt_sha256, schema_sha256,
            OUTPUT_SCHEMA_VERSION, PROMPT_VERSION_CREATED_AT,
        ),
    )
    model = connection.execute(
        "SELECT provider,model_reference,manifest_sha256,config_digest,request_options_json FROM reasoning_model_versions WHERE model_version=?",
        (MODEL_VERSION,),
    ).fetchone()
    prompt = connection.execute(
        "SELECT system_prompt_sha256,output_schema_sha256,output_schema_version FROM reasoning_prompt_versions WHERE prompt_version=?",
        (PROMPT_VERSION,),
    ).fetchone()
    if model is None or tuple(model) != (
        "ollama", MODEL_REFERENCE, MODEL_MANIFEST_SHA256,
        MODEL_CONFIG_DIGEST, options_json,
    ):
        raise TriageError("triage model registration differs")
    if prompt is None or tuple(prompt) != (
        prompt_sha256, schema_sha256, OUTPUT_SCHEMA_VERSION,
    ):
        raise TriageError("triage prompt registration differs")


def template_text(message: str) -> str:
    value = CONTROL_RE.sub(" ", message)
    value = URL_RE.sub("<url>", value)
    value = IPV4_RE.sub("<ipv4>", value)
    value = IPV6_RE.sub("<ipv6>", value)
    value = MAC_RE.sub("<mac>", value)
    value = HEX_RE.sub("<hex>", value)
    value = NUMBER_RE.sub("<n>", value)
    value = SPACE_RE.sub(" ", value).strip().casefold()
    encoded = value.encode("utf-8")
    if len(encoded) <= MAX_TEMPLATE_BYTES:
        return value
    prefix = encoded[:MAX_TEMPLATE_BYTES]
    while prefix:
        try:
            return prefix.decode("utf-8")
        except UnicodeDecodeError:
            prefix = prefix[:-1]
    return ""


def signature_value(row) -> dict:
    try:
        event = json.loads(row["event_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise TriageError("triage source event JSON is invalid") from exc
    if not isinstance(event, dict):
        raise TriageError("triage source event JSON is invalid")
    template = template_text(row["message"] or "")
    material = canonical_json(
        [
            "triage-signature-v1",
            row["vendor_hint"] or "unknown",
            event.get("os_family") or "unknown",
            row["event_code"] or "",
            row["family"] or "unknown",
            template,
        ]
    )
    return {
        "signature_id": "triage-sig-v1-" + sha256_text(material)[:32],
        "vendor_hint": row["vendor_hint"] or "unknown",
        "os_family": event.get("os_family") or "unknown",
        "event_code": row["event_code"] or "",
        "event_family": row["family"] or "unknown",
        "template_text": template,
        "template_sha256": sha256_text(template),
    }


def effective_severity(row) -> int | None:
    severity = SEVERITY_NUMBER.get((row["severity"] or "").strip().casefold())
    try:
        attributes = json.loads(row["attributes_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise TriageError("triage source attributes are invalid") from exc
    embedded = attributes.get("event_code_severity") if isinstance(attributes, dict) else None
    if type(embedded) is not int or not 0 <= embedded <= 7:
        embedded = None
    values = [item for item in (severity, embedded) if item is not None]
    return min(values) if values else None


def state_value(connection, key: str) -> int:
    row = connection.execute("SELECT value FROM agent_state WHERE key=?", (key,)).fetchone()
    if row is None:
        return 0
    try:
        value = int(row[0])
    except (TypeError, ValueError) as exc:
        raise TriageError("triage cursor is invalid") from exc
    if value < 0 or str(value) != row[0]:
        raise TriageError("triage cursor is invalid")
    return value


def set_state(connection, key: str, value: int, updated_at: str) -> None:
    connection.execute(
        """
        INSERT INTO agent_state(key,value,updated_at) VALUES(?,?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at
        """,
        (key, str(value), updated_at),
    )


def notice_admitted(connection, row, signature: dict, now_ms: int) -> bool:
    known = connection.execute(
        "SELECT 1 FROM triage_signatures WHERE signature_id=?",
        (signature["signature_id"],),
    ).fetchone()
    if known is None:
        return True
    cutoff = now_ms - NOTICE_REPEAT_MS
    count, devices = connection.execute(
        """
        SELECT COUNT(*),COUNT(DISTINCT e.device)
        FROM recent_events r JOIN event_enrichment e ON e.event_id=r.id
        WHERE r.timestamp_epoch_ms>=? AND e.event_code=?
          AND e.attention_eligible=1
        """,
        (cutoff, row["event_code"]),
    ).fetchone()
    return count >= NOTICE_REPEAT_COUNT or devices >= NOTICE_DEVICE_COUNT


def cached_negative(connection, signature_id: str, now_ms: int) -> bool:
    row = connection.execute(
        """
        SELECT d.decision,d.created_at
        FROM triage_decisions d JOIN triage_runs r ON r.run_id=d.run_id
        WHERE d.signature_id=? AND r.model_version=? AND r.prompt_version=?
        ORDER BY d.created_at DESC,d.decision_id DESC LIMIT 1
        """,
        (signature_id, MODEL_VERSION, PROMPT_VERSION),
    ).fetchone()
    return bool(
        row is not None
        and row["decision"] == "ignore"
        and now_ms - epoch_ms(row["created_at"]) < NEGATIVE_CACHE_MS
    )


def source_rows(connection, start: int, end: int):
    return connection.execute(
        """
        SELECT
            r.id,r.source_file,r.record_number,r.timestamp,r.timestamp_epoch_ms,
            r.severity,r.message,r.event_json,e.event_code,e.family,e.device,
            e.entity_type,e.entity_key,e.state,e.attention_eligible,e.repeat_count,
            e.classification_version,e.vendor_hint,e.protocol,e.signal_type,
            e.attributes_json,
            CASE WHEN ie.event_id IS NULL THEN 0 ELSE 1 END AS has_incident
        FROM recent_events r JOIN event_enrichment e ON e.event_id=r.id
        LEFT JOIN incident_evidence ie ON ie.event_id=r.id
        WHERE r.id>? AND r.id<=?
        ORDER BY r.id LIMIT ?
        """,
        (start, end, MAX_SCAN_ROWS),
    ).fetchall()


def ensure_signature(connection, signature: dict, created_at: str) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO triage_signatures (
            signature_id,signature_version,vendor_hint,os_family,event_code,
            event_family,template_text,template_sha256,created_at
        ) VALUES (?,1,?,?,?,?,?,?,?)
        """,
        (
            signature["signature_id"], signature["vendor_hint"],
            signature["os_family"], signature["event_code"],
            signature["event_family"], signature["template_text"],
            signature["template_sha256"], created_at,
        ),
    )
    stored = connection.execute(
        "SELECT vendor_hint,os_family,event_code,event_family,template_text,template_sha256 FROM triage_signatures WHERE signature_id=?",
        (signature["signature_id"],),
    ).fetchone()
    expected = tuple(signature[key] for key in (
        "vendor_hint", "os_family", "event_code", "event_family",
        "template_text", "template_sha256",
    ))
    if stored is None or tuple(stored) != expected:
        raise TriageError("triage signature identity collision")


def build_packet(connection, groups: dict, start: int, end: int, created_at: str):
    signatures = []
    for signature_id in sorted(groups):
        group = groups[signature_id]
        members = group["members"]
        signatures.append(
            {
                "affected_devices": len({item["device"] for item in members}),
                "event_code": group["signature"]["event_code"],
                "event_family": group["signature"]["event_family"],
                "first_seen": min(item["timestamp"] for item in members),
                "last_seen": max(item["timestamp"] for item in members),
                "occurrences": sum(item["repeat_count"] for item in members),
                "severity": NUMBER_SEVERITY[group["severity"]],
                "severity_number": group["severity"],
                "signature_id": signature_id,
                "template": group["signature"]["template_text"],
                "vendor": group["signature"]["vendor_hint"],
            }
        )
    identity = canonical_json(
        [
            "triage-batch-v1", POLICY_VERSION, start, end,
            [[item["signature_id"], [m["event_id"] for m in groups[item["signature_id"]]["members"]]] for item in signatures],
        ]
    )
    batch_id = "triage-batch-v1-" + sha256_text(identity)[:32]
    packet = {
        "batch_id": batch_id,
        "created_at": created_at,
        "policy_version": POLICY_VERSION,
        "schema": "gx10-uncovered-event-triage-packet",
        "schema_version": 1,
        "signatures": signatures,
    }
    packet_json = canonical_json(packet)
    if len(packet_json.encode("utf-8")) > MAX_PACKET_BYTES:
        raise TriageError("triage packet exceeds size limit")
    return batch_id, packet_json, sha256_text(packet_json)


def active_learned_rule(connection, row, severity: int):
    if severity > PROMOTION_MAX_SEVERITY or not row["event_code"]:
        return None
    return connection.execute(
        """
        SELECT * FROM learned_detection_rules
        WHERE event_code=? AND status='ACTIVE'
          AND maximum_severity_number>=?
        """,
        (row["event_code"], severity),
    ).fetchone()


def apply_learned_row(connection, engine, row, signature, rule, created_at: str) -> int:
    ensure_signature(connection, signature, created_at)
    effective = effective_row(
        connection, row["id"], signature["signature_id"], "learned_rule",
        rule["rule_id"], rule["category"], created_at,
    )
    engine.process_event(connection, effective)
    incident = engine.active_incident(connection, engine.correlation_key(effective))
    if incident is None:
        raise TriageError("learned detection rule did not create an incident")
    connection.execute(
        """
        INSERT OR IGNORE INTO triage_incident_summaries (
            incident_id,source_id,signature_id,title,summary,confidence,created_at
        ) VALUES (?,?,?,?,?,95,?)
        """,
        (
            incident["incident_id"], rule["rule_id"], signature["signature_id"],
            rule["title"], rule["summary"], created_at,
        ),
    )
    return 1


def create_next_batch(
    connection,
    now_value: str,
    *,
    engine=None,
    learned_coverage=False,
):
    pending = connection.execute(
        "SELECT * FROM triage_batches WHERE status='PENDING'"
    ).fetchone()
    if pending is not None:
        return pending, 0
    cursor = state_value(connection, CURSOR_KEY)
    incident_cursor = state_value(connection, "incident_engine_v1_last_event_id")
    if incident_cursor <= cursor:
        return None, 0
    now_ms = epoch_ms(now_value)
    groups = {}
    learned_applied = 0
    scan_end = cursor
    for row in source_rows(connection, cursor, incident_cursor):
        scan_end = row["id"]
        if row["has_incident"]:
            continue
        severity = effective_severity(row)
        signature = signature_value(row)
        if (
            row["classification_version"] != 4
            or row["attention_eligible"] != 1
            or severity is None
            or severity > 5
        ):
            continue
        if learned_coverage:
            rule = active_learned_rule(connection, row, severity)
            if rule is not None:
                if engine is None:
                    raise TriageError("learned coverage lacks incident engine")
                learned_applied += apply_learned_row(
                    connection, engine, row, signature, rule, now_value
                )
                continue
        if severity == 5 and not notice_admitted(connection, row, signature, now_ms):
            continue
        if cached_negative(connection, signature["signature_id"], now_ms):
            continue
        if signature["signature_id"] not in groups and len(groups) >= MAX_BATCH_SIGNATURES:
            scan_end = row["id"] - 1
            break
        group = groups.setdefault(
            signature["signature_id"],
            {"signature": signature, "severity": severity, "members": []},
        )
        group["severity"] = min(group["severity"], severity)
        group["members"].append(
            {
                "device": row["device"] or "unknown",
                "event_id": row["id"],
                "repeat_count": row["repeat_count"],
                "severity": severity,
                "timestamp": row["timestamp"],
            }
        )
    if not groups:
        if scan_end > cursor:
            set_state(connection, CURSOR_KEY, scan_end, now_value)
        return None, learned_applied
    for group in groups.values():
        ensure_signature(connection, group["signature"], now_value)
    batch_id, packet_json, packet_sha256 = build_packet(
        connection, groups, cursor + 1, scan_end, now_value
    )
    priority = min(group["severity"] for group in groups.values())
    connection.execute(
        """
        INSERT INTO triage_batches (
            batch_id,policy_version,scan_start_event_id,scan_end_event_id,
            priority_severity,status,packet_json,packet_sha256,created_at,
            completed_at
        ) VALUES (?,1,?,?,?,'PENDING',?,?,?,NULL)
        """,
        (batch_id, cursor + 1, scan_end, priority, packet_json, packet_sha256, now_value),
    )
    for signature_id, group in groups.items():
        for member in group["members"]:
            connection.execute(
                """
                INSERT INTO triage_batch_members (
                    batch_id,signature_id,event_id,device,severity_number
                ) VALUES (?,?,?,?,?)
                """,
                (
                    batch_id, signature_id, member["event_id"],
                    member["device"], member["severity"],
                ),
            )
    return connection.execute(
        "SELECT * FROM triage_batches WHERE batch_id=?", (batch_id,)
    ).fetchone(), learned_applied


def request_object(config, prompt, schema, batch):
    packet = json.loads(batch["packet_json"])
    return {
        "format": schema,
        "messages": [
            {"content": prompt, "role": "system"},
            {"content": canonical_json({"packet": packet, "packet_sha256": batch["packet_sha256"]}), "role": "user"},
        ],
        "model": config["model_reference"],
        "options": config["request_options"],
        "stream": False,
        "think": False,
    }


def ollama_request(request_json: str, endpoint: str = OLLAMA_ENDPOINT) -> bytes:
    parsed = urllib.parse.urlsplit(endpoint)
    if (
        parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
        or parsed.port != 11434 or parsed.path != "/api/chat"
        or parsed.query or parsed.fragment
    ):
        raise InferenceFailure("TRANSPORT_ERROR")
    request = urllib.request.Request(
        endpoint,
        data=request_json.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            if response.status != 200:
                raise InferenceFailure("INFERENCE_UNAVAILABLE", {"http_status": response.status})
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = "INFERENCE_TIMEOUT" if exc.code in {408, 504} else "INFERENCE_UNAVAILABLE" if exc.code in {429, 502, 503} else "TRANSPORT_ERROR"
        raise InferenceFailure(status, {"http_status": exc.code}) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise InferenceFailure("INFERENCE_TIMEOUT") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise InferenceFailure("INFERENCE_UNAVAILABLE") from exc
    if len(payload) > MAX_RESPONSE_BYTES:
        raise InferenceFailure("INVALID_RESPONSE")
    return payload


def parse_response(payload: bytes):
    try:
        response = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InferenceFailure("INVALID_RESPONSE") from exc
    if (
        not isinstance(response, dict)
        or response.get("model") != MODEL_REFERENCE
        or response.get("done") is not True
        or not isinstance(response.get("message"), dict)
        or response["message"].get("role") != "assistant"
        or not isinstance(response["message"].get("content"), str)
    ):
        raise InferenceFailure("INVALID_RESPONSE")
    diagnostics = {
        key: response[key]
        for key in (
            "done_reason", "total_duration", "load_duration",
            "prompt_eval_count", "prompt_eval_duration", "eval_count",
            "eval_duration",
        )
        if key in response and type(response[key]) in {str, int}
    }
    content = response["message"]["content"]
    if len(content.encode("utf-8")) > MAX_RESULT_BYTES:
        raise InferenceFailure("INVALID_OUTPUT", diagnostics)
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InferenceFailure("INVALID_OUTPUT", diagnostics) from exc
    if not isinstance(result, dict):
        raise InferenceFailure("INVALID_OUTPUT", diagnostics)
    return result, diagnostics


def validate_result(result, batch):
    try:
        if not isinstance(result, dict) or set(result) != {
            "schema", "schema_version", "batch_id", "decisions"
        }:
            raise InferenceFailure("INVALID_OUTPUT")
        if (
            result["schema"] != "gx10-uncovered-event-triage"
            or result["schema_version"] != 1
            or result["batch_id"] != batch["batch_id"]
            or not isinstance(result["decisions"], list)
        ):
            raise InferenceFailure("INVALID_OUTPUT")
        expected = [
            row[0]
            for row in batch["connection"].execute(
                "SELECT DISTINCT signature_id FROM triage_batch_members WHERE batch_id=? ORDER BY signature_id",
                (batch["batch_id"],),
            )
        ]
        observed = []
        for decision in result["decisions"]:
            if not isinstance(decision, dict) or set(decision) != {
                "signature_id", "decision", "confidence", "category", "title",
                "summary", "reason",
            }:
                raise InferenceFailure("INVALID_OUTPUT")
            bounded_text(decision["signature_id"], 128, "triage signature ID")
            if decision["decision"] not in DECISIONS:
                raise InferenceFailure("INVALID_OUTPUT")
            if type(decision["confidence"]) is not int or not 0 <= decision["confidence"] <= 95:
                raise InferenceFailure("INVALID_OUTPUT")
            if decision["category"] not in CATEGORIES:
                raise InferenceFailure("INVALID_OUTPUT")
            bounded_text(decision["title"], 160, "triage title")
            bounded_text(decision["summary"], 1000, "triage summary")
            bounded_text(decision["reason"], 500, "triage reason")
            observed.append(decision["signature_id"])
        if observed != expected:
            raise InferenceFailure("INVALID_OUTPUT")
    except TriageError as exc:
        if isinstance(exc, InferenceFailure):
            raise
        raise InferenceFailure("INVALID_OUTPUT") from exc
    return canonical_json(result)


def load_incident_engine(path: Path, database: Path):
    specification = importlib.util.spec_from_file_location("gx10_triage_incident_engine", path)
    if specification is None or specification.loader is None:
        raise TriageError("triage incident engine cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    fake = types.ModuleType("runtime_config")
    fake.load_runtime_config = lambda: types.SimpleNamespace(database_path=database)
    previous = sys.modules.get("runtime_config")
    sys.modules["runtime_config"] = fake
    try:
        specification.loader.exec_module(module)
    finally:
        if previous is None:
            del sys.modules["runtime_config"]
        else:
            sys.modules["runtime_config"] = previous
    return module


def effective_row(connection, event_id: int, signature_id: str, source_type: str, source_id: str, category: str, created_at: str):
    row = connection.execute(
        """
        SELECT r.id,r.source_file,r.record_number,r.timestamp,r.timestamp_epoch_ms,
               r.severity,e.event_code,e.family,e.device,e.repeat_count,
               e.classification_version,e.protocol,e.attributes_json
        FROM recent_events r JOIN event_enrichment e ON e.event_id=r.id
        WHERE r.id=?
        """,
        (event_id,),
    ).fetchone()
    if row is None:
        raise TriageError("triage member event disappeared")
    device = row["device"] or "unknown"
    code = row["event_code"] or "unknown"
    entity_key = f"event_signature|{device}|{code}|{signature_id}"
    try:
        attributes = json.loads(row["attributes_json"])
    except json.JSONDecodeError as exc:
        raise TriageError("triage member attributes are invalid") from exc
    attributes = dict(attributes)
    attributes["triage_category"] = category
    attributes["triage_signature_id"] = signature_id
    attributes["triage_source_id"] = source_id
    attributes["triage_source_type"] = source_type
    attributes_json = canonical_json(attributes)
    connection.execute(
        """
        INSERT OR IGNORE INTO event_detection_overrides (
            event_id,signature_id,source_type,source_id,entity_type,entity_key,
            state,signal_type,attributes_json,created_at
        ) VALUES (?,?,?,?,'event_signature',?,'detected','degradation',?,?)
        """,
        (event_id, signature_id, source_type, source_id, entity_key, attributes_json, created_at),
    )
    override = connection.execute(
        "SELECT signature_id,source_type,source_id,entity_key,attributes_json FROM event_detection_overrides WHERE event_id=?",
        (event_id,),
    ).fetchone()
    if override is None or tuple(override) != (
        signature_id, source_type, source_id, entity_key, attributes_json
    ):
        raise TriageError("triage event override differs")
    return {
        "id": row["id"], "source_file": row["source_file"],
        "record_number": row["record_number"], "timestamp": row["timestamp"],
        "timestamp_epoch_ms": row["timestamp_epoch_ms"], "severity": row["severity"],
        "event_code": row["event_code"], "family": row["family"],
        "entity_type": "event_signature", "entity_key": entity_key,
        "state": "detected", "attention_eligible": 1,
        "repeat_count": row["repeat_count"],
        "classification_version": row["classification_version"],
        "protocol": row["protocol"], "signal_type": "degradation",
        "attributes_json": attributes_json,
    }


def apply_positive(connection, engine, decision, source_type: str, source_id: str, created_at: str, batch_id: str | None = None):
    if batch_id is None:
        members = connection.execute(
            "SELECT event_id FROM event_detection_overrides WHERE source_type='learned_rule' AND source_id=? ORDER BY event_id",
            (source_id,),
        ).fetchall()
    else:
        members = connection.execute(
            "SELECT event_id FROM triage_batch_members WHERE batch_id=? AND signature_id=? ORDER BY event_id",
            (batch_id, decision["signature_id"]),
        ).fetchall()
    incidents = set()
    for member in members:
        row = effective_row(
            connection, member["event_id"], decision["signature_id"],
            source_type, source_id, decision["category"], created_at,
        )
        engine.process_event(connection, row)
        key = engine.correlation_key(row)
        incident = engine.active_incident(connection, key)
        if incident is not None:
            incidents.add(incident["incident_id"])
    for incident_id in sorted(incidents):
        connection.execute(
            """
            INSERT OR IGNORE INTO triage_incident_summaries (
                incident_id,source_id,signature_id,title,summary,confidence,created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                incident_id, source_id, decision["signature_id"],
                decision["title"], decision["summary"],
                decision["confidence"], created_at,
            ),
        )
    return len(incidents)


def apply_unapplied_decisions(connection, engine) -> int:
    applied = 0
    decisions = connection.execute(
        """
        SELECT d.* FROM triage_decisions d
        WHERE d.decision='incident'
          AND EXISTS (
              SELECT 1 FROM triage_batch_members m
              WHERE m.batch_id=d.batch_id AND m.signature_id=d.signature_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM triage_batch_members m
              JOIN event_detection_overrides o ON o.event_id=m.event_id
              WHERE m.batch_id=d.batch_id AND m.signature_id=d.signature_id
          )
        ORDER BY d.created_at,d.decision_id
        """
    ).fetchall()
    for decision in decisions:
        applied += apply_positive(
            connection, engine, decision, "ai_decision",
            decision["decision_id"], decision["created_at"], decision["batch_id"],
        )
    return applied


def promote_rules(connection, created_at: str) -> int:
    promoted = 0
    codes = [
        row[0]
        for row in connection.execute(
            """
            SELECT DISTINCT s.event_code
            FROM triage_decisions d
            JOIN triage_signatures s ON s.signature_id=d.signature_id
            JOIN triage_runs r ON r.run_id=d.run_id
            WHERE d.decision='incident' AND d.confidence>=?
              AND r.model_version=? AND r.prompt_version=?
              AND s.event_code!=''
            """,
            (PROMOTION_MIN_CONFIDENCE, MODEL_VERSION, PROMPT_VERSION),
        )
    ]
    for code in codes:
        if not EVENT_CODE_RE.fullmatch(code):
            continue
        if connection.execute(
            "SELECT 1 FROM learned_detection_rules WHERE event_code=? AND status='ACTIVE'",
            (code,),
        ).fetchone() is not None:
            continue
        rows = connection.execute(
            """
            SELECT d.decision_id,d.decision,d.confidence,d.category,d.title,
                   d.summary,d.created_at,d.signature_id,
                   MAX(m.severity_number) AS maximum_severity
            FROM triage_decisions d
            JOIN triage_signatures s ON s.signature_id=d.signature_id
            JOIN triage_runs r ON r.run_id=d.run_id
            JOIN triage_batch_members m
              ON m.batch_id=d.batch_id AND m.signature_id=d.signature_id
            WHERE s.event_code=? AND r.model_version=? AND r.prompt_version=?
            GROUP BY d.decision_id
            ORDER BY d.created_at,d.decision_id
            """,
            (code, MODEL_VERSION, PROMPT_VERSION),
        ).fetchall()
        positive = [
            row for row in rows
            if row["decision"] == "incident"
            and row["confidence"] >= PROMOTION_MIN_CONFIDENCE
            and row["maximum_severity"] <= PROMOTION_MAX_SEVERITY
        ]
        if len(positive) < PROMOTION_MIN_DECISIONS:
            continue
        if any(row["decision"] != "incident" for row in rows):
            continue
        if len({row["category"] for row in positive}) != 1:
            continue
        if epoch_ms(positive[-1]["created_at"]) - epoch_ms(positive[0]["created_at"]) < PROMOTION_MIN_SPAN_MS:
            continue
        signature_ids = {
            row[0]
            for row in connection.execute(
                "SELECT signature_id FROM triage_signatures WHERE event_code=?",
                (code,),
            )
        }
        if not signature_ids <= {row["signature_id"] for row in positive}:
            continue
        chosen = positive[-1]
        evidence = canonical_json(
            {
                "decision_ids": [positive[0]["decision_id"], positive[len(positive)//2]["decision_id"], positive[-1]["decision_id"]],
                "model_version": MODEL_VERSION,
                "prompt_version": PROMPT_VERSION,
                "schema_version": OUTPUT_SCHEMA_VERSION,
            }
        )
        material = canonical_json(["learned-detection-rule-v1", code, evidence])
        rule_id = "learned-rule-v1-" + sha256_text(material)[:32]
        connection.execute(
            """
            INSERT INTO learned_detection_rules (
                rule_id,rule_version,event_code,maximum_severity_number,
                category,title,summary,status,evidence_json,created_at,revoked_at
            ) VALUES (?,1,?,3,?,?,?,'ACTIVE',?,?,NULL)
            """,
            (
                rule_id, code, chosen["category"], chosen["title"],
                chosen["summary"], evidence, created_at,
            ),
        )
        promoted += 1
    return promoted


def sweep_triage_lifecycle(connection, engine, now_ms: int) -> int:
    transitions = 0
    for incident in connection.execute(
        "SELECT * FROM incidents WHERE entity_type='event_signature' AND status IN ('OPEN','RECOVERING') ORDER BY last_seen_epoch_ms,incident_id"
    ).fetchall():
        if incident["status"] == "OPEN":
            deadline = incident["last_seen_epoch_ms"] + TRIAGE_OPEN_QUIET_MS
            if deadline > now_ms:
                continue
            occurred = iso_from_epoch(deadline)
            engine.append_transition(
                connection, incident["incident_id"], "OPEN", "RECOVERING",
                None, "triage_quiet_period", occurred, deadline,
            )
            connection.execute(
                "UPDATE incidents SET status='RECOVERING',recovering_at=?,updated_at=? WHERE incident_id=?",
                (occurred, occurred, incident["incident_id"]),
            )
            engine.refresh_context(connection, incident["incident_id"])
            transitions += 1
        else:
            deadline = epoch_ms(incident["recovering_at"]) + TRIAGE_RECOVERY_CONFIRM_MS
            if deadline > now_ms:
                continue
            engine.resolve_at_deadline(
                connection, incident, "triage_recovery_confirmation", deadline
            )
            transitions += 1
    return transitions


def attempt_due(connection, batch, now_ms: int) -> bool:
    row = connection.execute(
        "SELECT attempt_number,completed_at FROM triage_runs WHERE batch_id=? AND model_version=? AND prompt_version=? AND status!='STARTED' ORDER BY attempt_number DESC LIMIT 1",
        (batch["batch_id"], MODEL_VERSION, PROMPT_VERSION),
    ).fetchone()
    if row is None:
        return True
    index = min(row["attempt_number"] - 1, len(RETRY_BACKOFF_MS) - 1)
    return now_ms >= epoch_ms(row["completed_at"]) + RETRY_BACKOFF_MS[index]


def run_identifier(batch_id: str, attempt: int) -> str:
    return "triage-run-v1-" + sha256_text(
        canonical_json(["triage-run-v1", batch_id, MODEL_VERSION, PROMPT_VERSION, attempt])
    )[:32]


def finalize_failure(database, run_id: str, failure: InferenceFailure, completed_at: str):
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            UPDATE triage_runs SET status=?,completed_at=?,error_code=?,diagnostics_json=?
            WHERE run_id=? AND status='STARTED'
            """,
            (
                failure.status, completed_at, FAILURE_CODES[failure.status],
                canonical_json(failure.diagnostics), run_id,
            ),
        )
        if connection.total_changes != 1:
            raise TriageError("triage failure reservation differs")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def reconcile_started_runs(connection, completed_at: str) -> int:
    rows = connection.execute(
        "SELECT run_id FROM triage_runs WHERE status='STARTED' ORDER BY run_id"
    ).fetchall()
    for row in rows:
        cursor = connection.execute(
            """
            UPDATE triage_runs
            SET status='TRANSPORT_ERROR',completed_at=?,
                error_code='transport_error',
                diagnostics_json='{"recovered_stale_reservation":true}'
            WHERE run_id=? AND status='STARTED'
            """,
            (completed_at, row["run_id"]),
        )
        if cursor.rowcount != 1:
            raise TriageError("triage stale reservation differs")
    return len(rows)


def run(
    database=DB,
    *,
    config_path=CONFIG_PATH,
    prompt_path=PROMPT_PATH,
    output_schema_path=OUTPUT_SCHEMA_PATH,
    incident_engine_path=INCIDENT_ENGINE_PATH,
    transport=ollama_request,
    now=utc_now,
    mode="shadow",
    learned_coverage=False,
):
    if database is None:
        raise TriageError("triage database is not configured")
    if mode not in {"shadow", "active"}:
        raise TriageError("triage mode is invalid")
    database = Path(database)
    config, prompt, schema, prompt_sha, schema_sha = load_artifacts(
        Path(config_path), Path(prompt_path), Path(output_schema_path)
    )
    engine = load_incident_engine(Path(incident_engine_path), database)
    now_value = now()
    now_ms = epoch_ms(now_value)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    reserved = None
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("BEGIN IMMEDIATE")
        validate_database_contract(connection)
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise TriageError("triage database quick_check failed")
        reconcile_started_runs(connection, now_value)
        register_versions(connection, config, prompt_sha, schema_sha)
        applied = apply_unapplied_decisions(connection, engine) if mode == "active" else 0
        promoted = promote_rules(connection, now_value) if learned_coverage and mode == "active" else 0
        transitions = sweep_triage_lifecycle(connection, engine, now_ms) if mode == "active" else 0
        batch, learned_applied = create_next_batch(
            connection,
            now_value,
            engine=engine,
            learned_coverage=learned_coverage and mode == "active",
        )
        applied += learned_applied
        connection.commit()
        if batch is None:
            return {
                "result": "idle", "invoked": 0, "applied_incidents": applied,
                "promoted_rules": promoted, "lifecycle_transitions": transitions,
            }
        connection.execute("BEGIN IMMEDIATE")
        batch = connection.execute(
            "SELECT * FROM triage_batches WHERE batch_id=?", (batch["batch_id"],)
        ).fetchone()
        if not attempt_due(connection, batch, now_ms):
            connection.commit()
            return {
                "result": "waiting", "invoked": 0, "batch_id": batch["batch_id"],
                "applied_incidents": applied, "promoted_rules": promoted,
                "lifecycle_transitions": transitions,
            }
        attempt = connection.execute(
            "SELECT COUNT(*)+1 FROM triage_runs WHERE batch_id=? AND model_version=? AND prompt_version=?",
            (batch["batch_id"], MODEL_VERSION, PROMPT_VERSION),
        ).fetchone()[0]
        request = request_object(config, prompt, schema, batch)
        request_json = canonical_json(request)
        run_id = run_identifier(batch["batch_id"], attempt)
        connection.execute(
            """
            INSERT INTO triage_runs (
                run_id,batch_id,model_version,prompt_version,attempt_number,
                request_sha256,status,started_at,completed_at,error_code,
                diagnostics_json
            ) VALUES (?,?,?,?,?,?,'STARTED',?,NULL,NULL,'{}')
            """,
            (
                run_id, batch["batch_id"], MODEL_VERSION, PROMPT_VERSION,
                attempt, sha256_text(request_json), now_value,
            ),
        )
        connection.commit()
        reserved = {"run_id": run_id, "batch_id": batch["batch_id"], "request_json": request_json}
    finally:
        connection.close()

    try:
        payload = transport(reserved["request_json"])
        result, diagnostics = parse_response(payload)
    except InferenceFailure as failure:
        finalize_failure(database, reserved["run_id"], failure, now())
        return {"result": "waiting", "invoked": 1, "batch_id": reserved["batch_id"], "failure": failure.status}

    completed_at = now()
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("BEGIN IMMEDIATE")
        batch = connection.execute(
            "SELECT * FROM triage_batches WHERE batch_id=? AND status='PENDING'",
            (reserved["batch_id"],),
        ).fetchone()
        if batch is None:
            raise TriageError("triage batch reservation differs")
        validation_context = dict(batch)
        validation_context["connection"] = connection
        result_json = validate_result(result, validation_context)
        for decision in result["decisions"]:
            item_json = canonical_json(decision)
            decision_id = "triage-decision-v1-" + sha256_text(
                canonical_json([reserved["run_id"], decision["signature_id"], item_json])
            )[:32]
            connection.execute(
                """
                INSERT INTO triage_decisions (
                    decision_id,run_id,batch_id,signature_id,decision,confidence,
                    category,title,summary,reason,result_json,result_sha256,
                    created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    decision_id, reserved["run_id"], reserved["batch_id"],
                    decision["signature_id"], decision["decision"],
                    decision["confidence"], decision["category"],
                    decision["title"], decision["summary"], decision["reason"],
                    item_json, sha256_text(item_json), completed_at,
                ),
            )
        connection.execute(
            """
            UPDATE triage_runs SET status='SUCCEEDED',completed_at=?,error_code=NULL,
                diagnostics_json=? WHERE run_id=? AND status='STARTED'
            """,
            (completed_at, canonical_json(diagnostics), reserved["run_id"]),
        )
        connection.execute(
            "UPDATE triage_batches SET status='SUCCEEDED',completed_at=? WHERE batch_id=? AND status='PENDING'",
            (completed_at, reserved["batch_id"]),
        )
        set_state(connection, CURSOR_KEY, batch["scan_end_event_id"], completed_at)
        applied = apply_unapplied_decisions(connection, engine) if mode == "active" else 0
        promoted = promote_rules(connection, completed_at) if learned_coverage and mode == "active" else 0
        connection.commit()
        return {
            "result": "pass", "invoked": 1, "batch_id": reserved["batch_id"],
            "decisions": len(result["decisions"]), "applied_incidents": applied,
            "promoted_rules": promoted, "result_sha256": sha256_text(result_json),
        }
    except InferenceFailure as failure:
        connection.rollback()
        finalize_failure(database, reserved["run_id"], failure, completed_at)
        return {"result": "waiting", "invoked": 1, "batch_id": reserved["batch_id"], "failure": failure.status}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    try:
        result = run()
        print(
            "GX10_AI_TRIAGE=" + result["result"].upper()
            + f" invoked={result.get('invoked', 0)}"
            + f" decisions={result.get('decisions', 0)}"
            + f" applied_incidents={result.get('applied_incidents', 0)}"
            + f" promoted_rules={result.get('promoted_rules', 0)}"
        )
        return 0
    except (OSError, sqlite3.Error, TriageError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("GX10_AI_TRIAGE=FAIL", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
