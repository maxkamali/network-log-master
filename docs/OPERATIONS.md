# Operations

## Purpose

This document records the current operational behavior of the observability pipeline without publishing environment-specific credentials, addresses, hostnames, or firewall policy.

For the exact current execution order, use `docs/CURRENT_STATE.md`. For fresh-session recovery, begin with `docs/START_HERE.md`.
For documentation ownership and required update points, use
`docs/DOCUMENTATION_GUIDE.md`.

## Collector ingest

Network devices send syslog to the collector. Vector is the collection and fan-out layer.

The important capture rule is that raw data is preserved before parsing decisions are made. The current ingest behavior is deliberately tolerant of vendor formatting differences:

1. preserve `raw_message`
2. attempt strict syslog parsing
3. attempt relaxed Cisco NX-OS parsing
4. attempt legacy NX-OS parsing
5. retain an explicit `raw_unparsed` observation when none of the structured paths match

UDP ingest uses a generic byte-oriented socket path rather than depending exclusively on a strict syslog source. TCP syslog remains supported through the structured syslog path.

Parser failure is metadata, not packet loss.

## ClickHouse delivery

Vector writes raw observations to ClickHouse. The production sink has a known operational exception: startup health checking is disabled because the health-check request path produced an authentication failure while runtime inserts were proven healthy.

Do not remove that exception merely because the configuration looks unusual. Re-enable startup health checking only after testing the exact authentication behavior with the deployed ClickHouse/Vector combination.

ClickHouse application listeners are collector-local. GX10 does not receive direct ClickHouse access.

## Durable retention

Current retention policy:

- raw syslog observations: approximately 12 months
- validated AI updates: approximately 12 months
- compressed GX10 backlog files: approximately 90 days

Retention policy is independent of AI decisions. Raw observations are not deleted because the reasoning layer ignored or suppressed them.

## Compressed backlog

The collector emits newline-delimited JSON compressed with Zstandard into hour-partitioned backlog files. This is the V1 handoff mechanism to GX10.

The backlog is intentionally file-based. A message bus is not introduced until throughput, latency, or operational requirements demonstrate a need for one.

## GX10 backlog fetch

The fetcher uses a read-only transport and must never mutate the collector backlog.

Operational behavior includes:

- short bootstrap window for first start
- overlap when scanning recent periods so late-arriving files are not skipped
- bounded catch-up window
- settle time before consuming a file that may still be written
- temporary local `.part` files
- Zstandard integrity testing before promotion
- SHA-256 verification/accounting
- atomic local move after validation
- durable checkpointing

The fetch path is designed so interruption can be retried without corrupting or deleting source data.

## Collector-side normalizer shadow boundary

The implemented production-integration package adds a separate collector-local worker after the durable raw backlog boundary. It reads only settled `/var/spool/vector-ai` files, injects trusted hints from a private operator inventory, and writes atomic normalized output beneath `/var/spool/network-log-normalizer-shadow` with a SQLite file ledger.

The worker is not inline with Vector. Failure cannot block the existing raw ClickHouse sink or raw GX10 backlog. It has no network or ClickHouse credentials and cannot modify source files. The complete design, acceptance metrics, promotion boundary, and rollback rules are in `docs/NORMALIZER_PRODUCTION_INTEGRATION.md`.

Repository implementation, packaging, synthetic validation, live shadow catch-up, and five initial normal-cadence steady-state cycles are complete. The shadow worker remains isolated from Vector and ClickHouse, while its independently verified output now supplies the separate forward-only GX10 handoff publisher.

The production handoff uses an immutable inclusive path floor and a separate verified handoff root. At/after-floor normalized files are copied under their original raw transport names so GX10 retains its existing filename and replay identity. The guarded bind-only activation passed with exact collector/GX10 hash and record-count parity, and all automatic schedules are active. Raw and shadow files remain untouched; rollback is still the documented read-only bind-view restoration in `docs/NORMALIZER_HANDOFF.md`.

## GX10 local ingest

Fetched JSONL records are ingested into a local SQLite working database. The captured applications enable foreign-key enforcement where needed and use a 5-second busy timeout; they do not explicitly set WAL mode.

Important ingest contracts:

- timestamp and message fields are required strings
- timestamps must carry timezone information
- individual input lines are size-bounded
- the original JSON record is retained
- files move from incoming to processed only after successful ingest
- `(source_file, record_number)` is unique, making replay idempotent
- replaying an already ingested file must not create duplicate observations

This local database is working state, not the authoritative raw-log archive.

## GX10 orchestration boundary

The public clean-machine package names its reconstructed base units
`network-log-gx10.service` and `network-log-gx10.timer`. The working production
host intentionally uses deployment-specific unit names that are not published.
Do not use a public package unit name as a live-host command: resolve the
operator-private pipeline unit from the host's installed unit inventory first.

In either environment, the original automatic chain is:

```text
fetch/ingest timer
  -> fetch-spool.py
  -> ingest-spool.py
```

The reconstructed timer contract uses a two-minute boot delay, a one-minute
inactive interval, and five-second accuracy. Its oneshot service is non-root
and retains the captured filesystem and kernel hardening.

A second independent offline chain is now active:

```text
network-log-gx10-correlation.timer
  -> canonical projection
  -> deterministic incident engine
```

The correlation timer uses a one-minute inactive interval. Its runner verifies exact stage hashes, takes a single-cycle advisory lock, performs up to three ordered passes to converge rows that arrive during execution, and succeeds only when both projection and incident lags are zero. The service has Unix-socket-only address families and may write only within the validated database parent. It does not call Ollama, write results, or change the original fetch/ingest timer.

Activation verifies the disabled installation, runs the initial backfill before timer enablement, and then requires active zero-lag verification. Any failure disables only correlation while preserving its replay-safe database state. The independent verifier checks unit/source/config integrity, SQLite integrity/foreign keys, cursor lags, duplicate active identities, evidence aggregates, service result, and timer state.

Historical version-3 enrichment remains in SQLite. Ollama is installed separately, active/enabled, and loopback-only. The item-27 packet builder and item-28 strict versioned caller are invoked only through the exact separately managed item-29 boundary; operators must not call either ad hoc against the working database.

The item-29 runner/service/timer/private binding is active after protected backup, compatibility correction, exact upgrade, and three natural-cadence gates. Each locked cycle defers packet construction while revised-version backlog exists and permits at most one inference reservation. The caller fixes loopback transport, reserves durable state before inference, accepts only strict bounded output, and makes unavailable/invalid inference an explicit terminal no-result state. One reviewed historical invalid-output run remains immutable evidence. Disabling reasoning must preserve all append-only packet/run/result truth and must not alter fetch/ingest or correlation. Follow `docs/MANAGED_REASONING.md`; do not invoke the service ad hoc.

## AI result return boundary

The collector exposes a separate write-only transport and applies a validation gate before durable ingestion of thin JSONL result files.

Current validation policy includes:

- settle interval before inspection
- maximum file size of 256 KiB
- maximum 100 JSONL records per file
- required timezone-aware timestamp
- required title and body
- accepted files move atomically to a ready area
- rejected files are quarantined with a reason
- the active version-1 ledger records immutable accepted filename/content identity beyond ready-file retention

Accepted ready-result payloads are deliberately preserved until a future
delivery-confirmed archive design is separately validated. Vector's file source
therefore has an explicit 65,536-descriptor systemd limit rather than the
inherited 1,024-descriptor process limit.

Validated records are then ingested into ClickHouse and become available to Grafana.

No historical GX10 application producer for this boundary was discovered. The reconstructed item-30 producer, outbox, dedicated write-only sender, collector validation/replay ledger, and ClickHouse ingestion path are active after protected first-live, exact-replay, divergent-conflict, natural recurring-delivery, and final conservation/provenance gates. The live original and enhanced AI incident dashboards read accepted records through the existing read-only Grafana datasource. New results project Device directly; immutable legacy records use the private run-to-device lookup where available. See `docs/RESULT_OUTBOX.md`, `docs/RESULT_TRANSPORT.md`, and `docs/GRAFANA.md`.

## Deterministic NOC lifecycle path

The result-outbox service now runs two local producers sequentially under the same private-network, shared-lock boundary:

```text
successful reasoning results -> AI result files
authoritative incidents      -> changed lifecycle batches
```

The sender remains one-file-per-cycle and uses the existing write-only identity. The collector gate validates both record families, its immutable filename/content ledger applies to both, and Vector routes them to separate ClickHouse tables. Lifecycle records cannot enter `ai_updates` and AI records cannot enter `incident_updates`.

The enhanced dashboard is the deterministic NOC queue. Active Events ignores the dashboard time range so unresolved non-interface work persists; Resolved Events uses `resolved_at` within the selected range. Interface entities are excluded from both windows. Interface Flaps is a separate read-only raw-log aggregation that shows only device/interface pairs with at least 10 exact interface-down transitions in the rolling preceding 60 minutes, regardless of the dashboard picker, and removes them automatically below threshold. Confirmed recovered BGP/OSPF/OSPFv3 incidents, including one-observation protocol candidates that expire without a second adverse observation, remain active for a 24-hour monitoring window, display `MONITORING`, and reuse the same incident/issue-occurrence counter if they relapse before resolution. Operators can search each window and filter Active/Resolved by severity. Resolution remains engine-driven; Grafana does not mutate incident state. See `docs/NOC_WORKFLOW.md`.

## Hidden AI detection side channel

The managed reasoning owner also reviews canonical events that have no deterministic incident evidence. It admits severity 0–4 and only novel or repeated severity-5 notices, groups at most 24 deterministic signatures, and permits at most one local-model invocation per five-minute cycle. Existing incident-reasoning backlog has priority. If Gemma is unavailable or returns invalid output, the immutable batch remains pending and no incident is created; normal incident reasoning may continue during retry backoff.

Validated positive decisions enter the same incident/outbox/collector/dashboard path as every other non-interface incident. They carry the real device, event-code-bearing entity name, AI title/detail, projected operational category, and `event-triage` transport protocol label. After 60 minutes without matching evidence they enter `RECOVERING`; after a further 15 minutes they resolve. A return before resolution reopens and increments the same correlation. Ignored and insufficient events remain available only in raw logs.

Repeated model decisions can create a learned exact-event-code rule only for severity 0–3 after three consistent confidence-70+ positives spanning at least 30 minutes with no contradictory decision. Rules never contain generated code or commands and can only select the same fixed incident bridge. Severity 4/5 is always model-reviewed and never auto-promoted.

## Grafana operational boundary

Grafana is served over HTTPS by the collector and reads ClickHouse through captured datasource identities.

The working deployment also has a separate NOC Viewer organization containing only `NOC View`, `AI Incident Analysis - Enhanced`, and two datasource copies backed by the read-only ClickHouse identity. Its Viewer can use Explore and temporary panel editing because the reversible `viewers_can_edit` compatibility setting is active, but cannot save dashboards or administer Grafana. Viewer Explore can query every datasource in the Viewer organization, which is why no other datasource is present there. Passwords remain private operator inputs. Grafana OSS cannot enforce an exact per-user left-navigation allowlist; organization isolation and Viewer permissions are the supported boundary.

The same organization has a single `NOC Rotation` playlist that shows `NOC View` and then `AI Incident Analysis - Enhanced` for one minute each. Start it with the shared auto-fit link or choose an auto-fit mode in the playlist dialog. The playlist is not the NOC login home; Grafana home preferences remain bound to `NOC View`. The Viewer may start the playlist but cannot create or modify playlists.

In `AI Incident Analysis - Enhanced`, click any cell in Active Events or Resolved Events. Grafana opens `View matching logs` in a new Explore tab against the organization-local read-only logs datasource with the SQL editor initially collapsed. The link uses the row's deterministic incident ID to recover device, entity, protocol/event family, and incident timestamps; it searches from 15 minutes before first detection through 15 minutes after last activity or resolution and returns at most 1,000 newest-first rows. A single click on any Interface Flaps cell opens the exact device/interface raw logs for the rolling preceding 60 minutes, also read-only, compact, newest first, and limited to 1,000 rows.

In `NOC View`, a single click on a linked Severity Breakdown slice or Top Devices, OSPF Events, or BGP Events value opens its existing read-only Explore lookup in a new tab with the SQL editor initially collapsed. The selected dashboard time range and existing 1,000-row cap are preserved.

Current dashboard reconstruction uses the supported Grafana 13 `dashboard.grafana.app/v2` API. Rebuild tooling must not write directly into Grafana's SQLite database.

The clean-machine runtime installer restores the six captured dashboard resources only after HTTPS health and both ClickHouse datasources are verified, then runs the independent dashboard verifier and the redacted thirteen-query original/enhanced verifier. Runtime restore is fail-closed for unexpected divergent existing dashboards: automatic replacement is not enabled.

The clean-machine Grafana bootstrap sequence is wired so that first startup is loopback-only on `127.0.0.1:3000`, administrator credentials come from an operator-owned private file, the reset runs through `--password-from-stdin`, and the temporary bootstrap override is removed before normal HTTPS exposure. Failure cleanup also removes the temporary override.

The Grafana CLI path/data targeting was proven non-destructively against a temporary copy of the Grafana database; the live administrator password hash remained unchanged.

## Clean-machine rebuild operations

The collector rebuild package separates installation from verification:

- package installer: `components/collector/install/install-packages.sh`
- package verifier: `components/collector/install/verify-packages.sh`
- configuration renderer: `components/collector/install/render-configs.py`
- runtime installer: `components/collector/install/install-runtime.sh`
- independent runtime verifier: `components/collector/install/verify-runtime.sh`

Package installation has a fail-closed no-autostart boundary. Before apt transactions begin, a temporary Debian service-policy guard and persistent systemd condition guards prevent unconfigured collector services from becoming active. Existing active SSH management access is preserved; an initially inactive SSH service is held until the transport configuration validates.

The runtime installer uses short-lived authorization tokens for required bootstrap starts without permanently removing the persistent guard. Vector, ClickHouse, and Grafana guards are removed only at the final configured-service activation boundary. A synthetic systemd proof validated the hold, temporary authorization, reassertion, and final release semantics without changing the working collector's service states.

The runtime installer is intended for a clean collector. Do not execute it against the working reference collector.

The complete collector runbook is `components/collector/README.md`. Clean-machine execution was unavailable and is waived for project sequencing with residual risk retained.

The GX10 rebuild package separates guarded installation, offline model import, preactivation verification, dual-confirmation activation, and active runtime verification. Its complete runbook is `components/gx10/CLEAN_MACHINE_RUNBOOK.md`. Clean-machine execution was unavailable and is waived for project sequencing with residual risk retained.

`docs/TWO_SERVER_REBUILD.md` coordinates the required collector-first order, independent transport-key roles, cross-server inputs, activation point, and acceptance evidence.

Rebuild inputs that are private or environment-specific are supplied by the operator through environment values and/or private files. They are not stored in the public repository.

The public rebuild should render concrete runtime configuration before starting services rather than permanently enabling unsafe environment interpolation solely to make templates work.

## External connectivity prerequisites

Firewall/nftables reconstruction is intentionally outside the public rebuild scope.

Operator documentation should state the required functional connectivity, for example:

- network devices must be able to deliver syslog to the collector's configured UDP/TCP syslog listeners
- operators/GX10 must reach the configured restricted SSH/SFTP service
- GX10 needs only the read-only backlog role for the currently reconstructed automatic path
- users must reach Grafana HTTPS
- certificate issuance/renewal must satisfy the chosen ACME validation requirements, including temporary HTTP validation reachability when applicable

Do not encode production firewall allowlists or addresses in the public repository.

## Failure behavior

The system should fail in the direction of preserving evidence:

- parser failure -> keep generic observation
- model unavailable -> retain deterministic incident/evidence state
- Ollama/model infrastructure unavailable -> fetch/ingest remains a separate deterministic path; no current pipeline caller is claimed
- malformed AI output -> reject/quarantine, do not write directly to ClickHouse
- transport interruption -> retry from durable file/checkpoint state
- replay -> no duplicate canonical records
- dashboard restore uncertainty -> validate through API/dry-run rather than mutate Grafana database state directly
- rebuild mismatch -> stop and reconcile against verified live behavior rather than guessing
- missing GX10 result producer or Ollama caller -> preserve the absence; do not fabricate connectivity to make validation appear end-to-end

## Operational change rule

Before promoting any new deterministic component into the production path:

1. test with synthetic fixtures
2. test malformed and future layouts
3. replay stored observations
4. compare against the current production/transitional behavior
5. document intentional parity differences
6. verify idempotency
7. only then automate the steady-state service path

## Documentation/continuity rule

After each completed validated project sub-section:

1. append the result, validation evidence, important decisions/corrections, and next action to `docs/PROJECT_JOURNAL.md`
2. push that journal update to GitHub before materially entering the next sub-section
3. update `docs/CURRENT_STATE.md` when verified state or execution order changes

This repository is the durable continuity mechanism; conversational context is not an operational dependency.
