PRAGMA foreign_keys=ON;
BEGIN IMMEDIATE;

CREATE TABLE incidents (
    incident_id TEXT PRIMARY KEY,
    correlation_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('CANDIDATE', 'OPEN', 'RECOVERING', 'RESOLVED')
    ),
    event_family TEXT NOT NULL,
    protocol TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    severity TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    first_seen_epoch_ms INTEGER NOT NULL,
    last_seen TEXT NOT NULL,
    last_seen_epoch_ms INTEGER NOT NULL,
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count >= 1),
    repeat_count_total INTEGER NOT NULL CHECK (repeat_count_total >= 1),
    observation_state_changes INTEGER NOT NULL DEFAULT 0 CHECK (
        observation_state_changes >= 0
    ),
    last_observation_state TEXT,
    opened_at TEXT,
    recovering_at TEXT,
    resolved_at TEXT,
    last_event_id INTEGER NOT NULL,
    context_json TEXT NOT NULL,
    engine_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(last_event_id) REFERENCES recent_events(id)
);

CREATE UNIQUE INDEX idx_incidents_active_correlation
ON incidents(correlation_key)
WHERE status != 'RESOLVED';

CREATE INDEX idx_incidents_status_last_seen
ON incidents(status, last_seen_epoch_ms);

CREATE INDEX idx_incidents_entity
ON incidents(entity_type, entity_key, last_seen_epoch_ms);

CREATE TABLE incident_evidence (
    incident_id TEXT NOT NULL,
    evidence_sequence INTEGER NOT NULL CHECK (evidence_sequence >= 1),
    event_id INTEGER NOT NULL UNIQUE,
    evidence_kind TEXT NOT NULL CHECK (
        evidence_kind IN ('adverse', 'recovery', 'supporting')
    ),
    observed_at TEXT NOT NULL,
    observed_at_epoch_ms INTEGER NOT NULL,
    event_code TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    observation_state TEXT,
    repeat_count INTEGER NOT NULL CHECK (repeat_count >= 1),
    attributes_json TEXT NOT NULL,
    PRIMARY KEY(incident_id, evidence_sequence),
    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id),
    FOREIGN KEY(event_id) REFERENCES recent_events(id)
);

CREATE INDEX idx_incident_evidence_time
ON incident_evidence(incident_id, observed_at_epoch_ms);

CREATE TABLE incident_transitions (
    incident_id TEXT NOT NULL,
    transition_sequence INTEGER NOT NULL CHECK (transition_sequence >= 1),
    from_status TEXT CHECK (
        from_status IS NULL OR
        from_status IN ('CANDIDATE', 'OPEN', 'RECOVERING', 'RESOLVED')
    ),
    to_status TEXT NOT NULL CHECK (
        to_status IN ('CANDIDATE', 'OPEN', 'RECOVERING', 'RESOLVED')
    ),
    event_id INTEGER,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    occurred_at_epoch_ms INTEGER NOT NULL,
    PRIMARY KEY(incident_id, transition_sequence),
    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id),
    FOREIGN KEY(event_id) REFERENCES recent_events(id)
);

CREATE INDEX idx_incident_transitions_time
ON incident_transitions(incident_id, occurred_at_epoch_ms);

CREATE TRIGGER incident_evidence_no_update
BEFORE UPDATE ON incident_evidence
BEGIN
    SELECT RAISE(ABORT, 'incident evidence is append-only');
END;

CREATE TRIGGER incident_evidence_no_delete
BEFORE DELETE ON incident_evidence
BEGIN
    SELECT RAISE(ABORT, 'incident evidence is append-only');
END;

CREATE TRIGGER incident_transitions_no_update
BEFORE UPDATE ON incident_transitions
BEGIN
    SELECT RAISE(ABORT, 'incident transitions are append-only');
END;

CREATE TRIGGER incident_transitions_no_delete
BEFORE DELETE ON incident_transitions
BEGIN
    SELECT RAISE(ABORT, 'incident transitions are append-only');
END;

COMMIT;
