# AI Handoff

Use this file to resume the project safely in a fresh AI session.

## Mandatory read order

1. `docs/START_HERE.md`
2. `docs/ARCHITECTURE.md`
3. `docs/CURRENT_STATE.md`
4. the active component rebuild status — currently `components/collector/REBUILD_STATUS.md`
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

Secure Grafana administrator bootstrap wiring in `components/collector/install/install-runtime.sh` is complete.

The implementation now uses:

- operator-supplied private `GRAFANA_ADMIN_PASSWORD_FILE`
- loopback-only first Grafana startup on `127.0.0.1:3000`
- explicit bootstrap health/listener verification
- administrator reset through `--password-from-stdin`
- explicit packaged Grafana config and `/var/lib/grafana` data targeting
- execution as the `grafana` service account from `/usr/share/grafana`
- database integrity/ownership verification
- cleanup of the bootstrap-only systemd override on success or failure

A temporary-database proof verified that explicit CLI data targeting changes only the selected temporary Grafana database; the working collector administrator password hash was unchanged.

Dashboard reconstruction wiring in the clean-machine runtime installer is complete.

The installer now:

- requires the dashboard API scripts and all four captured dashboard resources
- waits for normal Grafana HTTPS health
- verifies both ClickHouse datasources before dashboard work
- restores through loopback HTTPS using the private administrator password file
- creates missing dashboards and leaves exact matches unchanged
- does not automatically replace divergent existing dashboards
- runs `verify-dashboards.py` after restore
- uses Python `-B` for both runtime dashboard commands

The next implementation task is package-install no-autostart protection so package installation cannot transiently expose an unconfigured service before the runtime installer has applied the captured configuration.

Do not execute the clean-machine runtime installer against the working collector.

After the package no-autostart sub-section validates, update and push `docs/PROJECT_JOURNAL.md` before materially proceeding to installer structural/public-safety validation.

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