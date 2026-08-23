PRAGMA foreign_keys=ON;
BEGIN IMMEDIATE;

CREATE TABLE agent_state ( key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL );

CREATE TABLE source_files ( remote_path TEXT PRIMARY KEY, local_path TEXT, size_bytes INTEGER, sha256 TEXT, status TEXT NOT NULL DEFAULT 'discovered' CHECK ( status IN ( 'discovered', 'downloaded', 'processing', 'processed', 'failed' ) ), discovered_at TEXT NOT NULL, downloaded_at TEXT, processed_at TEXT, error TEXT , record_count INTEGER);

CREATE TABLE recent_events ( id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT NOT NULL, record_number INTEGER NOT NULL, timestamp TEXT NOT NULL, device_timestamp TEXT, hostname TEXT, source_ip TEXT, source_port INTEGER, facility TEXT, severity TEXT, message TEXT NOT NULL, raw_message TEXT, parse_status TEXT, parser TEXT, event_json TEXT NOT NULL, timestamp_epoch_ms INTEGER, FOREIGN KEY(source_file) REFERENCES source_files(remote_path), UNIQUE(source_file, record_number) );

CREATE TABLE suppression_rules ( id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, rule_type TEXT NOT NULL CHECK ( rule_type IN ( 'event_code_exact', 'event_code_prefix', 'message_regex' ) ), pattern TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)), reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL );

CREATE TABLE event_enrichment ( event_id INTEGER PRIMARY KEY, event_code TEXT NOT NULL DEFAULT '', family TEXT NOT NULL DEFAULT 'unknown', device TEXT NOT NULL DEFAULT '', entity_type TEXT, entity_key TEXT, state TEXT, attention_eligible INTEGER NOT NULL DEFAULT 1 CHECK ( attention_eligible IN (0,1) ), suppression_rule_id INTEGER, classified_at TEXT NOT NULL, repeat_count INTEGER NOT NULL DEFAULT 1, classification_version INTEGER NOT NULL DEFAULT 0, vendor_hint TEXT NOT NULL DEFAULT 'unknown', protocol TEXT NOT NULL DEFAULT '', signal_type TEXT NOT NULL DEFAULT 'observation', attributes_json TEXT NOT NULL DEFAULT '{}', FOREIGN KEY(event_id) REFERENCES recent_events(id), FOREIGN KEY(suppression_rule_id) REFERENCES suppression_rules(id) );

CREATE INDEX idx_enrichment_attention ON event_enrichment(attention_eligible);
CREATE INDEX idx_enrichment_entity ON event_enrichment(entity_type, entity_key);
CREATE INDEX idx_enrichment_event_code ON event_enrichment(event_code);
CREATE INDEX idx_enrichment_family ON event_enrichment(family);
CREATE INDEX idx_enrichment_protocol ON event_enrichment(protocol);
CREATE INDEX idx_enrichment_signal_type ON event_enrichment(signal_type);
CREATE INDEX idx_enrichment_vendor_hint ON event_enrichment(vendor_hint);
CREATE INDEX idx_recent_events_device_epoch ON recent_events(hostname, timestamp_epoch_ms);
CREATE INDEX idx_recent_events_device_time ON recent_events(hostname, timestamp);
CREATE INDEX idx_recent_events_epoch ON recent_events(timestamp_epoch_ms);
CREATE INDEX idx_recent_events_severity_time ON recent_events(severity, timestamp);
CREATE INDEX idx_recent_events_source_ip_time ON recent_events(source_ip, timestamp);
CREATE INDEX idx_recent_events_timestamp ON recent_events(timestamp);

INSERT INTO suppression_rules
    (id, name, rule_type, pattern, enabled, reason, created_at)
VALUES
    (
        1,
        'suppress-icmpv6-nd-log',
        'event_code_exact',
        'ICMPV6-3-ND_LOG',
        1,
        'Reconstructed functional suppression from GX10 item 12H.',
        '1970-01-01T00:00:00+00:00'
    ),
    (
        2,
        'suppress-icmpv6-nd-ra-log',
        'event_code_exact',
        'ICMPV6-3-ND_RA_LOG',
        1,
        'Reconstructed functional suppression from GX10 item 12H.',
        '1970-01-01T00:00:00+00:00'
    );

COMMIT;
