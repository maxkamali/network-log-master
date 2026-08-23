# AI Handoff

Use this file to resume the project safely in a fresh AI session.

## Mandatory read order

1. `docs/START_HERE.md`
2. `docs/ARCHITECTURE.md`
3. `docs/CURRENT_STATE.md`
4. the active component rebuild status — currently `components/gx10/REBUILD_STATUS.md`
5. the latest entries in `docs/PROJECT_JOURNAL.md`
6. `docs/DECISIONS.md`
7. `docs/DATA_CONTRACTS.md`
8. `docs/OPERATIONS.md`
9. component-specific documentation for the task at hand
10. verify repository reality with `git log -10 --oneline` and `git status --short`

`docs/CURRENT_STATE.md` is the execution authority. Do not infer a different work order from older journal entries or historical documents.

## Source precedence

When sources disagree, use this order:

1. live verified system/configuration and current checked-out code/tests
2. `docs/CURRENT_STATE.md` and the active component `REBUILD_STATUS.md`
3. current repository implementation and component documentation
4. architecture/decision documents
5. older runbooks or historical planning documents

Stop and reconcile meaningful disagreement instead of guessing.

## Project acceptance criterion

The rebuild/documentation project is complete only when two clean servers, this public repository, and operator-supplied environment values are sufficient for another engineer or AI to reconstruct the current functional system without undocumented implementation memory.

Operator-supplied values include environment-specific credentials, addresses, usernames, SSH keys, certificate material, and similar private identity that must not be committed publicly.

## Current durable milestones

### Normalizer

The normalizer is developed from `components/normalizer/` in this master repository.

Replay/parity milestone:

- 24 representative stored observations
- 21 strict semantic matches
- 3 intentional NX-OS OSPFv3 differences
- 0 unexpected differences
- repeated deterministic replay
- 73 tests passing

Reference public milestone commit:

`4220f50474d608fd8745b4465398af521d7625bd`

The production collector path has not been switched to the new normalizer.

### Collector

A public collector rebuild checkpoint was published at:

`e8df224` — `Checkpoint collector rebuild capture`

That checkpoint includes package/configuration capture, Vector, ClickHouse, Grafana datasources, HTTPS/TLS behavior, Certbot, SFTP transport, ACLs/bind mounts, AI-result validation, retention, runtime verification, Grafana dashboard resources, and dashboard restore/verification tooling.

Key validated gates include:

- `COLLECTOR_PACKAGE_VERIFY=PASS`
- `TRANSPORT_VERIFY=PASS`
- `COLLECTOR_RUNTIME_VERIFY=PASS`
- `GRAFANA_UNIFIED_RESOURCE_ROUND_TRIP=PASS`
- `GRAFANA_DRYRUN_RESTORE_PROOF=PASS`
- `GRAFANA_DASHBOARD_LIVE_NONDESTRUCTIVE_TEST=PASS`
- `GRAFANA_CLI_TEMP_DATABASE_TARGETING=PASS`
- `GRAFANA_DASHBOARD_WIRING_FINAL_VALIDATION=PASS`
- `PACKAGE_NO_AUTOSTART_FAILURE_PATH_VALIDATION=PASS`
- `PACKAGE_NO_AUTOSTART_SYNTHETIC_PROOF=PASS`

Detailed state is in `components/collector/REBUILD_STATUS.md`.

### Grafana dashboard restore

Four Grafana 13 dashboards are captured as `dashboard.grafana.app/v2` resources.

Supported restore behavior was proven against Grafana 13.1.1:

- POST creates
- PUT replaces
- `dryRun=All` validates without persistence
- captured `spec` objects round-trip exactly

Permanent scripts:

- `components/collector/grafana/scripts/dashboard_api.py`
- `components/collector/grafana/scripts/restore-dashboards.py`
- `components/collector/grafana/scripts/verify-dashboards.py`

Grafana 13.1.1 was also verified to support `grafana cli admin reset-admin-password --password-from-stdin` through `/usr/share/grafana/bin/grafana`.

## Current resume point

Read `docs/CURRENT_STATE.md` for the single `NEXT` item.

GX10 live-system rediscovery is complete through item 12N and the final closure audit.

The proven automatic application chain is:

`timer -> fetch -> ingest`

Preserve these rediscovery boundaries:

- deterministic enrichment exists but has no discovered automatic invocation
- Ollama is active with six complete models but has no discovered application-specific observability-pipeline caller
- the collector result-return boundary exists but has no discovered GX10 producer
- the original SQLite/bootstrap initializer did not survive the bounded search; reconstruct from the captured effective schema

The active component authority is `components/gx10/REBUILD_STATUS.md`.

Begin public reconstruction with its first bounded subsection: define the public-safe operator input plus filesystem/runtime identity contract. Do not execute clean-machine installers against either working reference system.

After the subsection validates, append and push `docs/PROJECT_JOURNAL.md` before proceeding.

## Working method

- change one bounded sub-section at a time
- inspect verified behavior before replacing it
- preserve known-good unusual configuration unless evidence justifies a change
- use exact target labels for operator commands
- keep potentially failing shell logic inside a child shell so diagnostics cannot terminate an interactive SSH session
- avoid heredoc delimiter collisions when generating scripts that themselves contain heredocs
- build beside production first where possible
- use fixtures, negative paths, replay, idempotency checks, and non-destructive API validation
- update `CURRENT_STATE.md` when execution order or verified current state changes
- append and push `PROJECT_JOURNAL.md` after every completed validated sub-section
- publish intermediate validated GitHub/journal checkpoints during long or risk-heavy sub-sections when they materially improve recovery
- do not advance `CURRENT_STATE.md` merely because an intermediate checkpoint was published
- update architecture/data contracts only when durable system design changes
- use `PUBLICATION_CHECKLIST.md` before public operational/code publication

## Security/publication rules

This is a public repository.

Never commit:

- credentials, API tokens, passwords, SSH private keys, or secret files
- production IP addresses or firewall allowlists
- customer/device-identifying raw logs
- private hostnames or operator identity
- certificate private keys
- generated databases or runtime state
- restricted historical branding or organization identifiers

Use RFC documentation address space and synthetic hostnames in examples.

## Scope notes

- Firewall/nftables reconstruction is intentionally out of scope for the current rebuild milestone.
- GX10 complete rebuild capture is the next major component milestone after the collector is closed.
- Long-lived deterministic incident correlation and production LLM orchestration are not yet complete; reconstruct the currently functional GX10 implementation before adding new architecture.
