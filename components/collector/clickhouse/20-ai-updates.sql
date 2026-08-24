CREATE TABLE observability.ai_updates
(
    `timestamp` DateTime64(3, 'UTC'),
    `incident_id` String DEFAULT '',
    `run_id` String DEFAULT '',
    `device` String DEFAULT '',
    `model` LowCardinality(String) DEFAULT '',
    `type` LowCardinality(String) DEFAULT '',
    `status` LowCardinality(String) DEFAULT '',
    `severity` LowCardinality(String) DEFAULT '',
    `first_seen` Nullable(DateTime64(3, 'UTC')),
    `last_seen` Nullable(DateTime64(3, 'UTC')),
    `occurrence_count` UInt32 DEFAULT 0,
    `title` String,
    `body` String,
    `tags` Array(String) DEFAULT [],
    `raw_json` String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, incident_id)
TTL timestamp + toIntervalMonth(12)
SETTINGS index_granularity = 8192

CREATE TABLE observability.ai_result_devices
(
    `run_id` String,
    `device` String,
    `mapped_at` DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY run_id
TTL mapped_at + toIntervalMonth(12)
SETTINGS index_granularity = 8192
