# Deterministic NOC Incident Workflow

## Purpose

The `AI Incident Analysis - Enhanced` dashboard is the operational NOC queue. It presents authoritative deterministic GX10 incident state; it does not wait for model inference and does not use AI text as incident truth.

The original `AI Incident Analysis` dashboard remains unchanged as the assessment-history fallback.

## Operator windows

The enhanced dashboard has three mutually understandable operational windows:

- **Active Events** — unresolved non-interface incidents. This query deliberately ignores the dashboard time picker, so a persistent incident remains visible until the deterministic engine resolves it. `Event Details` shows the latest stored AI summary when available and a deterministic event/entity/current-state description otherwise.
- **Interface Flaps** — every unresolved incident whose deterministic `entity_type` is `interface`, including its first adverse observation before a second state change exists. Every interface incident is excluded from Active Events and remains here until resolution.
- **Resolved Events** — the latest state of resolved incidents whose `resolved_at` timestamp falls inside the selected dashboard range.

Each window has a server-side text search across device, entity, event family, protocol, title, and incident ID. Active search also covers the displayed AI/deterministic detail. Active and Resolved have a server-side severity selector. The tables expose Device and Incident ID; they do not contain an assigned-operator field or an AI recommendation field.

## State authority and movement

GX10 owns deterministic lifecycle state in its local `incidents` table. The dashboard is a projection, not an editable ticket database.

```text
GX10 incidents
  -> changed-state cursor
  -> immutable incident_lifecycle JSONL batch
  -> existing one-file write-only sender
  -> collector validation and replay ledger
  -> Vector lifecycle-only route
  -> ClickHouse incident_updates
  -> Grafana latest-per-incident queries
```

An incident moves between dashboard windows only when the deterministic engine changes its lifecycle state:

- `CANDIDATE`, `OPEN`, or `RECOVERING` stays active.
- every active interface entity appears only in Interface Flaps, even when its lifecycle snapshot still has zero recorded state changes.
- `RESOLVED` leaves both active windows and appears in Resolved Events for ranges containing its resolution time.
- a later relapse produces a newer snapshot and returns the incident to the appropriate active window.

Manual resolution is intentionally not implemented. Adding it requires a separately designed, authenticated acknowledgement/override data contract rather than mutating Grafana presentation state.

## Transport and storage contract

The lifecycle producer is independent of the AI-result producer but shares its filesystem lock and ready/delivered directories. It emits only changed incidents in content-addressed batches of at most 100 records and 256 KiB. A protected local SQLite cursor records the last exported snapshot version per incident.

Lifecycle batches use `type = incident_lifecycle`. The collector gate validates their exact shape and Vector routes them exclusively to `observability.incident_updates`; they must never enter `observability.ai_updates`.

The exported `interface_flap` field continues to record whether interface state-change evidence exists. Dashboard queue placement deliberately uses authoritative `entity_type = interface` instead, so a newly opened interface-down incident cannot leak into Active Events before its next transition.

`incident_updates` has no TTL. Latest-per-incident dashboard queries use `argMax` over `(snapshot_version, snapshot_id)`, so active state does not age out and resolved history remains available. Retention changes require an explicit policy decision.

## Production acceptance

Item 34 production activation passed with:

```text
initial_incidents=804
initial_lifecycle_batches=9
latest_incidents=804
active_events=26
active_interface_flaps=10
resolved=768
empty_device=0
invalid_lifecycle_timestamp_rows=0
lifecycle_rows_in_ai_updates=0
grafana_resources_exact=6
grafana_queries_passed=13
```

Natural scheduled changes continued through the same bounded path after activation. Both GX10 timers remained enabled/active with zero service restarts, and the collector gate, Vector, ClickHouse, and Grafana stayed healthy.

Item 35 production correction passed after operator review. The repository candidate was published and independently verified before mutation; all thirteen queries passed before and after the protected change; Grafana `dryRun=All` identified only the enhanced resource for replacement; and all six live specifications reread exact afterward. Aggregate latest-state verification returned:

```text
active_non_interface_events=2
active_interface_events=34
active_interface_events_in_active_window=0
active_rows_with_ai_summary=0
active_rows_with_deterministic_fallback=2
grafana_resources_exact=6
grafana_queries_passed=13
```

The original dashboard remains byte-exact. Collector services stayed healthy with zero relevant restarts, and no lifecycle data, schema, transport, GX10 artifact, model behavior, or schedule changed.
