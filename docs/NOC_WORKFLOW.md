# Deterministic NOC Incident Workflow

## Purpose

The `AI Incident Analysis - Enhanced` dashboard is the operational NOC queue. It presents authoritative GX10 incident lifecycle state. Deterministically covered events do not wait for inference. The hidden side channel may admit otherwise uncovered important events only after a strict local-model decision; after admission, lifecycle state—not Grafana or subsequent model text—is authoritative.

The original `AI Incident Analysis` dashboard remains unchanged as the assessment-history fallback.

## Operator windows

The enhanced dashboard has three mutually understandable operational windows:

- **Active Events** — unresolved non-interface incidents. This query deliberately ignores the dashboard time picker, so a persistent incident remains visible until the deterministic engine resolves it. Confirmed recovered BGP/OSPF/OSPFv3 incidents remain here for 24 continuous healthy hours and display `MONITORING`. `Event Details` shows the latest stored AI summary when available and a deterministic event/entity/current-state description otherwise.
- **Interface Flaps** — a rolling raw-log rate view. A device/interface pair appears only after at least 10 `%ETHPORT-5-IF_DOWN_LINK_FAILURE` transitions in the preceding 60 minutes, independent of the dashboard time picker. A single down event, a port that goes down and stays down, and lower-rate reboot/bounce noise remain hidden. The row leaves automatically when its rolling count falls below 10.
- **Resolved Events** — the latest state of resolved non-interface incidents whose `resolved_at` timestamp falls inside the selected dashboard range. Interface lifecycle history remains retained and searchable in raw logs, but is intentionally absent from this operator queue.

Each window has a server-side text search. Active and Resolved search device, entity, event family, protocol, title, and incident ID; Active also covers the displayed AI/deterministic detail. Interface Flaps searches device and interface. Active and Resolved have a server-side severity selector. The incident tables expose Device and Incident ID; the rolling flap table exposes Device, Interface, rolling bounce count, and first/last bounce within the current hour. No table contains an assigned-operator field or an AI recommendation field.

Every cell provides a `View matching logs` link with the SQL editor initially collapsed. Active and Resolved use the selected incident ID: authoritative device plus entity, protocol, or event family must match inside the incident's first-seen through last-seen/resolution window, with a 15-minute context boundary. The Interface Flaps link is one-click and uses hidden hex-encoded row keys to select that exact device/interface over the same rolling 60-minute window. All lookups are read-only, newest first, and capped at 1,000 rows.

The four linked `NOC View` summaries—Severity Breakdown, Top Devices, OSPF Events, and BGP Events—use their sole data link as a one-click target and also open Explore with the SQL editor initially collapsed. The drilldown remains a read-only view over the selected dashboard time range.

## Access boundary

The working Grafana deployment exposes the operational queue through a dedicated NOC organization. Its Viewer sees only `NOC View`, `AI Incident Analysis - Enhanced`, and the two required read-only datasource copies. `NOC View` is the home dashboard and both dashboards are starred. Dashboard saves, administration, and access to dashboards in the main organization are denied.

Explore is available to the Viewer for read-only investigation. Grafana implements this compatibility by permitting temporary panel editing, but persistence remains denied and the available datasource inventory is isolated to the two read-only copies. Grafana OSS does not support an exact per-user navigation allowlist, so standard Viewer-accessible sections may still be present even though administration and unrelated organization resources are not.

The NOC organization also provides a `NOC Rotation` playlist. It displays `NOC View` followed by `AI Incident Analysis - Enhanced`, one minute per dashboard. Use its auto-fit start mode for the rotating wallboard. `NOC View` remains the login home, and the Viewer cannot create or modify playlists.

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

Non-interface incidents move between Active and Resolved only when the deterministic engine changes lifecycle state:

- `CANDIDATE`, `OPEN`, or `RECOVERING` stays active.
- Grafana presents protocol-monitoring `RECOVERING` rows as `MONITORING`; a relapse inside 24 hours returns the same incident to `OPEN`, increments its recurrence counter, and restarts the 24-hour window after the next recovery.
- every interface entity is excluded from both incident windows; its retained lifecycle does not determine flap visibility.
- `RESOLVED` leaves Active Events and appears in Resolved Events for ranges containing its resolution time.
- a later non-interface relapse produces a newer snapshot and returns the incident to Active Events.

Interface Flaps has independent presentation movement: each exact raw down transition contributes one observation to the device/interface rolling hour. The pair enters at 10 observations and leaves as soon as the rolling count is below 10. No dashboard write, manual acknowledgement, current-port-state inference, or lifecycle mutation is involved.

Manual resolution is intentionally not implemented. Adding it requires a separately designed, authenticated acknowledgement/override data contract rather than mutating Grafana presentation state.

Hidden side-channel positives use the same Active/Resolved windows and one-click log drilldown. They never appear in Interface Flaps because their entity type is `event_signature`. Their AI title and short factual summary are exported in the existing lifecycle record, their category is the validated operational category, and their device/entity identity comes from the canonical source event. They enter `RECOVERING` after 60 quiet minutes and `RESOLVED` after 15 additional quiet minutes; repeat evidence before resolution reopens the same correlation and increments its evidence counters. AI-negative events are not shown as incidents and remain searchable in raw logs.

## Transport and storage contract

The lifecycle producer is independent of the AI-result producer but shares its filesystem lock and ready/delivered directories. It emits only changed incidents in content-addressed batches of at most 100 records and 256 KiB. A protected local SQLite cursor records the last exported snapshot version per incident.

Lifecycle batches use `type = incident_lifecycle`. The collector gate validates their exact shape and Vector routes them exclusively to `observability.incident_updates`; they must never enter `observability.ai_updates`. Producer version 2 adds `recurrence_count`; the gate, sender, and shared-directory inventories continue accepting immutable version-1 lifecycle files.

The exported `interface_flap` field and all interface lifecycle snapshots remain part of the durable data contract. Dashboard presentation deliberately uses `entity_type != 'interface'` for both incident windows and a separate read-only aggregation over `observability.grafana_logs` for Interface Flaps. This prevents single downs and persistent-down ports from becoming operator work while preserving their raw and lifecycle history.

`incident_updates` has no TTL. Latest-per-incident dashboard queries use `argMax` over `(snapshot_version, snapshot_id)`, so active state does not age out and resolved history remains available. Retention changes require an explicit policy decision.

Dashboard `Occurrences` is the number of distinct issue episodes: initial episode plus adverse relapses. It is not the raw evidence-message count.

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

Item 41 production activation passed protected main and isolated-NOC native-resource dry-runs and replacements. Both copies now use the rolling 60-minute raw transition threshold described above. All six panel queries and sampled Active, Flap, and Resolved drilldowns passed in both organizations. Exact rereads, live/rollback database integrity, and service health passed; an aggregate predecessor comparison proved exactly the two enhanced resources changed and every other Grafana resource remained unchanged.
