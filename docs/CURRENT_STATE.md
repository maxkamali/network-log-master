# Current State

Last verified project checkpoint: 2026-08-22.

This file is the authority for current execution order. Exactly one item should be marked `NEXT`.

## Project acceptance criterion

The rebuild/documentation project is complete only when two clean servers, this public repository, and operator-supplied environment values are sufficient for another engineer or AI to reconstruct the current functional system without undocumented implementation memory.

Environment-specific credentials, addresses, usernames, SSH keys, certificate private keys, and similar identity-bearing values are intentionally supplied by the operator during rebuild rather than stored publicly.

## Platform state

The working observability path currently provides:

- network syslog collection through Vector
- durable raw syslog storage in ClickHouse
- Grafana visualization over captured ClickHouse data
- compressed file backlog creation for GX10
- restricted read-only backlog retrieval by GX10
- GX10 local durable ingest with replay/idempotency protection
- transitional deterministic enrichment on GX10
- write-only AI-result return to the collector
- collector-side AI-result validation and ClickHouse ingestion

The long-lived deterministic incident correlator and production local-LLM orchestration are not yet complete.

## Normalizer milestone

Status: `DONE`

The active normalizer source is `components/normalizer/` in this master repository.

Completed replay/parity milestone:

- 24 representative stored observations
- 21 strict semantic matches
- 3 intentional NX-OS OSPFv3 differences
- 0 unexpected differences
- deterministic replay repeated successfully
- 73 tests passing
- public-repository sanitation gate passing

Reference milestone commit:

`4220f50474d608fd8745b4465398af521d7625bd`

The production collector path has not yet been switched to the new normalizer. Production cutover remains a later controlled migration task and is not required to finish the current rebuild-documentation milestone.

## Collector rebuild milestone

Status: `IN PROGRESS`

A durable public collector checkpoint was published at:

`e8df224` — `Checkpoint collector rebuild capture`

The collector checkpoint includes captured and public-safe rebuild artifacts for:

- package versions and package verification
- configuration rendering
- Vector ingest, transforms, ClickHouse sinks, AI-result ingestion, and GX10 spool output
- ClickHouse database objects, users, grants, and settings profile
- Grafana ClickHouse datasources
- Grafana HTTPS systemd configuration
- TLS ownership/mode contract
- Certbot renewal service, timer, and deploy hook
- restricted SFTP/chroot transport boundary
- ACLs and bind mounts
- AI-result validation gate
- GX10 spool-retention behavior
- independent collector runtime verification
- four Grafana 13 dashboard resources
- Grafana dashboard restore and verification scripts

Important completed collector validation includes:

- `COLLECTOR_PACKAGE_VERIFY=PASS`
- `TRANSPORT_VERIFY=PASS`
- `RETENTION_SCRIPT_CONTRACT=PASS`
- `RETENTION_RUNTIME_CONTRACT=PASS`
- `CLICKHOUSE_OBJECT_CONTRACT=PASS`
- `CLICKHOUSE_COLUMN_CONTRACT=PASS`
- `CLICKHOUSE_USER_POLICY=PASS`
- `CLICKHOUSE_GRANT_CONTRACT=PASS`
- `CLICKHOUSE_LOOPBACK_LISTENERS=PASS`
- `VECTOR_CRITICAL_CONFIG_PARITY=PASS`
- `VECTOR_SYSLOG_LISTENERS=PASS`
- `GRAFANA_HTTPS_OVERRIDE=PASS`
- `GRAFANA_HTTPS_HEALTH=PASS`
- `GRAFANA_DATASOURCE_CONTRACT=PASS`
- `CERTBOT_RUNTIME_CONTRACT=PASS`
- `COLLECTOR_RUNTIME_VERIFY=PASS`
- `GRAFANA_ADMIN_BOOTSTRAP_PATCH_VALIDATION=PASS`
- `GRAFANA_BOOTSTRAP_FAILURE_FLOW_VALIDATION=PASS`
- `GRAFANA_CLI_WORKDIR_FIX_VALIDATION=PASS`
- `GRAFANA_CLI_TEMP_DATABASE_TARGETING=PASS`
- `GRAFANA_DASHBOARD_WIRING_FINAL_VALIDATION=PASS`

Detailed component state is in `components/collector/REBUILD_STATUS.md`.

## Grafana dashboard reconstruction

Status: `DONE` for capture, restore mechanism, and clean-machine runtime-installer integration; clean-machine end-to-end execution remains a later collector validation gate.

Four current dashboards are captured as Grafana 13 `dashboard.grafana.app/v2` resources.

The supported API behavior was proven against Grafana 13.1.1:

- GET round-trip preserves captured dashboard `spec`
- POST creates a dashboard
- PUT replaces a dashboard
- `dryRun=All` validates without persistence
- dry-run create did not persist
- dry-run replace did not change live resource versions

Permanent scripts are published under `components/collector/grafana/scripts/`:

- `dashboard_api.py`
- `restore-dashboards.py`
- `verify-dashboards.py`

Completed validation:

- `GRAFANA_UNIFIED_RESOURCE_ROUND_TRIP=PASS`
- `GRAFANA_DRYRUN_RESTORE_PROOF=PASS`
- `GRAFANA_DASHBOARD_VERIFY=PASS`
- `GRAFANA_DASHBOARD_RESTORE_DRYRUN=PASS`
- `GRAFANA_DASHBOARD_LIVE_NONDESTRUCTIVE_TEST=PASS`
- `GRAFANA_DASHBOARD_WIRING_FINAL_VALIDATION=PASS`

The clean-machine runtime installer now restores the four captured dashboards after HTTPS health and datasource verification, then runs the independent dashboard verifier. Automatic replacement is intentionally not enabled; an unexpected existing divergent dashboard causes the installer to fail rather than overwrite it.

## Grafana administrator bootstrap

Status: `DONE` for clean-machine installer wiring; clean-machine end-to-end execution remains a later collector validation gate.

`install-runtime.sh` now:

- requires an operator-supplied private `GRAFANA_ADMIN_PASSWORD_FILE`
- rejects an empty, multiline, or group/world-accessible administrator password file
- starts first-run Grafana through a temporary systemd drop-in bound only to `127.0.0.1:3000`
- waits for Grafana health and confirms the bootstrap listener is loopback-only
- stops Grafana after database initialization
- runs `/usr/share/grafana/bin/grafana` as the `grafana` account from `/usr/share/grafana`
- explicitly selects `/etc/grafana/grafana.ini` and `/var/lib/grafana`
- resets administrator user ID 1 with `--password-from-stdin`
- checks Grafana SQLite integrity and ownership after reset
- removes the temporary bootstrap override before the later HTTPS startup path
- removes the temporary bootstrap override through the installer cleanup trap on failure

A non-destructive targeting proof used a temporary copy of the Grafana database and a synthetic user ID. The temporary password hash changed, the copied database passed `PRAGMA quick_check`, the synthetic user remained absent from the live database, and the live administrator password hash remained unchanged.

The clean-machine runtime installer itself has not been executed against the working reference collector.

## GX10 state

Status: `NOT STARTED` for complete public rebuild capture.

Verified working capabilities already known from the live system include:

- read-only secure fetch of compressed backlog files
- local durable SQLite ingest
- replay/idempotency protection
- transitional deterministic enrichment
- write-only secure AI-result return
- local Ollama runtime

Still requiring complete capture/rebuild treatment:

- package/runtime reconstruction
- NVIDIA/GB10 environment dependencies
- Ollama/model configuration
- spool fetcher implementation
- local SQLite schema and ingest implementation
- deterministic enrichment/classification implementation
- systemd service/timer configuration
- inference integration
- result-return implementation
- verification scripts
- operator rebuild documentation

Long-lived incident correlation and production LLM orchestration remain separate future implementation work beyond reconstruction of the currently functional system.

## Explicit execution order

1. `DONE` — publish durable collector capture checkpoint and recovery status.
2. `DONE` — prove Grafana 13 dashboard round-trip, create, replace, and non-destructive dry-run restore behavior.
3. `DONE` — publish permanent Grafana dashboard restore/verification scripts.
4. `DONE` — establish repository recovery/journal operating rules and canonical startup documentation.
5. `DONE` — secure Grafana administrator bootstrap is wired into `components/collector/install/install-runtime.sh` with private-file input, loopback-only first startup, explicit Grafana CLI path/data targeting, failure cleanup, and non-destructive temporary-database targeting proof.
6. `DONE` — `restore-dashboards.py` and `verify-dashboards.py` are wired into the clean-machine collector runtime installer after HTTPS health and datasource verification, using loopback HTTPS and the private administrator password file.
7. `NEXT` — add package-install no-autostart protection so services cannot transiently expose an unconfigured first-start state.
8. `NOT STARTED` — re-run collector installer structural, credential-exposure, and public-safety validation.
9. `NOT STARTED` — finish collector README and operator-facing clean-machine rebuild documentation.
10. `NOT STARTED` — run final collector public sanitation and close the collector rebuild milestone.
11. `NOT STARTED` — perform a clean-machine collector rebuild validation when practical.
12. `NOT STARTED` — capture and reconstruct the complete GX10 implementation.
13. `NOT STARTED` — validate the GX10 rebuild package and operator documentation.
14. `NOT STARTED` — reconcile and update full two-server architecture, operations, and rebuild documentation.
15. `NOT STARTED` — run final repository sanitation and two-server acceptance validation.
16. `NOT STARTED` — publish the final rebuild milestone.

Do not skip ahead unless this execution order is explicitly updated first. Only one item may be marked `NEXT`.

## Scope constraints

- Preserve verified working Vector and Grafana behavior; do not change behavior merely because a setting appears unusual.
- Firewall/nftables reconstruction is intentionally out of scope. Public docs should state required connectivity prerequisites without publishing deployment-specific firewall policy.
- Production device identities, addresses, credentials, authorized keys, certificate private keys, and similar private environment values stay outside the public repository.
- Public rebuild artifacts may generalize identity-bearing historical service names while preserving their behavior.
- Clean-machine rebuild installers must not be executed against working reference systems unless an explicit safe mode is designed and validated.

## Continuity rule

After each completed project sub-section passes its validation checkpoint, append the result to `docs/PROJECT_JOURNAL.md` and push the journal update to GitHub before materially proceeding into the next sub-section.