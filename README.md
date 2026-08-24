# Network Log Intelligence Platform

A capture-first network observability and local-AI incident reasoning platform.

This repository is the master public engineering record and active source repository for the deterministic normalizer plus complete public-safe collector and GX10 rebuild packages. Disposable-host execution of both clean-machine runbooks was not available and remains empirically unverified.

Final repository-only rebuild milestone status: `PUBLISHED`. The operator explicitly accepted the residual clean-host execution risk on 2026-08-23 so the project could advance; the unavailable execution is `WAIVED`, not falsely recorded as passed.

## Start here

For a fresh engineering or AI session, begin with:

1. [`docs/START_HERE.md`](docs/START_HERE.md)
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
3. [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)
4. [`components/collector/REBUILD_STATUS.md`](components/collector/REBUILD_STATUS.md) and [`components/gx10/REBUILD_STATUS.md`](components/gx10/REBUILD_STATUS.md)
5. the latest entries in [`docs/PROJECT_JOURNAL.md`](docs/PROJECT_JOURNAL.md)

`docs/CURRENT_STATE.md` is the authority for execution order and should contain exactly one item marked `NEXT`.

## Rebuild acceptance criterion

The reconstruction/documentation effort is complete only when:

> Two clean servers, this public repository, and operator-supplied environment values are sufficient for another engineer or AI to reconstruct the current functional system without undocumented implementation memory.

Environment-specific credentials, addresses, usernames, SSH keys, certificate private keys, and similar identity-bearing values are intentionally supplied during rebuild and are not stored publicly.

The empirical clean-host proof was unavailable. The operator accepted that residual risk and authorized the project to treat the rebuild/documentation milestone as complete for execution-order purposes while retaining the missing evidence as an explicit qualification.

## Core design

```text
Network devices
    |
    | syslog
    v
Collector / log server
    |-- Vector ingest and fan-out
    |-- ClickHouse durable storage
    |-- captured Vector normalization and fan-out
    |-- Grafana presentation
    |-- validated AI-result ingestion
    |
    | durable/prepared observations
    v
GX10
    |-- scheduled read-only backlog fetch
    |-- replay-safe SQLite ingest
    |-- unscheduled deterministic-enrichment reference
    |-- local Ollama infrastructure without a pipeline caller
```

The collector has a validated write-only AI-result return boundary, but no GX10 producer for it was discovered. Long-lived incident correlation, automatic LLM reasoning, and result production remain future implementation work.

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

The collector-side durable shadow worker, private-inventory validator, ledger, hardened unit/timer, artifact manifests, handoff publisher, and independent verifiers are implemented. The expanded suite has 94 normalizer/worker tests plus 14 collector-package tests passing. Complete shadow catch-up/steady-state validation passed, and the forward-only immutable-floor handoff completed its production cutover with exact collector/GX10 file-hash and record-count parity. GX10 now consumes the verified normalized handoff view; the raw backlog, shadow history, and exact mount-only rollback boundary remain preserved.

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

The collector public rebuild package, operator documentation, sanitation, and repository-only validation gates are complete. Clean-machine execution remains empirically unverified and was waived by the operator because no disposable Debian 13 amd64 target is available.

### GX10

GX10's complete public rebuild package is published under [`components/gx10/`](components/gx10/). It preserves the proven `timer -> fetch -> ingest` chain, exact SQLite state, unscheduled canonical normalized-field projection with historical version-3 enrichment retained, platform/dependency contract, Ollama service and six-model store, guarded activation, and the clean-machine runbook.

Repository-only validation reports `GX10_REBUILD_PACKAGE_VALIDATION=PASS` with 136 tests. Clean-machine execution remains empirically unverified and was waived by the operator because no disposable Ubuntu 24.04 arm64 GX10-class target is available.

### Two-server rebuild

[`docs/TWO_SERVER_REBUILD.md`](docs/TWO_SERVER_REBUILD.md) coordinates the collector-first rebuild order, independent transport keys, cross-server inputs, activation boundary, and acceptance evidence without duplicating the component runbooks.

## Repository map

- [`docs/START_HERE.md`](docs/START_HERE.md) - canonical recovery/read order and project acceptance criterion.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - end-to-end design and ownership boundaries.
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) - verified project checkpoint and strict execution order.
- [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md) - raw, normalized, incident, and AI-result contracts.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) - ingest, backlog, validation, replay, failure, and rebuild behavior.
- [`docs/TWO_SERVER_REBUILD.md`](docs/TWO_SERVER_REBUILD.md) - collector-first two-host reconstruction and acceptance order.
- [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) - final repository/reference acceptance evidence and waived clean-host boundary.
- [`docs/CLICKHOUSE.md`](docs/CLICKHOUSE.md) - durable table and sink contracts.
- [`docs/GRAFANA.md`](docs/GRAFANA.md) - datasource, dashboard restore, drilldown, and NOC-view behavior.
- [`docs/NORMALIZER_MIGRATION.md`](docs/NORMALIZER_MIGRATION.md) - controlled collector-side normalization migration.
- [`docs/NORMALIZER_PRODUCTION_INTEGRATION.md`](docs/NORMALIZER_PRODUCTION_INTEGRATION.md) - shadow-first collector integration, observability, promotion, and rollback design.
- [`docs/REASONING_PACKETS.md`](docs/REASONING_PACKETS.md) - deterministic wake policy and compact append-only packet boundary.
- [`docs/LOCAL_REASONING.md`](docs/LOCAL_REASONING.md) - versioned local-model caller, strict output, and safe-failure boundary.
- [`docs/MANAGED_REASONING.md`](docs/MANAGED_REASONING.md) - bounded, observable, separately disableable reasoning invocation candidate.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) - architecture decision log and rationale.
- [`docs/PUBLICATION_CHECKLIST.md`](docs/PUBLICATION_CHECKLIST.md) - required public-release gates.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) - broader milestone sequence.
- [`docs/PROJECT_JOURNAL.md`](docs/PROJECT_JOURNAL.md) - append-only engineering history and continuity record.
- [`docs/AI_HANDOFF.md`](docs/AI_HANDOFF.md) - fresh-session recovery instructions.
- [`SECURITY.md`](SECURITY.md) - public-repository publication rules.
- [`components/normalizer/`](components/normalizer/) - active deterministic normalizer source and tests.
- [`components/collector/`](components/collector/) - collector rebuild artifacts, verifiers, and component state.
- [`components/collector/normalizer/`](components/collector/normalizer/) - non-activating collector-side normalizer shadow package and verifier.
- [`components/gx10/`](components/gx10/) - complete GX10 rebuild artifacts, verifiers, tests, and clean-machine runbook.
- [`scripts/validate-public-repository.py`](scripts/validate-public-repository.py) - current-tree, reachable-history, link, and ref-topology public gate.

## Source-of-truth policy

This repository is the durable public project control plane. Production changes must still be verified against the live system and current deployed configuration before modification. If documentation, repository code, and a live implementation disagree, stop and reconcile the difference instead of guessing.

Source precedence for resuming work is defined in `docs/AI_HANDOFF.md`.

Historical documents and retired standalone component repositories are reference material only. Current verified state and current master-repository code take precedence.

## Continuity rule

Every completed project sub-section must be validated, recorded in `docs/PROJECT_JOURNAL.md`, and pushed to GitHub before materially proceeding into the next sub-section. When current state or execution order changes, update `docs/CURRENT_STATE.md` as well.

## Public-repository posture

This repository intentionally excludes credentials, keys, tokens, production addresses, firewall allowlists, private hostnames/operator identity, customer/device-identifying raw logs, certificate private keys, generated databases, and other sensitive operational data. Public examples use documentation-only addresses and synthetic identities.
