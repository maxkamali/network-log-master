PRAGMA foreign_keys=ON;
BEGIN IMMEDIATE;

CREATE TABLE reasoning_packets (
    packet_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    policy_version INTEGER NOT NULL CHECK (policy_version = 1),
    packet_version INTEGER NOT NULL CHECK (packet_version = 1),
    primary_reason TEXT NOT NULL CHECK (
        primary_reason IN (
            'critical_condition',
            'incident_reopened',
            'incident_opened',
            'interface_flap',
            'ospf_retransmission',
            'incident_recovering',
            'incident_resolved',
            'meaningful_update'
        )
    ),
    wake_reasons_json TEXT NOT NULL,
    priority INTEGER NOT NULL CHECK (priority BETWEEN 0 AND 100),
    as_of_event_id INTEGER NOT NULL,
    as_of_evidence_sequence INTEGER NOT NULL CHECK (
        as_of_evidence_sequence >= 1
    ),
    as_of_transition_sequence INTEGER NOT NULL CHECK (
        as_of_transition_sequence >= 1
    ),
    basis_repeat_count_total INTEGER NOT NULL CHECK (
        basis_repeat_count_total >= 1
    ),
    basis_state_change_count INTEGER NOT NULL CHECK (
        basis_state_change_count >= 0
    ),
    basis_last_seen_epoch_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    packet_json TEXT NOT NULL,
    packet_sha256 TEXT NOT NULL CHECK (length(packet_sha256) = 64),
    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id),
    FOREIGN KEY(as_of_event_id) REFERENCES recent_events(id),
    UNIQUE(
        incident_id,
        policy_version,
        packet_version,
        as_of_evidence_sequence,
        as_of_transition_sequence
    )
);

CREATE INDEX idx_reasoning_packets_priority
ON reasoning_packets(priority DESC, basis_last_seen_epoch_ms, packet_id);

CREATE INDEX idx_reasoning_packets_incident
ON reasoning_packets(incident_id, as_of_evidence_sequence, as_of_transition_sequence);

CREATE TRIGGER reasoning_packets_no_update
BEFORE UPDATE ON reasoning_packets
BEGIN
    SELECT RAISE(ABORT, 'reasoning packets are append-only');
END;

CREATE TRIGGER reasoning_packets_no_delete
BEFORE DELETE ON reasoning_packets
BEGIN
    SELECT RAISE(ABORT, 'reasoning packets are append-only');
END;

COMMIT;
