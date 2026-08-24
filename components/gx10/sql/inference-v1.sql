PRAGMA foreign_keys=ON;
BEGIN IMMEDIATE;

CREATE TABLE reasoning_model_versions (
    model_version TEXT PRIMARY KEY,
    provider TEXT NOT NULL CHECK (provider = 'ollama'),
    model_reference TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    config_digest TEXT NOT NULL CHECK (
        length(config_digest) = 71 AND config_digest LIKE 'sha256:%'
    ),
    request_options_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE reasoning_prompt_versions (
    prompt_version TEXT PRIMARY KEY,
    system_prompt_sha256 TEXT NOT NULL CHECK (
        length(system_prompt_sha256) = 64
    ),
    output_schema_sha256 TEXT NOT NULL CHECK (
        length(output_schema_sha256) = 64
    ),
    output_schema_version INTEGER NOT NULL CHECK (
        output_schema_version BETWEEN 1 AND 65535
    ),
    created_at TEXT NOT NULL
);

CREATE TABLE reasoning_runs (
    run_id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL,
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
    FOREIGN KEY(packet_id) REFERENCES reasoning_packets(packet_id),
    FOREIGN KEY(model_version) REFERENCES reasoning_model_versions(model_version),
    FOREIGN KEY(prompt_version) REFERENCES reasoning_prompt_versions(prompt_version),
    UNIQUE(packet_id, model_version, prompt_version, attempt_number)
);

CREATE TABLE reasoning_results (
    run_id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (
        schema_version BETWEEN 1 AND 65535
    ),
    disposition TEXT NOT NULL CHECK (
        disposition IN (
            'action_required',
            'monitor',
            'resolved_no_action',
            'insufficient_evidence'
        )
    ),
    severity TEXT NOT NULL CHECK (
        severity IN (
            'critical',
            'high',
            'medium',
            'low',
            'informational'
        )
    ),
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
    summary TEXT NOT NULL CHECK (length(summary) BETWEEN 1 AND 4000),
    result_json TEXT NOT NULL,
    result_sha256 TEXT NOT NULL CHECK (length(result_sha256) = 64),
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES reasoning_runs(run_id),
    FOREIGN KEY(packet_id) REFERENCES reasoning_packets(packet_id),
    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
);

CREATE INDEX idx_reasoning_runs_packet
ON reasoning_runs(packet_id, model_version, prompt_version, attempt_number);

CREATE INDEX idx_reasoning_runs_status
ON reasoning_runs(status, started_at, run_id);

CREATE INDEX idx_reasoning_results_incident
ON reasoning_results(incident_id, created_at, run_id);

CREATE TRIGGER reasoning_model_versions_no_update
BEFORE UPDATE ON reasoning_model_versions
BEGIN
    SELECT RAISE(ABORT, 'reasoning model versions are append-only');
END;

CREATE TRIGGER reasoning_model_versions_no_delete
BEFORE DELETE ON reasoning_model_versions
BEGIN
    SELECT RAISE(ABORT, 'reasoning model versions are append-only');
END;

CREATE TRIGGER reasoning_prompt_versions_no_update
BEFORE UPDATE ON reasoning_prompt_versions
BEGIN
    SELECT RAISE(ABORT, 'reasoning prompt versions are append-only');
END;

CREATE TRIGGER reasoning_prompt_versions_no_delete
BEFORE DELETE ON reasoning_prompt_versions
BEGIN
    SELECT RAISE(ABORT, 'reasoning prompt versions are append-only');
END;

CREATE TRIGGER reasoning_runs_guard_update
BEFORE UPDATE ON reasoning_runs
WHEN
    OLD.status != 'STARTED'
    OR NEW.status = 'STARTED'
    OR OLD.run_id != NEW.run_id
    OR OLD.packet_id != NEW.packet_id
    OR OLD.model_version != NEW.model_version
    OR OLD.prompt_version != NEW.prompt_version
    OR OLD.attempt_number != NEW.attempt_number
    OR OLD.request_sha256 != NEW.request_sha256
    OR OLD.started_at != NEW.started_at
    OR OLD.completed_at IS NOT NULL
    OR NEW.completed_at IS NULL
    OR (
        NEW.status = 'SUCCEEDED'
        AND (
            NEW.error_code IS NOT NULL
            OR NOT EXISTS (
                SELECT 1 FROM reasoning_results
                WHERE run_id = NEW.run_id
            )
        )
    )
    OR (
        NEW.status != 'SUCCEEDED'
        AND (
            NEW.error_code IS NULL
            OR EXISTS (
                SELECT 1 FROM reasoning_results
                WHERE run_id = NEW.run_id
            )
        )
    )
BEGIN
    SELECT RAISE(ABORT, 'invalid reasoning run transition');
END;

CREATE TRIGGER reasoning_runs_no_delete
BEFORE DELETE ON reasoning_runs
BEGIN
    SELECT RAISE(ABORT, 'reasoning runs cannot be deleted');
END;

CREATE TRIGGER reasoning_results_no_update
BEFORE UPDATE ON reasoning_results
BEGIN
    SELECT RAISE(ABORT, 'reasoning results are append-only');
END;

CREATE TRIGGER reasoning_results_no_delete
BEFORE DELETE ON reasoning_results
BEGIN
    SELECT RAISE(ABORT, 'reasoning results are append-only');
END;

COMMIT;
