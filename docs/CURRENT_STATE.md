# Current State

Last verified project checkpoint: 2026-08-23.

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
- transitional deterministic enrichment implementation on GX10
- collector-side write-only AI-result return boundary and validation/ingestion path
- local Ollama runtime on GX10

Current rediscovery has not identified a GX10 application producer that writes to the collector result-return boundary, nor an application-specific observability-pipeline caller of Ollama.

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

Status: `DONE` for the public collector rebuild package, operator documentation, and public sanitation; clean-machine end-to-end validation is `DEFERRED` pending a disposable Debian 13 amd64 validation system.

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
- `PACKAGE_NO_AUTOSTART_FAILURE_PATH_VALIDATION=PASS`
- `PACKAGE_NO_AUTOSTART_SYNTHETIC_PROOF=PASS`
- `ITEM8C_CREDENTIAL_EXPOSURE_CLOSED=PASS`
- `ITEM8D_RUNTIME_DEPENDENCY_CHECKPOINT=PASS`
- `ITEM8E_STRUCTURAL_PREFLIGHT_CONTRACT=PASS`
- `SYNTHETIC_PRIVATE_KEY_DETECTOR=PASS`
- `ITEM8F_SHELL_EVALUATION_SAFETY=PASS`
- `ITEM8F_FINDING_CLASSIFICATION_RETRY=PASS`
- `ITEM9B_README_OPERATOR_RUNBOOK_CONTRACT=PASS`
- `ITEM10A_FINAL_SANITATION_AUDIT=PASS`

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

## Package-install no-autostart protection

Status: `DONE` for clean-machine package/runtime installer wiring and synthetic behavioral proof; clean-machine end-to-end execution remains a later collector validation gate.

`install-packages.sh` establishes the package-install safety boundary before apt transactions begin:

- a temporary `policy-rc.d` denies policy-aware package maintainer scripts from starting/restarting services
- persistent systemd `ConditionPathExists` guards hold Vector, ClickHouse, and Grafana until runtime configuration deliberately authorizes them
- an already-active SSH management plane is preserved
- an initially inactive SSH service/socket pair is held until transport configuration validates
- package completion verifies guarded collector services remain inactive
- the temporary `policy-rc.d` is removed after the package transaction

`install-runtime.sh` validates the same guard contract. ClickHouse, an initially inactive SSH service, and loopback-bootstrap Grafana use short-lived authorized starts while their persistent guards remain installed. The authorization token is removed immediately and through `EXIT` cleanup. Vector, ClickHouse, and Grafana guards are permanently removed only at the final configured-service activation boundary.

A synthetic temporary systemd unit proved unauthorized blocking, temporary authorization, guard reassertion after token removal, and normal start after permanent release. All real collector service active/enabled states were unchanged by that proof.

Completed validation includes:

- `PACKAGE_NO_AUTOSTART_PATCH_VALIDATION=PASS`
- `PACKAGE_NO_AUTOSTART_FAILURE_PATH_VALIDATION=PASS`
- `SYSTEMD_GUARD_BLOCK=PASS`
- `SYSTEMD_TEMPORARY_AUTHORIZATION=PASS`
- `SYSTEMD_GUARD_REASSERTION=PASS`
- `SYSTEMD_FINAL_RELEASE=PASS`
- `collector_service_state_unchanged=PASS`
- `PACKAGE_NO_AUTOSTART_SYNTHETIC_PROOF=PASS`

## GX10 state

Status: `IN PROGRESS` — live-system rediscovery is nearly complete; public rebuild implementation has not yet begun.

Durably journaled rediscovery through item 12M has established:

- Ubuntu 24.04.4 LTS / arm64 / NVIDIA GB10 platform baseline
- NVIDIA driver and CUDA runtime/compiler baseline
- timer-driven oneshot pipeline service and hardening contract
- exact fetch, ingest, and deterministic-enrichment executable provenance
- remote-spool fetch/catch-up/SFTP/Zstandard semantics
- local SQLite ingest and replay/idempotency behavior
- deterministic classification version 3 and enrichment schema
- complete two-rule active suppression corpus
- proven automatic runtime chain `timer -> fetch -> ingest`
- no discovered automatic invocation mechanism for deterministic enrichment
- no discovered GX10 application producer for the collector result-return boundary
- no discovered application-specific observability-pipeline caller of Ollama
- Ollama active/enabled service state, executable provenance, loopback listener, model storage, and six complete local model manifests
- complete effective SQLite schema: 5 application tables, 13 explicit indexes, 3 foreign keys, and zero unexpected schema objects
- no surviving bounded SQLite/bootstrap initializer artifact

Item 12N runtime/filesystem/dependency inspection was executed immediately before the environment-transition pause. Its runtime identity, filesystem ownership/mode, SSH metadata, systemd sandbox, and Python-runtime portions passed, but the external-executable dependency detector incorrectly reported zero external tools despite earlier proven SFTP and Zstandard use.

Therefore item 12N is `PARTIAL` and must not be treated as complete until that narrow detector is corrected and rerun.

Detailed partial evidence and the exact resume procedure are recorded in:

`docs/VM_HANDOFF.md`

The known application hashes remain:

- fetch: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- ingest: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- deterministic enrichment: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`
- pipeline service unit: `0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`

Current rediscovery conclusions that must not be silently changed during reconstruction:

- automatic pipeline behavior currently proven is `timer -> fetch -> ingest`
- deterministic enrichment exists but is not proven automatically scheduled
- Ollama/model infrastructure exists but no observability-pipeline caller has been identified
- the collector result-return boundary exists but no GX10 result producer has been identified
- missing historical bootstrap/install provenance should be reconstructed from captured effective contracts rather than invented and presented as discovered history

## Execution pause and direct-access VM handoff

Status: `PAUSED FOR EXECUTION-ENVIRONMENT MIGRATION`

The project is intentionally paused while execution moves to an operator-controlled VM with direct authenticated access to the collector reference system, GX10, and GitHub.

This changes the execution mechanism, not project scope or safety rules.

The new VM session must begin by reading `docs/VM_HANDOFF.md`, verifying public `main`, verifying authenticated connectivity to both reference systems, and revalidating the known GX10 artifact hashes before materially continuing.

The first technical action after those preconditions is to correct and rerun only the item-12N external-executable dependency/provenance check. Earlier rediscovery already proves SFTP and Zstandard usage, so a zero external-tool result must not be accepted.

After corrected 12N validation:

1. complete and journal item 12N
2. run the final GX10 rediscovery closure audit
3. publish a rediscovery-complete checkpoint
4. only then begin GX10 public rebuild implementation

Direct credentials must not be interpreted as blanket authorization for destructive changes. Human intervention remains required for destructive/high-risk actions, architecture/scope decisions, or ambiguity requiring operator intent.

## Explicit execution order

1. `DONE` — publish durable collector capture checkpoint and recovery status.
2. `DONE` — prove Grafana 13 dashboard round-trip, create, replace, and non-destructive dry-run restore behavior.
3. `DONE` — publish permanent Grafana dashboard restore/verification scripts.
4. `DONE` — establish repository recovery/journal operating rules and canonical startup documentation.
5. `DONE` — secure Grafana administrator bootstrap is wired into `components/collector/install/install-runtime.sh` with private-file input, loopback-only first startup, explicit Grafana CLI path/data targeting, failure cleanup, and non-destructive temporary-database targeting proof.
6. `DONE` — `restore-dashboards.py` and `verify-dashboards.py` are wired into the clean-machine collector runtime installer after HTTPS health and datasource verification, using loopback HTTPS and the private administrator password file.
7. `DONE` — package-install no-autostart protection uses a temporary Debian service-policy guard plus persistent systemd condition guards, with failure-safe runtime authorization and synthetic behavior proof.
8. `DONE` — collector installer structural, credential-exposure, dependency, failure-cleanup, and public-safety validation completed.
9. `DONE` — collector README and operator-facing clean-machine rebuild documentation completed and validated.
10. `DONE` — final collector public sanitation passed and the public collector rebuild-package/documentation milestone was closed.
11. `DEFERRED` — clean-machine collector rebuild validation remains outstanding because no disposable Debian 13 amd64 validation system is currently available.
12. `NEXT` — finish GX10 rediscovery, publish the rediscovery-complete checkpoint, then capture and reconstruct the complete GX10 implementation.
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
- Direct authenticated VM access does not authorize destructive changes to reference systems by default.

## Continuity rule

After each completed project sub-section passes its validation checkpoint, append the result to `docs/PROJECT_JOURNAL.md` and push the journal update to GitHub before materially proceeding into the next sub-section.

For long, risk-heavy, or multi-step sub-sections, publish meaningful validated intermediate implementation/journal checkpoints when they create useful recovery points. Intermediate checkpoints do not advance the single `NEXT` item until the sub-section is actually complete.
