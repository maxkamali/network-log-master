# Architecture

## Purpose

The platform turns raw network telemetry into durable observations, deterministic normalized events, long-lived incident state, and concise local-AI explanations without allowing the LLM to become the source of truth for identity or lifecycle.

The architecture is intentionally split across two roles: a durable collector/log server and a replaceable local-inference host named GX10.

## Rebuildability contract

The current reconstruction/documentation effort is complete only when:

> Two clean servers, this public repository, and operator-supplied environment values are sufficient for another engineer or AI to reconstruct the current functional system without undocumented implementation memory.

The public repository therefore owns implementation logic, non-sensitive configuration, rebuild scripts, verifiers, data contracts, and operator instructions. Environment-specific identity and secrets remain operator-supplied at rebuild time.

This rebuildability contract does not require publishing production addresses, credentials, usernames, SSH keys, certificate private keys, firewall allowlists, customer-identifying data, or other private deployment identity.

## Component ownership

### Collector / log server

Owns:

- syslog ingress
- durable raw capture
- parsing and normalization
- ClickHouse storage
- Grafana presentation
- unknown-event inventory
- validation and storage of AI results
- compressed durable backlog for GX10
- large and long-lived data stores
- service boundaries that protect durable storage from GX10

### GX10

Target ownership:

- receiving/fetching prepared or durable observation backlog
- compact local working state
- deterministic incident correlation target
- repeat/burst accounting target
- rolling incident context target
- deciding when the local LLM should run
- local inference
- returning thin AI result records

GX10 is intentionally not the authoritative raw-log archive, dashboard server, or direct ClickHouse writer.

Current production has three independent GX10 schedules: read-only backlog fetch followed by replay-safe local SQLite ingest; offline canonical projection followed by deterministic incident correlation; and bounded packet/backlog draining followed by one strict local-model invocation. The item-29 reasoning boundary passed protected activation, one diagnosed terminal safe failure, immutable portable prompt revision `r3`, exact upgrade, and three natural drain cadences. Reasoning results remain append-only and nonauthoritative. No result-return producer exists.

## Current data path

```text
Devices
  -> syslog ingress
  -> Vector
     -> ClickHouse raw store
     -> compressed GX10 backlog

GX10
  -> restricted read-only backlog fetch
  -> local durable replay-safe ingest
  -> separately scheduled canonical projection
  -> deterministic incident correlation/lifecycle
  -> deterministic versioned reasoning packets
  -> separately scheduled bounded local inference
  -> append-only validated local results
```

Separately present but not connected by a discovered GX10 producer:

```text
collector write-only result transport
  -> validation/quarantine gate
  -> ClickHouse validated AI updates
  -> Grafana
```

Ollama is installed, active, enabled, and loopback-only with six complete model manifests. No application-specific caller was found during rediscovery; the reconstructed strict caller is now active only through the separately managed item-29 boundary. The versioned result-outbox producer and inactive no-network managed package pass repository, protected-copy, exact-stage, isolated-install/run, failure-cleanup, and corrected working-system inactive-install gates. Exact artifacts and empty states are installed with a never-invoked disabled timer. The collector return path stays disconnected until protected local activation and later credential/live-return gates pass.

## Target data path

Future architecture, after separate implementation and promotion gates, is:

```text
collector capture
  -> collector-side deterministic normalization
  -> durable prepared observations
  -> GX10 deterministic incident correlation/lifecycle
  -> deterministic wake policy
  -> local Ollama reasoning
  -> thin result producer
  -> collector write-only validation boundary
  -> ClickHouse/Grafana
```

The collector-side normalizer has passed selected replay/parity, complete live shadow validation, and the production GX10 handoff gate. Its integration remains a separate durable-file worker reading settled collector backlog files without changing Vector's raw sinks. A forward-only handoff view now exposes only verified normalized outputs at or after an immutable floor while retaining the original GX10 transport identity. The raw and shadow histories and exact raw-view rollback remain preserved. After a multi-cadence stability review, transitional GX10 vendor/message reparsing was replaced by a canonical-field projector that preserves local suppression policy and historical enrichment evidence. The deterministic GX10 incident schema/engine and separately disableable offline managed `projection -> incident` runner/service/timer passed production backfill and multi-cadence activation gates. The deterministic wake-policy/compact-packet builder and versioned caller/schema/configuration/prompt boundary are active only through the separately disableable managed reasoning schedule. They bind immutable packets to exact model/prompt/run versions and strict append-only structured results. The item-30 result-outbox projection, shared-lock ready/delivered state machine, and no-network managed package are installed inactive and empty after copy/package/portability gates; protected local activation, write-only credentials, sender crash-window closure, and collector return remain separate gates.

## Capture-first contract

The system captures legitimate observations before deciding whether they are understood. Unknown events are valid observations and remain attention-eligible by default.

Vendor/event decoders are enrichment modules. A parser mismatch or exception must not drop the raw event.

Suppression is narrowly defined: an explicit rule may prevent an event from waking the reasoning layer, but suppression never means deletion.

## Time contract

Collector arrival time is authoritative for event ordering. A device-supplied timestamp is retained separately when available.

## Incident model

Syslog records are observations. Incidents are persistent deterministic objects assembled from observations.

Target lifecycle:

```text
CANDIDATE -> OPEN -> RECOVERING -> RESOLVED
```

The LLM may summarize or explain an incident but does not decide canonical identity, deduplication, or lifecycle state.

The long-lived deterministic incident engine is implemented and active behind a separately disableable offline schedule. Its identity, evidence, lifecycle, repeat, rolling-context, transaction, replay, and managed-invocation contracts are documented in `docs/INCIDENT_ENGINE.md` and `docs/MANAGED_CORRELATION.md`. The original fetch/ingest schedule remains independent.

## Context model

The target incident engine should build deterministic compact summaries over approximately:

- 60 minutes
- 180 minutes
- 24 hours

Open incidents persist until resolved. Compact resolved history may remain available for substantially longer periods to improve operator context.

## LLM wake policy

Target reasoning runs are event-driven and rate-limited rather than invoked for every record. Approximate intended behavior:

- periodic analysis when meaningful new evidence exists
- immediate wake for major/critical conditions
- interface flaps are valid wake reasons
- OSPF retransmission degradation is a valid wake reason

The exact policy remains deterministic and testable outside the LLM.

## Trust boundaries

Input and output transport credentials are independent and least-privilege.

- backlog reader: read-only
- AI result writer boundary: write-only; no current GX10 producer/private-key installation is claimed
- AI results: validated before durable ingestion
- GX10: no direct ClickHouse write path
- ClickHouse application listeners: collector-local boundary
- Grafana/collector rebuild secrets: operator-supplied, never embedded in public artifacts

## Dashboard restoration boundary

Grafana dashboard state is reconstructed through the supported Grafana resource API rather than by writing directly to Grafana's SQLite database.

Current captured dashboards use `dashboard.grafana.app/v2`. The rebuild path preserves captured dashboard `spec` content while allowing Grafana to generate server-owned metadata.

## Production migration rule

New deterministic parsing or correlation logic is built beside the current production path first. It is promoted only after fixtures, negative-path tests, replay, parity, idempotency, and explicit rollback planning are satisfactory.

Transitional logic is retired deliberately rather than rewritten in place without comparison.

## Reconstruction rule

Before adding new architecture to a component, first capture enough of the currently functional implementation that a clean machine can reproduce it from this repository plus operator-supplied environment values. This prevents modernization work from destroying the only known working implementation history.

Both component reconstruction packages and operator runbooks now satisfy the repository-only portion of that rule. Full clean-host execution remains empirically unverified and was explicitly waived by the operator for project sequencing because disposable targets are unavailable. `docs/TWO_SERVER_REBUILD.md` defines the cross-system order and acceptance evidence.
