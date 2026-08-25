CREATE TABLE observability.incident_updates
(
    `timestamp` DateTime64(3, 'UTC'),
    `snapshot_id` String,
    `snapshot_version` UInt64,
    `incident_id` String,
    `device` String,
    `entity_type` LowCardinality(String),
    `entity_name` String,
    `event_family` LowCardinality(String),
    `protocol` LowCardinality(String),
    `lifecycle_status` LowCardinality(String),
    `severity` LowCardinality(String),
    `first_seen` DateTime64(3, 'UTC'),
    `last_seen` DateTime64(3, 'UTC'),
    `opened_at` Nullable(DateTime64(3, 'UTC')),
    `recovering_at` Nullable(DateTime64(3, 'UTC')),
    `resolved_at` Nullable(DateTime64(3, 'UTC')),
    `occurrence_count` UInt32,
    `repeat_count_total` UInt64,
    `state_change_count` UInt32,
    `last_observation_state` LowCardinality(String),
    `interface_flap` Bool,
    `engine_version` UInt16,
    `title` String,
    `body` String,
    `type` LowCardinality(String),
    `producer_schema` LowCardinality(String),
    `producer_version` UInt16,
    `raw_json` String DEFAULT ''
)
ENGINE = ReplacingMergeTree(snapshot_version)
ORDER BY incident_id
SETTINGS index_granularity = 8192;
