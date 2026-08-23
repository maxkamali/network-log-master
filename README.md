# Network Log Intelligence Platform

A capture-first network observability and local-AI incident reasoning platform.

This repository is the master public engineering record and active source repository for components already consolidated here. It now contains the active deterministic normalizer and a substantial public-safe collector rebuild capture. GX10 remains the next major component to receive the same reconstruction treatment.

## Start here

For a fresh engineering or AI session, begin with:

1. [`docs/START_HERE.md`](docs/START_HERE.md)
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
3. [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)
4. the active component rebuild status, currently [`components/collector/REBUILD_STATUS.md`](components/collector/REBUILD_STATUS.md)
5. the latest entries in [`docs/PROJECT_JOURNAL.md`](docs/PROJECT_JOURNAL.md)

`docs/CURRENT_STATE.md` is the authority for execution order and should contain exactly one item marked `NEXT`.

## Rebuild acceptance criterion

The reconstruction/documentation effort is complete only when:

> Two clean servers, this public repository, and operator-supplied environment values are sufficient for another engineer or AI to reconstruct the current functional system without undocumented implementation memory.

Environment-specific credentials, addresses, usernames, SSH keys, certificate private keys, and similar identity-bearing values are intentionally supplied during rebuild and are not stored publicly.

## Core design

```text
Network devices
    |
    | syslog
    v
Collector / log server
    |-- Vector ingest and fan-out
    |-- ClickHouse durable storage
    |-- Python deterministic normalizer
    |-- Grafana presentation
    |-- validated AI-result ingestion
    |
    | durable/prepared observations
    v
GX10
    |-- compact incident/state engine target
    |-- deterministic correlation target
    |-- rolling context target
    |-- local LLM reasoning via Ollama
    |
    | validated AI updates
    v
Collector / ClickHouse / Grafana
```

## Architectural invariants

- Capture first. Legitimate observations are retained even when no parser recognizes them.
- Unknown and rare events remain attention-eligible by default.
- Vendor-specific parsing enriches events; it never acts as an admission allowlist.
- Suppression means "do not wake the reasoning layer", not deletion.
- Raw messages remain replayable.
- Collector arrival time is authoritative; device-provided time is secondary metadata.
- The collector owns collection, durable storage, normalization, presentation, and large/long-lived datasets.
- GX10 owns compact working state, correlation, reasoning, and explanation.
- GX10 is replaceable and does not become the authoritative raw-log store.
- The LLM does not own identity, deduplication, incident lifecycle, or deterministic state transitions.
- GX10 does not write directly to ClickHouse; AI results cross a validation boundary first.
- File-based backlog remains the V1 transport until measured requirements justify a streaming bus.

## Current milestone state

### Normalizer

The active normalizer source is [`components/normalizer/`](components/normalizer/).

The selected replay/parity milestone is complete with 73 tests passing and 0 unexpected semantic differences in the reviewed 24-sample production replay scope.

### Collector

The collector rebuild capture is published under [`components/collector/`](components/collector/).

The published checkpoint includes:

- package/version reconstruction
- configuration renderer
- Vector configuration
- ClickHouse schema/access artifacts
- Grafana datasource and HTTPS artifacts
- Certbot renewal artifacts
- SFTP/chroot/ACL/bind-mount transport reconstruction
- AI-result gate and retention behavior
- package and runtime verifiers
- four Grafana 13 dashboard resources
- API-based dashboard restore and verification scripts

The independent live collector verifier reached `COLLECTOR_RUNTIME_VERIFY=PASS`.

The collector clean-machine installer now includes both the secure Grafana administrator bootstrap and API-based dashboard restore/verification wiring. Package no-autostart hardening and the remaining validation/documentation gates remain before the collector rebuild milestone is closed.

### GX10

GX10 currently provides working backlog fetch, local durable ingest, transitional deterministic enrichment, write-only result return, and local Ollama availability, but its complete public rebuild capture has not yet been performed.

## Repository map

- [`docs/START_HERE.md`](docs/START_HERE.md) - canonical recovery/read order and project acceptance criterion.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - end-to-end design and ownership boundaries.
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) - verified project checkpoint and strict execution order.
- [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md) - raw, normalized, incident, and AI-result contracts.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) - ingest, backlog, validation, replay, failure, and rebuild behavior.
- [`docs/CLICKHOUSE.md`](docs/CLICKHOUSE.md) - durable table and sink contracts.
- [`docs/GRAFANA.md`](docs/GRAFANA.md) - datasource, dashboard restore, drilldown, and NOC-view behavior.
- [`docs/NORMALIZER_MIGRATION.md`](docs/NORMALIZER_MIGRATION.md) - controlled collector-side normalization migration.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) - architecture decision log and rationale.
- [`docs/PUBLICATION_CHECKLIST.md`](docs/PUBLICATION_CHECKLIST.md) - required public-release gates.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) - broader milestone sequence.
- [`docs/PROJECT_JOURNAL.md`](docs/PROJECT_JOURNAL.md) - append-only engineering history and continuity record.
- [`docs/AI_HANDOFF.md`](docs/AI_HANDOFF.md) - fresh-session recovery instructions.
- [`SECURITY.md`](SECURITY.md) - public-repository publication rules.
- [`components/normalizer/`](components/normalizer/) - active deterministic normalizer source and tests.
- [`components/collector/`](components/collector/) - collector rebuild artifacts, verifiers, and component state.
- [`components/gx10/`](components/gx10/) - GX10 ownership/migration area; full rebuild capture remains pending.

## Source-of-truth policy

This repository is the durable public project control plane. Production changes must still be verified against the live system and current deployed configuration before modification. If documentation, repository code, and a live implementation disagree, stop and reconcile the difference instead of guessing.

Source precedence for resuming work is defined in `docs/AI_HANDOFF.md`.

Historical documents and retired standalone component repositories are reference material only. Current verified state and current master-repository code take precedence.

## Continuity rule

Every completed project sub-section must be validated, recorded in `docs/PROJECT_JOURNAL.md`, and pushed to GitHub before materially proceeding into the next sub-section. When current state or execution order changes, update `docs/CURRENT_STATE.md` as well.

## Public-repository posture

This repository intentionally excludes credentials, keys, tokens, production addresses, firewall allowlists, private hostnames/operator identity, customer/device-identifying raw logs, certificate private keys, generated databases, and other sensitive operational data. Public examples use documentation-only addresses and synthetic identities.