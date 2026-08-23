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
