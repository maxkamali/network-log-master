PRAGMA foreign_keys=ON;
BEGIN IMMEDIATE;

CREATE TABLE triage_signatures (
    signature_id TEXT PRIMARY KEY,
    signature_version INTEGER NOT NULL CHECK (signature_version = 1),
    vendor_hint TEXT NOT NULL,
    os_family TEXT NOT NULL,
    event_code TEXT NOT NULL,
    event_family TEXT NOT NULL,
    template_text TEXT NOT NULL,
    template_sha256 TEXT NOT NULL CHECK (length(template_sha256) = 64),
    created_at TEXT NOT NULL
);

CREATE TABLE triage_batches (
    batch_id TEXT PRIMARY KEY,
    policy_version INTEGER NOT NULL CHECK (policy_version = 1),
    scan_start_event_id INTEGER NOT NULL CHECK (scan_start_event_id >= 1),
    scan_end_event_id INTEGER NOT NULL CHECK (
        scan_end_event_id >= scan_start_event_id
    ),
    priority_severity INTEGER NOT NULL CHECK (priority_severity BETWEEN 0 AND 5),
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'SUCCEEDED')),
    packet_json TEXT NOT NULL,
    packet_sha256 TEXT NOT NULL CHECK (length(packet_sha256) = 64),
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE UNIQUE INDEX idx_triage_batches_pending
ON triage_batches(status)
WHERE status = 'PENDING';

CREATE TRIGGER triage_batches_guard_update
BEFORE UPDATE ON triage_batches
WHEN OLD.status != 'PENDING'
  OR NEW.status != 'SUCCEEDED'
  OR OLD.batch_id != NEW.batch_id
  OR OLD.policy_version != NEW.policy_version
  OR OLD.scan_start_event_id != NEW.scan_start_event_id
  OR OLD.scan_end_event_id != NEW.scan_end_event_id
  OR OLD.priority_severity != NEW.priority_severity
  OR OLD.packet_json != NEW.packet_json
  OR OLD.packet_sha256 != NEW.packet_sha256
  OR OLD.created_at != NEW.created_at
  OR OLD.completed_at IS NOT NULL
  OR NEW.completed_at IS NULL
BEGIN
    SELECT RAISE(ABORT, 'invalid triage batch transition');
END;

CREATE TRIGGER triage_batches_no_delete
BEFORE DELETE ON triage_batches
BEGIN
    SELECT RAISE(ABORT, 'triage batches cannot be deleted');
END;

CREATE TABLE triage_batch_members (
    batch_id TEXT NOT NULL,
    signature_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    device TEXT NOT NULL,
    severity_number INTEGER NOT NULL CHECK (severity_number BETWEEN 0 AND 5),
    PRIMARY KEY(batch_id, event_id),
    FOREIGN KEY(batch_id) REFERENCES triage_batches(batch_id),
    FOREIGN KEY(signature_id) REFERENCES triage_signatures(signature_id),
    FOREIGN KEY(event_id) REFERENCES recent_events(id)
);

CREATE INDEX idx_triage_members_signature
ON triage_batch_members(batch_id, signature_id, event_id);

CREATE TABLE triage_runs (
    run_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
    status TEXT NOT NULL CHECK (
        status IN (
            'STARTED',
            'SUCCEEDED',
            'INFERENCE_UNAVAILABLE',
            'INFERENCE_TIMEOUT',
            'TRANSPORT_ERROR',
            'INVALID_RESPONSE',
            'INVALID_OUTPUT'
        )
    ),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_code TEXT,
    diagnostics_json TEXT NOT NULL,
    FOREIGN KEY(batch_id) REFERENCES triage_batches(batch_id),
    FOREIGN KEY(model_version) REFERENCES reasoning_model_versions(model_version),
    FOREIGN KEY(prompt_version) REFERENCES reasoning_prompt_versions(prompt_version),
    UNIQUE(batch_id, model_version, prompt_version, attempt_number)
);

CREATE INDEX idx_triage_runs_batch
ON triage_runs(batch_id, attempt_number);

CREATE TABLE triage_decisions (
    decision_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    signature_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('incident', 'ignore', 'insufficient_evidence')
    ),
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 95),
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    reason TEXT NOT NULL,
    result_json TEXT NOT NULL,
    result_sha256 TEXT NOT NULL CHECK (length(result_sha256) = 64),
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES triage_runs(run_id),
    FOREIGN KEY(batch_id) REFERENCES triage_batches(batch_id),
    FOREIGN KEY(signature_id) REFERENCES triage_signatures(signature_id),
    UNIQUE(batch_id, signature_id)
);

CREATE INDEX idx_triage_decisions_signature
ON triage_decisions(signature_id, created_at);

CREATE TABLE event_detection_overrides (
    event_id INTEGER PRIMARY KEY,
    signature_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (
        source_type IN ('ai_decision', 'learned_rule')
    ),
    source_id TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type = 'event_signature'),
    entity_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state = 'detected'),
    signal_type TEXT NOT NULL CHECK (signal_type = 'degradation'),
    attributes_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES recent_events(id),
    FOREIGN KEY(signature_id) REFERENCES triage_signatures(signature_id)
);

CREATE INDEX idx_detection_overrides_signature
ON event_detection_overrides(signature_id, event_id);

CREATE TABLE triage_incident_summaries (
    incident_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    signature_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 95),
    created_at TEXT NOT NULL,
    PRIMARY KEY(incident_id, source_id),
    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id),
    FOREIGN KEY(signature_id) REFERENCES triage_signatures(signature_id)
);

CREATE INDEX idx_triage_incident_summary_latest
ON triage_incident_summaries(incident_id, created_at, source_id);

CREATE TABLE learned_detection_rules (
    rule_id TEXT PRIMARY KEY,
    rule_version INTEGER NOT NULL CHECK (rule_version = 1),
    event_code TEXT NOT NULL,
    maximum_severity_number INTEGER NOT NULL CHECK (
        maximum_severity_number = 3
    ),
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'REVOKED')),
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE UNIQUE INDEX idx_learned_rules_active_code
ON learned_detection_rules(event_code)
WHERE status = 'ACTIVE';

CREATE TRIGGER triage_signatures_no_update
BEFORE UPDATE ON triage_signatures
BEGIN
    SELECT RAISE(ABORT, 'triage signatures are append-only');
END;

CREATE TRIGGER triage_signatures_no_delete
BEFORE DELETE ON triage_signatures
BEGIN
    SELECT RAISE(ABORT, 'triage signatures are append-only');
END;

CREATE TRIGGER triage_batch_members_no_update
BEFORE UPDATE ON triage_batch_members
BEGIN
    SELECT RAISE(ABORT, 'triage batch members are append-only');
END;

CREATE TRIGGER triage_batch_members_no_delete
BEFORE DELETE ON triage_batch_members
BEGIN
    SELECT RAISE(ABORT, 'triage batch members are append-only');
END;

CREATE TRIGGER triage_runs_guard_update
BEFORE UPDATE ON triage_runs
WHEN OLD.status != 'STARTED'
  OR NEW.status = 'STARTED'
  OR OLD.run_id != NEW.run_id
  OR OLD.batch_id != NEW.batch_id
  OR OLD.model_version != NEW.model_version
  OR OLD.prompt_version != NEW.prompt_version
  OR OLD.attempt_number != NEW.attempt_number
  OR OLD.request_sha256 != NEW.request_sha256
  OR OLD.started_at != NEW.started_at
  OR OLD.completed_at IS NOT NULL
  OR NEW.completed_at IS NULL
  OR (NEW.status = 'SUCCEEDED' AND NEW.error_code IS NOT NULL)
  OR (NEW.status != 'SUCCEEDED' AND NEW.error_code IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'invalid triage run transition');
END;

CREATE TRIGGER triage_runs_no_delete
BEFORE DELETE ON triage_runs
BEGIN
    SELECT RAISE(ABORT, 'triage runs cannot be deleted');
END;

CREATE TRIGGER triage_decisions_no_update
BEFORE UPDATE ON triage_decisions
BEGIN
    SELECT RAISE(ABORT, 'triage decisions are append-only');
END;

CREATE TRIGGER triage_decisions_no_delete
BEFORE DELETE ON triage_decisions
BEGIN
    SELECT RAISE(ABORT, 'triage decisions are append-only');
END;

CREATE TRIGGER detection_overrides_no_update
BEFORE UPDATE ON event_detection_overrides
BEGIN
    SELECT RAISE(ABORT, 'event detection overrides are append-only');
END;

CREATE TRIGGER detection_overrides_no_delete
BEFORE DELETE ON event_detection_overrides
BEGIN
    SELECT RAISE(ABORT, 'event detection overrides are append-only');
END;

CREATE TRIGGER triage_incident_summaries_no_update
BEFORE UPDATE ON triage_incident_summaries
BEGIN
    SELECT RAISE(ABORT, 'triage incident summaries are append-only');
END;

CREATE TRIGGER triage_incident_summaries_no_delete
BEFORE DELETE ON triage_incident_summaries
BEGIN
    SELECT RAISE(ABORT, 'triage incident summaries are append-only');
END;

CREATE TRIGGER learned_detection_rules_guard_update
BEFORE UPDATE ON learned_detection_rules
WHEN OLD.status != 'ACTIVE'
  OR NEW.status != 'REVOKED'
  OR OLD.rule_id != NEW.rule_id
  OR OLD.rule_version != NEW.rule_version
  OR OLD.event_code != NEW.event_code
  OR OLD.maximum_severity_number != NEW.maximum_severity_number
  OR OLD.category != NEW.category
  OR OLD.title != NEW.title
  OR OLD.summary != NEW.summary
  OR OLD.evidence_json != NEW.evidence_json
  OR OLD.created_at != NEW.created_at
  OR OLD.revoked_at IS NOT NULL
  OR NEW.revoked_at IS NULL
BEGIN
    SELECT RAISE(ABORT, 'invalid learned detection rule transition');
END;

CREATE TRIGGER learned_detection_rules_no_delete
BEFORE DELETE ON learned_detection_rules
BEGIN
    SELECT RAISE(ABORT, 'learned detection rules cannot be deleted');
END;

COMMIT;
