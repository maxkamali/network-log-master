# Current State

Last verified project checkpoint: 2026-08-24.

This file is the authority for current execution order. Exactly one item should be marked `NEXT`.

## Project acceptance criterion and disposition

The rebuild/documentation project is complete only when two clean servers, this public repository, and operator-supplied environment values are sufficient for another engineer or AI to reconstruct the current functional system without undocumented implementation memory.

Environment-specific credentials, addresses, usernames, SSH keys, certificate private keys, and similar identity-bearing values are intentionally supplied by the operator during rebuild rather than stored publicly.

Suitable disposable systems were unavailable. On 2026-08-23, the operator explicitly accepted the residual risk and authorized advancement without executing the clean-host gate. This closes the rebuild/documentation milestone for project sequencing; it does not manufacture empirical clean-host evidence.

## Final rebuild milestone status

Public rebuild packages, documentation, sanitation, and repository/read-only-reference acceptance: `DONE`.

Disposable clean-two-server execution: `WAIVED BY OPERATOR`, empirically unverified.

Rebuild/documentation milestone disposition: `ACCEPTED WITH RESIDUAL RISK`.

The final public repository milestone remains published without claiming that unavailable clean-host execution passed. If suitable disposable systems become available later, the runbooks should still be executed and the qualification removed only after successful evidence is recorded.

## Platform state

The working observability path currently provides:

- network syslog collection through Vector
- durable raw syslog storage in ClickHouse
- Grafana visualization over captured ClickHouse data
- compressed raw file backlog creation and preserved collector-local history
- restricted read-only retrieval of verified normalized handoff files by GX10
- GX10 local durable ingest with replay/idempotency protection
- managed canonical normalized-field projection and deterministic incident correlation on GX10, with historical version-3 enrichment preserved
- collector-side write-only AI-result return boundary and validation/ingestion path
- local Ollama runtime on GX10

Current rediscovery has not identified a GX10 application producer that writes to the collector result-return boundary, nor an application-specific observability-pipeline caller of Ollama.

The deterministic incident correlator now has a validated schema/engine contract, passing private working-database-copy and independent deterministic replay proof, a completed working-system migration under protected backup, and a separately managed production `projection -> incident` timer. Initial backfill and three scheduled zero-lag cadences passed while the original fetch/ingest timer continued advancing. Production local-LLM orchestration is not yet implemented.

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

The production collector GX10 handoff was switched to verified normalized output on 2026-08-24 through the documented immutable-floor, identity-preserving bind-only cutover. Raw backlog and shadow history remain intact, and the exact mount-only rollback boundary is retained.

Collector-side shadow integration implementation is now complete in the repository:

- durable settled-file worker with strict source containment and unchanged postcheck
- trusted private platform-inventory validator that rejects untrusted record hints
- atomic normalized Zstandard output with exact input/output cardinality
- SQLite processing/completion ledger with source/output/inventory/version evidence
- mutation refusal, interrupted-publication recovery, and independent full-output verification
- locked dedicated runtime identity and hardened no-network systemd service/timer
- non-activating, no-overwrite staging installer and exact SHA-256 package manifest
- pinned reference dependencies: Python `3.13.5-1` and Zstandard `1.5.7+dfsg-1`
- forward-only handoff publisher with an immutable inclusive floor, separate durable ledger, original transport identities, atomic no-overwrite copies, and complete stable-state verification
- synthetic cutover/retry/rollback proof with no historical exposure or duplicate GX10 identities
- 94 full normalizer/worker tests passing and 14 collector-package tests passing

The shadow package is deployed and active on the collector under its isolated timer. Bounded catch-up and steady-state evidence covers 11,983 completed files and 1,107,749 normalized records with exact cardinality, 36,241 parser enrichments, zero parser errors, zero incomplete rows, and zero pending work after every reviewed steady-state cycle. The item-23 stable cutover snapshot passed over 12,082 completed files and 1,117,167 records; the final post-cutover snapshot passed over 12,099 files and 1,118,724 records. The separate handoff publisher is active, and GX10 consumed the first 19 verified at/after-floor files and 1,916 records with exact aggregate parity, zero failed/queued rows, and zero duplicate identities. Vector, ClickHouse, raw backlog creation, and historical transport identities remain unchanged.

## Collector rebuild milestone

Status: `DONE` for the public collector rebuild package, operator documentation, and public sanitation; clean-machine end-to-end validation is `WAIVED BY OPERATOR` and remains empirically unverified because no disposable Debian 13 amd64 validation system is available.

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

Status: `DONE` for live-system rediscovery, public rebuild implementation, guarded activation, operator documentation, and repository-only validation. Clean-machine end-to-end execution is `WAIVED BY OPERATOR` and remains empirically unverified because no disposable Ubuntu 24.04 arm64 GX10-class validation system is available.

Durably journaled rediscovery through item 12N and the final closure audit has established:

- Ubuntu 24.04.4 LTS / arm64 / NVIDIA GB10 platform baseline
- NVIDIA driver and CUDA runtime/compiler baseline
- timer-driven oneshot pipeline service and hardening contract
- exact fetch, ingest, and deterministic-enrichment executable provenance
- remote-spool fetch/catch-up/SFTP/Zstandard semantics
- local SQLite ingest and replay/idempotency behavior
- deterministic classification version 3 and enrichment schema
- complete two-rule active suppression corpus
- rediscovery-time automatic runtime chain `timer -> fetch -> ingest`
- no rediscovered historical automatic invocation mechanism for deterministic enrichment
- no discovered GX10 application producer for the collector result-return boundary
- no discovered application-specific observability-pipeline caller of Ollama
- Ollama active/enabled service state, executable provenance, loopback listener, model storage, and six complete local model manifests
- complete effective SQLite schema: 5 application tables, 13 explicit indexes, 3 foreign keys, and zero unexpected schema objects
- no surviving bounded SQLite/bootstrap initializer artifact
- complete runtime-account, filesystem ownership/mode, SSH-material metadata, and systemd writable-path contracts
- Python `3.12.3`, SQLite runtime `3.45.1`, zero third-party Python imports, and exact Python package provenance
- required external dependencies `sftp`/`openssh-client` and `zstd` with package provenance

The corrected item-12N analyzer resolved command values through helper-function returns and found 5 external-tool source references across 2 dependencies, including 1 SFTP and 2 Zstandard subprocess invocations. Both executables are present and package-owned. Item 12N is complete.

The final live closure audit passed. It found exactly one match for each known application/service/timer hash, preserved the timer/service contract, reconfirmed zero systemd/cron enrichment references, verified external dependencies, and passed unchanged postcheck hashes.

After the normalized handoff stability gate passed, item 24 retired the unscheduled live transitional vendor/message reparser under its exact captured hash. The active replacement is the canonical schema-version-1 projector at SHA-256 `f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079`. Item 26 later placed that exact projector and the deterministic incident engine behind a separate managed offline service/timer. The initial production backfill created `8712` version-4 rows and `23` incidents at zero lag; three later scheduled gates ended at maximum event IDs `956240`, `956338`, and `956413`, all with zero projection/incident lag and zero service restarts. Historical version-3 rows remain preserved.

Detailed reconstruction authority is now in:

`components/gx10/REBUILD_STATUS.md`

The completed public package provides:

- synthetic operator-input template and neutral runtime identity/path contract
- guarded filesystem/SSH-material bootstrap and protected runtime configuration
- captured fetch/ingest applications, historical enrichment provenance, and the item-24 canonical normalized-field projector
- deterministic SQLite initialization matching all recovered DDL/index/foreign-key and suppression contracts
- captured service/timer preserving fetch-then-ingest order, cadence, and hardening
- exact pinned application packages and fail-closed platform verification
- exact Ollama binary/unit and offline six-model-store installation/verification
- reference-like/nonempty-state preactivation refusal
- dual-confirmation activation with full blob hashing and failure rollback
- complete clean-machine runbook and two-server integration runbook
- 94 passing GX10 tests
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`

The known application hashes remain:

- fetch: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- ingest: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- deterministic enrichment: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`
- canonical projection candidate: `f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079`
- managed correlation runner: `dde1aff929ec52957250ebd86bac01f88554caf20117b95463bc0313e00722c4`
- managed correlation service unit: `5dc2525f241f4d0574f695001d11c6cd8e5ff2f5d5597e16afadbedd6ebe0708`
- managed correlation timer unit: `af4e5d582eaf76b79e5a0a4acbbe7bff9f2cc6643c36fbc8e9ea81ed7367e73c`
- pipeline service unit: `0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`
- pipeline timer unit: `5371995539846d4cca6014a70548e95c942e9f601d0736b06f4bda61c1ccc0f5`

Rediscovery conclusions retained as the historical baseline; later implemented changes are separately journaled:

- automatic pipeline behavior discovered before reconstruction was `timer -> fetch -> ingest`
- deterministic enrichment had no discovered historical scheduler; item 26 later added the separate managed `projection -> incident` schedule
- Ollama/model infrastructure exists but no observability-pipeline caller has been identified
- the collector result-return boundary exists but no GX10 result producer has been identified
- missing historical bootstrap/install provenance should be reconstructed from captured effective contracts rather than invented and presented as discovered history

## Direct-access execution environment

Status: `ACTIVE`

The project is running from the operator-controlled VM. Public GitHub `main` and authenticated read-only command execution to both reference-system roles were verified before item 12N resumed.

Both reference-system SSH aliases now work directly through the operator VM's existing key configuration. Private connection values are not published.

The environment transition, both component rebuild packages, guarded activation, component/cross-system runbooks, architecture reconciliation, final repository sanitation, repository/read-only-reference acceptance validation, final public milestone publication, clean-host risk disposition, collector-side production-normalizer integration, forward-only production cutover, multi-cadence stability review, deliberate transitional-parser retirement, deterministic incident engine, managed projection/incident boundary, deterministic wake-policy/compact-packet implementation, and guarded local-reasoning installation are complete. Item 28 installed the exact calibrated Gemma caller/schema/configuration/prompt artifacts under a protected backup, but deliberately left all packet/model/prompt/run/result tables empty and created no scheduler reference. A later independent cadence check found both deterministic cursors at zero lag, both existing timers active, zero correlation restarts, and no production inference. Item 29 now has a repository-only exact-hash managed runner/installer/activator/verifier candidate with one-inference-per-cycle locking, aggregate backlog/run health, protected-backup-first activation, an injection-only private rehearsal seam, and passing 135-test validation. Protected-copy and working-system gates remain. The LLM remains outside identity and lifecycle authority.

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
11. `WAIVED BY OPERATOR` — clean-machine collector rebuild validation remains empirically unverified because no disposable Debian 13 amd64 validation system is available.
12. `DONE` — reconstructed the captured GX10 implementation as a public clean-machine rebuild package with guarded activation, offline model import, operator runbook, and final package audit.
13. `WAIVED BY OPERATOR` — clean-machine GX10 end-to-end validation remains empirically unverified because no disposable Ubuntu 24.04 arm64 GX10-class validation system is available; repository-only package/documentation validation passes.
14. `DONE` — reconciled full two-server architecture, current/target data contracts, operations, key-role boundaries, rebuild order, and acceptance documentation.
15. `DONE` — final current-tree/reachable-history sanitation, component tests, collector synthetic validation, Git/ref/link checks, private-identifier audit, and read-only two-server revalidation passed; the later unavailable disposable-host execution was waived with residual risk.
16. `DONE` — published the final public rebuild milestone with complete repository/reference-read-only evidence and explicit clean-host deferrals.
17. `WAIVED BY OPERATOR` — disposable collector, GX10, and two-server execution was unavailable; the operator accepted the residual risk and authorized advancement without representing this gate as passed.
18. `DONE` — designed collector-side production-normalizer integration with durable input/output boundaries, private platform-inventory injection, shadow observability, failure isolation, promotion gates, and rollback behavior.
19. `DONE` — implemented and validated the repository-side durable normalizer shadow worker, private-inventory validator, idempotency ledger, packaging, and independent verifier without deploying to the live collector.
20. `DONE` — obtained explicit live-shadow authorization, built and privately installed a conservative source-IP platform inventory, staged the package, completed two independently verified cycles, and activated only the isolated shadow timer without changing Vector, ClickHouse, or the GX10 handoff.
21. `DONE` — completed historical catch-up, five normal-cadence steady-state cycles, active-concurrency verifier correction/proof, full cardinality/output verification, source immutability checks, service isolation checks, and unchanged raw-handoff/GX10 artifact validation.
22. `DONE` — designed and synthetically rehearsed a forward-only file-identity-safe GX10 handoff and rollback using one immutable inclusive floor, verified normalized copies under original transport names, a separate durable ledger, and unchanged GX10 idempotency keys; the live handoff was not changed.
23. `DONE` — staged the validated exact-hash handoff package, corrected a systemd portability condition before activation, selected and protected an immutable inclusive floor, paused GX10 with zero conflicting identities, switched only its read-only bind view, proved exact collector/GX10 hash and cardinality parity, resumed all schedules, and retained the exact raw-view rollback boundary.
24. `DONE` — reviewed the multi-cadence normalized-handoff stability window, proved exact schema-v1 authority and legacy field divergence, built/rehearsed a replay-safe canonical projector with local suppression overlay, and atomically replaced the unscheduled live transitional parser under exact hash with protected rollback while leaving the database and automatic fetch/ingest chain unchanged.
25. `DONE` — implemented and validated deterministic GX10 incident identity/lifecycle, append-only evidence/transitions, repeat/burst accounting, rolling compact context, replay/idempotency, clean-install integration, guarded migration/rollback, private live-copy execution, independent deterministic rebuild, cursor-reset replay, and the unscheduled working-system schema/artifact migration with protected backup and unchanged fetch/ingest operation.
26. `DONE` — completed the fail-closed production backfill, exact private write-scope correction, timer activation, and three independent zero-lag scheduled cadences for the managed canonical-projection/incident boundary. The original fetch/ingest timer continued advancing, correlation restarts remained zero, and deterministic counts were monotonic.
27. `DONE` — implemented fixed deterministic wake priority/cooldowns and compact versioned append-only packet construction; passed 94 tests plus protected production-state-copy migration/build/no-op/replay/independent-reproduction/threshold/lifecycle/tamper/rollback gates; installed exact empty schema/builder unscheduled under a protected backup with zero packet rows/invocations/scheduler references and both production timers restored at zero correlation lag.
28. `DONE` — calibrated the strict versioned Gemma reasoning boundary, passed synthetic and protected production-state-copy success/invalid/unavailable/interrupted/idempotency gates, published the copy checkpoint, and installed only the exact inference schema/caller/configuration/prompt artifacts under a protected backup. Production remains at zero packet/model/prompt/run/result rows, zero caller scheduler references, and zero inference invocations.
29. `NEXT` — design and validate a separately disableable managed `packet build -> local inference` invocation boundary with an exact-hash runner, single-cycle locking, bounded work per cadence, explicit backlog/run/stale-reservation health, and failure isolation from fetch/ingest/correlation. Begin with repository and protected-copy gates; do not schedule production reasoning or return results to the collector until separate activation evidence passes.

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
