# ClickHouse

## Role

ClickHouse is the durable analytical store for raw observations and validated AI updates. It is not written directly by GX10.

## Raw syslog table

The current raw-observation table is logically represented by `observability.syslog` and retains approximately 12 months of data.

Representative schema:

```text
timestamp            DateTime64(9, 'UTC')
ingest_timestamp     DateTime64(9, 'UTC')
device_timestamp     Nullable(DateTime64(9, 'UTC'))
collector_local_time String
source_ip             String
source_port           UInt16
hostname              String
host                  String
facility              LowCardinality(String)
severity              LowCardinality(String)
appname               String
message               String
raw_message           String
parse_status          LowCardinality(String)
source_type           LowCardinality(String)
version               UInt8
event_json            String
```

Storage characteristics:

- MergeTree family
- monthly partitioning
- ordering begins with event time and source identity
- retention approximately 12 months

The raw table is a replay/evidence store. Presentation-specific convenience fields belong in semantic views rather than forcing display concerns into the durable schema.

## AI update table

Validated model/result records are stored separately in `observability.ai_updates` with approximately 12 months retention.

Representative schema:

```text
timestamp        DateTime64(3, 'UTC')
incident_id      String
run_id           String
device           String
model            LowCardinality(String)
type             LowCardinality(String)
status           LowCardinality(String)
severity         LowCardinality(String)
first_seen       Nullable(DateTime64(3, 'UTC'))
last_seen        Nullable(DateTime64(3, 'UTC'))
occurrence_count UInt32
title            String
body             String
tags             Array(String)
raw_json         String
```

This table contains accepted AI result records only. Malformed files are rejected before this ingestion boundary.

`observability.ai_result_devices` is a small 12-month private lookup keyed by `run_id`. It supplies device identity only for immutable legacy result files that predate the direct `device` projection. Grafana has read-only access; Vector does not write this table. Current result files carry `device` directly.

## Deterministic incident update table

Authoritative GX10 incident snapshots are stored separately in `observability.incident_updates`. This table is not an AI-output table.

Representative fields include:

```text
snapshot_id          String
snapshot_version     UInt64
incident_id          String
device               String
entity_type          LowCardinality(String)
entity_name          String
event_family         LowCardinality(String)
protocol             LowCardinality(String)
lifecycle_status     LowCardinality(String)
severity             LowCardinality(String)
first_seen           DateTime64(3, 'UTC')
last_seen            DateTime64(3, 'UTC')
resolved_at          Nullable(DateTime64(3, 'UTC'))
occurrence_count     UInt32
recurrence_count     UInt32
state_change_count   UInt32
interface_flap       Bool
type                 LowCardinality(String)
raw_json             String
```

The table uses `ReplacingMergeTree(snapshot_version)` ordered by `incident_id`. It intentionally has no TTL: unresolved state must not disappear because it is old, and resolved history remains available until an explicit retention policy is approved. Grafana selects the latest row per incident with `argMax` over `(snapshot_version, snapshot_id)`. The additive `recurrence_count` column defaults to zero for immutable producer-version-1 history; producer version 2 supplies the derived relapse count directly.

Vector may insert into this table and Grafana may select from it. Lifecycle records are routed exclusively here; `type = incident_lifecycle` must never appear in `observability.ai_updates`.

## Grafana semantic view

Grafana reads network logs through a semantic view that exposes display-oriented fields such as level, body, and device context while preserving the raw table unchanged.

This separation is intentional:

- raw schema -> durable evidence and replay
- semantic view -> operator presentation
- AI result table -> validated reasoning output
- incident update table -> authoritative deterministic NOC lifecycle projection

## Vector sink exception

The deployed Vector-to-ClickHouse path has a known configuration exception: startup sink health checking is disabled because the health-check authentication path failed while steady-state inserts were independently proven operational.

Treat that setting as an operationally validated exception. Do not remove it during cleanup without reproducing and resolving the authentication behavior first.

## Access boundary

GX10 does not receive direct ClickHouse write authority. AI results and deterministic lifecycle snapshots return through the same bounded write-only file path and collector-side validation gate, then split into exclusive Vector sinks.
