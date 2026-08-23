# Project Journal

This file is append-only. It records important engineering checkpoints, architectural decisions, migration boundaries, and recovery context. Detailed implementation evidence belongs in commits, tests, component documentation, and rebuild status files.

## Journal operating rules

The journal is historical context, not the execution queue.

Authoritative roles:

- `docs/ARCHITECTURE.md` describes the intended system architecture and ownership boundaries.
- `docs/CURRENT_STATE.md` describes the present implementation state and is the authority for execution order and the single next action.
- `components/<component>/REBUILD_STATUS.md` contains detailed component-specific rebuild and validation state.
- `docs/PROJECT_JOURNAL.md` explains what happened, why decisions were made, what failed, and how the project reached the current state.

Each substantial work-session entry should record, when applicable:

- local timestamp including timezone
- goal of the session or checkpoint
- starting branch and commit
- affected components or files
- work completed
- validation evidence and important PASS/FAIL results
- architectural or operational decisions
- failed approaches or corrections worth remembering
- known risks, constraints, and intentionally deferred work
- resulting Git commit and whether the remote was verified
- worktree state at the checkpoint
- the explicit next action

Additional rules:

- Every completed project sub-section must be recorded in this journal and pushed to GitHub before proceeding materially into the next sub-section.
- A sub-section is considered complete only after its intended validation/checkpoint passes; the journal entry should record that validation evidence and the next action.
- Do not silently rewrite history when an earlier assumption is later found to be wrong. Append a new entry that supersedes or corrects the earlier entry.
- Do not use the journal as a substitute for `CURRENT_STATE.md`. Execution order must remain explicit in `CURRENT_STATE.md`.
- Do not record secrets, credentials, private keys, production addresses, customer-identifying logs, private operator identities, or restricted historical branding.
- Failed experiments should be recorded when repeating them would waste time, risk production, or obscure why the current implementation was chosen. Routine command noise should not be preserved.
- At milestone checkpoints, record the commit SHA and whether the remote branch was verified to match it.
- Before beginning work after a context reset, read `ARCHITECTURE.md`, `CURRENT_STATE.md`, the relevant component `REBUILD_STATUS.md`, the latest journal entries, then verify `git log` and `git status` before changing anything.

## 2026-08-19 - Master repository established

- Established this repository as the public master project record.
- Confirmed the preferred long-term structure is a single master repository with component subdirectories rather than multiple independently drifting copies.
- Kept the existing normalizer repository temporarily separate while its live development checkout remains ahead of the published remote.
- Established the rule that live verified code and system state take precedence over historical documentation.
- Established a strict public-repository posture: no credentials, production addresses, customer-identifying logs, or restricted historical branding.

## 2026-08-19 - Architecture boundary confirmed

- Collector/log server owns collection, durable storage, deterministic normalization, presentation, unknown-event inventory, AI-result validation, and long-lived stores.
- GX10 owns compact incident state, deterministic correlation, local reasoning, and explanation.
- Transitional vendor parsing that exists on GX10 is a migration reference, not the desired permanent boundary.
- GX10 remains replaceable and receives prepared observations instead of becoming the raw-log authority.

## 2026-08-19 - Normalizer checkpoint

Verified live development state:

```text
f95db38 Enable NX-OS ETHPORT parser in default registry
58 tests passing
clean working tree
```

Implemented parser families at this checkpoint:

- Arista EOS BGP adjacency
- Cisco IOS XR BGP adjacency
- Cisco NX-OS ETHPORT state

## 2026-08-19 - OSPF research checkpoint

Production examples were inspected before parser implementation.

Verified that the generic normalizer distinguishes:

```text
OSPF-5-NBR_RETRANSMISSIONS   -> event_family ospf
OSPFV3-5-NBR_RETRANSMISSIONS -> event_family ospfv3
```

Both remain generic observations until the NX-OS parser is added.

A transitional GX10 classifier already treats retransmission evidence as a degradation and keys known neighbors using a deterministic OSPF device/process/neighbor identity. A limitation was identified in the transitional process extraction: it recognizes `ospf-N` but does not fully preserve `ospfv3-N`. The new collector-side parser should correct this while preserving OSPF versus OSPFv3 family identity.

Implementation was deliberately paused at this point for design discussion.

## 2026-08-19 - Documentation hardening pass

- Added operational pipeline documentation covering collector ingest, durable backlog, GX10 replay-safe ingest, AI-result validation, and failure behavior.
- Added ClickHouse schema and sink-contract documentation.
- Added Grafana datasource, drilldown, and NOC-view behavior documentation.
- Added an architecture decision log covering capture-first behavior, collector/GX10 ownership, LLM authority limits, transport boundaries, and master-repository policy.
- Added a controlled normalizer migration document with parser-by-parser parity gates.
- Added a public publication checklist for secrets, restricted terms, fixtures, tests, diffs, and migration provenance.
- Expanded the master README so these documents are discoverable from the repository front page.
- No production path was changed as part of this documentation pass.

## 2026-08-20 - Normalizer source consolidated into master repository

- Reconciled the live normalizer checkout with its standalone public repository at `f95db38`.
- Re-ran the public-repository sanitation gate successfully.
- Re-ran the full normalizer suite with 58 tests passing.
- Published the 14 previously local reviewed commits to the standalone repository to preserve provenance.
- Imported the standalone normalizer history into `components/normalizer/` using a Git subtree merge.
- Master import commit `8d55320` retains `f95db38` as a parent and records the subtree split SHA.
- Verified the imported package resolves from the master-repository path rather than the old checkout.
- Re-ran all 58 tests from the imported master-repository component successfully.
- Published the history-preserving import to the master repository.
- Declared `components/normalizer/` in the master repository the active development source for future normalizer work.
- The standalone normalizer repository is now historical/migration reference only.
- No production collector or GX10 service behavior changed during this consolidation.

## 2026-08-20 - NX-OS OSPF/OSPFv3 parser completed

- Repaired the public-repository gate for the monorepo layout in `18ec113` without weakening the local forbidden-term policy.
- Added the isolated Cisco NX-OS OSPF/OSPFv3 retransmission parser in `7f7f592`.
- Registered the parser in the default parser registry in `81a3812`.
- Parser coverage includes both `%OSPF-5-NBR_RETRANSMISSIONS` and `%OSPFV3-5-NBR_RETRANSMISSIONS`.
- Preserved generic family identity (`ospf` versus `ospfv3`) while grouping both under protocol `ospf`.
- Added deterministic `OSPF|device|process|neighbor` identity and required the process prefix to agree with the event code.
- Added negative-path tests for malformed identity, future codes, OSPF/OSPFv3 process mismatches, Cisco IOS XR, and Arista EOS.
- Verified source-IP fallback when hostname is absent.
- Verified malformed and unsupported observations stay capture-first generic and attention-eligible.
- Full suite reached 70 passing tests.
- Public-repository gate passed with all five local forbidden terms loaded.
- Published the parser and registry commits to the master repository.
- No production collector or GX10 path was changed.
- Next gate is replay/parity against stored observations and transitional GX10 enrichment, not additional parser breadth by default.

## 2026-08-20 - Platform resolution and first real replay proof

- Inspected live collector Vector parsing behavior and established that fallback parser labels describe syslog envelope parsing rather than trustworthy device platform identity.
- Established a private platform-resolution contract based on the deployment's stable syslog `source_ip` identity.
- Used deliberately narrow production-observed message fingerprints only to bootstrap and audit the private inventory.
- Kept the runtime trust path independent of message fingerprints.
- Preserved fail-closed behavior: sources absent from the private inventory remain generic capture-first observations.
- Kept production source identities, hostnames, and the private inventory outside the public repository.
- Replay exposed an initial inventory-evidence gap for NX-OS OSPF retransmission events.
- Added the already-supported narrow OSPF/OSPFv3 retransmission grammar to the private bootstrap evidence rather than creating a one-off source exception.
- The revised private evidence set introduced no reviewed cross-platform conflicts.
- Replayed three real stored NX-OS OSPF and three real stored NX-OS OSPFv3 retransmission observations through trusted platform resolution and the collector-side normalizer.
- All six passed the semantic gate for vendor, OS family, event family, protocol, signal type, entity type, state, entity-key presence, process identity, and neighbor presence.
- Verified that transitional GX10 v3 leaves the reviewed OSPFv3 retransmission observations generic, while the collector-side parser intentionally recognizes them as OSPFv3 neighbor degradation.
- No production collector path was changed.
- Next gate is broader replay/parity for EOS BGP, IOS XR BGP, and NX-OS ETHPORT before production integration design.

## 2026-08-20 - Selected normalizer replay/parity milestone completed

- Replayed the selected EOS BGP, IOS XR BGP, NX-OS ETHPORT, NX-OS OSPF, and NX-OS OSPFv3 migration scope.
- Compared 24 representative stored observations against transitional GX10 v3.
- Corrected two genuine collector gaps: EOS peer-AS preservation and NX-OS ETHPORT protocol identity.
- Confirmed the IOS XR reason/detail discrepancy was representational rather than semantic.
- Final parity result: 21 strict matches, 3 intentional OSPFv3 differences, 0 unexpected differences, PASS.
- Added sanitized deterministic replay coverage including an unmapped-source generic case.
- Repeated replay passed twice with identical output.
- Full normalizer suite reached 73 passing tests.
- No production collector or GX10 service path was changed.
- Next gate is production integration and rollback design.

## 2026-08-21 01:58 PDT - Collector rebuild capture checkpoint published

### Goal

Create a durable public recovery point before continuing deeper clean-machine integration work so the collector does not need to be rediscovered if conversational context is lost.

### Starting point

- Branch: `main`
- Previous public milestone: normalizer replay/parity complete at `4220f50474d608fd8745b4465398af521d7625bd`
- Collector rebuild artifacts were present locally but had not yet been published.

### Work completed

Captured and published the current collector reconstruction artifacts for:

- package versions and package verification
- configuration rendering
- Vector syslog ingestion, ClickHouse sinks, AI-result ingestion, and durable GX10 spool output
- ClickHouse database objects, service accounts, grants, and settings profile
- Grafana ClickHouse datasources
- Grafana HTTPS configuration and TLS file contract
- Certbot renewal service, timer, and deploy hook
- restricted SFTP transport boundary, chroots, ACLs, and bind mounts
- AI-result validation gate
- spool-retention behavior
- independent collector runtime verification
- four Grafana 13 dashboard resources
- Grafana dashboard restore and verification scripts
- component recovery document at `components/collector/REBUILD_STATUS.md`

### Validation evidence

Important completed validation gates include:

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
- `GRAFANA_UNIFIED_RESOURCE_ROUND_TRIP=PASS`
- `GRAFANA_DRYRUN_RESTORE_PROOF=PASS`
- `GRAFANA_DASHBOARD_VERIFY=PASS`
- `GRAFANA_DASHBOARD_RESTORE_DRYRUN=PASS`
- `GRAFANA_DASHBOARD_LIVE_NONDESTRUCTIVE_TEST=PASS`

Grafana 13.1.1 was also verified to support secure administrator reset using `grafana cli admin reset-admin-password --password-from-stdin`.

### Decisions and constraints

- Do not execute `components/collector/install/install-runtime.sh` against the working collector. It is a clean-machine installer with an explicit clean-install guard.
- Preserve the current working Vector and Grafana behavior rather than changing configuration merely because it looks unusual.
- Public rebuild artifacts use neutral service names when live historical names contain private identity.
- Firewall/nftables reconstruction remains intentionally out of scope. Public documentation should state required network prerequisites without publishing deployment-specific firewall policy.
- Grafana dashboards are restored through the supported `dashboard.grafana.app/v2` API rather than by writing directly to Grafana SQLite state.
- Credentials, addresses, SSH keys, TLS private keys, and private environment identity remain operator-supplied and outside the public repository.

### Failed approaches worth remembering

- Early Grafana bootstrap audit commands incorrectly assumed `grafana` or `grafana-cli` was on `PATH`. The package service actually uses `/usr/share/grafana/bin/grafana`.
- One diagnostic contained a bare interactive-shell `exit 1` and could terminate the SSH session. Subsequent potentially failing command sequences must run inside a child shell.
- Grafana runtime wiring patch attempts were aborted because of an ambiguous text anchor and a heredoc delimiter collision. Those attempts failed before replacing `install-runtime.sh`; the published checkpoint intentionally records the Grafana runtime integration as unfinished.

### Git checkpoint

- Collector checkpoint commit: `e8df224`
- Commit message: `Checkpoint collector rebuild capture`
- 39 collector files were committed.
- `origin/main` was explicitly verified to match the local checkpoint commit.
- Worktree was clean after publication.

### Known incomplete work

Collector:

1. Wire `GRAFANA_ADMIN_PASSWORD_FILE` into `install-runtime.sh`.
2. Implement loopback-only first Grafana startup and secure administrator reset with `--password-from-stdin`.
3. Wire `restore-dashboards.py` and `verify-dashboards.py` into the clean-machine runtime installer.
4. Add package-install no-autostart protection before first configuration.
5. Re-run structural, runtime-contract, and public-safety checks.
6. Finish collector README/operator rebuild documentation.
7. Run final collector sanitation and milestone publication.
8. Perform a clean-machine end-to-end rebuild validation when practical.

GX10 remains the next major component milestone after the collector is closed.

### Next action

Refresh `docs/CURRENT_STATE.md` so it contains a strict numbered execution order with exactly one item marked `NEXT`. Then resume collector Grafana clean-machine integration from the published `e8df224` checkpoint. Do not begin GX10 capture until the collector milestone execution order is explicitly advanced or intentionally reprioritized in `CURRENT_STATE.md`.

## 2026-08-21 02:00 PDT - Journal-after-each-subsection rule adopted

### Decision

From this point forward, every completed project sub-section must be journaled and pushed to GitHub before materially proceeding into the next sub-section.

A sub-section is complete only after its intended validation/checkpoint passes. The corresponding journal entry should capture the completed work, validation evidence, material decisions or corrections, and the explicit next action.

### Purpose

This makes GitHub the durable continuity mechanism for the project. A fresh engineer or AI session should be able to recover progress from the repository rather than depending on conversational memory.

### Next action

Update `docs/CURRENT_STATE.md` with the strict execution order and exactly one item marked `NEXT`, then continue collector Grafana clean-machine integration.

## 2026-08-21 02:03 PDT - Documentation consistency audit

### Goal

Identify which durable project documents are now stale after the collector rebuild capture checkpoint and the new journal/recovery rules.

### Findings

Documents requiring immediate update before more implementation work:

1. `docs/CURRENT_STATE.md` - still reports a 2026-08-20 checkpoint and identifies normalizer production integration as the next work. It does not record the published collector rebuild checkpoint, Grafana dashboard restore proof, strict execution order, or single `NEXT` action.
2. `docs/AI_HANDOFF.md` - resume point still ends at normalizer replay/parity and does not direct a fresh session through the collector `REBUILD_STATUS.md` or the new journal-after-each-subsection rule.
3. `docs/ROADMAP.md` - remains a broad architecture/build roadmap but does not reflect the current ordered rebuild-completion sequence: close collector rebuild first, then capture/rebuild GX10, then final two-server acceptance validation.
4. `README.md` - repository description still says remaining live components will move here only after reconciliation, although the collector now has a substantial published rebuild capture. The repository map should explicitly surface collector rebuild status and recovery entry points.
5. `components/collector/README.md` - remains only a short ownership description and does not point operators to package/runtime installers, verifiers, dashboard restore tooling, or `REBUILD_STATUS.md`.

Documents that are substantially consistent and do not require immediate execution-control updates:

- `docs/ARCHITECTURE.md` - target ownership and data-path boundaries remain consistent.
- `docs/CLICKHOUSE.md` - current durable table/view and access-boundary description remains consistent with captured implementation.
- `docs/OPERATIONS.md` - current ingest, backlog, transport, validation, retention, and failure behavior remain consistent at the architectural/operational level.
- `docs/DATA_CONTRACTS.md` - current raw/normalized/AI-result/target incident contracts remain consistent.

Documents that should receive targeted additions during final collector documentation hardening rather than blocking the immediate execution-control refresh:

- `docs/GRAFANA.md` - should document the proven Grafana 13 `dashboard.grafana.app/v2` restore/verify mechanism and current datasource reconstruction contract.
- `docs/DECISIONS.md` - should add durable decisions for the public two-clean-server rebuild acceptance contract and supported Grafana API restoration instead of direct SQLite modification.

### Next action

Update `docs/CURRENT_STATE.md` first because it is the execution authority. Then update `docs/AI_HANDOFF.md`, `docs/ROADMAP.md`, `README.md`, and `components/collector/README.md` before returning to Grafana implementation work. Each completed documentation sub-section must be journaled and pushed before proceeding to the next.

## 2026-08-21 02:05 PDT - Recovery and execution documentation refresh completed

### Goal

Bring the durable repository documentation into alignment with the published collector rebuild checkpoint, the proven Grafana 13 restore mechanism, the two-clean-server rebuild acceptance criterion, and the new GitHub-based continuity rules before returning to implementation work.

### Work completed

Created a canonical recovery entry point:

- `docs/START_HERE.md`

Updated the execution and recovery control documents:

- `docs/CURRENT_STATE.md`
- `docs/AI_HANDOFF.md`
- `docs/ROADMAP.md`
- top-level `README.md`

Updated collector/component recovery documentation:

- `components/collector/README.md`
- `components/collector/REBUILD_STATUS.md`

Updated durable architecture/operations documentation:

- `docs/ARCHITECTURE.md`
- `docs/OPERATIONS.md`
- `docs/GRAFANA.md`
- `docs/NORMALIZER_MIGRATION.md`

Updated durable decision/publication rules:

- `docs/DECISIONS.md`
- `docs/PUBLICATION_CHECKLIST.md`

Documents reviewed and intentionally left unchanged because their current contracts remain accurate:

- `docs/CLICKHOUSE.md`
- `docs/DATA_CONTRACTS.md`

### Execution-control result

`docs/CURRENT_STATE.md` now:

- records the 2026-08-21 collector rebuild checkpoint
- records the completed Grafana 13 dashboard restore proof
- distinguishes completed capture from unfinished runtime-installer integration
- defines the complete numbered project execution order
- contains exactly one item marked `NEXT`

The single current `NEXT` item is secure Grafana administrator bootstrap wiring in `components/collector/install/install-runtime.sh`.

### Durable decisions recorded

Added/clarified durable decisions that:

- rebuildability is a formal project acceptance criterion
- two clean servers plus the public repository and operator-supplied environment values must be enough to reconstruct the current functional system
- Grafana dashboards are restored through the supported `dashboard.grafana.app/v2` API rather than direct SQLite writes
- GitHub documentation/journal state is the durable continuity mechanism for project execution
- current functional implementation is captured before substantial modernization work

### Publication/recovery rules recorded

The repository now explicitly requires:

- `docs/START_HERE.md` as the canonical fresh-session entry point
- `docs/CURRENT_STATE.md` as execution authority with exactly one `NEXT` item
- component `REBUILD_STATUS.md` for detailed rebuild evidence
- append-only `docs/PROJECT_JOURNAL.md` for chronological decisions/results
- journal-and-push after every completed validated sub-section before materially entering the next one

### Git commits created during this documentation refresh

- `7a2b028` — add canonical project recovery entry point
- `dbc5092` — refresh current state and execution order
- `3c86195` — refresh AI handoff for collector rebuild phase
- `2bea66b` — align roadmap with rebuild milestones
- `283b3e5` — refresh repository overview and recovery entry points
- `ea4699f` — expand collector rebuild component documentation
- `860ae88` — add rebuildability contract to architecture
- `7d76b2e` — document Grafana 13 rebuild and dashboard restore contract
- `10858d6` — record rebuildability and Grafana restore decisions
- `972378a` — add rebuild and continuity publication gates
- `bb0348a` — document rebuild operations and continuity rules
- `4b133ba` — clarify normalizer migration is deferred during rebuild capture
- `9e6a2cf` — align collector rebuild status with execution authority

All writes were made directly to the repository `main` branch through the GitHub connector. No production service/configuration was changed by this documentation sub-section.

### Next action

Return to collector implementation work at the single `NEXT` item in `docs/CURRENT_STATE.md`: finish secure Grafana administrator bootstrap wiring in `components/collector/install/install-runtime.sh`. After that sub-section passes its intended validation, append and push its journal entry before moving to dashboard restore/verification wiring.
## 2026-08-22 18:23 PDT - Secure Grafana administrator bootstrap completed

### Goal

Complete the clean-machine Grafana administrator bootstrap in `components/collector/install/install-runtime.sh` without exposing an unconfigured Grafana instance or placing the administrator password in process arguments or public configuration.

### Work completed

The runtime installer now:

- requires operator-supplied `GRAFANA_ADMIN_PASSWORD_FILE`
- requires the administrator password file to be non-empty and mode-private
- rejects multiline administrator passwords
- creates a temporary Grafana systemd override for HTTP on `127.0.0.1:3000`
- starts Grafana only on that loopback bootstrap listener
- waits for `/api/health` and requires the Grafana database to report healthy
- verifies the TCP/3000 listener is exactly loopback-only
- stops Grafana after first database initialization
- invokes `/usr/share/grafana/bin/grafana` as the `grafana` service account
- runs the CLI from `/usr/share/grafana`
- explicitly supplies `/etc/grafana/grafana.ini`
- explicitly selects `/var/lib/grafana` through `--configOverrides`
- resets administrator user ID 1 using `--password-from-stdin`
- verifies the Grafana SQLite database with `PRAGMA quick_check`
- verifies Grafana database ownership remains `grafana:grafana`
- removes the temporary bootstrap-only systemd override before the normal HTTPS startup path
- removes the bootstrap override and stops temporary Grafana through cleanup if bootstrap fails

The clean-machine runtime installer was not executed against the working reference collector.

### Validation evidence

Repository/structural validation:

- `GRAFANA_ADMIN_BOOTSTRAP_PATCH_VALIDATION=PASS`
- `GRAFANA_BOOTSTRAP_FAILURE_FLOW_VALIDATION=PASS`
- `GRAFANA_CLI_WORKDIR_FIX_VALIDATION=PASS`
- `install_runtime_bash_syntax=PASS`
- `grafana_admin_checkpoint_contract=PASS`
- `current_state_single_next=PASS`
- `PUBLIC REPO GATE: PASS`

Grafana CLI capability validation:

- Grafana version: 13.1.1
- `reset-admin-password` supports `--password-from-stdin`
- `--configOverrides "cfg:default.paths.data=..."` was proven to select the intended Grafana data directory

Non-destructive behavioral proof:

- a consistent temporary copy of the live Grafana SQLite database was created
- administrator user ID 1 was changed to a synthetic ID only inside the temporary copy
- the Grafana CLI reset targeted that synthetic user in the explicitly selected temporary data directory
- the temporary password hash changed
- the temporary database passed `PRAGMA quick_check`
- the synthetic user remained absent from the live database
- the live administrator password hash remained unchanged
- final result: `GRAFANA_CLI_TEMP_DATABASE_TARGETING=PASS`

### Corrections discovered during implementation

Several checks prevented unsafe or incorrect behavior from being committed:

1. Grafana 13 CLI does not accept service-style bare `cfg:...` arguments in CLI mode. The supported CLI form is `--configOverrides`.
2. Wrapping the bootstrap body in `if ! ( ... )` could interfere with expected `set -e` behavior. The implementation was changed to use the installer's top-level strict mode plus cleanup through the existing `EXIT` trap.
3. `runuser` inherited an inaccessible operator working directory during the first temporary-database proof. The final implementation explicitly changes to `/usr/share/grafana` before invoking the CLI as the `grafana` account.
4. The temporary-database proof was rerun after that correction and passed without modifying the live administrator password.

### Git checkpoint

Implementation commit:

`fe5a611d5379b946660d6255032d02fa40a8c310` — `Complete Grafana admin bootstrap wiring`

`origin/main` was explicitly verified to match that implementation commit before this journal entry was created.

The implementation checkpoint also advanced `docs/CURRENT_STATE.md` so item 5 is `DONE` and item 6 is the single `NEXT` item.

### Next action

Wire `components/collector/grafana/scripts/restore-dashboards.py` and `verify-dashboards.py` into the clean-machine runtime installer after normal Grafana HTTPS health and datasource provisioning are established.

Do not proceed to package no-autostart hardening until the dashboard-wiring sub-section is validated, journaled, and pushed.

## 2026-08-22 18:35 PDT - Grafana dashboard runtime wiring completed

### Goal

Integrate the already-proven Grafana 13 dashboard restore and verification tooling into the clean-machine collector runtime installer without introducing direct SQLite dashboard writes or automatic destructive replacement.

### Work completed

`components/collector/install/install-runtime.sh` now:

- requires `grafana/scripts/dashboard_api.py`
- requires `grafana/scripts/restore-dashboards.py`
- requires `grafana/scripts/verify-dashboards.py`
- requires all four captured Grafana dashboard resource files
- waits for normal Grafana HTTPS health before dashboard reconstruction
- verifies both captured ClickHouse datasources before dashboard reconstruction
- invokes dashboard restoration through `https://127.0.0.1:443`
- authenticates using the existing operator-supplied private `GRAFANA_ADMIN_PASSWORD_FILE`
- runs the independent dashboard verifier immediately after restore
- uses Python `-B` for both dashboard commands so runtime execution does not create `__pycache__` artifacts inside the repository
- no longer reports dashboard resources as requiring a separate restore step

The installer deliberately does not pass `--replace`.

Runtime restore policy is therefore fail-closed:

- missing captured dashboard -> create it
- exact existing captured dashboard -> leave unchanged
- divergent existing dashboard -> fail rather than replace automatically

The clean-machine runtime installer was not executed against the working reference collector.

### Runtime ordering

The validated installer order is:

1. start normal HTTPS Grafana
2. verify Grafana HTTPS health
3. verify both ClickHouse datasources
4. restore the four captured dashboard resources
5. independently verify the four dashboard resources
6. continue to the SSH reload policy and final runtime-install completion

### Validation evidence

Completed validation includes:

- `grafana_dashboard_wiring_patch=PASS`
- `install_runtime_bash_syntax=PASS`
- `grafana_dashboard_script_cli=PASS`
- `grafana_dashboard_wiring_contract=PASS`
- `dashboard_restore_policy=create_or_exact_match_only`
- `dashboard_replace_automatic=no`
- `dashboard_python_no_bytecode_patch=PASS`
- `grafana_dashboard_runtime_invocation_contract=PASS`
- `python_bytecode_artifacts=absent`
- `GRAFANA_DASHBOARD_WIRING_FINAL_VALIDATION=PASS`
- `grafana_dashboard_checkpoint_contract=PASS`
- `current_state_single_next=PASS`
- `PUBLIC REPO GATE: PASS`
- `cached_diff_check=PASS`

The previously completed Grafana API proofs remain the behavioral basis for this integration:

- `GRAFANA_UNIFIED_RESOURCE_ROUND_TRIP=PASS`
- `GRAFANA_DRYRUN_RESTORE_PROOF=PASS`
- `GRAFANA_DASHBOARD_VERIFY=PASS`
- `GRAFANA_DASHBOARD_RESTORE_DRYRUN=PASS`
- `GRAFANA_DASHBOARD_LIVE_NONDESTRUCTIVE_TEST=PASS`

### Correction discovered during implementation

The first wiring validation invoked the Python dashboard scripts with `--help`, which generated an untracked `__pycache__` directory.

The modified installer was automatically rolled back, the generated cache was removed, and the repository was verified clean before retrying.

The integration was then reapplied with bytecode generation disabled during validation. The final runtime implementation was also changed from plain `python3` to `python3 -B` for both dashboard commands so a real clean-machine installer run will not write Python bytecode caches into the repository checkout.

### Git checkpoint

Implementation commit:

`ca8e3ec8c07a9162d1213f680b3ac72eeef57de3` — `Wire Grafana dashboard restore into runtime installer`

`origin/main` was explicitly verified to match that commit before this journal entry was created.

The implementation checkpoint also advanced `docs/CURRENT_STATE.md`:

- item 6 is now `DONE`
- item 7 is the single `NEXT` item

### Next action

Add package-install no-autostart protection so package installation cannot transiently start unconfigured collector services before the clean-machine runtime configuration is applied.

Do not proceed to installer structural/public-safety validation until the package no-autostart sub-section itself is completed, validated, journaled, and pushed.

## 2026-08-22 19:05 PDT - Package no-autostart intermediate recovery checkpoint

### Status

`IN PROGRESS` — this is an intermediate recovery checkpoint, not completion of the package no-autostart sub-section.

`docs/CURRENT_STATE.md` item 7 remains the single `NEXT` item.

### Goal

Prevent package installation or an intervening reboot from exposing unconfigured collector services before the clean-machine runtime installer intentionally starts them.

### Package maintainer-script audit

The installed Debian package scripts were inspected before implementation.

Observed behavior:

- OpenSSH service start/restart actions use Debian policy-aware helpers including `invoke-rc.d` and `deb-systemd-invoke`
- Vector restart uses `deb-systemd-invoke`
- ClickHouse directly runs `systemctl enable clickhouse-server` but does not directly start the service in the reviewed post-install path
- Grafana does not start on a fresh installation; its direct `systemctl restart grafana-server` path applies to upgrades
- the current package installer previously stopped Vector and Grafana only after package installation, leaving a possible transient-start/reboot exposure window

No package installation or production service mutation was performed during this audit.

### Current implementation

`components/collector/install/install-packages.sh` now establishes two layers of protection:

1. a temporary `/usr/sbin/policy-rc.d` returning status 101 during package transactions
2. persistent systemd condition drop-ins using:

`ConditionPathExists=/run/collector-rebuild/runtime-service-start-authorized`

Persistent guards are installed for:

- `vector.service`
- `clickhouse-server.service`
- `grafana-server.service`

SSH handling preserves the management plane:

- if SSH was already active before package installation, the existing management plane is preserved
- if SSH was inactive, guards are installed for `ssh.service` and `ssh.socket`

The package installer verifies guarded collector services remain inactive and removes its temporary `policy-rc.d` before successful completion.

### Runtime release design

`components/collector/install/install-runtime.sh` now understands and validates the package-installed guard contract.

For services that must start before final activation, the runtime installer uses a short-lived authorization token while leaving the persistent guard installed:

- ClickHouse receives a temporary authorized start for schema/bootstrap work
- an initially inactive SSH management plane is started only after transport configuration and `sshd -t` validation
- Grafana receives a temporary authorized start only after the loopback bootstrap override has been installed

The authorization token is removed immediately after each authorized start and is also covered by the runtime installer's `EXIT` cleanup.

Collector service guards for Vector, ClickHouse, and Grafana are permanently removed only at the final service-activation boundary.

### Failure-path corrections

The first structural implementation exposed two important failure-path issues before publication:

1. an initially inactive SSH installation would have had its guards removed without actually starting the configured SSH service
2. the Grafana guard would have been permanently removed for bootstrap, so a later bootstrap failure followed by reboot could have allowed an unintended unguarded start

The runtime design was changed to use temporary authorization while retaining persistent guards.

A subsequent validation attempt reported:

`FAIL: ClickHouse authorized start ordering changed`

That was a validator bug, not an implementation-ordering failure. The validator matched the earlier required-artifact reference to `bootstrap-transport.sh` rather than the later executable invocation. The failed hardening patch was rolled back automatically.

The patch was reapplied with the validator anchored to the executable transport section and then passed.

### Validation evidence at this checkpoint

Passed:

- `package_no_autostart_preconditions=PASS`
- `package_no_autostart_patch=PASS`
- `package_installer_bash_syntax=PASS`
- `runtime_installer_bash_syntax=PASS`
- `package_no_autostart_structural_contract=PASS`
- `package_policy_rc_d=temporary`
- `collector_service_guards=persistent_until_runtime_release`
- `ssh_policy=preserve_existing_management_plane`
- `package_no_autostart_failure_path_patch=PASS`
- `package_no_autostart_failure_safe_contract=PASS`
- `validator_transport_anchor=executable_invocation`
- `clickhouse_bootstrap=temporary_authorization_guard_retained`
- `grafana_bootstrap=temporary_authorization_guard_retained`
- `inactive_ssh=start_after_transport_then_release`
- `active_ssh=preserved_without_forced_reload`
- `collector_guard_release=final_activation`
- `authorization_token_exit_cleanup=PASS`
- `git_diff_check=PASS`
- `modified_file_scope=PASS`
- `PACKAGE_NO_AUTOSTART_FAILURE_PATH_VALIDATION=PASS`

### Safety boundary

Neither clean-machine installer has been executed against the working reference collector.

No collector service, systemd unit, package, package policy file, or live configuration was changed by this implementation work.

### Remaining work in this sub-section

Before item 7 can be marked `DONE`:

1. behaviorally prove the systemd `ConditionPathExists` hold-and-temporary-authorization mechanism with a synthetic temporary unit
2. review any findings from that proof
3. run the final package no-autostart implementation/documentation/public-safety checkpoint
4. update `docs/CURRENT_STATE.md` only after the sub-section is fully validated
5. append and push the completion journal entry

### Continuity policy update

For long, risk-heavy, or multi-step work, meaningful validated intermediate states will now be committed and pushed more frequently.

Intermediate journal entries will also be used when they preserve non-obvious decisions, corrections, or exact recovery state.

This supplements rather than replaces the existing journal-after-each-completed-subsection rule.

### Next action

Run a non-destructive behavioral proof of the systemd condition-guard and temporary authorization mechanism using a synthetic temporary unit. Do not touch collector services during that proof.

## 2026-08-22 19:09 PDT - Package no-autostart synthetic behavior proof passed

### Status

`IN PROGRESS` — package no-autostart implementation has now passed its synthetic systemd behavioral proof, but the overall sub-section is not yet marked complete.

`docs/CURRENT_STATE.md` item 7 remains the single `NEXT` item until the final implementation/documentation/public-safety checkpoint is completed.

### Behavioral proof goal

Validate the systemd `ConditionPathExists` hold-and-temporary-authorization mechanism used by the package/runtime installer design without starting, stopping, restarting, enabling, or disabling any real collector service.

### Proof method

A synthetic temporary oneshot systemd unit was created entirely under `/run`.

The synthetic unit used the same behavioral contract as the collector package guards:

`ConditionPathExists=/run/collector-rebuild-no-autostart-proof/runtime-service-start-authorized`

The proof did not execute either clean-machine installer.

### Test results

#### Guard without authorization

Starting the synthetic service without the authorization token:

- did not execute the service payload
- left the unit inactive
- produced `ConditionResult=no`

Result:

`SYSTEMD_GUARD_BLOCK=PASS`

#### Temporary authorization

Creating the temporary authorization token and starting the synthetic service:

- allowed the service payload to execute
- allowed the service to become active
- produced `ConditionResult=yes`

The token was then removed while the service remained active.

Result:

`SYSTEMD_TEMPORARY_AUTHORIZATION=PASS`

#### Guard reassertion

With the persistent guard still installed and the authorization token removed, a subsequent restart attempt:

- did not execute the service payload
- returned the unit to inactive state
- re-evaluated the condition as false

Result:

`SYSTEMD_GUARD_REASSERTION=PASS`

This proves that temporary authorization does not permanently bypass the persistent hold.

#### Permanent release

After removing the synthetic condition drop-in and reloading systemd:

- the service started normally
- the service payload executed
- no authorization token was required

Result:

`SYSTEMD_FINAL_RELEASE=PASS`

### Cleanup proof

All synthetic artifacts were removed after the test:

- temporary unit
- temporary condition drop-in
- proof authorization token
- proof execution marker
- proof runtime directory

Result:

`synthetic_artifact_cleanup=PASS`

The real collector authorization-token path remained absent.

### Working collector safety proof

Before the synthetic test, active/enabled state was captured for:

- `ssh.service`
- `ssh.socket`
- `vector.service`
- `clickhouse-server.service`
- `grafana-server.service`

The same state was checked afterward.

No active or enabled state changed for any real collector unit.

Result:

`collector_service_state_unchanged=PASS`

### Final behavioral validation

Passed:

- `live_service_state_captured=PASS`
- `synthetic_guard_installed=PASS`
- `SYSTEMD_GUARD_BLOCK=PASS`
- `SYSTEMD_TEMPORARY_AUTHORIZATION=PASS`
- `SYSTEMD_GUARD_REASSERTION=PASS`
- `SYSTEMD_FINAL_RELEASE=PASS`
- `synthetic_artifact_cleanup=PASS`
- `collector_service_state_unchanged=PASS`
- `SYSTEMD_NO_AUTOSTART_BEHAVIOR_PROOF=PASS`
- `repository_unchanged=PASS`
- `PACKAGE_NO_AUTOSTART_SYNTHETIC_PROOF=PASS`

### Implementation checkpoint

The implementation under test is already published at:

`2f40156af9b610cddf552ae83753db9973cdc369` — `Checkpoint package no-autostart hardening`

That checkpoint contains the package/runtime implementation, ADR-013, and the earlier in-progress recovery journal entry.

### Next action

Run the final package no-autostart sub-section checkpoint:

1. perform final installer structural and failure-path validation
2. update durable collector documentation and `docs/CURRENT_STATE.md`
3. move item 7 to `DONE`
4. make item 8 the single `NEXT` item
5. run the public repository gate
6. commit and push the completed implementation/documentation state
7. append and push the completion journal entry before beginning item 8

## 2026-08-22 19:14 PDT - Package no-autostart protection completed

### Goal

Prevent package installation, package maintainer scripts, or an intervening reboot from exposing unconfigured collector services before the clean-machine runtime installer has deliberately applied and validated their configuration.

### Package behavior audited before implementation

The installed Debian package maintainer scripts were inspected before choosing the protection mechanism.

Observed service behavior included:

- OpenSSH start/restart actions through policy-aware Debian helpers
- Vector restart through `deb-systemd-invoke`
- ClickHouse directly enabling `clickhouse-server` without a direct reviewed post-install start
- Grafana not starting on fresh installation, with its direct `systemctl restart grafana-server` path applying to upgrades

This established that `policy-rc.d` alone was not a sufficient reboot-safe boundary because package enablement can still occur independently of service-start policy.

### Completed package-install design

`components/collector/install/install-packages.sh` now establishes two protection layers before apt package transactions begin.

First, it installs a temporary `/usr/sbin/policy-rc.d` that returns status 101 so Debian policy-aware maintainer scripts cannot start or restart services during package installation.

Second, it installs persistent systemd condition guards using:

`ConditionPathExists=/run/collector-rebuild/runtime-service-start-authorized`

Persistent guards are installed for:

- `vector.service`
- `clickhouse-server.service`
- `grafana-server.service`

SSH behavior is management-plane aware:

- if SSH is already active, the existing management path is preserved rather than deliberately interrupted
- if SSH is initially inactive, guards are installed for `ssh.service` and `ssh.socket`

Package completion verifies the guarded collector services remain inactive and removes the temporary managed `policy-rc.d`.

The prior post-install strategy of merely stopping Vector and Grafana after package installation is no longer used.

### Completed runtime-release design

`components/collector/install/install-runtime.sh` validates the package-installed guard contract before releasing or temporarily authorizing guarded services.

Services required before final activation use a short-lived authorization token while retaining their persistent guard:

- ClickHouse receives a temporary authorized start for schema/bootstrap work
- initially inactive SSH is started only after transport configuration and `sshd -t` validation
- Grafana receives a temporary authorized start only after the loopback administrator-bootstrap override is installed

The authorization token is removed immediately after the intentional start and is also removed through installer `EXIT` cleanup.

Vector, ClickHouse, and Grafana persistent guards are permanently removed only at the final configured-service activation boundary.

### Failure-path corrections

The first structural implementation exposed two real failure-path issues before checkpoint publication:

1. an initially inactive SSH installation would have had its guards removed without actually starting the newly configured SSH service
2. the Grafana guard would have been permanently removed for temporary administrator bootstrap, allowing a later reboot to start Grafana unguarded if bootstrap failed afterward

The design was corrected to retain persistent guards and use temporary authorization for deliberate bootstrap starts.

A later validation attempt reported:

`FAIL: ClickHouse authorized start ordering changed`

That failure was caused by the validator selecting the first textual reference to `bootstrap-transport.sh` from the required-artifact section instead of the later executable invocation.

The failed hardening patch rolled back automatically. The validator was corrected to anchor on the executable transport section, the patch was reapplied, and validation passed.

The first completion-documentation attempt also failed safely with:

`FAIL: continuity rule anchor count=0, expected=1`

The implementation was unaffected. The documentation rollback succeeded.

The cause was an exact-text replacement anchor that assumed a trailing newline at the end of `docs/CURRENT_STATE.md`. The file ended directly after the continuity-rule sentence. The retry used an EOF-safe anchor and passed.

### Synthetic behavioral proof

The systemd protection mechanism was tested with a synthetic temporary unit under `/run`; no real collector service was started, stopped, restarted, enabled, or disabled by the proof.

The synthetic proof established:

- no authorization token -> service payload does not execute
- condition evaluates false and service remains inactive
- temporary authorization token -> deliberate start succeeds
- token removal does not terminate the already-authorized running instance
- a later restart with the guard retained and token absent is blocked again
- permanent guard removal restores normal start behavior
- all synthetic artifacts are removed afterward

Before and after the proof, active/enabled state was compared for:

- `ssh.service`
- `ssh.socket`
- `vector.service`
- `clickhouse-server.service`
- `grafana-server.service`

All real collector unit states were unchanged.

### Validation evidence

Completed implementation and structural validation includes:

- `package_no_autostart_patch=PASS`
- `package_installer_bash_syntax=PASS`
- `runtime_installer_bash_syntax=PASS`
- `package_no_autostart_structural_contract=PASS`
- `package_no_autostart_failure_path_patch=PASS`
- `package_no_autostart_failure_safe_contract=PASS`
- `validator_transport_anchor=executable_invocation`
- `clickhouse_bootstrap=temporary_authorization_guard_retained`
- `grafana_bootstrap=temporary_authorization_guard_retained`
- `inactive_ssh=start_after_transport_then_release`
- `active_ssh=preserved_without_forced_reload`
- `collector_guard_release=final_activation`
- `authorization_token_exit_cleanup=PASS`
- `PACKAGE_NO_AUTOSTART_FAILURE_PATH_VALIDATION=PASS`

Synthetic behavioral validation includes:

- `SYSTEMD_GUARD_BLOCK=PASS`
- `SYSTEMD_TEMPORARY_AUTHORIZATION=PASS`
- `SYSTEMD_GUARD_REASSERTION=PASS`
- `SYSTEMD_FINAL_RELEASE=PASS`
- `synthetic_artifact_cleanup=PASS`
- `collector_service_state_unchanged=PASS`
- `SYSTEMD_NO_AUTOSTART_BEHAVIOR_PROOF=PASS`
- `PACKAGE_NO_AUTOSTART_SYNTHETIC_PROOF=PASS`

Final completion validation includes:

- `package_no_autostart_final_structural_contract=PASS`
- `policy_guard_before_apt=PASS`
- `persistent_guards_before_apt=PASS`
- `temporary_authorization_ordering=PASS`
- `final_guard_release_boundary=PASS`
- `authorization_token_cleanup=PASS`
- `package_no_autostart_completion_documentation_contract=PASS`
- `current_state_single_next=PASS`
- `PUBLIC REPO GATE: PASS`
- `cached_diff_check=PASS`
- `PACKAGE_NO_AUTOSTART_COMPLETION_CHECKPOINT=PASS`

### Durable Git checkpoints

Intermediate implementation/recovery checkpoint:

`2f40156af9b610cddf552ae83753db9973cdc369` — `Checkpoint package no-autostart hardening`

Synthetic behavioral-proof journal checkpoint:

`c9cbd10269b91b83995e3e3659268ebe963f9470` — `Journal package no-autostart behavior proof`

Completed implementation/documentation checkpoint:

`887502ab8d8f7971367eded96e736ed6f57a804d` — `Complete package no-autostart protection`

`origin/main` was explicitly verified to match the completion checkpoint before this completion journal entry was created.

### Safety boundary

Neither clean-machine installer was executed against the working reference collector.

The systemd behavioral proof used only a synthetic temporary service. The working collector's real service states remained unchanged.

### Execution-state transition

`docs/CURRENT_STATE.md` now records:

- item 7: `DONE`
- item 8: the single `NEXT`

### Next action

Begin item 8 only after this completion journal entry is committed, pushed, and verified remotely:

re-run the collector installer structural, credential-exposure, and public-safety validation.

Do not begin final collector README/operator rebuild documentation until item 8 itself is completed, validated, journaled, and pushed.

## 2026-08-22 19:18 PDT - Item 8 clean-package-installer guard correction

### Status

`IN PROGRESS` — this is an intermediate item-8 validation/correction checkpoint.

`docs/CURRENT_STATE.md` item 8 remains the single `NEXT` item.

### Item 8 goal

Re-run collector installer structural, credential-exposure, and public-safety validation before final operator/rebuild documentation.

### Finding

The first item-8 structural review found that:

- `install-runtime.sh` already required explicit operator acknowledgement with `CLEAN_INSTALL_CONFIRM=YES-CLEAN-COLLECTOR`
- `install-packages.sh` did not have the equivalent clean-machine acknowledgement guard

This created an avoidable accidental-execution risk because the package installer can perform apt transactions, install temporary package policy, and install systemd no-autostart guards.

### Correction

`components/collector/install/install-packages.sh` now requires:

`CLEAN_INSTALL_CONFIRM=YES-CLEAN-COLLECTOR`

The check occurs immediately after root validation and before:

- temporary package-install state is created
- `/usr/sbin/policy-rc.d` can be installed
- persistent systemd package guards can be installed
- apt metadata or package transactions can begin

The runtime and package installers therefore use the same explicit clean-machine acknowledgement contract.

### Validation evidence

Passed:

- `package_clean_install_guard_preconditions=PASS`
- `package_clean_install_guard_patch=PASS`
- `package_installer_bash_syntax=PASS`
- `package_clean_install_guard_contract=PASS`
- `guard_before_temp_state=PASS`
- `guard_before_policy_rc_d=PASS`
- `guard_before_apt=PASS`
- `clean_install_confirmation_parity=PASS`
- `current_state_item8_still_next=PASS`
- `git_diff_check=PASS`
- `modified_file_scope=PASS`
- `checkpoint_file_scope=PASS`
- `PUBLIC REPO GATE: PASS`
- `cached_diff_check=PASS`
- `PACKAGE_CLEAN_INSTALL_GUARD_CHECKPOINT=PASS`

### Git checkpoint

Implementation correction:

`545922abe50099a9ee2e322304cd3b9dacc61836` — `Guard collector package installer against accidental use`

`origin/main` was independently verified to match this commit before this journal checkpoint.

### Safety boundary

The package installer was not executed.

No apt transaction, systemd mutation, service change, package-policy change, or live collector configuration change occurred during this correction.

### Next action

Continue item 8 from this durable checkpoint with the broader installer validation, including:

1. shell/Python syntax and static structural contracts
2. secret and credential-flow review
3. command-line exposure review
4. environment/private-file input validation
5. clean-machine versus reference-system safety boundaries
6. tracked-file/public repository sanitation
7. staged/tracked restricted-term and secret scanning
8. consistency between installer behavior and durable documentation

Item 8 must remain `NEXT` until the complete validation sub-section passes, is documented, committed, pushed, journaled, and remotely verified.

## 2026-08-22 19:23 PDT - Item 8 renderer credential handling hardened

### Status

`IN PROGRESS` — this is an intermediate item-8 credential-exposure validation/correction checkpoint.

`docs/CURRENT_STATE.md` item 8 remains the single `NEXT` item.

### Audit finding

A synthetic credential-handling audit was run against the published configuration renderer using only temporary synthetic passwords and output directories.

Before correction, direct invocation of `render-configs.py` under `umask 022` showed two credential-safety defects.

First:

`renderer_accepts_group_world_readable_password_files=yes`

The renderer accepted password source files with mode `0644`. The enclosing runtime installer already rejected group/world-readable password files, but the renderer is a separately published and directly invokable tool and did not independently enforce that contract.

Second, an intentional failure after the ClickHouse credential SQL had been rendered showed:

- `partial_clickhouse_secret_output_mode=644`
- `partial_output_contains_synthetic_credentials=yes`
- `partial_secret_output_private=no`

Successful rendering eventually changed the secret-bearing output files to `0600`, but the chmod occurred only after all render stages completed. Therefore a mid-render failure could leave an already-created credential-bearing file permissively readable.

### Correction

`components/collector/install/render-configs.py` was hardened so credential safety no longer depends on the caller's umask or on successful completion of all rendering stages.

Secret input handling now:

- opens the password source directly
- uses `fstat` on the opened descriptor
- requires a regular file
- rejects any group/world permission bits
- reads through the same opened descriptor after validation

Secret-bearing rendered output now uses a dedicated private-write helper that:

- opens/creates the destination with mode `0600`
- explicitly applies `fchmod(0600)` before content is written
- writes through that already-private descriptor

This is used for:

- `40-access-control.sql`
- `clickhouse-datasources.yaml`

The former end-of-run chmod dependency for those credential-bearing files was removed.

### Regression proof

With synthetic password files intentionally set to mode `0644`:

- `permissive_password_files_rejected=yes`
- `secret_output_written_after_input_rejection=no`
- `RENDERER_PRIVATE_INPUT_REGRESSION=PASS`

With private input files and an intentional mid-render failure under `umask 022`:

- `partial_output_contains_synthetic_credentials=yes`
- `partial_clickhouse_secret_output_mode=600`
- `partial_secret_output_private=yes`
- `RENDERER_FAILURE_PATH_PRIVATE_OUTPUT=PASS`

A complete successful render under `umask 022` also verified:

- `successful_clickhouse_secret_output_mode=600`
- `successful_grafana_secret_output_mode=600`
- `successful_certbot_hook_mode=700`
- `RENDERER_SUCCESS_OUTPUT_MODES=PASS`

Synthetic credential artifacts were deleted after validation.

### Additional validation

Passed:

- `renderer_credential_hardening_patch=PASS`
- `renderer_python_syntax=PASS`
- `renderer_private_input_contract=PASS`
- `renderer_private_output_contract=PASS`
- `late_secret_chmod_dependency=absent`
- `synthetic_credential_artifacts_removed=PASS`
- `current_state_item8_still_next=PASS`
- `git_diff_check=PASS`
- `modified_file_scope=PASS`
- `checkpoint_file_scope=PASS`
- `PUBLIC REPO GATE: PASS`
- `cached_diff_check=PASS`
- `RENDERER_CREDENTIAL_HARDENING_CHECKPOINT=PASS`

### Git checkpoint

Renderer credential-hardening implementation:

`1babbedf1efe42e5816b4cc1882a1d953c05303d` — `Harden collector renderer credential handling`

`origin/main` was independently verified to point to this commit before this journal checkpoint.

### Safety boundary

The audit used only synthetic credentials and temporary files.

Neither clean-machine installer was executed.

No production password file was read, copied, modified, or published.

No package, service, systemd unit, production configuration, or collector runtime state was changed.

### Next action

Continue item 8 with the next bounded credential-exposure validation slice:

- inspect every clean-machine installer/tool invocation for credential material placed directly in process arguments, environment values, temporary files, rendered files, logs, or command output
- distinguish secret file paths from secret contents
- verify generated private files are private from creation through failure cleanup
- identify any remaining independently invokable helper that relies only on a parent installer's safety checks

Checkpoint and journal any material correction before proceeding further.

Item 8 remains `NEXT` until the complete installer structural, credential-exposure, and public-safety validation sub-section is finished and journaled.

## 2026-08-22 19:51 PDT - Item 8 runtime verifier credential handling hardened

### Status

`IN PROGRESS` — intermediate item-8 credential-exposure validation/correction checkpoint.

`docs/CURRENT_STATE.md` item 8 remains the single `NEXT` item.

### Credential-flow audit validator correction

The first item-8C credential-flow audit stopped with:

`FAIL: runtime references raw secret-like shell variable(s): CLICKHOUSE_DEFAULT_PASSWORD, GRAFANA_ADMIN_PASSWORD, GRAFANA_READER_PASSWORD, VECTOR_INGEST_PASSWORD`

That result was a validator defect, not a credential leak.

The scanner's regular expression matched prefixes inside complete variables ending in `_PASSWORD_FILE`, incorrectly classifying file-path variables such as `CLICKHOUSE_DEFAULT_PASSWORD_FILE` as raw password variables.

The repository remained unchanged.

The corrected scanner parsed complete shell variable references before classification.

### Corrected credential-flow audit

The corrected audit identified the runtime installer secret-like variable set as:

`CLICKHOUSE_DEFAULT_PASSWORD_FILE,GRAFANA_ADMIN_PASSWORD_FILE,GRAFANA_READER_PASSWORD_FILE,VECTOR_INGEST_PASSWORD_FILE`

Validation showed:

- `runtime_raw_secret_shell_variables=absent`
- `runtime_password_file_variable_set=PASS`
- `runtime_password_inputs=file_backed_private=PASS`
- `runtime_secret_content_in_argv=absent`
- `grafana_admin_password_transport=stdin`
- `dashboard_admin_password_transport=file_path`
- `clickhouse_admin_password_transport=private_config_file`
- `RUNTIME_PROCESS_ARGUMENT_CREDENTIAL_CONTRACT=PASS`
- `renderer_secret_inputs=file_backed_private=PASS`
- `renderer_secret_outputs=private_from_creation=PASS`
- `dashboard_password_source=private_file`
- `dashboard_credentials_in_url=forbidden`
- `dashboard_authorization=in_process_header`
- `DASHBOARD_CREDENTIAL_CONTRACT=PASS`
- `vector_clickhouse_password=secret_provider`
- `clickhouse_service_passwords=renderer_placeholders`
- `STORED_CONFIGURATION_CREDENTIAL_CONTRACT=PASS`
- `verify_runtime_secret_content_in_argv=absent`
- `verify_runtime_clickhouse_transport=config_file`
- `credential_relevant_shell_xtrace=absent`
- `direct_secret_argument_candidates=0`
- `EXECUTABLE_CREDENTIAL_EXPOSURE_SCAN=PASS`
- `COLLECTOR_CREDENTIAL_PROCESS_ARGUMENT_AUDIT=PASS`
- `ITEM8C_CREDENTIAL_EXPOSURE_AUDIT_RETRY=PASS`

### Remaining finding

The corrected audit found:

- `finding_verify_runtime_private_file_enforcement=missing`
- `verify_runtime_explicit_private_umask=missing`
- `ITEM8C_FINDING=verify_runtime_password_source_not_mode_private_enforced`

`verify-runtime.sh` accepted a ClickHouse administrator password source based only on existence and non-empty content.

Although it kept the actual password out of process arguments by using a generated ClickHouse client configuration, the independently invokable verifier did not enforce the same private source-file contract as the runtime installer.

Its generated client configuration also relied on a post-write chmod instead of being private before secret content was written.

### Correction

`components/collector/install/verify-runtime.sh` now:

- includes `require_private_file`
- rejects an empty ClickHouse password source
- rejects group/world-accessible ClickHouse password sources
- applies `umask 077`
- creates the temporary ClickHouse client configuration as root-owned mode `0600` before Python writes secret content
- continues to pass only the private configuration path to `clickhouse-client`
- no longer relies on post-write `os.chmod()` for the credential-bearing client configuration

### Static validation

Passed:

- `verify_runtime_credential_hardening_patch=PASS`
- `verify_runtime_bash_syntax=PASS`
- `verify_runtime_private_file_enforcement=PASS`
- `verify_runtime_private_umask=PASS`
- `verify_runtime_client_config_private_before_write=PASS`
- `verify_runtime_late_secret_chmod_dependency=absent`
- `verify_runtime_secret_content_in_argv=absent`
- `VERIFY_RUNTIME_CREDENTIAL_CONTRACT=PASS`

### Synthetic behavioral proof

A temporary synthetic password source was first created with mode `0644`.

The message:

`FAIL: synthetic password file must not be group/world accessible`

was the expected result of the deliberate negative test, not a failure of the overall checkpoint.

The test then confirmed:

- `permissive_password_source_rejected=yes`
- a mode `0600` synthetic password source was accepted
- `private_password_source_accepted=yes`
- a synthetic client configuration created under an intentionally permissive `umask 022` still had mode `0600`
- `synthetic_client_config_mode=600`
- `SYNTHETIC_VERIFY_RUNTIME_CREDENTIAL_BEHAVIOR=PASS`
- `synthetic_credential_artifacts_removed=PASS`

No production credential content was used by this synthetic proof.

### Additional checkpoint validation

Passed:

- `current_state_item8_still_next=PASS`
- `git_diff_check=PASS`
- `modified_file_scope=PASS`
- `checkpoint_file_scope=PASS`
- `PUBLIC REPO GATE: PASS`
- `cached_diff_check=PASS`
- `VERIFY_RUNTIME_CREDENTIAL_HARDENING_CHECKPOINT=PASS`

### Git checkpoint

Runtime verifier credential hardening:

`50390f60643f610f7ae4098f6636cac0698adcf4` — `Harden runtime verifier credential handling`

`origin/main` was independently verified to point to this exact commit before this journal checkpoint.

### Safety boundary

Neither clean-machine installer was executed.

The full runtime verifier was not executed as part of this correction.

Synthetic tests used temporary files and synthetic credential strings only.

No production password content was displayed, copied into the repository, passed on a command line, or modified.

No package, service, systemd unit, production configuration, or collector runtime state was changed.

### Next action

Continue item 8 by rerunning the corrected credential/process-argument audit against the hardened verifier.

The expected result is that the prior verifier finding disappears while all existing credential-transport and public-repository checks continue to pass.

After that, continue the remaining installer structural and public-safety validation slices.

Checkpoint and journal any additional material finding/correction before proceeding.

Item 8 remains `NEXT` until the complete structural, credential-exposure, and public-safety validation sub-section is completed, documented, pushed, journaled, and remotely verified.

## 2026-08-22 19:54 PDT - Item 8 credential-exposure audit closed

### Status

`DONE` for the credential-exposure portion of item 8.

Item 8 as a whole remains `IN PROGRESS` and remains the single `NEXT` item because installer structural and public-safety validation still remain.

### Final closure audit

The credential/process-argument audit was rerun after hardening `verify-runtime.sh`.

The final audit confirmed:

- `runtime_raw_secret_shell_variables=absent`
- `runtime_password_file_variable_set=PASS`
- `runtime_password_inputs=file_backed_private=PASS`
- `runtime_secret_content_in_argv=absent`
- `grafana_admin_password_transport=stdin`
- `dashboard_admin_password_transport=file_path`
- `clickhouse_admin_password_transport=private_config_file`
- `RUNTIME_PROCESS_ARGUMENT_CREDENTIAL_CONTRACT=PASS`

Renderer handling remained correct:

- `renderer_secret_inputs=file_backed_private=PASS`
- `renderer_secret_outputs=private_from_creation=PASS`

Grafana dashboard tooling remained correct:

- `dashboard_password_source=private_file`
- `dashboard_credentials_in_url=forbidden`
- `dashboard_authorization=in_process_header`
- `DASHBOARD_CREDENTIAL_CONTRACT=PASS`

Stored configuration handling remained correct:

- `vector_clickhouse_password=secret_provider`
- `clickhouse_service_passwords=renderer_placeholders`
- `STORED_CONFIGURATION_CREDENTIAL_CONTRACT=PASS`

The hardened independent runtime verifier confirmed:

- `finding_verify_runtime_private_file_enforcement=present`
- `verify_runtime_explicit_private_umask=present`
- `verify_runtime_client_config_private_before_write=PASS`
- `verify_runtime_secret_content_in_argv=absent`
- `VERIFY_RUNTIME_CREDENTIAL_CONTRACT=PASS`

Repository-wide executable scanning confirmed:

- `credential_relevant_shell_xtrace=absent`
- `direct_secret_argument_candidates=0`
- `EXECUTABLE_CREDENTIAL_EXPOSURE_SCAN=PASS`

Final classification:

- `ITEM8C_FINDING=none`
- `COLLECTOR_CREDENTIAL_PROCESS_ARGUMENT_AUDIT=PASS`
- `ITEM8C_CREDENTIAL_EXPOSURE_CLOSED=PASS`
- `PUBLIC REPO GATE: PASS`
- `current_state_item8_still_next=PASS`
- `repository_unchanged=PASS`
- `ITEM8C_FINAL_AUDIT=PASS`

### Findings corrected during this validation slice

Three credential/safety issues were found and corrected during item 8 so far.

1. `install-packages.sh` lacked the explicit clean-machine acknowledgement guard used by the runtime installer.

   Corrected at:

   `545922abe50099a9ee2e322304cd3b9dacc61836`

2. `render-configs.py` accepted permissively readable password source files and could leave a secret-bearing partial output at mode `0644` after mid-render failure.

   Corrected at:

   `1babbedf1efe42e5816b4cc1882a1d953c05303d`

3. `verify-runtime.sh` did not independently enforce a private ClickHouse password source and created its secret-bearing client configuration before applying its final private mode.

   Corrected at:

   `50390f60643f610f7ae4098f6636cac0698adcf4`

### Audit-tool correction

The first credential scanner incorrectly matched prefixes of variables ending in `_PASSWORD_FILE` and reported those file-path variables as raw password variables.

The validator was corrected to classify complete shell variable names.

The corrected audit demonstrated that the runtime installer uses only password-file variables rather than shell variables containing password contents.

### Safety boundary

No clean-machine installer was executed during the credential-exposure audit.

The final closure audit was static/read-only.

Synthetic credential behavioral tests used only temporary synthetic data.

No production credential contents were printed, committed, or passed directly through process arguments.

### Next action

Continue item 8 with the remaining installer structural and public-safety validation.

The next validation slice should concentrate on:

- installer/helper dependency completeness
- clean-machine execution ordering and fail-closed assumptions
- placeholder and operator-input completeness
- executable/configuration artifact consistency
- tracked-file sanitation and forbidden environment identifiers
- validation that public rebuild artifacts contain no production-derived identity material

Item 8 must remain `NEXT` until those remaining checks pass and the complete item-8 result is documented and published.

## 2026-08-22 20:06 PDT - Item 8 runtime dependency contract hardened

### Status

`IN PROGRESS` — intermediate item-8 structural/rebuild-dependency correction checkpoint.

The credential-exposure portion of item 8 remains closed.

Item 8 as a whole remains the single `NEXT` item because additional structural and public-safety validation remains.

### External dependency audit

A read-only audit enumerated externally supplied commands required by the collector runtime and transport implementation and mapped them to their Debian package providers.

The audit confirmed these relevant providers on the Debian 13 reference collector:

- `sqlite3` -> package `sqlite3`
- `ss` -> package `iproute2`
- `runuser` -> package `util-linux`
- `setfacl` / `getfacl` -> package `acl`
- `sshd` -> package `openssh-server`
- `mount` -> package `mount`
- `findmnt` -> package `util-linux`
- account-management commands -> package `passwd`
- standard file/text utilities -> required or essential Debian packages

The package installer already explicitly installed `acl` and `openssh-server`.

The audit found:

- `sqlite3_not_explicitly_installed`
- `iproute2_not_explicitly_installed`
- `sqlite3_not_package_verified`
- `ss_not_package_verified`

Both missing packages are required by published runtime behavior:

- `install-runtime.sh` invokes the `sqlite3` CLI for Grafana database integrity and administrator checks
- Grafana bootstrap listener validation uses `ss`, supplied by `iproute2`

### Package-verifier execution-context finding

The first attempted dependency patch correctly added the dependency checks, but its read-only validation invoked `verify-packages.sh` as the non-root operator account.

That verifier reported:

`FAIL: Grafana ClickHouse plugin is missing`

The patch rollback completed before any commit.

A subsequent read-only visibility audit showed that this was not plugin drift.

Observed:

- non-root plugin visibility: `no`
- root plugin existence: `yes`
- plugin ID: `grafana-clickhouse-datasource`
- plugin version: `4.20.0`
- Grafana CLI reports the same plugin at `4.20.0`

The plugin directory is intentionally not traversable by an unrelated non-root account.

Classification:

`ITEM8D_PLUGIN_VISIBILITY_FINDING=verify_packages_requires_root_context`

The repository remained unchanged after the failed attempt and audit.

### Correction

`components/collector/install/install-packages.sh` now explicitly installs:

- `iproute2`
- `sqlite3`

`components/collector/install/verify-packages.sh` now:

- explicitly requires root execution
- uses a root-style command search path
- verifies that `iproute2` is installed
- verifies that `sqlite3` is installed
- verifies that `ss` resolves
- verifies that `sqlite3` resolves
- retains the existing exact application/package version checks
- retains the existing Grafana ClickHouse plugin identity/version verification

This makes the dependency assumptions required by the runtime installer explicit rather than depending on incidental presence in a base image or another package dependency.

### Validation

Static validation passed:

- `explicit_iproute2_dependency=PASS`
- `explicit_sqlite3_dependency=PASS`
- `package_verifier_requires_root=PASS`
- `package_verifier_iproute2_contract=PASS`
- `package_verifier_sqlite3_contract=PASS`
- `package_verifier_ss_command_contract=PASS`
- `runtime_dependency_usage_contract=PASS`
- `clean_install_confirmation_guard_preserved=PASS`
- `ITEM8D_DEPENDENCY_VERIFIER_STATIC_CONTRACT=PASS`

The verifier also proved fail-closed outside its required execution context:

- `package_verifier_nonroot_rejected=yes`

A root-context read-only verification then confirmed:

- `dependency_package=iproute2 installed=yes`
- `dependency_package=sqlite3 installed=yes`
- `dependency_command=ss path=/usr/bin/ss`
- `dependency_command=sqlite3 path=/usr/bin/sqlite3`
- Vector `0.57.0-1`
- ClickHouse server/client `26.3.17.110`
- Grafana `13.1.1`
- Certbot `5.7.0`
- Grafana ClickHouse plugin `4.20.0`
- `COLLECTOR_PACKAGE_VERIFY=PASS`
- `package_verifier_root_context=PASS`

Additional validation passed:

- `clean_machine_package_installer_executed=no`
- `current_state_item8_still_next=PASS`
- `git_diff_check=PASS`
- `modified_file_scope=PASS`
- `checkpoint_file_scope=PASS`
- `PUBLIC REPO GATE: PASS`
- `cached_diff_check=PASS`
- `ITEM8D_RUNTIME_DEPENDENCY_CHECKPOINT=PASS`

### Git checkpoint

Runtime dependency implementation:

`524b962002fed7c42bfcbad7048ad9aa69293a70` — `Declare collector runtime dependencies`

The public `main` branch was independently verified to point to this exact commit before this journal checkpoint.

### Safety boundary

The clean-machine package installer was not executed against the working collector.

Package/version verification was read-only.

No package was installed, removed, upgraded, or downgraded during this validation.

No service state, production configuration, credential, firewall state, or runtime database was modified.

### Next action

Continue item 8 with the remaining structural/public-safety validation.

The next bounded slice should validate:

- every runtime-installed repository artifact is present and correctly referenced
- installer execution ordering remains fail-closed
- required operator inputs are complete and validated before destructive/runtime mutation
- generated/rendered configuration dependencies are complete
- clean-machine versus live/reference verification boundaries remain explicit
- tracked collector content contains only public-safe placeholders and synthetic/example values where environment-specific data would otherwise appear

Any material finding must be corrected, validated, pushed, and journaled before advancing.

Item 8 remains `NEXT`.

## 2026-08-22 20:16 PDT - Item 8 transport key validation hardened

### Status

`IN PROGRESS` — intermediate item-8 structural and public-safety checkpoint.

The credential-exposure and explicit runtime-dependency portions of item 8 remain closed.

Item 8 as a whole remains the single `NEXT` item because final structural/public-safety validation still remains.

### Structural preflight finding

The runtime installer requires these two operator-supplied public authorized-keys files:

- `AI_SPOOL_READER_AUTHORIZED_KEYS_FILE`
- `AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE`

Before this correction, `install-runtime.sh` required both environment variables but did not validate the files themselves before beginning persistent runtime mutation.

Detailed file validation existed only in `bootstrap-transport.sh`.

The runtime sequence starts and initializes ClickHouse and applies the observability schema before executing the transport bootstrap.

Therefore invalid, empty, missing, or accidentally supplied private-key input could fail only after earlier clean-machine runtime state had already been created.

Classification:

`authorized_keys_operator_files_validated_after_clickhouse_mutation`

### Validator corrections during discovery

Several read-only structural-audit attempts failed because of validator construction errors rather than implementation errors.

The first validator over-escaped the shell line-continuation marker while parsing the required environment-variable block and incorrectly reported that `CLICKHOUSE_DEFAULT_PASSWORD_FILE` was missing.

The next validator matched the repository-artifact reference to `bootstrap-transport.sh` rather than its later executable invocation and incorrectly classified transport bootstrap as the first runtime mutation.

A subsequent ordering validator used a Python string containing a trailing backslash in a brittle exact marker and failed to locate the ClickHouse authorized-start call.

Each of these failures left the repository unchanged.

The audits were corrected or superseded rather than weakening the implementation checks.

### Private-key detector defect

While validating the proposed early preflight with synthetic files, a separate implementation defect was discovered in the existing transport validation.

The transport script used:

`grep -aEq`

with a pattern whose first characters were:

`-----BEGIN`

Because the pattern begins with `-` and the command did not use `--` or `-e`, GNU grep interpreted the pattern as an option.

The synthetic test produced:

`grep: unrecognized option '-----BEGIN ...'`

The check appeared inside an `if` condition, so grep status `2` did not cause the script to abort under `set -e`.

The result was that the intended private-key rejection check could fail to detect supplied private-key material.

Classification:

`transport_private_key_grep_option_bug=confirmed`

### Correction

`components/collector/install/install-runtime.sh` now defines:

`require_public_authorized_keys_file()`

The helper:

- requires a regular file
- requires the file to be non-empty
- rejects private-key PEM markers
- invokes grep with the explicit option terminator `--`

Both operator-supplied authorized-keys files are validated by this helper before the first ClickHouse persistent runtime mutation.

The later validation in `bootstrap-transport.sh` remains in place as defense in depth.

`components/collector/filesystem/bootstrap-transport.sh` was also corrected from:

`grep -aEq`

to:

`grep -aEq --`

for the private-key PEM detector.

### Validation

Shell syntax passed for both modified scripts.

Static validation confirmed:

- `runtime_private_key_detector_uses_option_terminator=PASS`
- `transport_private_key_detector_uses_option_terminator=PASS`
- `unsafe_leading_hyphen_grep_form=absent`
- `runtime_authorized_keys_preflight=PASS`
- `authorized_keys_preflight_before_clickhouse_enable=PASS`
- `transport_authorized_keys_validation_preserved=PASS`
- `ITEM8E_AUTHORIZED_KEYS_STATIC_CONTRACT=PASS`

Synthetic behavior confirmed:

- synthetic public authorized-keys content did not match the private-key detector
- synthetic private-key material was detected
- an empty synthetic authorized-keys file was identified as empty
- `SYNTHETIC_PRIVATE_KEY_DETECTOR=PASS`

The remaining structural contract also passed:

- `runtime_required_artifacts_tracked=PASS`
- `transport_required_artifacts_referenced=PASS`
- `renderer_environment_export_contract=PASS`
- `renderer_outputs_consumed_by_runtime=PASS`
- `ITEM8E_PREFLIGHT_FINDING=closed`
- `ITEM8E_PRIVATE_KEY_DETECTOR_FINDING=closed`
- `ITEM8E_ARTIFACT_REFERENCE_CONTRACT=PASS`
- `ITEM8E_STRUCTURAL_PREFLIGHT_CONTRACT=PASS`

Repository/publication validation passed:

- `current_state_item8_still_next=PASS`
- `git_diff_check=PASS`
- `modified_file_scope=PASS`
- `checkpoint_file_scope=PASS`
- `PUBLIC REPO GATE: PASS`
- `cached_diff_check=PASS`

Execution safety boundary:

- `clean_machine_runtime_installer_executed=no`
- `transport_bootstrap_executed=no`

### Git checkpoint

Implementation commit:

`0e4d617be2abc09053c244d515a590127be05c15` — `Harden collector transport key validation`

The public `main` branch was independently verified to point to this exact commit before this journal checkpoint.

The independently observed commit diff contains only:

1. the `grep -aEq --` correction in `bootstrap-transport.sh`
2. the new early authorized-keys validation helper and two preflight calls in `install-runtime.sh`

### Safety boundary

No clean-machine installer or transport bootstrap was executed against the working collector.

No production authorized-keys contents were read into project output or committed.

Synthetic validation used only generated non-production test files.

No package state, service state, firewall state, production database, credential, TLS material, or runtime configuration was changed.

### Next action

Continue item 8 with the remaining public-safety and failure-cleanup validation.

The next bounded slice should inspect:

- temporary/bootstrap artifact lifetime and cleanup on failure
- configuration destination ownership and modes
- TLS private-key destination mode
- service authorization-token cleanup
- temporary Grafana bootstrap drop-in cleanup
- unsafe shell evaluation or environment interpolation
- environment-specific values and tracked production identity material
- public placeholders and synthetic/example addressing
- final collector public-repository sanitation

Any additional material finding must be corrected, validated, pushed, and journaled before item 8 is marked complete.

Item 8 remains `NEXT`.

## 2026-08-22 20:29 PDT - Item 8 collector structural and public-safety validation complete

### Status

`DONE` — execution-order item 8 is complete.

`docs/CURRENT_STATE.md` advances item 9, collector README and operator-facing clean-machine rebuild documentation, to the single `NEXT` position.

### Completed validation scope

Item 8 completed collector installer validation for:

- credential file handling
- credential process-argument exposure
- explicit runtime dependencies
- package-verifier execution context
- operator-input preflight
- authorized-keys safety
- runtime artifact-reference completeness
- renderer input/output completeness
- failure cleanup
- temporary service authorization
- Grafana bootstrap cleanup
- sensitive destination ownership/modes
- TLS private-key handling
- shell evaluation/xtrace exposure
- public identity/material scanning
- live-reference versus clean-rebuild representation differences
- public repository sanitation

### Credential and dependency closure

Credential/process-argument exposure closed with:

- `COLLECTOR_CREDENTIAL_PROCESS_ARGUMENT_AUDIT=PASS`
- `ITEM8C_CREDENTIAL_EXPOSURE_CLOSED=PASS`

Explicit rebuild dependencies now include:

- `sqlite3`
- `iproute2`, supplying `ss`

Root-context package verification passed:

- `COLLECTOR_PACKAGE_VERIFY=PASS`
- `ITEM8D_RUNTIME_DEPENDENCY_CHECKPOINT=PASS`

### Operator-input and transport-key closure

Both operator-supplied authorized-keys files are now validated before the first persistent ClickHouse mutation.

The later transport checks remain as defense in depth.

Synthetic validation discovered and corrected the existing leading-hyphen grep pattern defect.

Both detectors now use an explicit grep option terminator.

Validation passed:

- `ITEM8E_STRUCTURAL_PREFLIGHT_CONTRACT=PASS`
- `SYNTHETIC_PRIVATE_KEY_DETECTOR=PASS`

### Failure cleanup and sensitive modes

Validation confirmed:

- `umask 077` precedes private temporary artifacts
- runtime `EXIT` cleanup precedes persistent mutation
- Grafana bootstrap override is removed on success and failure
- temporary service authorization uses mode `0600`
- temporary service authorization is removed on success and failure
- runtime temporary directory is removed through `EXIT` cleanup
- Vector ClickHouse secret destination is `0400 vector:vector`
- Grafana datasource clean-rebuild destination is `0640 root:grafana`
- Grafana TLS private-key destination is `0400 grafana:grafana`
- Certbot renewal preserves the TLS ownership/mode contract
- renderer private mode is established before secret-bearing output is written
- synthetic `umask 077` file creation produced mode `0600`

### Shell-safety validator correction

The first shell-source scan produced two validator false positives.

`. "$SCRIPT_DIR/versions.env"` in `verify-packages.sh` is an intentional fixed repository-controlled input.

`source = Path(sys.argv[1])` in `verify-runtime.sh` is Python code inside an embedded heredoc, not shell sourcing.

The corrected scan excludes heredoc bodies and permits only known fixed source inputs.

Final result:

- `shell_eval_commands=absent`
- `shell_xtrace=absent`
- `shell_source_commands=tracked_fixed_inputs_only`
- `ITEM8F_SHELL_EVALUATION_SAFETY=PASS`

### Public identity validator correction

The generic IPv4-syntax scanner found two values in `REBUILD_STATUS.md`:

- `127.0.0.1`, intentional loopback-only addressing
- `26.3.17.110`, the pinned ClickHouse software version

Classification passed:

- `public_ipv4_candidate_127.0.0.1=allowed_loopback`
- `public_ipv4_candidate_26.3.17.110=software_version_not_address`
- `ITEM8F_PUBLIC_IDENTITY_FINDINGS=none`

No unapproved deployment address, non-example email address, hardcoded user home path, URL credential, or literal private-key material remained as a public identity finding.

### Grafana datasource representation

The working reference collector does not contain the clean-rebuild provisioning file at:

`/etc/grafana/provisioning/datasources/clickhouse.yaml`

That is an expected representation difference, not live drift.

The reference collector stores the two functional datasource records in Grafana's database.

Read-only validation confirmed both captured UIDs, protocols, ports, loopback host policy, `grafana_reader`, expected tables, and secure data.

Results:

- `LIVE_GRAFANA_DATASOURCE_DB_CONTRACT=PASS`
- `ITEM8F_LIVE_DATASOURCE_FINDING=expected_representation_difference`
- `ITEM8F_LIVE_REFERENCE_FINDINGS=none`
- `ITEM8F_DATASOURCE_CLASSIFICATION=PASS`

The clean-machine rebuild creates the same functional state from the captured provisioning template.

### Execution and publication safety

The public repository gate passed throughout item 8.

The final read-only audits left the repository unchanged.

No clean-machine package installer, runtime installer, or transport bootstrap was executed on the working reference collector.

No production credential, authorized-key content, certificate private key, production log data, deployment device identity, or deployment firewall policy was published.

Firewall reconstruction remains intentionally out of scope.

### Conclusion

Collector installer structural, credential-exposure, dependency, failure-cleanup, operator-input, artifact-reference, and public-safety validation is complete.

Execution-order item 8 is `DONE`.

Execution-order item 9 is the single `NEXT` item:

Finish the collector README and operator-facing clean-machine rebuild documentation.
