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

## 2026-08-22 20:32 PDT - Item 9A collector documentation gap audit

### Status

`IN PROGRESS` — execution-order item 9 remains the single `NEXT` item.

This checkpoint records the validated gap inventory before modifying the collector README/operator runbook.

### Execution authority

`docs/CURRENT_STATE.md` was verified to contain exactly one `NEXT` item:

Item 9 — finish collector README and operator-facing clean-machine rebuild documentation.

### Installer-derived operator contract

The clean-machine runtime installer currently requires ten operator-supplied values:

- `CLICKHOUSE_DEFAULT_PASSWORD_FILE`
- `GRAFANA_READER_PASSWORD_FILE`
- `GRAFANA_ADMIN_PASSWORD_FILE`
- `VECTOR_INGEST_PASSWORD_FILE`
- `GRAFANA_PUBLIC_HOST`
- `CERT_NAME`
- `CERTBOT_EMAIL`
- `SSH_PORT`
- `AI_SPOOL_READER_AUTHORIZED_KEYS_FILE`
- `AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE`

Both package and runtime installation require:

`CLEAN_INSTALL_CONFIRM=YES-CLEAN-COLLECTOR`

Additional validated installer contract:

- clean package bootstrap expects Debian 13
- package bootstrap expects amd64
- `SSH_PORT` must be numeric, valid, and nonstandard
- `RELOAD_SSH=yes` is optional; the default is no
- default syslog listeners are UDP/514 and TCP/514
- default ClickHouse HTTP endpoint is loopback `127.0.0.1:8123`
- default ClickHouse host is loopback `127.0.0.1`
- default ClickHouse ingest user is `vector_ingest`
- package verification requires root
- runtime verification requires root

Password-bearing runtime inputs are file-backed rather than supplied as raw secret command arguments.

The runtime requires private password files to be regular, non-empty, and inaccessible to group/world permission bits.

The Grafana administrator password must be one non-empty line.

The authorized-keys source files must be regular and non-empty, and private-key PEM material is rejected.

`GRAFANA_PUBLIC_HOST` and `CERT_NAME` must describe the same IPv4 address under the currently captured certificate contract.

### README gap inventory

The read-only README coverage audit identified these missing operator-facing topics:

- Debian 13 clean-machine baseline
- explicit `CLEAN_INSTALL_CONFIRM=YES-CLEAN-COLLECTOR`
- `CLICKHOUSE_DEFAULT_PASSWORD_FILE`
- `GRAFANA_READER_PASSWORD_FILE`
- `GRAFANA_ADMIN_PASSWORD_FILE`
- `VECTOR_INGEST_PASSWORD_FILE`
- `GRAFANA_PUBLIC_HOST`
- `CERT_NAME`
- `CERTBOT_EMAIL`
- `SSH_PORT`
- `AI_SPOOL_READER_AUTHORIZED_KEYS_FILE`
- `AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE`
- optional `RELOAD_SSH`
- private password-file mode guidance
- UDP/514 syslog prerequisite
- TCP/514 syslog prerequisite
- TCP/443 Grafana prerequisite
- TCP/80 ACME standalone-validation prerequisite

The README already references:

- `install-packages.sh`
- `verify-packages.sh`
- `install-runtime.sh`
- `verify-runtime.sh`
- the clean-machine safety boundary
- `COLLECTOR_RUNTIME_VERIFY=PASS`
- firewall/nftables reconstruction being intentionally out of scope

### Stale README state

The README still describes installer/public-safety validation as remaining work even though execution-order item 8 is now complete.

Its checkpoint-oriented remaining-work sequence therefore needs to be refreshed so item 9 documentation is the active phase.

### Item 9 documentation objective

The README should become a clean-machine operator runbook that another engineer or AI can follow using:

- a clean Debian 13 amd64 collector
- this public repository
- operator-supplied environment values
- operator-supplied password files
- operator-supplied SSH public-key files

The documentation must not contain real deployment credentials, addresses, usernames, SSH keys, certificate private keys, or private deployment identity.

It should preserve the actual installer contract rather than introducing a parallel manual installation procedure.

### Planned next bounded slice

Update `components/collector/README.md` without rewriting unrelated captured architecture material.

The update should add:

- supported clean-machine baseline
- required external connectivity prerequisites
- all operator-supplied variables and their constraints
- secure preparation guidance for password/key files
- exact package-install and verification sequence
- exact runtime-install invocation pattern
- post-install runtime verification
- deferred SSH reload guidance
- explicit description of what the installer creates
- failure/retry guidance
- explicit reminder that firewall reconstruction is outside scope
- refreshed remaining-work state

Item 9 remains `NEXT` until the completed operator documentation is validated and journaled.

## 2026-08-22 20:37 PDT - Item 9B collector clean-machine operator runbook published

### Status

`IN PROGRESS` — execution-order item 9 remains the single `NEXT` item pending its final documentation closure/state transition.

The operator-facing collector README implementation is published and validated.

### Published checkpoint

Implementation commit:

`62fbb0b668efad92955ad4ab19fcdf6aecd658a0` — `Document collector clean rebuild`

Independent GitHub verification confirmed that this commit changes only:

`components/collector/README.md`

The public `main` branch was independently verified to point to the same commit before this journal checkpoint.

### Documentation added

`components/collector/README.md` now contains a clean-machine operator runbook based on the actual published installers rather than a parallel manual reconstruction procedure.

The runbook documents the supported baseline:

- clean Debian 13
- amd64
- root or sudo access
- public repository checkout
- operator-supplied environment values
- operator-supplied credential files
- no pre-existing `observability` ClickHouse database

Both package and runtime installers are documented as requiring:

`CLEAN_INSTALL_CONFIRM=YES-CLEAN-COLLECTOR`

The documentation explicitly warns that this confirmation is only an accidental-execution guard and does not make the runtime installer safe for an existing collector.

### External prerequisites

The runbook now documents required external connectivity without reconstructing deployment-specific firewall policy.

Documented inbound requirements include:

- UDP/514 for syslog
- TCP/514 for syslog
- TCP/443 for Grafana HTTPS
- TCP/80 when ACME standalone validation is required
- the operator-selected nonstandard SSH port for authorized management/GX10 transport

ClickHouse application listeners remain documented as loopback-only.

Firewall/nftables reconstruction remains explicitly out of scope.

### Operator input contract

All ten required runtime inputs are documented:

- `CLICKHOUSE_DEFAULT_PASSWORD_FILE`
- `GRAFANA_READER_PASSWORD_FILE`
- `GRAFANA_ADMIN_PASSWORD_FILE`
- `VECTOR_INGEST_PASSWORD_FILE`
- `GRAFANA_PUBLIC_HOST`
- `CERT_NAME`
- `CERTBOT_EMAIL`
- `SSH_PORT`
- `AI_SPOOL_READER_AUTHORIZED_KEYS_FILE`
- `AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE`

The runbook documents:

- private password files
- recommended root-owned mode `0600`
- one-line Grafana administrator password requirement
- public authorized-key files rather than private SSH keys
- same-IPv4 `GRAFANA_PUBLIC_HOST` / `CERT_NAME` contract
- numeric nonstandard SSH-port requirement

Optional `RELOAD_SSH=yes` behavior is documented along with the safer default of deferring the first SSH reload.

Captured defaults are documented for:

- `SYSLOG_UDP_ADDRESS`
- `SYSLOG_TCP_ADDRESS`
- `CLICKHOUSE_ENDPOINT`
- `CLICKHOUSE_HOST`
- `CLICKHOUSE_USER`

### Rebuild sequence

The runbook now provides the operator sequence for:

1. cloning the repository
2. preparing an external root-owned input directory
3. preparing private password and authorized-key source files
4. running `install-packages.sh`
5. running `verify-packages.sh`
6. setting non-secret deployment values
7. running `install-runtime.sh`
8. validating and safely reloading SSH when deferred
9. running `verify-runtime.sh`

Documented success markers include:

- `PACKAGE_NO_AUTOSTART_HOLD=PASS`
- `COLLECTOR_PACKAGE_INSTALL=PASS`
- `COLLECTOR_PACKAGE_VERIFY=PASS`
- `COLLECTOR_RUNTIME_INSTALL=PASS`
- `COLLECTOR_RUNTIME_VERIFY=PASS`

### SSH management safety

The runbook tells the operator to keep the original management connection open when SSH reload is deferred.

It documents:

- `sudo sshd -t`
- verification that network policy permits the selected nonstandard port
- `sudo systemctl reload ssh.service`
- opening and validating a second management connection before closing the original one
- validating the GX10 SFTP role access

The documentation avoids broad `sudo -E` environment forwarding.

### Failure and retry semantics

The runbook now states that the installers are fail-closed rebuild tools, not general idempotent convergence tools.

It warns against:

- manually removing package no-autostart guards to force progress
- blindly rerunning a partially completed runtime installation
- bypassing clean-install confirmation
- bypassing the existing-database refusal
- bypassing private-file validation
- bypassing authorized-key validation

For deterministic recovery after persistent runtime state has been created, it directs the operator to restore a clean-server snapshot or reprovision the clean collector, fix the identified input/environment issue, and restart the documented sequence.

### Publication validation

README validation passed:

- `readme_required_operator_inputs=10`
- `readme_operator_input_contract=PASS`
- `readme_clean_machine_baseline=PASS`
- `readme_external_connectivity_contract=PASS`
- `readme_private_input_guidance=PASS`
- `readme_package_install_sequence=PASS`
- `readme_runtime_install_sequence=PASS`
- `readme_ssh_reload_safety=PASS`
- `readme_runtime_verification_sequence=PASS`
- `readme_failure_retry_policy=PASS`
- `readme_stale_item8_execution_state=absent`
- `readme_explicit_sudo_environment_forwarding=PASS`
- `ITEM9B_README_OPERATOR_RUNBOOK_CONTRACT=PASS`

The public repository gate passed.

No package installer, runtime installer, or runtime verifier was executed during the documentation change.

### Safety boundary

No production credential, password, authorized-key content, certificate private key, private username, production device identity, or deployment-specific address was added to the README.

The runbook uses operator-supplied placeholders and public-safe instructions.

### Next action

Perform the final item-9 documentation closure check.

If the README remains consistent with the installer/verifier contracts and the public repository gate passes, mark execution-order item 9 `DONE` and advance item 10, final collector public sanitation and milestone closure, to the single `NEXT` position.

Item 9 remains `NEXT` until that state transition is committed.

## 2026-08-22 20:38 PDT - Item 9 collector operator documentation complete

### Status

`DONE` — execution-order item 9 is complete.

`docs/CURRENT_STATE.md` advances item 10, final collector public sanitation and collector milestone closure, to the single `NEXT` position.

### Published operator runbook

`components/collector/README.md` is now the validated clean-machine operator runbook for the collector.

The implementation checkpoint was:

`62fbb0b668efad92955ad4ab19fcdf6aecd658a0` — `Document collector clean rebuild`

Its journal checkpoint was:

`37e499d720a1d7e5e694d36c97ab7bbf053954db` — `Journal collector operator runbook`

### Final consistency validation

The final documentation-to-implementation check confirmed:

- exactly ten runtime operator inputs are documented
- both installers' `YES-CLEAN-COLLECTOR` safety confirmation is documented
- Debian 13 amd64 package baseline is documented
- package and runtime success markers in the README exist in the actual scripts
- private password-file and authorized-key guidance is present
- external UDP/514, TCP/514, TCP/443, TCP/80, and nonstandard SSH connectivity requirements are documented
- ClickHouse external exposure is not required; application listeners remain loopback-only
- deferred SSH reload behavior is documented
- broad `sudo -E` forwarding is not used
- failure/retry guidance preserves fail-closed clean-machine semantics

Final marker:

`ITEM9_FINAL_DOCUMENTATION_CONSISTENCY=PASS`

### Operator workflow now documented

The published runbook covers:

1. clean Debian 13 amd64 baseline
2. repository checkout
3. external private operator-input directory
4. password and SSH public-key source preparation
5. package installation
6. independent package verification
7. non-secret deployment variables
8. runtime installation
9. safe deferred SSH activation
10. independent runtime verification
11. failure/reprovision semantics

### Safety boundary

No package installer, runtime installer, transport bootstrap, or runtime verifier was executed during item 9.

No production credential, password, SSH key, certificate private key, production device identity, private username, deployment-specific address, raw production log content, or firewall policy was added to public documentation.

Firewall/nftables reconstruction remains intentionally out of scope.

### Item 9 conclusion

The collector README/operator clean-machine documentation is complete for the current captured implementation.

Execution-order item 9 is now `DONE`.

### Next action

Execution-order item 10 is now the single `NEXT` item:

Run final collector public sanitation and close the collector rebuild milestone.

The final collector sanitation step must re-check the complete tracked collector/public documentation state rather than only the files changed by item 9.

## 2026-08-22 20:56 PDT - Item 10 collector public sanitation and milestone closure

### Status

`DONE` — execution-order item 10 is complete.

Item 11 becomes the single `NEXT` item pending the operator decision on availability of a disposable clean Debian 13 amd64 validation system.

### Final sanitation

The final sanitation audit covered the current tracked repository and complete Git history reachable from public `main`.

Validated public topology:

- one public branch: `main`
- zero public tags

Current tracked state:

- `tracked_file_count=87`
- `ITEM10A_TRACKED_PATH_SANITATION=PASS`
- `ITEM10A_COLLECTOR_SYNTAX=PASS`
- public repository gate passed with five local forbidden terms

Public-main history:

- `historical_unique_blob_count=205`
- `collector_doc_history_blob_count=151`
- all sensitive-history finding counts were zero
- `ITEM10A_PUBLIC_MAIN_HISTORY_SANITATION=PASS`

Current-head validation:

- `ITEM10A_CURRENT_TRACKED_SANITATION=PASS`

Final result:

`ITEM10A_FINAL_SANITATION_AUDIT=PASS`

### Audit-tool corrections

Two read-only validator defects failed safely.

First, a zero-tag repository caused a `grep -v` pipeline to return nonzero under `set -o pipefail`.

Second, the audit initially looked for the local forbidden-term policy at repository root instead of the actual untracked path:

`components/normalizer/.public-gate-local.txt`

Both were diagnosed without repository changes before the final successful audit.

The staged closure validator also initially classified the documentation placeholder describing a home-directory path as a hardcoded identity. That closure attempt rolled back completely.

The corrected closure preserves the strict home-directory identity scanner and avoids adding such a placeholder.

### Safety boundary

No package installer, runtime installer, transport bootstrap, or runtime verifier was executed during item 10.

No clean-machine rebuild was executed.

No production credential, SSH key, certificate private key, private username, deployment-specific address, raw production log content, or deployment firewall policy was published.

### Collector milestone

The public collector rebuild-package, operator documentation, and public sanitation milestone is closed.

Clean-machine end-to-end rebuild execution remains a separate validation gate and is not represented as completed.

### Next action

Item 11 is the next execution-order gate.

If a disposable clean Debian 13 amd64 system is unavailable, item 11 may be explicitly deferred by operator decision and execution can advance to GX10 reconstruction without claiming clean-machine validation.

## 2026-08-22 20:57 PDT - Item 11 clean-machine collector validation deferred

### Status

`DEFERRED` — clean-machine collector rebuild validation remains outstanding.

The operator confirmed that no disposable clean Debian 13 amd64 system is currently available for destructive end-to-end rebuild validation.

This item is therefore deferred rather than marked complete.

Execution-order item 12, complete GX10 capture and reconstruction, becomes the single `NEXT` item.

### Collector milestone state

The public collector rebuild package remains closed for:

- implementation capture
- package/runtime reconstruction artifacts
- structural validation
- credential-exposure validation
- dependency validation
- failure-path validation
- operator documentation
- current tracked-state sanitation
- public-main history sanitation

The following claim is intentionally not made:

That the published clean-machine rebuild procedure has already been executed successfully from start to finish on a fresh Debian 13 amd64 collector.

### Deferral reason

The installer is intentionally designed for a genuinely clean collector and contains fail-closed protections against execution on an existing stateful collector.

The working collector must not be repurposed as the clean-machine test environment.

Without a disposable clean Debian 13 amd64 system, executing item 11 safely is not practical at this checkpoint.

### Deferred acceptance gate

When a disposable clean collector becomes available, item 11 should be resumed and should validate at minimum:

- package installation
- package verification
- operator credential-file preparation
- runtime installation
- certificate/HTTPS behavior
- SSH/SFTP transport
- Vector listeners and spool output
- ClickHouse schema/access/listeners
- Grafana datasources and dashboards
- AI-result validation
- retention behavior
- final `COLLECTOR_RUNTIME_VERIFY=PASS`

Until then, clean-machine execution remains an explicit open validation debt.

### Safety boundary

No collector installer or verifier was executed during this state transition.

No functionality on the working collector was changed.

### Next action

Execution-order item 12 is now the single `NEXT` item:

Capture and reconstruct the complete GX10 implementation.

Begin with read-only GX10 inventory and state capture before publishing or changing GX10 configuration.

## 2026-08-23 11:26 PDT - GX10 item 12A read-only platform inventory

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The first GX10 capture pass was intentionally read-only and limited to platform/runtime inventory plus discovery of likely pipeline components.

### Platform baseline

The current GX10 reports:

- Ubuntu 24.04.4 LTS
- Linux kernel `6.17.0-1029-nvidia`
- AArch64 / Debian architecture `arm64`
- 20 CPU cores across Cortex-X925 and Cortex-A725 clusters
- 130596118528 bytes of system memory
- 982819848192-byte root filesystem
- NVIDIA GB10
- NVIDIA driver `580.173.02`
- CUDA compiler release 13.0, build `V13.0.88`

### Core runtime baseline

Observed tool versions include:

- Python 3.12.3
- OpenSSH 9.6p1 from Ubuntu 24.04
- rsync 3.2.7
- Zstandard CLI 1.5.5
- Git 2.43.0

The standalone `sqlite3` CLI is not currently installed.

This does not establish that SQLite is absent from the application runtime; Python's SQLite support and application-owned state remain to be inspected separately.

### Ollama

Ollama is installed at version `0.32.14`.

Its system service is active and enabled.

Installed local model names observed during the read-only inventory were:

- `qwen3-coder-next:latest`
- `north-mini-code-1.0:latest`
- `qwen3.8:27b`
- `qwen3:8b`
- `nemotron-3.5-lightning:30b`
- `gemma4:latest`

The inventory does not yet claim which model is selected by the production log-processing pipeline.

### Pipeline discovery

A timer-driven AI spool pipeline exists on GX10.

The live identity-bearing unit name is intentionally not copied into the public journal. Public rebuild artifacts should use a functional GX10 pipeline name while preserving the live behavior.

Observed state:

- pipeline service is a static unit and was inactive at the inventory instant
- pipeline timer is active and enabled

That state is consistent with a timer-triggered one-shot workload, but the service type and timer schedule have not yet been inspected and must be verified from the unit definition.

No Git worktree was discovered in the scanned user, `/opt`, `/srv`, or `/usr/local/src` roots.

The active pipeline source therefore still needs to be located from the systemd unit and its referenced executable paths.

### SQLite discovery

The broad filename scan found application SQLite databases associated with Open WebUI and ordinary operating-system/user software.

The scan did not identify the GX10 pipeline state database by a clearly attributable filename.

No database content was read.

The pipeline code/unit definition must be inspected to locate the actual state database before its schema can be captured safely.

### Safety boundary

The item-12A inventory did not request or print:

- network addresses
- production hostnames
- GPU UUIDs or serial numbers
- process command lines
- process environment variables
- SSH configuration contents
- database contents
- credentials or secret values

No GX10 filesystem changes were requested.

### Item 12A conclusion

The hardware, operating-system, CUDA, Ollama, model inventory, and presence of the timer-driven pipeline are now established.

The implementation is not yet reconstructed.

### Next action

Continue execution-order item 12 with a read-only pipeline-definition discovery pass.

Inspect the pipeline service and timer metadata sufficiently to identify:

- service type
- timer schedule
- executable path
- working directory
- environment-file presence without reading secret values
- runtime user classification
- local source/config paths

Do not dump command arguments containing remote identities, network addresses, credentials, SSH configuration, environment values, or database contents.

## 2026-08-23 11:39 PDT - GX10 item 12B pipeline definition discovery

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The GX10 pipeline service and timer definitions were inspected read-only with live identity-bearing names and configuration values withheld from the public journal.

### Service contract

The active GX10 spool-processing service is:

- systemd `Type=oneshot`
- static rather than independently enabled
- normally inactive/dead between timer invocations
- `RemainAfterExit=no`
- `Restart=no`
- explicit non-root runtime user
- explicit non-root runtime group
- no `DynamicUser`

The service has no configured:

- working directory
- systemd state directory
- systemd cache directory
- systemd runtime directory
- systemd logs directory
- drop-in files

The service unit SHA-256 at this checkpoint is:

`0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`

The identity-bearing live service-unit filename is intentionally not recorded publicly.

### Service hardening

Observed systemd hardening includes:

- `PrivateTmp=yes`
- `ProtectHome=yes`
- `ProtectSystem=strict`
- `NoNewPrivileges=yes`

These settings are part of the currently functional GX10 behavior and must be preserved during reconstruction unless later testing proves that a deliberate change is required.

### Timer contract

The pipeline timer is enabled, active, and waiting.

Configured monotonic scheduling includes:

- `OnBootSec=2min`
- `OnUnitInactiveSec=1min`
- no calendar schedule
- `AccuracySec=5s`
- no randomized delay
- `Persistent=no`
- `FixedRandomDelay=no`
- `RemainAfterElapse=yes`

This confirms that the current implementation is a timer-triggered one-shot pipeline rather than a continuously running daemon.

The timer unit SHA-256 at this checkpoint is:

`5371995539846d4cca6014a70548e95c942e9f601d0736b06f4bda61c1ccc0f5`

The identity-bearing live timer-unit filename is intentionally not recorded publicly.

### Launcher contract

The service executes exactly one program with no additional ExecStart arguments.

The launcher is currently:

- a regular file
- root-owned
- mode `0755`
- 9523 bytes

Launcher SHA-256:

`662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`

The live identity-bearing executable filename is intentionally withheld from the public journal until the implementation is captured into a public-safe GX10 component layout.

### Configuration-input discovery

The systemd service contains:

- zero inline environment variables
- zero `Environment=` directives
- zero `EnvironmentFile=` references

No systemd environment values were printed.

Because the service also has only the executable itself in ExecStart, the remaining pipeline configuration and implementation assumptions must be discovered from the launcher and the local resources that it invokes.

This is a discovery conclusion, not yet a claim about where credentials, model selection, state paths, transport configuration, or remote identities are stored.

### Safety boundary

The item-12B inspection did not print:

- the full ExecStart definition
- environment values
- remote target values
- SSH configuration contents
- database contents
- production addresses
- credentials

No GX10 filesystem changes were requested.

### Item 12B conclusion

The scheduling model, systemd service type, runtime privilege classification, hardening contract, absence of systemd-level configuration inputs, and exact unit/launcher provenance hashes are now captured.

The launcher source has not yet been printed or published.

### Next action

Continue execution-order item 12 with a read-only launcher implementation inspection.

The next pass should classify the launcher before exposing source text and identify, without printing sensitive values:

- interpreter/language
- imported or invoked external tools
- local script/config paths
- local database/state paths
- spool input/output paths
- model-selection mechanism
- SFTP/SSH usage
- credential/key references
- remote-target references
- suppression/rule files
- child processes

Only after those references are classified should the implementation itself be copied into a public-safe GX10 rebuild component.

## 2026-08-23 11:45 PDT - GX10 item 12C launcher structural inspection

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The GX10 pipeline launcher was structurally inspected without publishing its source text, deployment-specific transport identity, credentials, SSH configuration contents, or database contents.

### Provenance

The launcher remained unchanged from item 12B.

Observed properties:

- Python 3 executable script
- 472 source lines
- 9523 bytes

SHA-256:

`662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`

Python syntax validation passed using in-memory AST parsing and compilation.

### Validator correction

The first item-12C syntax check used `python3 -m py_compile` against the root-owned system launcher.

That attempted to create Python bytecode beside the launcher and failed with a permission error.

This was a validation-method defect rather than a launcher defect.

The retry used `ast.parse()` and in-memory `compile()` with bytecode generation disabled.

The retry confirmed:

- launcher syntax passes
- no bytecode write was attempted
- launcher SHA-256 remained unchanged
- no GX10 filesystem write was requested by the corrected inspection

### Python implementation structure

Imported standard-library modules are:

- `datetime`
- `hashlib`
- `os`
- `pathlib`
- `re`
- `sqlite3`
- `subprocess`
- `sys`

Twelve top-level functions were identified:

- `download`
- `floor_hour`
- `get_state`
- `list_remote_hour`
- `log`
- `main`
- `run_sftp`
- `set_state`
- `sftp_base_command`
- `sha256_file`
- `timestamp_from_filename`
- `verify_zstd`

Relevant configuration/state identifiers include:

- `BOOTSTRAP_HOURS`
- `DB`
- `FILE_RE`
- `INCOMING_DIR`
- `KNOWN_HOSTS`
- `MAX_CATCHUP_HOURS`
- `OVERLAP_HOURS`
- `SETTLE_SECONDS`
- `SFTP_HOST`
- `SFTP_PORT`
- `SFTP_USER`
- `SSH_KEY`
- `TMP_DIR`

The values of transport identity and credential-related variables were not printed.

### Transport and decompression behavior

Static classification found literal use of:

- SFTP
- Zstandard

The launcher imports `subprocess` and includes calls through `subprocess.run`.

It therefore appears to orchestrate external transport/decompression commands rather than implementing those protocols directly in Python.

Detailed subprocess arguments have not yet been published or reconstructed.

### SQLite state

The launcher imports Python's `sqlite3` module and contains a call to `sqlite3.connect`.

One database-path reference was identified.

The exact live database path is intentionally withheld because it contains deployment-local identity.

No database contents or schema were read during item 12C.

### Filesystem-reference classes

Static classification identified:

- one database-path reference
- four spool/transfer-path references
- one SSH/credential-path reference
- zero separate script/config-path references

The exact live private paths are intentionally not reproduced in the public journal.

The inspection reported these private paths as not existing from the login account's perspective.

That result must not be interpreted as proof of absence: lack of traversal permission on a private parent directory can cause a non-root `Path.exists()` check to return false.

Existence, ownership, mode, and schema of the pipeline's private state must therefore be checked later through a bounded privileged metadata inspection without reading credentials or production records.

### Deployment-specific transport identity

Static classification found:

- one IPv4 literal in the launcher
- zero combined `user@host` literals
- no HTTP URL literals

The actual IPv4 value was not printed by the structural classifier and is not recorded publicly.

Because the implementation also contains `SFTP_HOST`, `SFTP_PORT`, and `SFTP_USER` configuration identifiers, the transport endpoint must be treated as deployment-specific operator input in the public rebuild implementation rather than copied as a live address.

### Credential and SSH classification

The implementation contains references associated with:

- an SSH private-key path
- a known-hosts path
- SFTP transport identity

No recognized literal secret pattern was found.

No private key, authorized key, known-host entry, credential value, password, or token was read or printed.

### LLM and classification boundary

The launcher contains:

- zero model literals
- zero suppression identifiers
- no Ollama literal detected by static string classification
- no `requests` import
- no `urllib` import

This establishes that the inspected launcher is primarily the spool acquisition/state layer and does not itself expose the model-selection or suppression logic expected elsewhere in the GX10 pipeline.

The later GX10 capture must locate that downstream enrichment/inference implementation separately.

### Safety boundary

The successful item-12C inspection did not print:

- launcher source text
- deployment-specific IPv4 value
- remote username or host value
- SSH key contents
- known-hosts contents
- credential values
- database contents

The launcher SHA-256 was unchanged at the end of inspection.

### Item 12C conclusion

The current launcher is a Python timer-invoked SFTP spool acquisition component with local SQLite state and Zstandard verification/decompression support.

Its transport identity and private paths are embedded/configured inside the launcher rather than supplied through systemd environment configuration.

The public reconstruction must preserve behavior while converting environment-specific endpoint, username, SSH key, known-hosts, and state-path assumptions into documented operator-supplied or rendered configuration.

### Next action

Continue item 12 with a read-only semantic inspection of the launcher.

The next pass should extract structure without printing private literals, including:

- numeric timing/catch-up constants
- filename-matching contract
- SQLite table/schema definition
- state keys and update semantics
- SFTP command-option contract
- remote directory construction semantics
- download eligibility and settle-time behavior
- temporary-file and atomic-move behavior
- Zstandard verification behavior
- deduplication/hash behavior
- failure and retry semantics
- precise subprocess return-code handling

It should also determine whether the one deployment-specific IPv4 literal is the value assigned to the SFTP host variable without printing the address itself.

## 2026-08-23 11:53 PDT - GX10 item 12D fetcher semantic contract

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

Read-only AST inspection established the current GX10 spool fetcher's behavioral contract without executing the launcher, opening its application database, contacting SFTP, or publishing deployment-specific transport values.

### Provenance

The inspected fetcher remained unchanged.

SHA-256:

`662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`

Python parsing and in-memory compilation both passed.

### Timing and catch-up policy

The current implementation defines:

- `BOOTSTRAP_HOURS=2`
- `MAX_CATCHUP_HOURS=24`
- `OVERLAP_HOURS=1`
- `SETTLE_SECONDS=120`

When no previous remote-scan state exists, scanning starts from the current time minus the two-hour bootstrap interval, rounded down to an hour.

When previous scan state exists, scanning starts one hour before the recorded previous scan point, rounded down to an hour.

A single invocation advances no farther than 24 hours from that calculated scan start.

The scan end is also bounded by the current hour.

File eligibility uses a cutoff equal to the current time minus the 120-second settle interval.

### Remote spool and filename contract

Remote spool directories follow:

`/spool/%Y/%m/%d/%H`

The fetcher uses that value through `strftime`.

Accepted spool filenames match:

`^syslog-(\d{8})-(\d{4})\.jsonl\.zst$`

The filename timestamp is parsed with:

`%Y%m%d%H%M`

This establishes a minute-resolution timestamp encoded in each accepted compressed JSONL spool filename.

### Deployment-specific transport input

The fetcher contains one valid IPv4 literal.

The corrected inspection confirmed that the sole IPv4 literal is the value assigned to `SFTP_HOST`.

The actual address is intentionally not recorded publicly.

The SFTP port and username are also literal configuration values in the live implementation, but their values remain withheld.

The public rebuild implementation must render or otherwise obtain these deployment-specific transport values from the operator rather than embed the live values.

### SFTP command contract

The current fetcher uses SFTP with command flags including:

- `-P`
- `-b`
- `-i`
- `-o`
- `-q`

SSH/SFTP option names include:

- `IdentitiesOnly`
- `StrictHostKeyChecking`
- `UserKnownHostsFile`

Observed boolean settings include:

- `IdentitiesOnly=yes`
- `StrictHostKeyChecking=yes`

SFTP batch operations identified are:

- `ls`
- `get`

This preserves strict host-key validation rather than accepting unknown remote keys automatically.

The private-key path, known-hosts path, username, port, and host value were not published.

### SQLite contract

The fetcher uses two real SQLite tables:

- `agent_state`
- `source_files`

The earlier semantic scanner incorrectly reported `SET` as a table because it matched the SQL `UPDATE ... SET` clause.

The corrected SQL parser confirmed:

`sqlite_false_table_SET_present=no`

The `agent_state` table CREATE contract contains:

- `key`
- `value`
- `updated_at`

Observed operations include:

- CREATE on `agent_state`
- SELECT on `agent_state`
- INSERT on `agent_state`
- SELECT on `source_files`
- INSERT on `source_files`
- UPDATE on `source_files`

The CREATE statement/column contract for `source_files` was not recovered by this inspection and must not yet be inferred.

One explicit agent-state key is used:

`last_remote_scan_utc`

No live database content was read.

### Download transaction

The observed download call sequence is:

1. remove a pre-existing temporary target when required
2. invoke SFTP download
3. verify the temporary compressed file with Zstandard
4. inspect temporary-file metadata
5. compute SHA-256
6. atomically move the validated file into its final location with `os.replace`

The implementation contains explicit temporary-file unlink cleanup and atomic replacement.

It does not rely on a non-atomic rename sequence exposed by the inspected AST.

### Zstandard integrity verification

The fetcher invokes Zstandard verification through a subprocess.

Observed flags are:

- `-q`
- `-t`

This means downloaded compressed spool objects are integrity-tested before final placement.

### Hashing and deduplication state

`sha256_file()` is called by the download path.

SHA-256 is therefore part of the source-file handling/state contract.

The exact `source_files` status-transition schema and duplicate-decision predicates still need to be captured before the complete deduplication behavior can be reconstructed.

### Subprocess behavior

Two `subprocess.run()` call sites were identified:

- SFTP execution
- Zstandard verification

The SFTP subprocess uses explicit stdin/stdout/stderr handling with text mode.

The Zstandard subprocess captures stdout/stderr in text mode.

Return codes are explicitly examined in the surrounding fetcher functions rather than relying solely on `subprocess.run(check=True)`.

### Failure behavior

The outer `main()` function contains an `Exception` handler and has a literal failure return value of `1`.

The helper functions inspected do not contain their own broad exception handlers.

This indicates that unexpected helper exceptions can propagate to the outer fetcher failure boundary.

Detailed log-message wording and every status transition remain to be captured before reproducing implementation source.

### Semantic-validator corrections

Two issues in the first item-12D semantic extractor were corrected before this checkpoint.

First, the initial SQL scanner misclassified the SQL keyword `SET` as a table name.

Second, the initial remote-directory extractor only searched formatted-string AST nodes and therefore missed the literal strftime format.

The corrected pass established:

- exactly two real SQLite tables: `agent_state` and `source_files`
- no false `SET` table
- exactly one remote spool strftime format
- `/spool/%Y/%m/%d/%H` is actually passed to `strftime`

These were validator defects, not production implementation defects.

### Safety boundary

The semantic inspection did not:

- execute the fetcher
- execute subprocesses
- contact SFTP
- open the application SQLite database
- print the deployment-specific IPv4 value
- print the SFTP username
- print the SSH private-key path
- print the known-hosts path
- read SSH key contents
- read known-hosts contents
- modify the GX10 filesystem

### Item 12D conclusion

The GX10 fetcher's acquisition contract is now captured sufficiently to reconstruct its scheduling, remote-hour discovery, filename eligibility, strict SFTP transport, temporary download validation, SHA-256 handling, atomic file publication, and durable scan cursor.

The `source_files` table's full schema and detailed status-transition semantics remain unresolved.

The downstream enrichment/inference portion of the GX10 implementation has also not yet been located.

### Next action

Continue execution-order item 12 by locating the downstream enrichment/inference implementation.

Use read-only discovery focused on:

- additional systemd units and timers related to the spool directories
- executables or Python files referencing the incoming spool location
- files referencing Ollama
- files referencing known suppression identifiers
- SQLite files or code containing enrichment/incident-state schema
- any result-return transport back to the collector

Do not recursively dump source contents or production records.

First identify candidate files by path class, size, mode, owner class, and hash; then inspect candidates individually.

## 2026-08-23 11:56 PDT - GX10 item 12E downstream candidate discovery

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

A privileged but read-only filesystem discovery pass searched for the GX10 implementation downstream of the already-captured spool fetcher.

No candidate source text, application database records, SSH material, environment values, or source-derived network addresses were printed.

### Discovery scope and noise classification

The broad classifier returned 154 candidates.

Most are not GX10 observability-pipeline components.

A large fraction came from NVIDIA profiling and SDK trees because generic search markers such as:

- return/result terminology
- incident/correlation terminology
- SQLite terminology

also occur naturally in vendor tooling.

Those vendor SDK matches must not be interpreted as pipeline dependencies.

The discovery pass was useful for locating a small number of custom executables, but future inspection should be targeted rather than recursively scanning vendor software.

### Established fetcher

The previously captured spool-fetch component remained unchanged.

SHA-256:

`662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`

Its existing provenance and semantic contract remain authoritative.

### Custom downstream candidate A

A separate root-owned custom Python executable was found with:

- mode `0755`
- 9372 bytes
- Python syntax validation passing
- spool-input marker present
- SQLite-state marker present
- result/return terminology present

SHA-256:

`6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`

Its live filename indicates a local ingest role, but that role has not yet been independently reconstructed from its source semantics.

The identity-bearing live filename is intentionally not copied into the public journal.

### Custom downstream candidate B

A second root-owned custom Python executable was found with:

- mode `0755`
- 23011 bytes
- Python syntax validation passing
- SQLite-state marker present
- result/return terminology present

SHA-256:

`6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

Its live filename indicates an enrichment role, but its current semantic behavior has not yet been independently reconstructed from source.

The identity-bearing live filename is intentionally not copied into the public journal.

### Ollama/model discovery result

The scan reported six Ollama-marker candidates.

The visible matches were associated with Ollama service configuration, Open WebUI service/configuration, and related UI/container configuration rather than the two custom downstream pipeline executables.

The broad scan reported:

- zero model-reference candidates
- zero explicit enrichment-content-marker candidates
- zero known-suppression-literal candidates

These zero counts are search results, not proof that the custom enrichment implementation lacks deterministic enrichment or suppression logic.

Static search can miss:

- constructed strings
- regex fragments
- identifiers encoded differently from the search patterns
- logic expressed without those literal terms

The custom candidate must therefore be inspected directly.

### Current architecture inference boundary

The discovery pass does not establish that production Ollama orchestration is wired into the GX10 observability pipeline.

It establishes only that:

- Ollama itself is installed and active from earlier inventory
- the broad custom-code search did not locate an obvious pipeline-side Ollama/model invocation
- two custom downstream Python executables exist and are higher-signal than the vendor SDK matches

No claim about active LLM orchestration should be made until the targeted custom-code inspection is complete.

### Safety boundary

The discovery pass:

- used read-only source inspection
- did not execute candidate programs
- did not open production SQLite databases
- did not scan the private SSH directory
- did not read SSH keys
- did not read known-host entries
- did not contact SFTP
- did not send an Ollama request
- did not modify the GX10 filesystem

Incidental Python `SyntaxWarning` messages from NVIDIA SDK scripts were produced while classifying vendor files.

They are unrelated to the custom GX10 implementation and are not pipeline failures.

### Item 12E conclusion

The broad discovery phase is complete.

The next useful targets are the two custom downstream Python executables identified by hashes:

- `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

Further broad recursive discovery would add noise rather than materially improve implementation capture.

### Next action

Continue item 12 with targeted, read-only structural inspection of the two custom downstream candidates.

Inspect the local-ingest candidate first to establish:

- compressed-file consumption behavior
- JSONL line-size limits
- required input fields
- timestamp handling
- exact-event preservation
- SQLite table creation and schema
- idempotency key
- incoming-to-processed file movement
- failure/retry semantics

Then inspect the enrichment candidate for:

- classification version
- enrichment table schema
- attention-eligibility default
- suppression rules
- vendor/protocol classifiers
- entity-key construction
- state/signal mappings
- repeat handling
- any actual model/Ollama invocation

Do not execute either candidate or read production database rows during structural inspection.

## 2026-08-23 12:05 PDT - GX10 item 12F local-ingest contract

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The first downstream GX10 custom executable was inspected read-only and its local spool-ingest contract is now captured.

The live identity-bearing executable filename and private state paths are intentionally omitted from the public journal.

### Provenance

The component is:

- Python
- root-owned
- mode `0755`
- 9372 bytes
- 410 source lines

SHA-256:

`6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`

Python AST parsing and in-memory compilation passed.

The component was not executed during inspection.

### Implementation structure

Imported standard-library modules are:

- `datetime`
- `io`
- `json`
- `os`
- `pathlib`
- `sqlite3`
- `subprocess`
- `sys`

Six top-level functions were identified:

- `ensure_schema`
- `log`
- `main`
- `parse_epoch_ms`
- `process_file`
- `reconcile_processed`

Configuration identifiers include:

- database path
- incoming spool directory
- processed spool directory
- maximum decompressed JSONL line size

The live private path values are not recorded publicly.

### Decompressed-line size contract

The maximum permitted decompressed JSONL line size is:

`1048576` bytes

This is exactly 1 MiB.

The guard measures:

`len(line.encode(...))`

against the maximum, so the constraint applies to encoded line bytes rather than merely Python character count.

### Input event fields

The parser was observed reading the following event keys through dictionary `.get()` access:

- `device_timestamp`
- `facility`
- `hostname`
- `message`
- `parse_status`
- `parser`
- `raw_message`
- `severity`
- `source_ip`
- `source_port`
- `timestamp`

No direct required-key subscript accesses were identified by the structural inspection.

That is a description of the current access pattern, not a claim that all possible malformed inputs are accepted.

### Timestamp normalization

Timestamp parsing uses Python `fromisoformat`.

The timestamp normalization function converts a terminal UTC `Z` representation to the explicit `+00:00` offset form before parsing.

The ingest layer also stores an integer millisecond epoch representation in `timestamp_epoch_ms`.

### Zstandard streaming

Compressed spool files are consumed through exactly one `subprocess.Popen` call.

The decompression command includes:

`-dc`

and the resulting stream is wrapped with `io.TextIOWrapper`.

This confirms streaming decompression rather than first materializing a fully decompressed copy on disk.

No decompression subprocess was executed during inspection.

### SQLite role

The ingest component contains 18 resolved SQLite API calls.

Its `ensure_schema()` function does not create the three base pipeline tables.

Instead, it performs compatibility/migration work against an existing schema.

Observed migration actions include:

- add `timestamp_epoch_ms INTEGER` to `recent_events`
- add `record_count INTEGER` to `source_files`
- create two indexes on the newer epoch-millisecond data

The current final live schema was therefore captured separately using SQLite read-only immutable schema metadata.

### Live-schema inspection safety

The existing state database was opened with:

- `mode=ro`
- `immutable=1`
- `PRAGMA query_only=ON`

Only SQLite schema metadata was read.

No application-data row was selected.

The inspection confirmed all three expected tables exist:

- `agent_state`
- `source_files`
- `recent_events`

### `agent_state` schema

The current table contains:

- `key TEXT` — primary key
- `value TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

The primary-key index is unique on:

`key`

This table is shared with the previously captured remote-fetch cursor logic.

### `source_files` schema

The current table contains:

- `remote_path TEXT` — primary key
- `local_path TEXT`
- `size_bytes INTEGER`
- `sha256 TEXT`
- `status TEXT NOT NULL`
- `discovered_at TEXT NOT NULL`
- `downloaded_at TEXT`
- `processed_at TEXT`
- `error TEXT`
- `record_count INTEGER`

A default value exists for `status`.

The literal default value was not printed by the schema-metadata inspection and is therefore not asserted in this checkpoint.

The primary-key index is unique on:

`remote_path`

This establishes remote-path identity for durable source-file tracking.

### `recent_events` schema

The current table contains:

- `id INTEGER` — primary key
- `source_file TEXT NOT NULL`
- `record_number INTEGER NOT NULL`
- `timestamp TEXT NOT NULL`
- `device_timestamp TEXT`
- `hostname TEXT`
- `source_ip TEXT`
- `source_port INTEGER`
- `facility TEXT`
- `severity TEXT`
- `message TEXT NOT NULL`
- `raw_message TEXT`
- `parse_status TEXT`
- `parser TEXT`
- `event_json TEXT NOT NULL`
- `timestamp_epoch_ms INTEGER`

The table has a unique constraint on:

`source_file, record_number`

This is the ingest idempotency key.

The event insert uses:

`INSERT OR IGNORE`

so replaying a source record with the same source-file identity and record number does not create a second event row.

### `recent_events` indexes

Current indexes include non-unique indexes on:

- `timestamp`
- `hostname, timestamp`
- `source_ip, timestamp`
- `severity, timestamp`
- `timestamp_epoch_ms`
- `hostname, timestamp_epoch_ms`

The table also has the unique auto-index for:

`source_file, record_number`

These indexes are part of the currently functional local event-query/state behavior and should be represented in the GX10 rebuild schema.

### Event insert mapping

The ingest component inserts 15 explicit fields into `recent_events`:

- `source_file`
- `record_number`
- `timestamp`
- `timestamp_epoch_ms`
- `device_timestamp`
- `hostname`
- `source_ip`
- `source_port`
- `facility`
- `severity`
- `message`
- `raw_message`
- `parse_status`
- `parser`
- `event_json`

Observed mappings include:

- source identity from the remote source path
- record identity from the decompressed line number
- normalized timestamp fields
- parsed syslog metadata from the JSON object

### Exact-event preservation

`event_json` is not reconstructed with `json.dumps(event)`.

The inserted value comes directly from:

`line.rstrip(...)`

on the decompressed input line.

This means the implementation preserves the input JSON representation after its configured trailing-character removal rather than serializing the parsed dictionary into a new JSON representation.

The exact argument supplied to `rstrip()` was not printed by this inspection and is intentionally not inferred here.

That nuance must be preserved from the actual source when the public-safe implementation is captured.

### File lifecycle

Two `os.replace()` calls were identified.

They occur in:

- processed-file reconciliation
- normal file processing

Both code paths construct destinations under the processed-spool directory.

This confirms an incoming-to-processed lifecycle using atomic replacement semantics.

The earlier inspection's report of a `replace()` call inside timestamp parsing was correctly identified as string replacement, not filesystem movement.

### Recovery/reconciliation behavior

A `reconcile_processed()` function exists specifically to reconcile source-file database state with files that have already reached the processed filesystem location.

The code also queries and updates `source_files` around processing.

This indicates explicit recovery support for filesystem/database state that can diverge across interrupted runs.

Detailed source-file status literals have not yet been published and should be retained directly from the implementation during the public-safe source capture rather than guessed.

### Event-data preservation boundary

The ingest database stores both:

- structured parsed columns used for query/filtering
- the source JSON line in `event_json`

It also preserves both:

- parsed `message`
- `raw_message` when provided by the upstream event

This gives downstream enrichment access to structured fields while retaining the upstream event representation.

### LLM and suppression boundary

The local-ingest component contains:

- no Ollama literal
- no known local model literal
- no known suppression-rule literal

It is therefore a deterministic spool-to-SQLite ingestion component, not the LLM/inference layer.

The enrichment candidate remains the next implementation target.

### Validator corrections during item 12F

Several inspection-tool limitations were corrected before this checkpoint.

The initial SQL literal scanner failed to reconstruct schema creation because this component is a schema migrator rather than the base schema creator.

A later in-memory DDL test attempted to create indexes without the pre-existing `recent_events` table and failed.

That failure was a validation-design issue, not a production GX10 failure.

The final pass used read-only live SQLite schema metadata instead of inferring missing base DDL.

The initial filesystem-call scanner also conflated:

- string `.replace()`
- `os.replace()`

The corrected AST inspection established exactly two relevant filesystem `os.replace()` calls.

The first subprocess scanner looked only for `subprocess.run()` and therefore missed streaming decompression.

The corrected inspection found one `subprocess.Popen()` call using Zstandard decode streaming.

### Safety boundary

Item 12F did not:

- execute the ingest component
- execute the decompression subprocess
- open any production compressed spool object
- select application-data rows from SQLite
- print production event records
- print private state paths
- print network addresses from production records
- modify GX10 files

The live database access was limited to immutable, read-only schema metadata.

### Item 12F conclusion

The local ingest stage is now captured sufficiently to reconstruct:

- streaming Zstandard consumption
- the 1 MiB line-size guard
- event timestamp normalization
- source-file and record-number idempotency
- structured event extraction
- upstream JSON-line retention
- the current three-table SQLite schema
- current event-query indexes
- incoming-to-processed atomic file movement
- schema migration behavior
- interrupted-run reconciliation

The base-schema creator has not yet been identified, but the current final schema is independently captured from the live database, so clean-rebuild reconstruction does not depend on locating historical schema-creation code.

### Next action

Continue execution-order item 12 with targeted read-only inspection of the second custom downstream candidate.

That inspection should establish:

- enrichment/classification version
- additional SQLite schema or migrations
- deterministic suppression rules
- vendor and protocol classifiers
- entity-key construction
- state and signal mappings
- repeat/repetition handling
- attention-eligibility semantics
- result/output behavior
- whether any Ollama or model invocation actually exists

Do not execute the candidate or read application-data rows while performing the structural inspection.

## 2026-08-23 12:13 PDT - GX10 item 12G deterministic enrichment contract

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The second downstream GX10 custom Python executable was inspected read-only.

Its deterministic enrichment/classification contract and current SQLite schema are now captured without executing the component, selecting production event rows, or reading the suppression-rule corpus.

The live identity-bearing executable filename and private database path are intentionally omitted from the public journal.

### Provenance

The enrichment component is:

- Python
- root-owned
- mode `0755`
- 23011 bytes
- 1071 source lines

SHA-256:

`6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

Python AST parsing and in-memory compilation passed.

The component remained unchanged throughout inspection.

### Classification version

The current classification version is:

`3`

This value is stored with enrichment records through the `classification_version` field.

### Implementation structure

Five standard-library imports were observed:

- `datetime`
- `json`
- `re`
- `sqlite3`
- `sys`

Nine top-level functions were identified:

- `bgp_key`
- `classify`
- `classify_bgp`
- `ensure_schema`
- `extract_event_code`
- `generic_family_from_code`
- `load_suppression_rules`
- `main`
- `suppression_for`

The main call graph includes:

- `main -> ensure_schema`
- `main -> extract_event_code`
- `main -> classify`
- `main -> load_suppression_rules`
- `main -> suppression_for`
- `classify -> classify_bgp`
- `classify -> generic_family_from_code`
- `classify_bgp -> bgp_key`

### Deterministic rather than LLM execution

The enrichment component contains:

- no Ollama literal
- no known model literal
- no HTTP URL literal
- no network-oriented Python module import
- no subprocess module import
- no subprocess API call

The inspected enrichment stage is therefore deterministic local classification over SQLite-backed event state.

No evidence was found that this executable invokes Ollama or any local language model.

Any LLM orchestration, if it exists elsewhere in the GX10 deployment, remains a separate implementation target.

### Regex classifier inventory

Twelve compiled regex classifiers were identified:

- `ARISTA_BGP_ADJ_RE`
- `ARISTA_BGP_CLEAR_RE`
- `ARISTA_BGP_NOTIFICATION_RE`
- `EVENT_CODE_FALLBACK_RE`
- `EVENT_CODE_RE`
- `INTERFACE_RE`
- `IOSXR_BGP_ADJ_RE`
- `IOSXR_BGP_NSR_RE`
- `NXOS_OSPF_PROCESS_RE`
- `OSPF_NEIGHBOR_RE`
- `PROCESS_RE`
- `REPEAT_RE`

All inspected regexes compiled successfully.

The source values of these expressions were intentionally not dumped during discovery.

Their exact implementation must be preserved when the public-safe executable source is captured rather than reconstructed approximately from the journal.

### Event-code extraction

Event-code extraction uses:

- a primary event-code regex
- a fallback event-code regex

The extracted event code feeds both:

- deterministic classification
- suppression-rule matching

### BGP classification

The BGP classifier has the signature:

`classify_bgp(event_code, message, device)`

Observed vendor hints include:

- `arista_eos`
- `cisco_ios_xr`
- `unknown`

Observed protocol value:

`bgp`

Observed entity types include:

- `bgp_peer`
- generic `bgp`

Observed state values include:

- `up`
- `down`
- `clear_requested`
- `notification`
- `nsr_disabled_standby`

Observed signal types include:

- `recovery`
- `state_transition`
- `administrative_action`
- `protocol_notification`
- `supporting_evidence`
- generic `observation`

The BGP entity-key function accepts:

- device
- VRF
- peer

and returns a BGP-prefixed compound entity key.

Exact normalization of the VRF and peer portions must be retained from source rather than inferred from the structural output.

### OSPF classification

Observed OSPF behavior includes:

- family `ospf`
- vendor hint `cisco_nxos`
- protocol `ospf`
- entity type `ospf_neighbor`

The entity key is built from:

- device
- process
- neighbor

Observed OSPF states/signals include:

- state `retransmissions`
- signal type `degradation`
- state `down`
- state `up`
- signal type `state_transition`
- signal type `recovery`

The classifier uses dedicated OSPF neighbor and process regexes.

### Interface classification

Observed interface classification includes:

- vendor hint `cisco_nxos`
- protocol `ethernet`
- entity type `interface`

The interface entity key is constructed from:

- device
- interface

The classifier carries explicit state and signal-type values for the matched interface event.

An `IF_DOWN` classification label is explicitly compared in the current implementation.

### Process classification

Observed process classification includes:

- family `process`
- entity type `process`
- vendor hint `unknown`
- generic observation signal behavior

The entity key is built from:

- device
- process name

### Syslog-repeat classification

A dedicated `REPEAT_RE` classifier is actively used by `classify()`.

Observed repeat classification includes:

- family `syslog_repeat`
- entity type `syslog_stream`
- entity key prefixed by `SYSLOG_REPEAT`
- state `repeat`
- signal type `repeat_notice`

The repeat count is parsed as an integer.

The default non-repeat classifier result uses a repeat count of `1`.

### Generic classification fallback

The generic classifier can return:

- an extracted/generic family
- vendor hint `unknown`
- no entity type
- no entity key
- no state
- signal type `observation`
- repeat count `1`

This provides a deterministic fallback for events not matched by the more specific protocol classifiers.

### Enrichment result fields

The current enrichment insert explicitly contains 16 fields:

- `event_id`
- `event_code`
- `family`
- `device`
- `entity_type`
- `entity_key`
- `state`
- `attention_eligible`
- `suppression_rule_id`
- `classified_at`
- `repeat_count`
- `classification_version`
- `vendor_hint`
- `protocol`
- `signal_type`
- `attributes_json`

This matches the current live `event_enrichment` table column set.

### `event_enrichment` schema

Read-only immutable SQLite metadata confirms the current table contains:

- `event_id INTEGER` — primary key
- `event_code TEXT NOT NULL`
- `family TEXT NOT NULL`
- `device TEXT NOT NULL`
- `entity_type TEXT`
- `entity_key TEXT`
- `state TEXT`
- `attention_eligible INTEGER NOT NULL`
- `suppression_rule_id INTEGER`
- `classified_at TEXT NOT NULL`
- `repeat_count INTEGER NOT NULL`
- `classification_version INTEGER NOT NULL`
- `vendor_hint TEXT NOT NULL`
- `protocol TEXT NOT NULL`
- `signal_type TEXT NOT NULL`
- `attributes_json TEXT NOT NULL`

Defaults exist on several enrichment fields.

The literal default values were not printed during metadata inspection and are therefore not asserted in this checkpoint.

### Enrichment indexes

Current non-unique indexes include:

- `event_code`
- `family`
- `attention_eligible`
- `entity_type, entity_key`
- `protocol`
- `signal_type`
- `vendor_hint`

These indexes are part of the currently functional GX10 enrichment-query contract and should be represented by the rebuild schema.

### Enrichment foreign keys

The live schema confirms:

`event_enrichment.event_id -> recent_events.id`

and:

`event_enrichment.suppression_rule_id -> suppression_rules.id`

This ties deterministic classification one-to-one to the ingested event identifier while preserving the identity of the matching suppression rule when applicable.

### Suppression engine architecture

Suppression logic is not hardcoded as the known production rule strings inside this executable.

Instead, rules are loaded from the SQLite `suppression_rules` table.

The loader selects:

- `id`
- `name`
- `rule_type`
- `pattern`

The loader query contains both:

- a `WHERE` clause
- an `ORDER BY` clause

The exact filter/order expressions were not printed by this inspection and are not inferred here.

### Supported suppression-rule types

The current `suppression_for()` implementation supports exactly three observed rule types:

- `event_code_exact`
- `event_code_prefix`
- `message_regex`

This establishes the public rebuild rule-engine contract.

The actual live rule rows remain intentionally uncaptured at this subsection boundary.

### `suppression_rules` schema

Read-only immutable SQLite metadata confirms the table contains:

- `id INTEGER` — primary key
- `name TEXT NOT NULL`
- `rule_type TEXT NOT NULL`
- `pattern TEXT NOT NULL`
- `enabled INTEGER NOT NULL`
- `reason TEXT NOT NULL`
- `created_at TEXT NOT NULL`

A default exists for:

`enabled`

and for:

`reason`

The literal default values were not printed during metadata inspection and are not asserted here.

The table has a unique constraint on:

`name`

There are no foreign keys originating from `suppression_rules`.

### Attention eligibility

The enrichment stage contains explicit:

- `suppressed`
- `suppressed_this_run`
- `suppression_rule_id`
- `eligible`
- `attention_eligible`

state variables.

The final `attention_eligible` value is assigned as a conditional integer `0` or `1`.

The structural inspection did not print the full condition expression, so this checkpoint does not overstate the exact predicate.

That predicate should be retained directly from source during public-safe implementation capture.

### Classifier state model

Observed state-oriented values include:

- `up`
- `down`
- `clear_requested`
- `notification`
- `nsr_disabled_standby`
- `retransmissions`
- `repeat`

Observed signal taxonomy includes:

- `observation`
- `supporting_evidence`
- `state_transition`
- `recovery`
- `administrative_action`
- `protocol_notification`
- `degradation`
- `repeat_notice`

This is deterministic classification state, not long-lived incident lifecycle state.

No separate incident correlator was identified in this executable.

### SQLite role

The component queries:

- `recent_events`
- `event_enrichment`
- `suppression_rules`

and inserts into:

- `event_enrichment`

The component also performs enrichment schema compatibility/index work.

As with the local-ingest executable, the base-table creator was not identified from this file.

The final live table schemas are nevertheless independently captured from SQLite metadata and can therefore be reconstructed without relying on historical schema-creation code.

### Read-only live-schema safety

The existing application database was opened using:

- `mode=ro`
- `immutable=1`
- `PRAGMA query_only=ON`

Only SQLite schema metadata was read.

No production event rows were selected.

No suppression-rule rows were selected.

### Validator interpretation

The first item-12G classifier reported zero relevant module-level mappings.

That does not mean classification mappings are absent.

The implementation expresses most classification semantics procedurally through:

- regex matches
- conditional branches
- return dictionaries

rather than large module-level mapping dictionaries.

The semantic closeout captured these procedural return fields directly.

### Item 12G conclusion

The current GX10 enrichment stage is a deterministic classification and suppression engine at classification version 3.

It provides:

- event-code extraction
- BGP classification
- OSPF classification
- interface classification
- process classification
- repeat-event classification
- generic fallback classification
- entity-key construction
- state and signal classification
- SQLite-backed suppression matching
- attention-eligibility output
- indexed durable enrichment storage

It does not itself invoke Ollama or another local model.

### Unresolved boundary

The actual rows in `suppression_rules` were intentionally not read during item 12G.

The rule-engine schema and matching semantics are captured, but the clean rebuild still requires a public-safe reconstruction of the current rule corpus.

That corpus must be inspected separately because rule patterns and reasons need an explicit public-safety review before publication.

### Next action

Continue execution-order item 12 with a bounded read-only inspection of the active suppression-rule corpus.

For each rule, inspect only:

- rule identifier/name
- enabled state
- rule type
- pattern classification
- reason classification

Before printing any literal pattern or reason, test it for:

- IP addresses
- hostnames
- usernames
- organization names
- private paths
- secrets
- other deployment-specific identity

Publish literal values only when they are confirmed generic and public-safe.

The known generic IPv6 neighbor-discovery suppressions should be recoverable through this process without exposing unrelated deployment-specific rules.

## 2026-08-23 12:18 PDT - GX10 item 12H suppression corpus

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The active SQLite-backed GX10 suppression-rule corpus was inspected read-only.

The corpus contains exactly two rows.

Both are enabled, generic, public-safe network-event suppressions.

No production event or enrichment rows were read.

### Loader semantics

The deterministic enrichment component contains exactly one suppression-rule loader query.

That query selects:

- `id`
- `name`
- `rule_type`
- `pattern`

from the suppression-rule table.

The loader:

- has an explicit filter
- loads enabled rules only
- orders rules by `id`
- orders ascending

This establishes deterministic evaluation order for the active suppression corpus.

### Corpus size

Current suppression-rule row count:

`2`

Enabled rules:

`2`

Disabled rules:

`0`

Both active rules use:

`event_code_exact`

There are currently no active or inactive rows using the other supported rule-engine types:

- `event_code_prefix`
- `message_regex`

The engine continues to support those types even though the current corpus does not use them.

### Active suppression rule 1

Database rule ID:

`1`

Enabled:

`1`

Rule type:

`event_code_exact`

Pattern:

`ICMPV6-3-ND_LOG`

The pattern is generic protocol/event-code material and passed the bounded public-safety classifier with no detected sensitive marker.

The database rule-name literal was intentionally not printed.

For provenance, its current value has:

- length `18`
- SHA-256 `b353a75e0d1f901069f6cbc092e26fb23bcdf5cff6a1119ec2c13bf7e036437a`

The current reason value has:

- length `61`
- SHA-256 `73838c81792b6535040ab1bd62dd3137a5eb4186558c387d7535c46ccf4d411d`

No sensitivity marker was detected in either value, but their literals were not needed to establish suppression behavior and therefore were not exposed during this inspection.

### Active suppression rule 2

Database rule ID:

`2`

Enabled:

`1`

Rule type:

`event_code_exact`

Pattern:

`ICMPV6-3-ND_RA_LOG`

The pattern is generic protocol/event-code material and passed the bounded public-safety classifier with no detected sensitive marker.

The database rule-name literal was intentionally not printed.

For provenance, its current value has:

- length `21`
- SHA-256 `658e9e66fc6794532f18226ef9bc03fe9006fdeb5db0e85743dd5bdf6069107a`

The current reason value has:

- length `61`
- SHA-256 `efade090255af6dfd326c979d3701bf798a2262d2232d2f30cacc02e4bf69484`

No sensitivity marker was detected in either value, but their literals were not needed to establish suppression behavior and therefore were not exposed during this inspection.

### Public-safety result

The corpus inspection found:

- zero non-allowlisted patterns
- zero patterns with a detected sensitive marker
- zero production IP-address literals
- zero private-path literals
- zero credential/secret markers
- zero deployment-specific patterns requiring further review

Only the two explicitly allowlisted generic event-code patterns were printed.

Suppression-rule names and reasons were not printed.

### Functional suppression corpus

The complete currently active functional suppression pattern set is therefore:

1. `ICMPV6-3-ND_LOG`
2. `ICMPV6-3-ND_RA_LOG`

Both are exact event-code matches and both are enabled.

This confirms the previously expected IPv6 neighbor-discovery suppressions against the live GX10 state rather than relying on prior memory.

### Rebuild implications

A clean rebuild must seed two active exact-event-code suppression rules covering the patterns above.

Evaluation order is ascending rule ID.

The enrichment implementation supports additional prefix and regex rule types, but no current live row uses them.

The unique rule-name and descriptive reason fields remain database metadata rather than part of the matching predicate established here.

Their current hashes have been recorded so later source/config capture can prove exact preservation if those literals are recovered from a public-safe initialization artifact.

### Safety boundary

Item 12H:

- opened the SQLite database read-only
- used `immutable=1`
- used `PRAGMA query_only=ON`
- selected only suppression-rule rows
- did not select `recent_events`
- did not select `event_enrichment`
- did not execute the enrichment component
- did not modify SQLite
- did not modify GX10 files

### Item 12H conclusion

The current live suppression corpus is fully bounded at the functional matching level.

It contains exactly two enabled, public-safe, exact event-code suppressions:

- `ICMPV6-3-ND_LOG`
- `ICMPV6-3-ND_RA_LOG`

There is no hidden additional live suppression pattern requiring public-safety review.

### Next action

Continue execution-order item 12 by reconstructing GX10 runtime orchestration.

Perform a read-only reference inventory to determine exactly how the already-captured custom components are invoked:

- remote spool fetch
- local spool ingest
- deterministic enrichment

Inspect systemd units, timers, and cron references by exact local executable reference without dumping unit secrets or environment values.

Also identify whether a separate downstream inference/result-return launcher exists outside those three captured components.

Do not execute pipeline components or make network requests during orchestration discovery.

## 2026-08-23 12:31 PDT - GX10 item 12I runtime orchestration discovery

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

A bounded read-only GX10 orchestration inventory established how the already-captured remote-spool fetcher and local ingester are scheduled.

It also established that the deterministic enrichment component is not invoked by that same systemd service and is not referenced by cron.

Live identity-bearing executable and unit names remain omitted from this public journal.

### Scheduled pipeline service

Exactly one systemd unit directly references the captured fetch and ingest executables.

The unit SHA-256 is:

`0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`

This is the same service-unit provenance captured earlier during GX10 pipeline discovery.

The service contract is:

- `Type=oneshot`
- wants `network-online.target`
- ordered after `network-online.target`
- first `ExecStart` invokes the remote-spool fetch component
- second `ExecStart` invokes the local-spool ingest component

Systemd therefore provides explicit sequential execution:

`fetch -> ingest`

within a single oneshot service invocation.

### Runtime state

At inspection time:

- the pipeline service was `static`
- the pipeline service was `inactive/dead`
- its timer was `enabled`
- its timer was `active/waiting`

The inactive service state is consistent with a timer-driven oneshot that exits after each run.

The timer cadence and timer-unit provenance were captured previously during the GX10 service/timer inspection and were not re-derived by this bounded reference scan.

### Enrichment boundary

The deterministic enrichment executable was present with unchanged provenance:

`6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

However, the systemd unit that directly invokes fetch and ingest does not reference enrichment.

No other scanned systemd unit directly referenced that enrichment executable.

No cron file referenced:

- fetch
- ingest
- enrichment

Therefore the currently proven scheduled chain is only:

`timer -> fetch -> ingest`

How deterministic enrichment is invoked remains unresolved.

That unresolved invocation path is now a specific rediscovery target rather than an inferred part of the fetch/ingest timer.

### Component provenance recheck

All three already-known custom components remained unchanged during this inspection.

Remote-spool fetch SHA-256:

`662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`

Local-spool ingest SHA-256:

`6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`

Deterministic enrichment SHA-256:

`6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

### Ollama boundary

The Ollama service is:

- enabled
- active/running

The orchestration inspection found no direct systemd or cron reference connecting Ollama to the captured fetch, ingest, or enrichment executable paths.

This does not prove that no other component calls Ollama.

It does establish that Ollama is not part of the directly observed fetch/ingest systemd invocation.

### Broad-marker false positives

The local executable marker scan also returned the NVIDIA system-analysis executable and the Ollama executable because generic strings such as:

- `result`
- `return`
- SQLite-related text
- transport-related text

occur in large vendor/runtime binaries.

Those marker hits are not treated as evidence that either executable belongs to the application result-return pipeline.

The three already-proven custom Python components remain the only application components established by this scan.

### Cron boundary

No matching reference was found in the scanned cron locations.

Current orchestration discovery therefore has no evidence for cron-based execution of:

- fetch
- ingest
- enrichment

### Safety boundary

Item 12I did not:

- execute any pipeline component
- open the production database
- read production event rows
- make a network request
- print unit environment values
- print unit secret values
- dump custom executable source
- modify GX10 files

### Item 12I conclusion

Current runtime orchestration is now proven at the first scheduling boundary:

`timer -> oneshot service -> fetch -> ingest`

The deterministic enrichment component is not invoked at that boundary.

Its invocation path, any result-return path, and any actual Ollama/inference orchestration remain to be discovered.

### Next action

Continue rediscovery with a narrow reference search for:

- deterministic enrichment invocation
- result-return/upload logic
- wrappers that invoke already-known GX10 components
- additional application-specific systemd units or timers
- shell/profile/operator scheduling references
- any component that invokes Ollama or a local model

Avoid another broad vendor-tree scan.

Do not rebuild or modify the live GX10 system during this rediscovery phase.

## 2026-08-23 13:23 PDT - GX10 item 12J enrichment invocation closeout

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

A bounded rediscovery pass investigated the unresolved invocation path for the already-captured deterministic enrichment component.

The investigation found no current automatic invocation mechanism.

### Previously proven scheduling boundary

Item 12I established the current scheduled data-acquisition chain as:

`timer -> oneshot service -> fetch -> ingest`

The deterministic enrichment component is not referenced by that service.

No cron reference to the component had been found.

### Initial 12J reference scan

The first 12J pass performed:

- bounded local configuration/reference scanning
- saved shell-history reference counts
- an attempted system-journal metadata scan

The local filesystem portion found two apparent strong unknown candidates associated with enrichment references.

The system-journal step used an insufficiently bounded historical query and took unacceptably long.

The operator interrupted that query.

This was a discovery-validator design problem, not evidence of a GX10 implementation failure.

The interrupted pass:

- did not execute a pipeline component
- did not open the application database
- did not read event rows
- did not make a network request
- did not modify GX10 files

The system-journal approach was abandoned rather than retried.

### False-positive candidate resolution

A corrected bounded closeout compared the two apparent unknown candidates against the saved shell-history files.

Both candidates resolved exactly to shell-history files:

- one for the normal login account
- one for the root account

They were not:

- wrappers
- services
- timers
- cron files
- result-return components
- inference components

The initial strong-candidate result was therefore a scanner false positive caused by searching home-directory history files as ordinary text artifacts.

### Saved-history classification

The login-account Bash history contained:

`4`

references to the enrichment executable.

The root Bash history contained:

`16`

references.

All twenty references were classified as:

`reference_not_execution_position`

The bounded command-position classifier found zero saved-history instances of:

- direct enrichment executable invocation
- Python-interpreter invocation of the enrichment executable
- systemd-run invocation of the enrichment executable

No shell-history command text was printed.

The stored history therefore provides no evidence that the enrichment component was directly executed from those saved shell sessions.

This is not proof that the component has never been run historically because shell history is not a complete execution audit log.

### Non-history reference closeout

A second bounded scan excluded shell-history files and searched the relevant configuration and custom-code locations for an exact enrichment executable reference.

The final result was:

`non_history_enrich_reference_count=0`

No additional wrapper, scheduler, profile hook, custom executable, or configuration artifact referencing the enrichment component was found in that bounded search.

### Current orchestration conclusion

The only currently proven automatic runtime path remains:

`timer -> fetch -> ingest`

The enrichment implementation is present and has been completely characterized at the source/schema level, but no current automatic invocation mechanism has been discovered.

There is currently no evidence that enrichment is:

- part of the fetch/ingest oneshot service
- invoked by cron
- invoked by a discovered wrapper
- invoked by a discovered user-level systemd unit
- invoked by a discovered root-level systemd unit
- directly executed in the saved shell-history records examined

This is a rediscovery finding and must be preserved rather than silently "fixing" the live design during capture.

Any future rebuild decision to automate enrichment would be an implementation change unless additional live evidence establishes an existing invocation mechanism.

### Component integrity

All three previously captured custom components retained their expected SHA-256 values throughout the 12J investigation.

No production application rows were read.

No network request was issued.

No filesystem modification was requested on GX10.

### Rediscovery implications

The absence of a discovered enrichment invocation is itself part of the current-state reconstruction.

The public rebuild must distinguish between:

1. behavior proven to be automatically active today
2. deterministic implementation present on GX10 but not proven to be automatically scheduled
3. future architecture that may deliberately wire additional stages together

The rediscovery phase must not convert category 2 into category 1 without evidence.

### Remaining rediscovery targets

The remaining live-system rediscovery is now narrowly focused on:

1. the GX10 write-only result-return producer/path
2. any actual caller of Ollama or a local model
3. Ollama/model runtime configuration required to represent the current GX10 state
4. SQLite/base-state bootstrap or schema-creation provenance
5. remaining users, directories, permissions, and runtime dependencies needed to account for the live GX10 implementation
6. a final rediscovery closure audit confirming every current functional GX10 component has been accounted for

No rebuild implementation work should begin until those discovery gaps are closed and the rediscovery milestone is journaled in GitHub.

## 2026-08-23 13:26 PDT - GX10 item 12K result-return and Ollama caller boundary

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

A targeted read-only rediscovery pass searched for:

- a GX10 application component that produces or uploads result-return data
- an application-specific caller of Ollama or a local model

Neither was identified in the bounded live-system scan.

### Result-return application search

The targeted application scan returned:

`result_return_candidate_count=0`

No custom application artifact was identified that combined transport behavior with:

- AI-update semantics
- result-return semantics
- result-upload semantics
- ready/incoming result-directory semantics
- JSON result-generation semantics

The scan did not identify a GX10 producer currently writing to the collector's already-established write-only result-return boundary.

This does not invalidate the collector-side result-return infrastructure.

It establishes that a live GX10 producer for that boundary has not been discovered.

### Ollama/model caller search

The targeted scan returned:

`pipeline_ollama_candidate_count=0`

No scanned application-specific artifact combined an Ollama API/CLI/runtime reference with pipeline state, result semantics, model references, or enrichment state.

No application-specific pipeline caller of Ollama was identified.

### Systemd boundary

The bounded systemd semantic pass examined:

`146`

service/timer/path unit files.

Results:

`systemd_result_return_candidate_count=0`

and:

`systemd_pipeline_ollama_candidate_count=0`

No scanned systemd orchestration unit currently ties the application pipeline to:

- a GX10 result-return producer
- an Ollama API caller
- a model-execution wrapper

### Saved shell-history evidence

The saved login-account and root Bash histories were examined using semantic counts only.

For both histories, counts were zero for:

- SFTP put behavior
- SCP invocation
- rsync invocation
- `ollama run`
- Ollama API endpoint references
- known current model-name references

No shell-history command text was printed.

Saved shell history therefore provides no evidence for an operator-driven result upload or model invocation in the retained history.

As with earlier history inspection, absence from saved shell history is not treated as proof that an operation has never occurred.

### Ollama runtime state

Ollama itself is present as active infrastructure.

At inspection time its service was:

- loaded
- active
- enabled

Therefore the correct current-state distinction is:

1. Ollama runtime infrastructure exists and is running.
2. Locally installed model inventory has already been captured separately.
3. No application-specific pipeline caller of that runtime has been identified.

The project must preserve that distinction rather than infer production LLM orchestration solely from the presence of the running Ollama service.

### Existing collector return boundary

The collector rebuild capture already establishes a write-only GX10 result-return transport boundary and collector-side validation/ingestion path.

Item 12K does not change that collector finding.

The unresolved side is specifically the GX10 producer:

- no producer executable was identified
- no producer wrapper was identified
- no producer systemd unit was identified
- no retained shell-history transfer command was identified

A clean rebuild of the current proven GX10 state must not invent a result producer and label it as discovered production behavior.

### Search scope

The discovery scan deliberately focused on application-controlled locations and configuration.

Large vendor/runtime trees were pruned.

The Open WebUI implementation tree was also pruned.

Accordingly, this checkpoint does not claim that:

- no installed third-party application can communicate with Ollama
- Open WebUI cannot communicate with Ollama
- the Ollama runtime has never processed a request

The conclusion is specifically about the reconstructed network-observability application pipeline.

### Component integrity

The previously captured custom components retained their expected SHA-256 values throughout the scan.

No pipeline component was executed.

No production database was opened.

No production event rows were read.

No network request was made.

No GX10 filesystem write was requested.

### Rediscovery interpretation

Items 12I through 12K now establish a significant current-state boundary.

Proven automatic pipeline behavior:

`timer -> fetch -> ingest`

Present but not automatically invoked by any discovered mechanism:

`deterministic enrichment`

Present infrastructure without an identified application pipeline caller:

`Ollama runtime`

Collector-side capability present without an identified GX10 producer:

`write-only result-return boundary`

These distinctions are part of rediscovery and must remain separate from later design decisions.

### Remaining rediscovery targets

The major discovery gaps are now reduced to:

1. Ollama service/runtime configuration and current model metadata required to reproduce the existing installed state
2. SQLite/base-state bootstrap and schema-creation provenance
3. GX10 runtime user, group, directory, ownership, permission, and package/dependency contracts
4. final bounded discovery for any remaining application bootstrap/config artifacts
5. rediscovery closure audit and GitHub checkpoint

The result-return producer and production LLM orchestration should no longer be treated as undiscovered components that must exist.

Unless later evidence contradicts this checkpoint, they should be recorded as not currently identified in the live application implementation.

No GX10 rebuild implementation work begins until rediscovery closure is journaled.

## 2026-08-23 13:32 PDT - GX10 item 12L Ollama runtime and model state

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

A read-only local-filesystem and systemd inspection captured the current Ollama runtime and model state without invoking the Ollama API, running inference, pulling models, or making an external network request.

### Ollama service state

The Ollama service is:

- loaded
- active
- enabled

Runtime identity:

- user `ollama`
- group `ollama`

Service behavior:

- `Restart=always`
- restart delay `3s`
- no explicit working directory
- `LimitNOFILE=524288`

The current unit does not enable the following systemd hardening directives:

- `PrivateTmp`
- `ProtectHome`
- `ProtectSystem`
- `NoNewPrivileges`

These are current-state findings, not recommendations.

### Service dependency state

Observed `After` dependencies include:

- `basic.target`
- `network-online.target`
- `sysinit.target`
- `system.slice`
- `systemd-journald.socket`

The service has no explicit `Wants` dependencies.

Observed `Requires` dependencies are:

- `sysinit.target`
- `system.slice`

### Unit provenance

The service fragment is a regular `ollama.service` unit.

Current fragment SHA-256:

`11758d469d3f103e53a9612a8ffcb3a3e61834c994c08d412bb051f3c827dbd3`

Mode:

`0644`

Drop-in count:

`0`

### Executable contract

The Ollama executable is:

- basename `ollama`
- root-owned
- root-group
- mode `0755`
- size `35792104` bytes

Current executable SHA-256:

`26f44ca89143f2326a3aad98b2cb5e8b5af9397aef7001cd8d022e90d6e0b55e`

The service `ExecStart` references that executable and invokes its `serve` operation.

The raw `ExecStart` value was not printed.

The executable is not owned by a dpkg package.

This establishes that current Ollama installation provenance is not represented by the Debian package database.

It does not by itself establish how the binary was originally installed.

The Ollama version previously captured during GX10 platform inventory remains the version checkpoint for this rediscovery phase; item 12L did not execute the Ollama CLI to revalidate it.

### Service environment

Exactly one explicit service environment variable was present:

`PATH`

Its value was not printed.

For provenance, the current value SHA-256 is:

`f5a00065660f4ba15c80ff30175de9613f3def42dfbb702d707014bc162fe79c`

There are:

`0`

environment-file references.

No environment-file values were read or printed.

No explicit `OLLAMA_HOST` or `OLLAMA_MODELS` override was present in the systemd environment captured here.

### Model storage

The model root was resolved from the Ollama service account home.

Current model root:

`/usr/share/ollama/.ollama/models`

Ownership:

`ollama:ollama`

Mode:

`0755`

Both expected subtrees are present:

- manifests
- blobs

### Manifest inventory

Exactly six Ollama manifests are present.

Every manifest resolves to an already-reviewed public-safe model reference.

Unexpected or unreviewed model count:

`0`

Missing referenced blob count:

`0`

Every manifest-referenced blob is present.

### Model 1

Reference:

`gemma4:latest`

Manifest SHA-256:

`c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb`

Config digest:

`sha256:f0988ff50a2458c598ff6b1b87b94d0f5c44d73061c2795391878b00b2285e11`

Declared referenced bytes:

`9608350718`

Referenced blobs:

`4`

All referenced blobs are present.

### Model 2

Reference:

`nemotron-3.5-lightning:30b`

Manifest SHA-256:

`e7a64ff15fb174c42b4f463e5c888c4f2c7b9cabf9e8d65a1c0874405426c1b2`

Config digest:

`sha256:7101a4a1d9e30ce87a71265e93215173f5e4cc84883e5cf1ef88862547f31fcd`

Declared referenced bytes:

`25430749387`

Referenced blobs:

`5`

All referenced blobs are present.

### Model 3

Reference:

`north-mini-code-1.0:latest`

Manifest SHA-256:

`d8b269ad5c7c7144ce104b83ce93bc3efb85e0f74e01be6be5f5d6f7ca90b60f`

Config digest:

`sha256:d7d22779fb87ed760b8b256143d423ccbbf760020d5277b9949759f67afbab12`

Declared referenced bytes:

`18593967008`

Referenced blobs:

`4`

All referenced blobs are present.

### Model 4

Reference:

`qwen3:8b`

Manifest SHA-256:

`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`

Config digest:

`sha256:05a61d37b08453e59290add468e3bb2f688e23a01e967fecb0e2fa41218cea76`

Declared referenced bytes:

`5225388164`

Referenced blobs:

`5`

All referenced blobs are present.

### Model 5

Reference:

`qwen3-coder-next:latest`

Manifest SHA-256:

`ca06e9e4087c714d44355bf954099187890e63084b4a632b8e9956c4b9492074`

Config digest:

`sha256:5d55cac51f303b790c7fafb707fbec596ad64c7af9282619aa7dc88a37646d4c`

Declared referenced bytes:

`51741611823`

Referenced blobs:

`4`

All referenced blobs are present.

### Model 6

Reference:

`qwen3.8:27b`

Manifest SHA-256:

`22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643`

Config digest:

`sha256:492b2922d38e553cabc2d319345644ed482874fbf5e5c9e4495cbf8e17b0cf5f`

Declared referenced bytes:

`17741872154`

Referenced blobs:

`5`

All referenced blobs are present.

### Listener boundary

Exactly one Ollama TCP listener was identified.

It is:

- loopback-only
- TCP port `11434`

The raw listener address was not printed.

This confirms that the current Ollama API is not exposed on all interfaces by the observed service state.

### Pipeline interpretation

Item 12L captures the Ollama runtime as installed infrastructure.

Combined with item 12K, the current evidence is:

- Ollama is installed
- Ollama is running
- Ollama is enabled
- six local model manifests are complete
- model blobs required by those manifests are present
- the API listener is loopback-only
- no application-specific network-observability pipeline caller has been identified

The existence of the models and running runtime must therefore remain distinct from production LLM orchestration.

### Safety boundary

Item 12L:

- did not call the Ollama API
- did not run an Ollama model operation
- did not execute inference
- did not pull a model
- did not read model blob contents
- read model manifest metadata
- did not print unknown environment values
- did not print raw listener addresses
- did not open the production application database
- did not read production event rows
- did not make an external network request
- did not request a filesystem write

All three previously captured GX10 pipeline executables retained their expected SHA-256 values after the inspection.

### Item 12L conclusion

The active Ollama service, its systemd contract, executable provenance, model-storage contract, six-manifest inventory, complete referenced-blob state, and loopback listener boundary are now captured.

The executable is not dpkg-owned, so later rebuild implementation must explicitly provide an Ollama installation mechanism rather than assuming the Debian package database can reproduce the current binary.

That later installation design must remain separate from this rediscovery record.

### Next action

Continue rediscovery with the SQLite/base-state bootstrap and schema-creation provenance.

Determine how the live application database and initial tables/rules were originally created, or establish that no surviving bootstrap artifact exists.

Do not read production event payload rows.

After database/bootstrap provenance is bounded, capture GX10 runtime identity, directory, ownership, permission, and dependency contracts.

No GX10 rebuild implementation work begins until the rediscovery closure checkpoint is published.

## 2026-08-23 13:37 PDT - GX10 item 12M SQLite schema and bootstrap provenance

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

A read-only immutable SQLite metadata inspection recovered the complete current application schema and bounded the search for its original bootstrap/initializer provenance.

No production event payload rows or suppression-rule rows were selected.

### Database-path consistency

All three captured GX10 application components contain exactly one absolute SQLite database-path literal.

All three resolve to the same live database path.

The private live path remains withheld.

Path-value SHA-256:

`bb6b9179d182ada7a636a1fe40bdeb79b6874382c013d3604a67db2d53a1a430`

Current database size:

`1798782976` bytes

Current mode:

`0640`

### SQLite metadata

The database was opened read-only and immutable with SQLite query-only mode enabled.

Observed metadata:

- `query_only=1`
- `user_version=0`
- `application_id=0`
- `schema_version=26`

There is no surviving nonzero SQLite application or migration-version identifier.

### Schema inventory

Noninternal SQLite schema objects:

`18`

Expected schema objects:

`18`

Unexpected schema objects:

`0`

The effective application schema contains:

- 5 application tables
- 13 explicit application indexes
- 3 foreign-key relationships

### Table `agent_state`

Normalized live DDL:

    CREATE TABLE agent_state ( key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL )

Normalized SQL SHA-256:

`8488a9c5f878e1979979c6bdb7868e6f6dffc9ba29592c02f3046fb55e83f3f2`

### Table `event_enrichment`

Normalized live DDL:

    CREATE TABLE event_enrichment ( event_id INTEGER PRIMARY KEY, event_code TEXT NOT NULL DEFAULT '', family TEXT NOT NULL DEFAULT 'unknown', device TEXT NOT NULL DEFAULT '', entity_type TEXT, entity_key TEXT, state TEXT, attention_eligible INTEGER NOT NULL DEFAULT 1 CHECK ( attention_eligible IN (0,1) ), suppression_rule_id INTEGER, classified_at TEXT NOT NULL, repeat_count INTEGER NOT NULL DEFAULT 1, classification_version INTEGER NOT NULL DEFAULT 0, vendor_hint TEXT NOT NULL DEFAULT 'unknown', protocol TEXT NOT NULL DEFAULT '', signal_type TEXT NOT NULL DEFAULT 'observation', attributes_json TEXT NOT NULL DEFAULT '{}', FOREIGN KEY(event_id) REFERENCES recent_events(id), FOREIGN KEY(suppression_rule_id) REFERENCES suppression_rules(id) )

Normalized SQL SHA-256:

`1a3d2819432ce6a4fbbbff6a9c1bbfb657f58ebe48f325358fd75f04fce83bf6`

### Table `recent_events`

Normalized live DDL:

    CREATE TABLE recent_events ( id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT NOT NULL, record_number INTEGER NOT NULL, timestamp TEXT NOT NULL, device_timestamp TEXT, hostname TEXT, source_ip TEXT, source_port INTEGER, facility TEXT, severity TEXT, message TEXT NOT NULL, raw_message TEXT, parse_status TEXT, parser TEXT, event_json TEXT NOT NULL, timestamp_epoch_ms INTEGER, FOREIGN KEY(source_file) REFERENCES source_files(remote_path), UNIQUE(source_file, record_number) )

Normalized SQL SHA-256:

`5e1c4e91a37f75421d445f75bae0830244a132f0193908e7f996bf90bf552e9e`

### Table `source_files`

Normalized live DDL:

    CREATE TABLE source_files ( remote_path TEXT PRIMARY KEY, local_path TEXT, size_bytes INTEGER, sha256 TEXT, status TEXT NOT NULL DEFAULT 'discovered' CHECK ( status IN ( 'discovered', 'downloaded', 'processing', 'processed', 'failed' ) ), discovered_at TEXT NOT NULL, downloaded_at TEXT, processed_at TEXT, error TEXT , record_count INTEGER)

Normalized SQL SHA-256:

`0b6219e204290200b2856b0afc34661ebadb31836ebb3f531de7fac23024d781`

### Table `suppression_rules`

Normalized live DDL:

    CREATE TABLE suppression_rules ( id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, rule_type TEXT NOT NULL CHECK ( rule_type IN ( 'event_code_exact', 'event_code_prefix', 'message_regex' ) ), pattern TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)), reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL )

Normalized SQL SHA-256:

`1262051a43077190c96ae1b6549dd3683bed38375d102319c96431b3f60366ec`

### Explicit indexes

Enrichment indexes:

    CREATE INDEX idx_enrichment_attention ON event_enrichment(attention_eligible)
    CREATE INDEX idx_enrichment_entity ON event_enrichment(entity_type, entity_key)
    CREATE INDEX idx_enrichment_event_code ON event_enrichment(event_code)
    CREATE INDEX idx_enrichment_family ON event_enrichment(family)
    CREATE INDEX idx_enrichment_protocol ON event_enrichment(protocol)
    CREATE INDEX idx_enrichment_signal_type ON event_enrichment(signal_type)
    CREATE INDEX idx_enrichment_vendor_hint ON event_enrichment(vendor_hint)

Recent-event indexes:

    CREATE INDEX idx_recent_events_device_epoch ON recent_events(hostname, timestamp_epoch_ms)
    CREATE INDEX idx_recent_events_device_time ON recent_events(hostname, timestamp)
    CREATE INDEX idx_recent_events_epoch ON recent_events(timestamp_epoch_ms)
    CREATE INDEX idx_recent_events_severity_time ON recent_events(severity, timestamp)
    CREATE INDEX idx_recent_events_source_ip_time ON recent_events(source_ip, timestamp)
    CREATE INDEX idx_recent_events_timestamp ON recent_events(timestamp)

### Foreign-key contract

Exactly three foreign-key relationships are present:

`event_enrichment.suppression_rule_id -> suppression_rules.id`

`event_enrichment.event_id -> recent_events.id`

`recent_events.source_file -> source_files.remote_path`

### Suppression-state relationship

Item 12H separately captured the complete current functional suppression corpus:

- exactly two rows
- both enabled
- both `event_code_exact`
- both public-safe patterns already recorded
- zero non-allowlisted patterns

Item 12M did not select those application rows again.

The recovered table DDL plus the item-12H corpus capture provide the current suppression schema/state contract for later reconstruction.

### Bootstrap-artifact search

A bounded search of relevant systemd, cron, `/usr/local`, bounded `/opt`, login-user-home, and root-home artifacts returned:

`bootstrap_candidate_count=0`

No surviving external artifact was identified containing strong evidence of:

- application table creation
- application index creation
- multi-table SQLite bootstrap
- suppression-rule seeding

### Saved-history bootstrap evidence

Login-account Bash history:

- create-table references: `0`
- SQLite/table references: `0`
- suppression-seed references: `0`

Root Bash history:

- create-table references: `0`
- SQLite/table references: `0`
- suppression-seed references: `0`

No shell-history command text was printed.

### Bootstrap provenance conclusion

No surviving bootstrap/initializer artifact was found in the bounded live-system search.

No retained shell-history bootstrap command was found.

This does not prove an initializer never existed.

It establishes that its original provenance is not recoverable from the surviving artifacts inspected during rediscovery.

The historical loss does not prevent deterministic reconstruction because the complete current effective SQLite schema has now been recovered directly from SQLite metadata.

The later rebuild can create a clean database from this recovered schema contract rather than inventing undocumented historical migration behavior.

### Safety boundary

Item 12M:

- opened the application database read-only and immutable
- enabled SQLite query-only mode
- inspected schema metadata
- did not select application rows
- did not read production event payload rows
- did not select suppression-rule rows
- did not read authorized keys
- did not read SSH private material
- did not print bootstrap candidate contents
- did not print shell-history commands
- did not execute pipeline components
- did not make a network request
- did not request a GX10 filesystem write

All three known GX10 pipeline executable hashes remained unchanged.

### Item 12M conclusion

GX10 SQLite data-model rediscovery is complete.

Captured:

- one shared database-path contract
- current database mode and size
- SQLite metadata/version state
- all five application table definitions
- all thirteen explicit application indexes
- all three foreign-key relationships
- zero unexpected schema objects
- zero surviving bounded bootstrap candidates
- zero retained shell-history bootstrap evidence

The original initializer should no longer be treated as an undiscovered component that must exist.

### Next action

Continue rediscovery with the GX10 runtime identity and filesystem/dependency contract.

Capture:

- application service account and group properties
- pipeline directories
- ownership and modes
- SFTP key and known-hosts metadata without reading private key material
- Python/runtime dependencies
- required external executables
- systemd filesystem-access restrictions
- any final application bootstrap/configuration artifacts

Then perform the final bounded GX10 rediscovery closure audit.

No GX10 rebuild implementation begins until that closure checkpoint is published.

## 2026-08-23 15:54 PDT - GX10 item 12N runtime and external-dependency contract complete

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The direct-access VM resume preconditions and the corrected item-12N external-executable dependency/provenance slice completed successfully.

Item 12N is now complete. The final bounded GX10 rediscovery closure audit remains outstanding before any GX10 rebuild implementation begins.

### Direct-access resume verification

The local repository was clean and matched public GitHub `main` at:

`3e4a7044c9bb13d5404301bd1069974288f2166e` — `auth test`

That commit is an empty authentication-test commit whose tree is unchanged from the documented handoff commit:

`d9d85f0e79c9187ec2e1c99fd6e83f09bf8b7fc8` — `Record direct-access VM execution decision`

Authenticated read-only SSH command execution succeeded against both reference-system roles from the VM.

The collector alias initially attempted the default SSH port and received a connection refusal. A one-shot connection using the already-captured nonstandard transport port from the GX10 fetch contract succeeded. The private port value, host identity, username, key path, and address were not printed or committed, and the VM SSH configuration was not modified.

### Artifact-integrity precondition

The three known GX10 application executables each had exactly one live match for the previously captured SHA-256 value:

- fetch: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- ingest: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- deterministic enrichment: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

The pipeline service unit also had exactly one live match for its captured SHA-256 value:

`0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`

### Corrected external-executable detector

The defective item-12N dependency slice was rerun with a corrected AST-based analyzer.

The correction resolves command values through:

- literal lists, tuples, sets, and dictionaries
- assigned variables
- concatenated and conditional expressions
- starred values
- helper-function arguments and return values
- nested calls passed to Python `subprocess` operations

This corrects the earlier false-zero result, which failed to follow the helper-function return that constructs the SFTP command.

Corrected source and invocation results:

- SFTP source references: `1`
- SFTP subprocess invocations: `1`
- SFTP referencing components: `1`
- Zstandard source references: `4`
- Zstandard subprocess invocations: `2`
- Zstandard referencing components: `2`
- total external-tool source references: `5`
- external-tool dependency count: `2`
- `external_tool_detector=PASS`

This result reconciles item 12N with the already-proven item-12C, item-12D, and item-12F transport/decompression behavior.

### Installed executable provenance

Both required external executables are present and owned by installed Ubuntu packages:

- `sftp`: package `openssh-client`, version `1:9.6p1-3ubuntu13.18`
- `zstd`: package `zstd`, version `1.5.5+dfsg2-2build1.1`

Combined with the already-captured Python contract, the known custom GX10 application dependency set is:

- Python `3.12.3`
- Python SQLite runtime `3.45.1`
- Python package provenance `python3.12-minimal` version `3.12.3-1ubuntu0.15`
- zero third-party Python imports
- OpenSSH client package for SFTP
- Zstandard CLI package

### Postcheck and safety boundary

All three application hashes remained unchanged after the corrected analysis.

The item-12N completion work:

- read application source only for static analysis
- did not print application source
- did not print private runtime account or group names
- did not print private paths or connection values
- did not read SSH private-key contents
- did not read known-hosts contents
- did not open the production application database
- did not read production event rows
- did not execute a pipeline component
- did not request a GX10 filesystem write
- did not modify either reference system

### Item 12N conclusion

The runtime identity, filesystem ownership/mode, SSH-material metadata, systemd sandbox, Python runtime/import, and external-executable dependency/provenance contracts are now complete.

The earlier zero-external-tool result is superseded by the corrected validated result above.

### Next action

Run the final bounded GX10 rediscovery closure audit.

The closure audit must reconcile the journaled item-12A through item-12N evidence, verify the known live artifact hashes again, bound any remaining application bootstrap/configuration gaps, update durable GX10 rebuild status/current-state documentation, and publish the rediscovery-complete checkpoint.

No GX10 rebuild implementation begins until that closure checkpoint is published.

## 2026-08-23 16:01 PDT - GX10 rediscovery closure complete

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item and now advances from rediscovery to public reconstruction.

The final bounded GX10 live-system rediscovery closure audit passed. Items 12A through 12N now account for the current functional application artifacts, runtime contracts, preserved absences, and effective state required to begin clean-machine reconstruction.

No GX10 rebuild implementation was started before this closure.

### Durable item-12N prerequisite

The completed item-12N runtime/dependency checkpoint was published and independently verified on GitHub at:

`8c06822` — `Journal GX10 runtime dependencies`

### Live closure audit

Authenticated read-only connectivity to both reference-system roles was revalidated.

The final GX10 audit found exactly one live match for each captured critical artifact:

- fetch executable: `1`
- ingest executable: `1`
- deterministic-enrichment executable: `1`
- pipeline service unit: `1`
- pipeline timer unit: `1`

The exact captured hashes remain:

- fetch: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- ingest: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- deterministic enrichment: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`
- pipeline service unit: `0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`
- pipeline timer unit: `5371995539846d4cca6014a70548e95c942e9f601d0736b06f4bda61c1ccc0f5`

The active service/timer contract also passed:

- service `Type=oneshot`
- service static
- timer active and enabled
- service directly references fetch and ingest
- zero service, other systemd, or cron enrichment references
- required SFTP and Zstandard executables present and package-owned
- all five critical hashes unchanged in the postcheck
- `gx10_rediscovery_live_closure_audit=PASS`

### Evidence reconciliation

The completed rediscovery record now covers:

- Ubuntu/arm64/NVIDIA GB10, driver, CUDA, Python, and SQLite runtime baselines
- timer/service scheduling, hardening, identity, filesystem-access, and provenance contracts
- SFTP backlog discovery/fetch/catch-up and Zstandard verification behavior
- replay-safe streaming ingest, local SQLite behavior, and effective schema
- deterministic enrichment/classification version 3 and the complete two-rule suppression corpus
- runtime account, group, directory, ownership, mode, SSH-material metadata, and dependency contracts
- Ollama service, executable, loopback listener, model storage, and six complete model manifests
- absence of a surviving bounded base-schema/bootstrap initializer
- absence of a discovered automatic deterministic-enrichment invocation
- absence of a discovered application-specific observability-pipeline Ollama caller
- absence of a discovered GX10 producer for the collector result-return boundary

No open rediscovery target remains that blocks faithful public reconstruction of the currently proven GX10 state.

### Durable documentation update

Created `components/gx10/REBUILD_STATUS.md` as the active component recovery authority.

Updated:

- `components/gx10/README.md`
- `docs/START_HERE.md`
- `docs/CURRENT_STATE.md`
- `docs/AI_HANDOFF.md`
- `docs/ROADMAP.md`

The documents now record the captured contracts, private-input boundary, preserved rediscovery conclusions, and bounded reconstruction order.

`docs/CURRENT_STATE.md` continues to contain exactly one `NEXT` item. Item 12 now directs reconstruction to begin with the public-safe operator-input and filesystem/runtime identity contract.

### Credential-file boundary

The operator identified an external GitHub token file under the VM's `Dev` area. The file was not read. A presence-only check confirmed it is outside the repository, and no `token.txt` is tracked or present in the repository working tree.

GitHub operations continued through the already-working VM credential setup.

### Safety boundary

The closure audit:

- did not execute a pipeline component
- did not open the production application database or read production event rows
- did not read SSH private-key or known-hosts contents
- did not print private paths, identities, addresses, ports, or credentials
- did not call Ollama or run inference
- did not write to either reference system or change service state

### Rediscovery closure conclusion

GX10 live-system rediscovery is complete.

The following distinctions are reconstruction requirements, not unresolved discovery tasks:

- automatic application behavior is `timer -> fetch -> ingest`
- deterministic enrichment exists without a discovered automatic schedule
- Ollama/model infrastructure exists without a discovered observability-pipeline caller
- the collector result-return boundary exists without a discovered GX10 producer
- missing historical bootstrap/install provenance must be reconstructed from captured effective contracts rather than invented as recovered history

### Next action

Begin the first bounded public GX10 reconstruction subsection:

1. define operator-supplied private inputs
2. define the dedicated runtime identity contract
3. define public-safe filesystem roles, ownership, and modes
4. add structural/public-safety validation for that contract

Do not execute clean-machine installation logic against the working GX10 reference system.

## 2026-08-23 16:10 PDT - GX10 reconstruction filesystem and operator-input contract

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The first bounded public GX10 reconstruction subsection is complete and validated.

### Implemented artifacts

Added:

- `components/gx10/config/operator-inputs.env.example`
- `components/gx10/install/filesystem-contract.env`
- `components/gx10/install/install-filesystem.sh`
- `components/gx10/tests/validate-filesystem-contract.sh`

Updated:

- `components/gx10/README.md`
- `components/gx10/REBUILD_STATUS.md`
- `docs/CURRENT_STATE.md`

### Operator-input boundary

The repository template contains only synthetic values.

Deployment-specific SFTP hostname, port, username, private-key source path, and known-hosts source path are operator inputs. The populated file must remain outside the repository.

Private key and known-hosts inputs must be regular, nonempty files with mode `0400` or `0600`.

No private input content is accepted directly as a command-line value or stored in the public repository.

### Runtime identity and filesystem contract

The public rebuild uses neutral identity and path names rather than publishing historical private live names.

The clean-machine contract defines:

- one dedicated locked non-login system user/group
- a runtime home under `/var/lib`
- an SSH-material parent under the runtime home
- incoming, processed, and temporary spool roles under `/var/spool`
- an application-state directory and database path under the runtime home
- a root-owned application executable directory under `/usr/local/libexec`

Modes preserve the captured live security contract:

- SSH-material parent: `0700`
- private key: `0600`
- known-hosts file: `0600`
- runtime home/state/spool directories: `0750`
- application database: reserved for later creation at `0640`
- executable directory: root-owned `0755`

UID and GID are allocated as system identities rather than pinning the live numeric IDs.

### Clean-machine safety behavior

`install-filesystem.sh`:

- requires root
- requires `CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10`
- requires explicit private input files
- validates input type, nonempty state, and restrictive modes
- creates or verifies the neutral runtime identity
- locks the runtime account
- verifies any existing account has the expected group, home, and `nologin` shell
- refuses an existing application database
- never overwrites divergent installed SSH material
- creates directories with explicit ownership and modes

The installer is clearly scoped to a clean machine and was not run against the working GX10 reference system.

### Validation

The non-mutating validator checks:

- shell syntax
- fixed neutral identity and path relationships
- clean-machine confirmation and existing-database refusal guards
- runtime directory, SSH directory, and private-file mode contracts
- account lock and non-login shell requirements
- synthetic example hostname use
- secret-like content
- accidental private key, token, or SQLite files

Result:

`GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`

The initial validator run self-matched its own secret signatures. The detector was corrected to construct those signatures from split literals, after which the intended GX10 component scan passed.

### Safety boundary

This subsection:

- did not read the operator's external GitHub token file
- did not copy or read live GX10 private-key or known-hosts contents
- did not publish live hostnames, addresses, ports, usernames, paths, or credentials
- did not execute the filesystem installer
- did not write to either reference system
- did not change service state

### Next action

Publish this validated subsection, verify GitHub, then begin capture of the three public-safe application implementations.

Before publication, derive private configuration literals out of the captured live sources and preserve the recorded fetch, ingest, and deterministic-enrichment semantics with public-safe fixtures and tests.

## 2026-08-23 16:13 PDT - GX10 public application source capture

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The three custom GX10 application implementations are captured in public-safe form and validated without executing them against the working reference system.

### Captured applications

Added:

- `components/gx10/sbin/fetch-spool.py`
- `components/gx10/sbin/ingest-spool.py`
- `components/gx10/sbin/enrich-events.py`
- `components/gx10/sbin/runtime_config.py`
- `components/gx10/sbin/PROVENANCE.md`

Live provenance remains:

- fetch: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- ingest: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- deterministic enrichment: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

Public captured SHA-256 values are intentionally different because private configuration literals were removed and the AST was rendered into neutral formatting:

- fetch: `a5b034b238ee137f65e71fc0bb5fc3e8702aa4bbfcb8a02fbbbe1167011b9db3`
- ingest: `f011976372191ebb8536376e4ec170e317aa4b9c89849ed2fa68db4b40e4499f`
- deterministic enrichment: `0c34343452c8d7c761e5b3b073c8e0f14291db32162b6eea3764148edff7dc46`
- runtime configuration loader: `8474e670581afe3ffb0d7d32c21fd605f2c1b6fe0e4f7dad55de4e2a1cc17f5e`

### Public-safety transformation

The source import used a bounded AST rewrite.

It changed only configuration binding:

- live database, spool, key, and known-hosts paths now resolve from `runtime_config.py`
- live SFTP host, port, and username now resolve from a protected JSON runtime configuration
- the already-public `/spool/%Y/%m/%d/%H` remote chroot pattern remains fixed
- public `/usr/bin/sftp` and `/usr/bin/zstd` executable paths remain fixed

The import gate rejected the first attempt when private absolute literals remained inside function bodies. Those duplicate literals were resolved by exact captured hashes and replaced before any source reached the public working tree.

The sole extra absolute fetch literal was classified by hash as the already-journaled public remote-hour format, not an application executable path.

No deployment IPv4 literal or non-public absolute path survived the final import gate.

### Function-level parity

All live and public function ASTs were compared by function name and canonical AST hash.

The first comparison differed on every function because Python 3.12 includes a `type_params` AST metadata field that the VM's local Python 3.9 does not expose.

After excluding only that version-specific metadata field:

- compared function count: `27`
- differing function count: `0`
- `gx10_live_function_ast_parity=PASS`

This covers every fetch, ingest, and deterministic-enrichment function.

### Protected runtime configuration

Added:

- `components/gx10/install/render-runtime-config.py`

The renderer:

- accepts only SFTP host, port, and username inputs
- validates input syntax without echoing rejected values
- supports a non-writing `--check` mode
- writes a fixed protected JSON path only when run as root
- uses atomic creation
- installs mode `0640` with root/runtime-group ownership
- refuses divergent existing content
- refuses symbolic or hard-linked existing configuration

The runtime loader:

- requires exactly the three expected keys
- rejects oversized or malformed configuration
- validates and normalizes the port
- supplies only neutral public filesystem paths to the applications

### Filesystem hardening follow-up

The clean-machine filesystem bootstrap was also hardened to:

- refuse symbolic-link private inputs and destinations
- refuse hard-linked installed private files
- reject an existing runtime account with supplementary groups
- explicitly require all commands it invokes

### Validation

Results:

- 12 synthetic application/configuration tests passing
- `GX10_RUNTIME_CONFIG_INPUT=PASS`
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `gx10_python_compile=PASS`
- `gx10_live_function_ast_parity=PASS`
- `gx10_live_application_postcheck=PASS`
- `gx10_private_file_scan=PASS`
- `gx10_secret_scan=PASS`

Synthetic tests cover:

- strict SFTP command construction and host-key options
- fixed remote-hour path contract
- timestamp/timezone behavior
- repeat-notice classification
- synthetic BGP recovery classification
- synthetic OSPF retransmission degradation classification
- runtime configuration validation and exact-key policy
- rejected-value non-echo behavior
- symlink refusal
- deployment IPv4 and private-path scanning

### Preserved scheduling boundary

This checkpoint captures deterministic enrichment source for faithful reconstruction and migration parity.

It does not add enrichment to the automatic service chain.

The proven automatic behavior remains:

`timer -> fetch -> ingest`

### Safety boundary

This subsection:

- did not execute any captured application
- did not open the production database
- did not read production event or suppression rows
- did not contact the collector through the application SFTP identity
- did not read live SSH private-key or known-hosts contents
- did not print or commit private live source values
- did not write to either reference system
- did not change service state

All three live application hashes remained unchanged after capture and validation.

### Next action

Publish this checkpoint and independently verify GitHub.

Then implement deterministic SQLite initialization from the complete effective schema captured in item 12M, including the two public-safe suppression rules captured in item 12H.

## 2026-08-23 16:17 PDT - GX10 deterministic SQLite initialization

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The clean-machine SQLite initialization subsection is implemented and validated from the effective schema recovered in item 12M.

### Implemented artifacts

Added:

- `components/gx10/sql/initialize.sql`
- `components/gx10/install/initialize-database.py`
- `components/gx10/tests/test_database_initialization.py`

Updated:

- `components/gx10/README.md`
- `components/gx10/REBUILD_STATUS.md`
- `docs/CURRENT_STATE.md`

### Effective-schema reconstruction

The SQL initializer creates exactly:

- 5 application tables
- 13 explicit application indexes
- 3 foreign-key relationships
- 18 noninternal table/index objects

The five `sqlite_master` table definitions reproduce the normalized SHA-256 values captured from the live database:

- `agent_state`: `8488a9c5f878e1979979c6bdb7868e6f6dffc9ba29592c02f3046fb55e83f3f2`
- `event_enrichment`: `1a3d2819432ce6a4fbbbff6a9c1bbfb657f58ebe48f325358fd75f04fce83bf6`
- `recent_events`: `5e1c4e91a37f75421d445f75bae0830244a132f0193908e7f996bf90bf552e9e`
- `source_files`: `0b6219e204290200b2856b0afc34661ebadb31836ebb3f531de7fac23024d781`
- `suppression_rules`: `1262051a43077190c96ae1b6549dd3683bed38375d102319c96431b3f60366ec`

SQLite `user_version` and `application_id` remain zero, matching the captured live contract.

### Suppression seed

The initializer seeds exactly two enabled rules in ascending ID order:

1. exact event code `ICMPV6-3-ND_LOG`
2. exact event code `ICMPV6-3-ND_RA_LOG`

Rediscovery intentionally did not expose the live rule-name and reason literals because they are nonfunctional metadata. The public initializer uses neutral reconstructed names/reasons and a deterministic neutral seed timestamp.

The functional rule IDs, order, type, pattern, and enabled state match the captured live corpus.

### Clean-machine initializer behavior

`initialize-database.py`:

- requires root and `CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10`
- uses the fixed public database path and runtime identity
- refuses an existing file or symbolic link at the database path
- refuses a missing/symlinked schema source or invalid database parent
- creates a temporary SQLite database in the target directory
- executes the recovered schema and seed transaction
- requires `PRAGMA quick_check=ok`
- requires exactly 18 noninternal schema objects
- requires the exact functional suppression corpus
- installs runtime ownership and mode `0640`
- publishes with a no-overwrite hard-link operation rather than replacement
- removes the temporary file on success or failure

The no-overwrite publication closes a race in which an unexpected target created after the initial existence check could otherwise have been replaced.

### Compatibility proof

Both captured application schema migrators were executed only against a synthetic initialized temporary database:

- ingest `ensure_schema()`
- deterministic-enrichment `ensure_schema()`

Before/after `sqlite_master` definitions were identical.

This proves that the recovered effective schema already contains every column/index expected by both captured migrators.

### Validation

The full GX10 reconstruction suite now reports:

- 18 tests passing
- all 5 recovered table DDL hashes exact
- 13 explicit indexes
- 3 foreign keys
- 2 exact functional suppression rules
- `PRAGMA quick_check=ok`
- database mode `0640`
- empty application event/state tables
- existing-database refusal passing
- captured schema-migrator no-op proof passing
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `gx10_python_compile=PASS`

### Safety boundary

This subsection:

- used only temporary synthetic databases
- did not open or copy the production database
- did not read production event, enrichment, or suppression rows
- did not execute a captured application against live state
- did not run the clean-machine initializer on GX10
- did not write to either reference system
- did not change service state

### Next action

Publish this validated SQLite checkpoint and independently verify GitHub.

Then implement public service/timer templates preserving the captured `timer -> fetch -> ingest` chain, cadence, hardening, runtime identity, writable paths, and absence of automatic enrichment invocation.

## 2026-08-23 16:19 PDT - GX10 service and timer reconstruction

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The live GX10 service/timer definitions are captured in public-safe form, and the clean-machine application/unit installation boundary is implemented and validated.

### Live unit capture

The live files were resolved by their recorded SHA-256 values:

- service: `0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`
- timer: `5371995539846d4cca6014a70548e95c942e9f601d0736b06f4bda61c1ccc0f5`

Added public units:

- `components/gx10/systemd/network-log-gx10.service`
- `components/gx10/systemd/network-log-gx10.timer`
- `components/gx10/systemd/PROVENANCE.md`

Public hashes:

- service: `6970f861fcde7e2f1c59a80264fa79ddda6a6ceb2f9dc3511afbd5c88bf694bf`
- timer: `25939b7ce8f424840cef35ebc58635919d706b104408094d164e342081a77436`

### Sanitized identity boundary

The capture replaced only:

- identity-bearing unit descriptions/filenames
- private live service user/group names
- private application executable paths
- private state/spool writable paths
- the timer's identity-bearing target unit name

The sanitizer required:

- exactly two known `ExecStart` programs
- fetch followed by ingest
- exactly two known writable path roles
- no environment or environment-file directives
- no unknown absolute paths
- no IPv4 literals

### Preserved service contract

The public service retains:

- `Type=oneshot`
- the two ordered `ExecStart` operations
- neutral dedicated runtime user/group
- `UMask=0027`
- `NoNewPrivileges=yes`
- `PrivateTmp=yes`
- `PrivateDevices=yes`
- `ProtectSystem=strict`
- `ProtectHome=yes`
- state and spool as the only writable path roles
- `ProtectKernelTunables=yes`
- `ProtectKernelModules=yes`
- `ProtectKernelLogs=yes`
- `ProtectControlGroups=yes`
- `RestrictNamespaces=yes`
- `LockPersonality=yes`
- empty capability bounding and ambient sets
- `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`

Several of these hardening directives were beyond the shorter handoff summary but were preserved from the complete live file.

Deterministic enrichment remains absent from `ExecStart`.

### Preserved timer contract

The timer retains:

- `OnBootSec=2min`
- `OnUnitInactiveSec=1min`
- `AccuracySec=5s`
- no calendar schedule
- no randomized-delay directive
- target `network-log-gx10.service`
- installation under `timers.target`

### Clean-machine application/unit installer

Added:

- `components/gx10/install/install-applications.py`
- `components/gx10/tests/test_application_install.py`
- `components/gx10/tests/test_systemd_contract.py`

The installer:

- requires root and `CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10`
- requires the initialized database at runtime-user/runtime-group mode `0640`
- requires the rendered runtime configuration at root/runtime-group mode `0640`
- requires both prerequisite files to be regular, non-symlinked, and single-linked
- preflights every source and destination before installation
- reuses exact existing artifacts only
- refuses divergent, symbolic-link, or hard-linked destinations
- publishes each new file atomically without replacement
- installs application executables root-owned mode `0755`
- installs the configuration module and units root-owned mode `0644`
- runs `systemd-analyze verify`
- reloads systemd only after all artifacts validate
- does not enable or start the timer/service

### Validation

The full GX10 suite now reports:

- 26 tests passing
- exact fetch-then-ingest order
- deterministic enrichment absent from automatic execution
- all live hardening directives present
- exact two-role writable-path boundary
- exact timer cadence
- atomic install/reuse passing
- divergent/symlink/hard-link refusal passing
- database/config ownership and mode preflight passing
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `gx10_python_compile=PASS`

### Safety boundary

This subsection:

- read only the two known live unit files
- did not print or publish private unit names, users/groups, or paths
- did not execute any pipeline application
- did not install a unit on GX10
- did not call `daemon-reload` on GX10
- did not enable, disable, start, stop, or restart any service/timer
- did not write to either reference system

### Next action

Publish this checkpoint and independently verify GitHub.

Then implement package/Ollama verification and the final clean-machine activation/runtime verification flow without claiming or creating an application-specific Ollama caller.

## 2026-08-23 16:25 PDT - GX10 package and Ollama reconstruction

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The captured platform dependency and Ollama infrastructure contracts are now represented by guarded public installers and fail-closed verifiers.

### Platform and package boundary

Added:

- `components/gx10/install/versions.env`
- `components/gx10/install/install-packages.sh`
- `components/gx10/install/verify-platform.py`

The version manifest records the captured public baseline for:

- Ubuntu 24.04 arm64
- kernel `6.17.0-1029-nvidia`
- NVIDIA driver `580.173.02`
- CUDA compiler build `V13.0.88`
- Python `3.12.3` and SQLite runtime `3.45.1`
- `python3.12-minimal` version `3.12.3-1ubuntu0.15`
- `openssh-client` version `1:9.6p1-3ubuntu13.18`
- `zstd` version `1.5.5+dfsg2-2build1.1`

The package installer requires root and `CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10`, checks the operating-system/architecture boundary, and installs only the exact three application-level Debian package versions.

Rediscovery did not recover trustworthy kernel, driver, or CUDA installation provenance. The public rebuild therefore verifies those prerequisites rather than inventing an installer and representing it as recovered history.

The first privileged revalidation probe could not resolve `nvcc` through its reduced command path. A bounded read-only path check established that the captured compiler is present at `/usr/local/cuda/bin/nvcc`. The verifier now invokes that exact public path. This was command-path resolution, not platform drift.

The complete live platform verifier then returned:

`GX10_PLATFORM_VERIFY=PASS`

### Ollama installation boundary

Added:

- `components/gx10/systemd/ollama.service`
- `components/gx10/install/install-ollama.py`
- `components/gx10/install/verify-ollama.py`
- `components/gx10/tests/test_ollama_contract.py`

The public unit preserves the live executable, service identity, restart behavior, service environment, and enablement target. Only the description was neutralized.

- live unit SHA-256: `11758d469d3f103e53a9612a8ffcb3a3e61834c994c08d412bb051f3c827dbd3`
- public unit SHA-256: `d8774a8a664856242805d0e5a78297db31865e2b56727edd8d16764921858cd4`

The clean-machine installer:

- requires root and the explicit clean-machine confirmation
- requires an operator-supplied exact Ollama binary
- verifies captured size `35792104` and SHA-256 `26f44ca89143f2326a3aad98b2cb5e8b5af9397aef7001cd8d022e90d6e0b55e`
- creates or validates the locked `ollama` service identity and protected model root
- installs the binary and unit atomically without replacing divergent files
- validates the unit and reloads systemd
- does not enable or start the service

The public repository does not contain the large model blobs. They remain an external operator-supplied prerequisite which must match the captured offline model-store contract before activation.

### Ollama verification boundary

The offline verifier requires:

- the exact executable size/hash and public unit hash
- the captured service identity, model-root ownership, and mode
- exactly six expected manifest paths and hashes
- the captured config digest for every model
- the captured total declared bytes for every manifest
- every referenced blob present as a real nonsymlinked file with its declared size

Normal runtime mode additionally requires:

- `ollama.service` active
- `ollama.service` enabled
- exactly one TCP listener on port `11434`
- that listener bound only to loopback

The verifier does not call the Ollama API or execute a model operation.

After substituting only the already-captured live unit hash for the public sanitized-unit hash, the complete read-only live verifier returned:

`GX10_OLLAMA_VERIFY=PASS`

This revalidated the currently installed binary, live unit, complete model metadata/blob-size contract, service state, enablement, and listener boundary.

### Preserved absence

No installer, unit, verifier, or test connects Ollama to fetch, ingest, deterministic enrichment, or the collector result-return boundary.

The proven automatic application chain remains:

`timer -> fetch -> ingest`

### Validation

The full GX10 suite now reports:

- 31 tests passing
- exact six-manifest inventory contract
- invalid Ollama binary rejection
- symbolic-link model-blob rejection
- fixed captured CUDA compiler path
- no pipeline application reference in the Ollama unit
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- shell syntax validation passing
- Python syntax validation passing with an isolated temporary bytecode cache

### Safety boundary

This subsection:

- did not install packages on either reference system
- did not run any clean-machine installer on GX10
- did not write, copy, or read model blob contents
- did not call the Ollama API
- did not pull a model or run inference
- did not open the production application database
- did not execute the fetch, ingest, or enrichment applications
- did not enable, disable, start, stop, or restart a service/timer
- did not write to either reference system

### Next action

Publish this checkpoint and independently verify GitHub.

Then implement the guarded clean-machine activation and runtime verification flow. It must refuse reference-like/nonempty application state, require every offline prerequisite to validate before activation, preserve the exact automatic chain, and never infer an application-specific Ollama caller.

## 2026-08-23 16:30 PDT - GX10 guarded activation and runtime verification

### Status

`IN PROGRESS` — execution-order item 12 remains the single `NEXT` item.

The final clean-machine activation boundary is now implemented with reference-like-state refusal, complete offline prerequisite verification, exact ordered activation, and failure rollback.

Added:

- `components/gx10/install/verify-runtime.py`
- `components/gx10/install/activate-runtime.py`
- `components/gx10/tests/test_runtime_activation.py`

### Preactivation runtime gate

Before service state can change, the runtime verifier requires:

- the exact neutral runtime identity, primary group, home, non-login shell, locked password, and absence of supplementary groups
- exact public directory ownership and modes
- real nonsymlinked, single-linked private key, known-hosts, configuration, database, application, and unit files
- nonempty protected SSH input files
- an exact three-key runtime configuration with valid host/user/port types, without printing values
- all installed application and pipeline unit bytes identical to their repository sources
- SQLite `quick_check=ok`
- the exact public reconstructed SQLite schema and suppression corpus
- SQLite `user_version=0` and `application_id=0`
- zero rows in all four application state/event tables
- empty incoming, processed, and temporary spool directories
- no SQLite journal/WAL/shared-memory sidecars
- all three required systemd units loaded from the exact public fragment paths
- zero systemd drop-ins for the pipeline service, timer, and Ollama
- the pipeline service static
- the pipeline timer and Ollama disabled
- all three runtime units inactive
- captured effective Ollama hard/soft file-descriptor limits

These checks make accidental execution against an already-used or reference-like deployment fail before activation.

### Full offline model gate

The Ollama verifier now supports `--hash-blobs`.

In addition to the previously validated manifest/path/config/size contract, that mode:

- accepts only canonical lowercase SHA-256 descriptor syntax
- hashes each unique referenced blob once
- compares its content digest with the digest declared by the manifest

The activator always combines `--offline` with `--hash-blobs` before starting Ollama. This can be expensive for the captured model inventory, but it ensures that a correctly named and sized corrupt blob cannot pass activation.

The live reference was not subjected to this content-hashing mode. No live model blob contents were read during this subsection.

### Activation authorization and order

Activation requires root and two exact independent confirmations:

- `CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10`
- `GX10_ACTIVATE_CONFIRM=ENABLE-VERIFIED-GX10`

The activator then runs:

1. platform verification
2. preactivation runtime verification
3. offline Ollama verification with full blob hashing
4. enable/start Ollama
5. wait for exact active Ollama verification
6. enable/start the pipeline timer
7. active runtime verification
8. final active Ollama verification

Only these units become enabled:

- `ollama.service`
- `network-log-gx10.timer`

The pipeline service remains static. Its captured unit still contains only fetch followed by ingest. Deterministic enrichment remains unscheduled.

### Failure rollback

If a post-preflight activation step fails, the activator:

- stops a potentially triggered pipeline service when the timer had been entered
- disables/stops changed units in reverse order
- returns failure instead of claiming a partial activation passed

Preactivation failures make no service-state change.

### Validation

The full GX10 suite now reports:

- 39 tests passing
- exact empty initialized database accepted
- nonempty application state refused
- unexpected schema object refused
- preexisting spool content refused
- both confirmation phrases required
- activation order fixed as Ollama then timer
- full blob hashing required by activation
- valid model content hash accepted and mismatch refused
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- shell and Python syntax validation passing

### Safety boundary

This subsection:

- used only temporary synthetic SQLite databases and model-blob fixtures
- did not execute the activator or runtime verifier against GX10
- did not read the production application database
- did not read live model blob contents
- did not call the Ollama API, pull a model, or run inference
- did not execute fetch, ingest, or deterministic enrichment
- did not enable, disable, start, stop, or restart any reference-system unit
- did not write to either reference system

### Clean-machine validation status

The scripts are synthetically validated but have not been executed end to end on a disposable Ubuntu 24.04 arm64 GX10-class host.

That remains a later validation gate rather than being falsely marked complete.

### Next action

Publish this activation checkpoint and independently verify GitHub.

Then write the complete clean-machine GX10 operator runbook, perform the final item-12 structural/public-safety audit, and close the public rebuild-package milestone without claiming disposable-host validation.

## 2026-08-23 16:35 PDT - GX10 public rebuild-package milestone closure

### Status

Execution-order item 12 is `DONE`.

Execution-order item 13 is `DEFERRED` because no disposable Ubuntu 24.04 arm64 GX10-class clean-machine validation target is currently available.

Execution-order item 14 is now the single `NEXT` item.

The GX10 public reconstruction package, clean-machine runbook, and final repository-only audit are complete.

### Offline model-store installation

The runbook review identified one remaining undocumented hand step: verification existed for a populated model store, but the repository did not yet provide a guarded installation mechanism for the externally supplied large model artifacts.

Added:

- `components/gx10/install/install-model-store.py`

The installer:

- requires root and `CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10`
- requires `OLLAMA_MODEL_STORE_DIR` outside the installed target
- requires the previously installed exact Ollama identity/model-root boundary
- fully verifies and hashes the source six-manifest store before writing
- ignores unreferenced source blobs and copies only the exact referenced inventory
- rejects symbolic-link source/target roots and target symbolic links
- rejects unexpected target files
- preflights every existing target artifact and refuses same-size or different-size divergent content
- creates only protected `ollama:ollama` mode-`0755` directories
- publishes mode-`0644` files atomically without replacement
- copies unique blobs before publishing manifests
- can resume by reusing exact already-copied files
- fully hashes and verifies the installed target store before returning success
- calls no Ollama API, pulls no model, and runs no inference

The verifier now returns its exact manifest/blob inventory to the installer while preserving existing verification behavior.

### Complete operator runbook

Added:

- `components/gx10/CLEAN_MACHINE_RUNBOOK.md`

Expanded:

- `components/gx10/config/operator-inputs.env.example`

The runbook now provides one ordered path covering:

1. clean checkout and repository audit
2. protected external operator inputs
3. exact application package installation and platform verification
4. runtime identity/filesystem/SSH-material bootstrap
5. protected runtime configuration rendering
6. exact empty SQLite initialization
7. application and service/timer installation without activation
8. exact Ollama binary installation without activation
9. offline model-store import
10. preactivation reference-like-state refusal
11. dual-confirmation guarded activation
12. post-activation runtime/Ollama verification
13. first timer-cycle inspection and failure/rerun rules

It explicitly states every preserved absence and warns that activation authorizes the captured automatic read-only fetch followed by local ingest.

No private operator value appears in the runbook or expanded template.

### Final package audit

Added:

- `components/gx10/tests/validate-rebuild-package.py`

The non-mutating audit covers the complete tracked and nonignored-untracked GX10 package inventory and requires:

- real nonsymlinked text artifacts only
- no generated database, key, known-hosts, populated operator-input, token, or bytecode artifact
- no workstation-private path prefix
- no private-key material marker
- no nonapproved IPv4 literal; only loopback/unspecified and documentation networks are accepted
- Python source compilation without bytecode output
- shell syntax validation
- executable shebang and mode validation for install/application/test scripts
- the full GX10 unit-test suite
- the filesystem/public-safety contract validator

Final result:

`GX10_REBUILD_PACKAGE_VALIDATION=PASS`

The complete suite reports:

- 42 tests passing
- exact/resumable model-file installation passing
- same-size divergent target refusal passing
- source/target identity refusal passing
- all prior application, SQLite, systemd, platform, Ollama, and activation tests passing
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`

### Milestone conclusion

The public repository now contains everything known and required to reconstruct the proven GX10 implementation from a clean host plus operator-supplied transport values, exact Ollama binary, and exact offline model store.

The following proven absences remain preserved:

- no automatic deterministic enrichment
- no application-specific network-observability Ollama caller
- no GX10 producer for the collector result-return boundary

The package does not claim those missing future capabilities exist.

### Deferred clean-machine validation

The complete runbook has not been executed on a disposable GX10-class host because none is available.

That external validation remains explicitly deferred, matching the collector milestone's handling of its unavailable disposable Debian target.

No installer or activator was executed against the working reference GX10.

### Safety boundary

This closure subsection:

- used only synthetic temporary files and databases
- did not read or publish private operator values
- did not read production database or model-blob contents
- did not call the Ollama API, pull a model, or run inference
- did not execute fetch, ingest, or enrichment
- did not modify service state
- did not write to either reference system

### Next action

Publish this milestone closure and independently verify GitHub.

Then reconcile project-wide architecture, operations, data/rebuild documentation, and the two component runbooks under execution-order item 14 before final repository sanitation and acceptance validation.

## 2026-08-23 16:40 PDT - Two-server architecture and operations reconciliation

### Status

Execution-order item 14 is `DONE`.

Execution-order item 15 is now the single `NEXT` item.

Project-wide architecture, data, operations, handoff, roadmap, and rebuild documentation now agree with the completed collector/GX10 captures and the preserved rediscovery absences.

### Two-server rebuild authority

Added:

- `docs/TWO_SERVER_REBUILD.md`

The new cross-system runbook coordinates rather than duplicates the component runbooks. It defines:

- one reviewed repository revision on both hosts
- collector-first installation and runtime verification
- collector transport readiness before GX10 activation
- independent backlog-reader and AI-result-writer keypairs
- backlog-reader public key on the collector and matching private key/known-hosts on GX10
- result-writer public key on the collector without claiming or installing a GX10 producer/private key
- GX10 preactivation before transport authorization
- dual-confirmation GX10 activation
- the first automatic read-only fetch/ingest cycle and replay/idempotency evidence
- separate validation of the collector result boundary without claiming an end-to-end GX10 AI-result round trip
- exact public-safe completion evidence for later disposable-host execution

### Current versus target architecture correction

Updated:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_CONTRACTS.md`
- `docs/OPERATIONS.md`

The previous high-level architecture could be read as if the current GX10 automatically performed enrichment, local inference, and result return.

Rediscovery did not prove that path.

The corrected current automatic path is:

`devices -> collector Vector/ClickHouse/backlog -> read-only SFTP -> GX10 fetch -> GX10 ingest`

Separately present boundaries are now shown separately:

- deterministic GX10 enrichment executable, unscheduled
- Ollama/model infrastructure, without an application-specific pipeline caller
- collector write-only result transport/gate/storage, without a GX10 producer

The target incident engine, wake policy, Ollama caller, and result producer remain future architecture.

### Data and operational corrections

`docs/DATA_CONTRACTS.md` now records:

- the current collector backlog file/path/JSONL/Zstandard contract
- GX10 required fields and original-line retention
- the exact five-table/13-index/3-foreign-key working-state boundary
- automatic versus explicitly invoked SQLite writes
- collector result validation limits and the absence of a GX10 producer
- the normalized/incident contracts as validated targets rather than current production claims

`docs/OPERATIONS.md` now records:

- the exact automatic systemd chain and cadence
- unscheduled enrichment and uncalled Ollama infrastructure
- the result-return boundary rather than an asserted GX10 result path
- both component runbooks and the cross-server order
- current read-only transport requirements
- failure behavior that preserves missing orchestration instead of fabricating it

It also corrects an inaccurate statement that the captured GX10 applications use SQLite WAL mode. The captured sources enable foreign keys where needed and a 5-second busy timeout; they do not explicitly set WAL mode.

### Durable decision

Added ADR-015:

`Reconstruction preserves absent orchestration`

This makes the central rediscovery distinction durable: presence of a component or boundary is not evidence of a caller. Any future enrichment scheduling, incident engine, Ollama integration, or result producer requires separate design/migration gates.

### Continuity and roadmap updates

Updated:

- `docs/CURRENT_STATE.md`
- `docs/START_HERE.md`
- `docs/AI_HANDOFF.md`
- `docs/ROADMAP.md`
- `docs/NORMALIZER_MIGRATION.md`
- `components/collector/README.md`

These documents no longer direct a fresh session to restart GX10 reconstruction. Both component packages are closed, both disposable-host validations remain explicitly deferred, and the final sanitation/acceptance phase is now active.

### Validation

Documentation reconciliation validation passed with:

- exactly one numbered `NEXT` item in `docs/CURRENT_STATE.md`
- zero current-document matches for the stale GX10-pending/WAL/result-producer claims audited in this subsection
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- 42 GX10 tests passing
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `git diff --check` passing

### Safety boundary

This subsection changed public documentation only.

It:

- did not read or publish private connection values
- did not read production logs, database rows, credentials, keys, or model contents
- did not execute either pipeline
- did not call Ollama or run inference
- did not modify either reference system or any service state

### Next action

Publish this documentation checkpoint and independently verify GitHub.

Then run execution-order item 15: final full-repository sanitation, public-history/ref-topology review, all practical repository-only component gates, and two-server acceptance validation with unavailable disposable-host execution reported as deferred rather than passed.

## 2026-08-23 16:47 PDT - Final sanitation and two-server acceptance validation

### Status

Execution-order item 15 is `DONE`.

Execution-order item 16 is now the single `NEXT` item.

Repository-only acceptance and read-only reference revalidation pass. Disposable clean-host execution remains explicitly deferred.

### Durable full-repository sanitation gate

Added:

- `scripts/validate-public-repository.py`
- `scripts/test_public_repository_validator.py`
- `docs/ACCEPTANCE.md`

The public gate scans the tracked plus nonignored-untracked current tree and every commit reachable from all refs.

It validates:

- text-only, nonsymlinked repository artifacts
- generated/private artifact path denial
- private-key and common GitHub/AWS/OpenAI/Slack/Google credential patterns
- workstation-private path denial
- public IPv4 policy, with only loopback/unspecified, documentation networks, and the reviewed ClickHouse version literal accepted
- local Markdown link targets
- exactly one numbered `NEXT`
- sensitive historical paths
- secret/private-address patterns throughout reachable history
- one local branch (`main`) and zero tags

Final markers:

- `PUBLIC_REPOSITORY_CURRENT_TREE=PASS`
- `PUBLIC_REPOSITORY_HISTORY=PASS`
- `PUBLIC_REPOSITORY_LINKS=PASS`
- `PUBLIC_REPOSITORY_REF_TOPOLOGY=PASS`
- `PUBLIC_REPOSITORY_VALIDATION=PASS`

Five synthetic tests passed, including negative cases for a private address, token, private-key marker, and sensitive artifact paths.

### Sanitation-tool corrections

The first self-scan correctly detected that the validator source contained literal private-key/private-path marker strings. The source now constructs its detector markers from noncontiguous public fragments, so the gate tests the repository without self-whitelisting a dangerous literal.

The first history IPv4 scan passed a Python lookaround expression to Git's POSIX ERE engine, which failed safely. The history prefilter now uses a compatible broad ERE and applies the precise Python address policy to each returned line.

Neither correction weakened the intended policy.

### Environment-specific identifier audit

A separate local-policy scan derived three private identifiers from the operator VM's existing SSH configuration without printing or persisting their values.

It scanned:

- the complete current working tree
- every commit reachable from all refs

Result:

`PRIVATE_IDENTIFIER_CURRENT_AND_HISTORY=PASS terms=3`

No private identifier value was printed or committed.

### Normalizer validation

The operator VM initially lacked the normalizer's required Python 3.13 runtime. Versioned Python 3.13 was installed through Homebrew on the operator VM only, and pytest 8 was installed into a temporary isolated environment.

The first consolidated invocation ran pytest from repository root without selecting the component's `pyproject.toml`; collection therefore could not resolve the `src` package. This was an invocation error, not a source/test failure.

The corrected explicit component-config invocation returned:

- 73 tests passing
- `PUBLIC REPO GATE: PASS`

Generated local bytecode caches from the failed invocation were removed, and the final run used bytecode-disabled/isolated-cache modes. No generated artifact remained in the repository.

### GX10 validation

Final results:

- 42 tests passing
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`

This covers source/configuration, SQLite, systemd, platform/Ollama contracts, model-store installation, activation refusal/order/rollback, syntax, modes, and GX10 public safety.

### Collector repository-only validation

Using documentation-only synthetic values and mode-private temporary password files:

- `COLLECTOR_CONFIG_RENDER=PASS`
- source and rendered YAML parsed successfully
- all four dashboard JSON resources parsed
- collector Python source compiled under Python 3.13 with an isolated bytecode cache
- Bash/POSIX shell syntax checks passed
- synthetic AI-result gate valid/invalid record behavior passed
- dashboard capture count, loopback HTTPS base-URL restriction, and clean-payload construction passed

Live-only/package-manager/systemd/ClickHouse/Grafana/ACME checks were not executed on the macOS operator VM. Their previously journaled independent live results remain authoritative, and clean-machine collector execution remains deferred.

### Git integrity and public topology

Final results:

- `git diff --check` passed
- `git fsck --full --strict` passed
- 118 reachable commits scanned during acceptance
- exactly one public branch: `main`
- zero public tags
- remote default branch: `main`
- public `main` matched the locally validated published checkpoint before these acceptance changes
- `PUBLIC_REMOTE_TOPOLOGY_AND_HEAD=PASS`

The final publication step must repeat the remote equality check after pushing the acceptance/final milestone commits.

### Read-only reference revalidation

Collector:

- authenticated SSH alias succeeded
- SSH, Vector, ClickHouse, and Grafana core units were active
- `COLLECTOR_CORE_RUNTIME_READONLY=PASS`

GX10:

- authenticated SSH alias succeeded
- `GX10_PLATFORM_VERIFY=PASS`
- `GX10_OLLAMA_VERIFY=PASS`

The GX10 recheck did not call the API, run inference, pull models, or read model blob contents.

No reference-system file or service state was changed.

### Acceptance boundary

Aggregate repository marker:

`FINAL_REPOSITORY_ONLY_ACCEPTANCE=PASS`

Passed:

- public implementation/package completeness
- repository-only tests and structural gates
- current-tree and reachable-history sanitation
- documentation links/current-state authority
- Git integrity and public topology
- read-only reference connectivity/core-state revalidation

Deferred, not passed:

- clean collector execution on disposable Debian 13 amd64
- clean GX10 execution on disposable Ubuntu 24.04 arm64 GX10-class hardware
- full disposable two-host execution of `docs/TWO_SERVER_REBUILD.md`

### Safety boundary

This item:

- installed Python 3.13 only on the operator VM for the required test runtime
- used only synthetic temporary renderer/test inputs
- did not print or persist private connection values
- did not read production logs, databases, credentials, keys, or model blob contents
- did not call Ollama or run inference
- did not execute fetch, ingest, enrichment, or result production
- did not write either reference system
- did not change reference-system service state

### Next action

Publish this acceptance checkpoint and independently verify GitHub.

Then publish execution-order item 16 as the final rebuild milestone, preserving the two clean-host validation deferrals and advancing future implementation only through a new explicit `NEXT` item.

## 2026-08-23 16:49 PDT - Final public rebuild milestone

### Status

Execution-order item 16 is `DONE`.

Execution-order item 17 is now the single `NEXT` item.

The final public repository rebuild milestone is complete and ready for publication.

### Published milestone scope

The milestone contains:

- consolidated deterministic normalizer with replay/parity evidence
- complete public collector rebuild package and operator runbook
- complete public GX10 rebuild package and operator runbook
- guarded collector package/runtime activation boundaries
- guarded GX10 package, offline-model, preactivation, and activation boundaries
- current-versus-target architecture and data/operations contracts
- collector-first two-server rebuild runbook and independent key-role mapping
- durable current-tree/reachable-history sanitation gate with synthetic tests
- final repository-only and read-only-reference acceptance report

The validated item-15 acceptance checkpoint is:

`27ca641c261552428dab88fc57b98851f7cedecf` — `Validate final two-server acceptance boundary`

### Honest completion boundary

Complete:

- implementation and reconstruction artifacts
- component and cross-system operator documentation
- repository-only tests/static/synthetic validation
- current-tree and reachable-history sanitation
- Git integrity, local/public topology, and remote checkpoint verification
- read-only reference connectivity/platform/core-service revalidation

Deferred:

- clean collector execution on disposable Debian 13 amd64
- clean GX10 execution on disposable Ubuntu 24.04 arm64 GX10-class hardware
- full disposable two-server execution and cross-host replay/idempotency proof

The final public milestone does not convert those unavailable environmental tests into a pass.

### Project acceptance status

The repository is ready for deterministic clean-host execution without undocumented conversational memory.

The project's ultimate acceptance criterion remains open until the component and two-server runbooks pass on suitable disposable hosts.

Accordingly, the only active execution item is now:

`17. NEXT — disposable clean-two-server execution`

Future production normalizer integration, incident-engine development, Ollama orchestration, and result production remain deferred until that gate is satisfied or the operator explicitly changes execution authority.

### Safety boundary

This milestone step changes public status/documentation only.

It:

- does not execute an installer
- does not call either application pipeline
- does not read private values or production data
- does not call Ollama or run inference
- does not write either reference system or change service state

### Publication sequence

Publish this milestone commit to GitHub and independently verify:

- public `main` equals the milestone commit
- public branch count remains one
- public tag count remains zero
- remote default branch remains `main`
- working tree remains clean
- final public-repository gate passes against the published history

Then append one final remote-verification journal entry identifying the milestone commit and push that verification closure.

## 2026-08-23 16:51 PDT - Final milestone remote verification

### Status

The final public rebuild milestone was published and independently verified.

Verified milestone commit:

`13c27ec7b7a6d3b9bc938a84414627a3937f1d9d` — `Publish final public rebuild milestone`

### Public verification result

After publication:

- local `HEAD` exactly matched public `main`
- the public branch count was one
- the public tag count was zero
- the remote default branch was `main`
- the working tree was clean
- `git diff --check` passed
- `git fsck --full --strict` passed
- the final public-repository gate passed for the current tree, all reachable history, local links, and ref topology

The verification did not use or publish the local fine-grained token file, private SSH key material, or private connection values.

### Remaining gate

This verification closes publication of execution-order item 16. It does not close execution-order item 17 or the ultimate project acceptance criterion.

The single `NEXT` item remains disposable clean collector, GX10, and two-server execution on suitable systems. No reference-system write or service-state change occurred during final publication or verification.

## 2026-08-23 17:08 PDT - Operator acceptance of clean-host residual risk

### Decision

The operator confirmed that no pair of disposable servers is available and directed the project to assume the validated rebuild packages are sufficient and continue toward the end goal.

Execution-order items 11, 13, and 17 are therefore `WAIVED BY OPERATOR`, not passed. Clean collector, clean GX10, and clean two-server execution remain empirically unverified.

ADR-016 records the durable rationale and consequence.

### Evidence retained

The decision relies on the already-published evidence:

- repository-only and reachable-history sanitation pass
- 73 normalizer tests and 42 GX10 package tests pass
- collector synthetic/static/runtime-contract gates pass
- Git integrity and public topology pass
- read-only reference connectivity and core-runtime revalidation pass
- guarded installers, independent verifiers, rollback boundaries, and operator runbooks are published

The waiver does not reinterpret unavailable external execution as empirical evidence.

### Safety and execution consequence

The operator authorization changes project sequencing only. It does not authorize running clean-machine installers against either working reference system, destructive production changes, or bypassing later migration/cutover safeguards.

The rebuild/documentation milestone is accepted with residual risk. Execution-order item 18 is now the single `NEXT` item:

`18. NEXT — design collector-side production-normalizer integration, including explicit input/output boundaries, private platform-inventory injection, shadow observability, failure isolation, and rollback behavior.`

Publish this decision checkpoint before materially implementing item 18.

## 2026-08-23 17:19 PDT - Production normalizer integration design completed

### Status

Execution-order item 18 is `DONE`.

Execution-order item 19 is now the single `NEXT` item.

### Design decision

Added `docs/NORMALIZER_PRODUCTION_INTEGRATION.md` and ADR-017.

The normalizer will first run on the collector as a separate unprivileged durable-file shadow worker over settled `/var/spool/vector-ai` files. It will write atomic normalized files to a separate shadow root and record source, output, inventory, version, record-count, and classification evidence in a SQLite ledger.

Vector's existing raw ClickHouse and backlog sinks remain unchanged. The current GX10 read-only handoff remains on the raw backlog throughout shadow operation.

The design rejects an inline or best-effort socket dependency because normalizer failure must not block capture and because the existing durable file boundary supports stronger replay, hash, cardinality, and idempotency evidence.

### Defined boundaries

The completed design specifies:

- private source-IP platform inventory validation and permissions
- exact source-file pattern, regular-file containment, settle, integrity, and unchanged-postcheck gates
- one-input-line/one-output-line deterministic normalization
- atomic output publication without unexpected overwrite
- durable per-source ledger and mutation refusal
- dedicated no-network/no-credential runtime identity
- public-safe shadow counters and backlog-age evidence
- promotion gates that do not invent a duration or event threshold before live rates are observed
- GX10 handoff-only promotion and rollback boundaries
- explicit file-identity/idempotency risk that must be solved before cutover

### Validation and safety

The design was reconciled against the captured Vector raw/backlog configuration, normalizer schema/API, platform-trust ADR, data contracts, and operations rules.

The public repository gate and documentation link validation pass.

No live collector/GX10 configuration, file, process, service, or data was changed or read for this design. No installer or application pipeline was executed.

### Next action

Implement item 19 entirely in the repository: the worker, private-inventory validator, ledger, package/service artifacts, synthetic tests, and independent verifier. Do not deploy it to the live collector during item 19.

## 2026-08-23 17:24 PDT - Normalizer shadow package implemented

### Status

Execution-order item 19 is `DONE`.

Execution-order item 20 is now the single `NEXT` item.

### Implementation

Implemented the collector-side normalizer shadow package without deploying it:

- `network_log_normalizer.shadow` durable-file worker and command interface
- strict versioned private platform-inventory parser with duplicate-key, canonical-IP, supported-pair, owner/group/mode, symlink, hardlink, and size refusal
- removal of untrusted per-record platform hints before trusted inventory injection
- exact backlog relative-path/date validation and 120-second settle boundary
- regular/nonsymlink/single-link source checks plus pre/post size, modification-time, inode, device, and SHA-256 closure
- external `/usr/bin/zstd` integrity/decode/encode boundary using the reference host's existing package
- stable schema-version-1 JSON serialization with one input line mapped to one output line
- atomic no-overwrite output publication with synchronized contents and directory entry
- version-1 SQLite ledger with `processing`/`completed` recovery state, source/output/inventory/version hashes, counts, and strict constraints
- exact completed-output reuse and mutation refusal
- locked `network-log-normalizer` runtime identity with only the `vector` supplementary group required by the captured `0750 vector:vector` source root
- systemd read-only source view, isolated writable output/state paths, no network, no capabilities, and no Vector-start coupling
- guarded non-activating staging installer and independent staged/active runtime verifier
- exact installed-artifact SHA-256 manifest and no-overwrite installation behavior
- reference package pins for Python `3.13.5-1` and Zstandard `1.5.7+dfsg-1`

### Corrections during validation

The first package-test run found two test defects, not product defects:

- a string assertion accidentally retained a literal patch marker
- a corruption test attempted an invalid ledger update that SQLite correctly rejected through the new cardinality constraint

The test was corrected to inspect the real package text and mutate an output artifact so the independent verifier detects the inconsistency without bypassing ledger protection.

Additional review tightened three contracts before closure:

- an exact eligible-path symlink now fails visibly rather than being silently skipped
- the service no longer has `Wants=vector.service`, so shadow execution cannot pull Vector up
- both staging and runtime verification enforce the captured Python/Zstandard package versions and executable presence

A final bounded-backlog review found and corrected one product defect before publication: applying `max-files` before completed-file skipping could repeatedly revisit the oldest retained files and prevent the cursor from advancing. The cycle now starts strictly after the greatest completed source path recorded in the durable ledger, retries an interrupted next file, limits only unprocessed work, and reports pending/oldest-backlog metrics without running the expensive full-output verifier every minute. A regression test proves cursor advancement to the next settled file.

### Validation

Completed results:

- full normalizer/parser/replay/shadow suite: `88 passed`
- collector normalizer-shadow package suite: `9 passed`
- `NORMALIZER_SHADOW_PACKAGE_VALIDATION=PASS`
- collector shell syntax: `PASS`
- `git diff --check`: `PASS`
- current-tree/reachable-history/link/ref public gate: `PASS`

The worker tests prove strict inventory behavior, settle/path selection, visible symlink refusal, source immutability, trusted enrichment, untrusted-hint removal, exact cardinality, idempotent skip, source-mutation refusal, malformed-input nonpublication, output-mutation detection, and exact ledger schema/mode.

The package tests prove manifest/source hashes, exact installed inventory, no-overwrite installation, private input modes, service isolation, non-activation, package-version pins/drift refusal, and independent output/cardinality verification.

### Reference-only dependency check

A bounded read-only collector package-metadata check established:

- Python runtime: `3.13.5` / Debian package `3.13.5-1`
- Zstandard executable present / Debian package `1.5.7+dfsg-1`
- source root metadata: `0750 vector:vector`

No production log, inventory content, credential, or private connection value was read or persisted.

### Safety boundary and next action

No file, account, unit, configuration, service state, Vector path, ClickHouse path, or GX10 handoff was changed on either reference system.

Item 20 requires a distinct authorization because it will stage new isolated files/account/units and generate new shadow output on the working collector. It also requires a trusted private source-IP platform inventory; runtime platform authority must not be inferred solely from messages.

## 2026-08-23 20:38 PDT - Normalizer shadow deployed and activated

### Status

Execution-order item 20 is `DONE`.

Execution-order item 21 is now the single `NEXT` item.

The operator explicitly directed the project to build the private inventory candidate and deploy shadow mode on the working collector. This authorized the isolated collector writes and shadow service-state change described below. It did not authorize GX10 handoff promotion, Vector/ClickHouse changes, raw-backlog mutation, or production cutover.

### Private inventory qualification

A one-time root-operated candidate builder scanned only settled compressed backlog files. It accepted exact platform-specific EOS, IOS XR, or NX-OS signatures only when all evidence for a canonical source identity was conflict-free. Unknown sources remained absent from the inventory and therefore continue through generic capture-first normalization. The running worker does not infer platform from message content; it trusts only the installed protected inventory.

Public-safe derivation totals:

- settled files examined: `11922`
- records examined: `1101997`
- invalid or identityless records: `0`
- distinct source identities: `281`
- candidate entries: `184`
- EOS entries: `6`
- IOS XR entries: `5`
- NX-OS entries: `173`
- ambiguous identities omitted: `0`
- unknown identities omitted: `97`
- exact-signature evidence events: EOS `527`, IOS XR `120`, NX-OS `36016`

The candidate and its audit remain outside the public repository beneath a root-only collector directory. Input files are mode `0600`. The installer copied the runtime inventory to the protected `0640 root:network-log-normalizer` target. No source identity or private inventory content was printed or committed.

### Baseline and staging

Before staging:

- local `HEAD` and public GitHub `main` both equaled `c68c96642aef97a520d1392467c1247444511d25`
- Vector, ClickHouse, and Grafana were active and enabled
- the shadow timer was absent/inactive and the shadow output path did not exist
- the raw backlog contained `11923` files totaling `67941148` bytes at the baseline instant
- Vector configuration SHA-256 was `c6c3cfed6ff4cd30c2bba220211403d56611a966145a76004e866050ae9c1a90`
- `/etc/fstab` SHA-256 was `37244f78ab8701d0375de18dda408060e1a519838a1351d8fe281e2258d07189`
- a protected 24-file source sample passed full SHA-256 verification
- exactly one live match remained for each recorded GX10 fetch, ingest, enrichment, and pipeline-service-unit hash

The guarded installer then created the locked runtime identity, isolated state/output/configuration paths, installed the manifest-verified artifacts and units, and left the timer disabled/inactive. The independent staged verifier returned:

```text
platform_entries=184
completed_files=0
normalized_records=0
normalizer_shadow_mode=staged
NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS
NORMALIZER_SHADOW_INSTALL=STAGED
normalizer_shadow_timer=disabled,inactive
```

### Bounded activation evidence

One manual bounded cycle completed before activation:

- completed files: `100`
- input/output records: `7578` / `7578`
- generic/parser-enriched records: `7467` / `111`
- inventory hits/misses: `6516` / `1062`
- parser-error records: `0`

The independent staged verifier passed the entire output/ledger inventory after that cycle. Only `network-log-normalizer-shadow.timer` was then enabled and started.

The first scheduled cycle advanced the durable cursor to these cumulative totals:

- completed files: `200`
- input/output records: `18446` / `18446`
- generic/parser-enriched records: `17926` / `520`
- inventory hits/misses: `15869` / `2577`
- parser-error records: `0`
- source/output bytes: `1116296` / `1236970`

The independent active verifier returned `NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS`. The timer was active/enabled and the oneshot service returned to inactive/success between cycles.

### Isolation and unchanged postcheck

After activation:

- the protected 24-file source sample remained byte-identical
- Vector configuration and `/etc/fstab` retained their exact baseline hashes
- Vector, ClickHouse, and Grafana remained active and enabled
- the restricted GX10 bind mount remained mounted read-only with `nosuid,nodev,noexec`
- the raw spool continued growing normally; no raw source file was renamed, modified, or deleted by shadow execution
- exactly one live match remained for every recorded GX10 fetch, ingest, enrichment, and pipeline-service-unit hash
- the GX10 handoff remained on the raw backlog

### Next action

Keep the isolated timer active and collect catch-up plus steady-state evidence. Review exact cardinality, inventory coverage/misses, parser errors, cursor/backlog age, source immutability, service isolation, and continued raw-handoff health before designing or rehearsing any handoff switch. Production cutover remains separately gated and unauthorized.

## 2026-08-23 21:36 PDT - Shadow catch-up and steady-state evidence closed

### Status

Execution-order item 21 is `DONE`.

Execution-order item 22 is now the single `NEXT` item.

The shadow timer remains active. The GX10 handoff remains on the raw backlog, and production cutover remains unauthorized.

### Historical catch-up

The worker retained its configured 100-file maximum per systemd invocation. After the first deployment cycles remained within the unit's CPU/memory bounds and left Vector, ClickHouse, and Grafana healthy, bounded manual starts of the same hardened unit accelerated historical catch-up. Every invocation retained the exact unit sandbox, source-read-only boundary, one-core CPU quota, memory limit, inventory, ledger, and atomic-output behavior.

Fail-fast checks after every catch-up invocation required:

- Vector, ClickHouse, and Grafana active
- zero restarts for those three services
- zero parser-error records
- zero incomplete ledger rows

Periodic independent full-output verification passed at 1,500, 4,000, 6,500, 8,500, and 10,500 completed files. The protected 24-file source sample and existing-service state checks also passed at each reviewed checkpoint.

Catch-up reached zero pending files at:

- completed files: `11968`
- normalized records: `1106379`

### Active-verifier concurrency defect and correction

The first all-output verification at the zero-pending boundary returned `output inventory differs from ledger`. Immediate bounded diagnosis found:

- the timer had completed one newly settled file while the verifier was scanning
- ledger outputs: `11969`
- filesystem outputs: `11969`
- missing outputs: `0`
- extra outputs: `0`
- incomplete ledger rows: `0`

The worker and evidence were correct. The independent verifier had compared a pre-cycle ledger snapshot with a post-cycle filesystem inventory.

The verifier now incrementally resnapshots append-only active progress. It verifies each completed row/output exactly once, rejects changes or disappearance of already verified rows, fails immediately for missing completed outputs or stable orphan outputs, waits only for legitimate in-progress publication, and retains strict no-concurrency behavior in staged mode. Active stabilization is time-bounded.

A regression test adds a second completed ledger/output entry during verification and proves the active verifier incorporates it. Collector package validation now reports `10` passing tests and `NORMALIZER_SHADOW_PACKAGE_VALIDATION=PASS`.

The live verifier-only correction used exact precondition hashes, a protected rollback copy, and atomic replacement while the shadow timer was disabled. Both the original verifier before replacement and the corrected verifier after replacement passed complete staged verification over `11972` files and `1106731` records.

Live concurrent proof then began active verification at `11972` completed files while the normalizer processed three newly settled files. The corrected verifier completed at `11975` files and returned:

```text
NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS
LIVE_CONCURRENT_ACTIVE_VERIFY=PASS
```

### Normal-cadence steady state

After the concurrency proof, no additional manual service starts were used. Five consecutive timer-driven cycles completed at the configured one-minute inactive interval.

Each cycle:

- selected and completed one newly settled file
- returned pending unprocessed files to `0`
- completed in `0.626` to `1.426` seconds
- retained exact input/output cardinality
- retained zero parser errors and zero incomplete rows
- left Vector, ClickHouse, and Grafana active with zero restarts

### Final cumulative evidence

The final independent active verifier passed while the timer continued operating. It absorbed two further legitimate concurrent file completions and returned:

- platform inventory entries: `184`
- completed files: `11983`
- input records: `1107749`
- output records: `1107749`
- generic records: `1071508`
- parser-enriched records: `36241` (`3.27%`)
- inventory hits: `933100` (`84.23%`)
- inventory misses: `174649`
- parser errors: `0`
- incomplete files: `0`
- source bytes: `68286219`
- output bytes: `73120191`
- pending files after each reviewed steady-state cycle: `0`

`NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS` covered every ledger row and normalized output, including file modes/ownership, Zstandard integrity, output SHA-256, schema, record count, package manifest, dependency pins, private inventory, runtime identity, and active timer state.

### Unchanged-production postcheck

Final postchecks established:

- the protected 24-file raw source sample remained byte-identical
- Vector configuration and `/etc/fstab` retained their predeployment hashes
- Vector, ClickHouse, and Grafana remained active/enabled with zero restarts
- the shadow timer remained active/enabled and its oneshot last result was success
- no SQLite journal/WAL/shared-memory sidecars remained
- the GX10 read-only bind mount retained `ro,nosuid,nodev,noexec`
- exactly one live match remained for every recorded GX10 fetch, ingest, enrichment, and pipeline-service-unit hash
- the GX10 handoff remained on `/var/spool/vector-ai`

### Validation and next action

The corrected package has `10` collector-package tests passing. Python syntax, `git diff --check`, and the current-tree/reachable-history/link/ref public-repository gate pass. The previously published `88` normalizer/worker tests remain the implementation baseline; the worker source did not change in this correction.

Item 22 must design and rehearse a file-identity-safe GX10 handoff switch and rollback without changing the live handoff. It must resolve the GX10 `(source_file, record_number)` namespace behavior, define preflight/activation/postcheck/rollback evidence, and preserve both raw and normalized spools. Actual promotion requires a later distinct operator authorization.

## 2026-08-23 21:51 PDT - Forward-only GX10 handoff design and rehearsal closed

### Status

Execution-order item 22 is `DONE`.

Execution-order item 23 is now the single `NEXT` item.

No handoff artifact was installed on the collector, no collector or GX10 service state changed, and the live GX10 bind view remains on the raw backlog. Production staging and cutover remain explicitly authorization-gated.

### Identity defect resolved

Repository review proved the existing GX10 fetcher accepts only raw-style `syslog-YYYYMMDD-HHMM.jsonl.zst` names. The validated shadow tree uses `.normalized.jsonl.zst`, so a direct shadow-root bind would expose files the fetcher ignores.

Changing GX10 to accept the normalized suffix would assign new `source_files.remote_path` values to all historical shadow files and replay observations already represented in `recent_events`. Renaming all normalized history to the original raw names would instead collide with existing paths without defining which side of the transition was authoritative.

The accepted design uses one immutable inclusive source-path floor. Files before the floor remain represented by already consumed raw paths. Verified normalized files at or after the floor are copied into a separate handoff root under their original raw relative paths. GX10 retains its current filename matcher, `/spool/...` namespace, `source_files.remote_path` primary key, and `(source_file, record_number)` uniqueness boundary.

### Repository implementation

The repository-only forward publisher now provides:

- strict duplicate-key and schema validation for a protected handoff plan
- exact canonical source-path floor validation and plan hashing
- a version-1 SQLite ledger binding the first floor permanently
- completed-shadow-row selection only at or after the floor
- exact shadow path, size, SHA-256, record-cardinality, Zstandard, mode, and runtime-owner verification
- same-directory temporary copy, content synchronization, rehash, Zstandard test, and atomic no-overwrite publication
- separate single-link handoff copies under original raw transport names
- exact crash-window copy adoption and divergence refusal
- complete stable-state verification across the plan, both ledgers, shadow outputs, and handoff tree
- missing, orphaned, pre-floor, mutated, hard-linked, wrong-mode, wrong-owner, and unexpected-schema failure boundaries
- a no-network hardened candidate oneshot/timer and a public example plan

The candidate launcher, unit files, and module are intentionally excluded from the active live-shadow package manifest. A later authorized step must build a separate exact-hash staging package rather than silently modifying the verified live package.

### Synthetic cutover and rollback rehearsal

The rehearsal used three sequential synthetic source paths with the middle path as the first normalized path. It proved:

- no pre-floor file entered the handoff tree
- at/after-floor copies used the exact raw filename pattern accepted by the unchanged GX10 fetcher
- the fetcher continued to reject `.normalized` shadow filenames
- a one-file publication bound advanced durably across cycles and a caught-up retry performed no work
- handoff/shadow bytes matched while retaining distinct single-link inodes
- an exact preexisting crash-window copy was adopted
- mutated handoff bytes and a changed initialized plan failed closed
- the complete tree, ledger, hashes, Zstandard streams, and record totals verified
- raw-view rollback attempts for already processed at/after-floor paths did not add source identities or duplicate `(source_file, record_number)` rows

The complete normalizer/worker suite reports `94` passing tests. The collector package validator reports `11` passing tests and `NORMALIZER_SHADOW_PACKAGE_VALIDATION=PASS`.

### Documented live gate

`docs/NORMALIZER_HANDOFF.md` now defines the exact later preflight, future-floor selection, GX10 stop/absence proof, protected runtime layout and ACL, publisher catch-up, bind-only activation, SFTP/hash/cardinality checks, bounded GX10 cycle, postchecks, and mount-only rollback.

The design forbids deleting or rewriting raw, shadow, handoff, or GX10 state. A successfully processed normalized file keeps the same remote identity after raw-view rollback and is skipped. A failed ingest retains the existing transaction rollback/retry behavior.

### Next action

Obtain explicit production-cutover authorization. Only after that approval may the project build and stage the separate exact-hash handoff package, run the live preflight, select the future floor, stop GX10 at the boundary, and switch the read-only bind view. If approval is unavailable, continue only repository, test, documentation, and read-only work.

## 2026-08-23 22:00 PDT - Item 23 read-only cutover-readiness resnapshot

### Status

Execution-order item 23 remains the single `NEXT` item.

Explicit production-cutover authorization has been requested and has not yet been recorded. No handoff artifact was installed, no timer or service state was changed, and no bind mount, configuration, spool, database, or application file was modified.

The validated item-22 checkpoint was published and independently matched on GitHub at:

`5f1b261fd847173d0fc13e3a21202c519b86f839` — `Design forward-only normalizer handoff`

### Collector readiness

Read-only checks established:

- Vector, ClickHouse, Grafana, and the normalizer shadow timer active/enabled
- zero restarts and successful last results for the application services and shadow oneshot
- GX10 SFTP bind still sourced from the raw backlog with `ro,nosuid,nodev,noexec`
- `/etc/fstab` and Vector configuration retained their recorded SHA-256 values
- protected handoff plan, handoff root, and handoff launcher absent from the live collector
- no premature handoff staging or activation state

The complete active shadow verifier then passed over the growing live tree:

```text
platform_entries=184
completed_files=12001
normalized_records=1109388
normalizer_shadow_mode=active
NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS
```

### GX10 readiness

The live GX10 artifact filenames and unit names remain intentionally identity-bearing and differ from the sanitized public reconstruction names. An initial lookup by public reconstructed names therefore found no live files/units. This was not runtime drift. The check was corrected to resolve artifacts only through the five already recorded SHA-256 identities without printing live names or paths.

Corrected read-only evidence:

- fetch executable hash matches: `1`
- ingest executable hash matches: `1`
- deterministic enrichment executable hash matches: `1`
- pipeline service-unit hash matches: `1`
- pipeline timer-unit hash matches: `1`
- pipeline timer active/enabled
- pipeline oneshot inactive after success with zero restarts
- source-file status: `10373 processed`, zero other states
- current source-file total: `10373`
- current recent-event total: `940884`
- incoming queue files: `0`
- last remote scan in the current UTC hour
- maximum remote path current through the latest settled minute at the audit instant

The database was discovered from the captured ingest source's existing absolute constants, opened read-only, and queried only for schema identity, aggregate counts/status, and cursors. No event row, message, private path, credential, connection value, or identity-bearing live filename was printed or persisted.

### Authorization boundary

Both systems are technically ready for the later bounded preflight. The only current blocker is the explicit operator authorization required by item 23. Until it is recorded, work remains limited to repository preparation, testing, documentation, and read-only validation.

## 2026-08-23 22:54 PDT - Production cutover authorized and staging package validated

### Status

Execution-order item 23 remains the single `NEXT` item.

The operator explicitly authorized the documented production cutover scope: stage the separate handoff package, choose a future floor, pause GX10 at the boundary, switch only its read-only spool view, validate a bounded normalized cycle, and retain the mount-only rollback. The authorization does not permit deleting or rewriting raw logs, shadow output, ClickHouse data, or existing GX10 history.

No live write or service-state change occurred in this repository subsection.

### Separate staging package

Added a handoff-only package that does not modify the installed shadow-package manifest:

- guarded `install-handoff.py`
- independent `verify-handoff.py`
- exact five-artifact `handoff-package-manifest.json`

The exact installed target set is:

- handoff publisher module
- handoff launcher
- independent handoff verifier
- handoff service unit
- handoff timer unit

The staging installer:

- requires root plus an exact confirmation phrase
- requires a private regular single-link plan with mode `0400` or `0600`
- requires the immutable floor to be at least ten minutes in the future
- requires the handoff timer absent/inactive and disabled
- verifies every repository artifact against the handoff-only manifest
- re-runs the complete active live-shadow verifier before installing anything
- requires the existing normalizer identity and protected shadow/state/config/library roots
- creates only an initially empty `0750` handoff root with exact read-only/default ACLs for the existing restricted spool-reader group
- installs the protected plan and new artifacts with no-overwrite exact-content behavior
- initializes and binds the separate handoff ledger through the runtime identity
- verifies both units and reloads definitions without enabling or starting the timer
- finishes with the independent staged verifier

The independent verifier checks installed hashes, exact inventory, modes/ownership, runtime paths, plan/ledger metadata, handoff ACL, stable timer/service state, complete core handoff evidence, and—only in cutover mode—the exact handoff bind source plus `ro,nosuid,nodev,noexec` options.

### Validation

- full normalizer/parser/replay/shadow/handoff suite: `94 passed`
- collector shadow/handoff package suite: `14 passed`
- `NORMALIZER_SHADOW_PACKAGE_VALIDATION=PASS`
- GX10 reconstruction suite: `42 passed`
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- root sanitation tests: `5 passed`
- current-tree/history/link/ref sanitation: `PASS`
- `git diff --check`: `PASS`

### Next action

Publish and independently verify this pre-cutover repository checkpoint. Then select a sufficiently future private floor, stage the package without activation, and re-run both systems' live preflight before pausing GX10.

## 2026-08-23 22:59 PDT - Handoff staged, GX10 paused, and unit portability correction bounded

### Status

Execution-order item 23 remains `NEXT` and in progress.

The live GX10 bind view remains on the raw backlog. Vector, ClickHouse, Grafana, and raw/shadow capture remain active. The handoff publisher timer remains disabled/inactive and has never run.

### Authorized staging result

The exact package at public checkpoint `e296633a2cc3eef7eccacf5e41e0361bee17901f` was transferred through the configured collector SSH path into a root-only staging directory. The transfer archive SHA-256 matched on both sides. A private `0600` plan selected the inclusive forward floor without publishing connection or identity values.

The guarded installer re-ran the complete active shadow verifier before installing:

```text
platform_entries=184
completed_files=12064
normalized_records=1115518
normalizer_shadow_mode=active
NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS
```

It then created the empty protected handoff root/ACL, installed the private plan and five manifest-pinned artifacts, initialized an empty plan-bound handoff ledger, left the timer disabled/inactive, and passed both the core empty-tree verifier and independent staged verifier.

### Unsupported unit condition caught before activation

The collector's `systemd-analyze verify` emitted a warning that `ConditionPathIsRegularFile` is not supported by its systemd version and would be ignored. The strict application verifier still enforces a regular nonsymlink protected plan, but an ignored unit precondition is not accepted.

Because the handoff timer was still disabled/inactive and the raw bind remained active, this was a staging-only defect with no data-path impact. Activation stopped. The repository unit now uses the portable `ConditionPathExists` directive while retaining the strict application-level type/mode/owner/group/contents validation. The handoff manifest was updated to the corrected service-unit SHA-256 and the 14-test collector package gate plus public sanitation gate pass.

### GX10 boundary pause

GX10 was paused before the selected floor could become settled. Exact recorded-hash resolution located the identity-bearing live service/timer without persisting their private names. Pre-pause database and queue evidence was:

- source files: `10437`
- recent events: `947064`
- source status: all processed
- at/after-floor conflicts: `0`
- incoming files: `0`
- maximum remote path: before the selected floor

The pipeline timer is now disabled/inactive and its oneshot is inactive. No database row or local spool file was changed by the pause.

### Next action

Publish the portable-condition correction. With the timer still disabled, replace only the two staged exact-hash artifacts affected by the correction—the handoff service unit and its handoff-only installed manifest—using old-hash preconditions and protected rollback copies. Re-run `systemd-analyze`, daemon reload, and the independent staged verifier before any publisher activation.

## 2026-08-23 23:35 PDT - Forward-only normalized production handoff activated and verified

### Status

Execution-order item 23 is `DONE`. Item 24 is now the single `NEXT` item.

The explicitly authorized production cutover completed without deleting, renaming, truncating, or rewriting raw backlog files, shadow output, ClickHouse data, or existing GX10 history. The live change was limited to the separately staged publisher/schedule, one exact `/etc/fstab` bind-entry replacement, the read-only GX10 spool remount, and normal service/timer state transitions. The protected raw-view rollback definition and operator-private evidence copy remain available.

### Corrected staging precondition

The portable service-unit correction from checkpoint `c7d609092164775518705e08a4c3ec672a59c364` replaced only the staged service artifact and installed handoff-only manifest under exact old-hash preconditions. Protected operator-private rollback copies were created before replacement. A clean `systemd-analyze verify`, daemon reload, core handoff verifier, and independent staged verifier passed before publisher activation.

No live unit name, application path, connection value, credential, private plan location, or operator-private evidence path was added to the public repository.

### Immutable floor and pause evidence

The protected plan selected inclusive floor:

```text
2026/08/24/06/syslog-20260824-0612.jsonl.zst
```

Public-safe immutable hashes:

- protected plan: `5cd4d29d4675b706db348845168b7f5c319004db90ed3342acb860d35e92464c`
- installed handoff-package manifest: `26b52aa0a75318ee6c2e768bffd91a8bf37c13b836c3f5b81691c687f8bb61d7`
- pre-cutover `/etc/fstab`: `37244f78ab8701d0375de18dda408060e1a519838a1351d8fe281e2258d07189`
- post-cutover `/etc/fstab`: `9f42af9d43124d66c3cb02cc20b23b7ee7272e02fd1afef428dcddd0e9e98259`

GX10 remained paused from the earlier zero-conflict boundary until the first eligible normalized handoff file was independently verified. Immediately before the mount switch, both collector writers were frozen and the complete stable verifiers passed:

```text
platform_entries=184
completed_files=12082
normalized_records=1117167
normalizer_shadow_mode=staged
NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS
normalizer_handoff_mode=prepared
NORMALIZER_HANDOFF_RUNTIME_VERIFY=PASS
```

The handoff tree contained exactly the floor file, `69` records, and no pre-floor, missing, or orphaned file. Its SHA-256 was:

`a9d99713de4aae447d8ad41154b3ee25332fe190a60f41f54bbb5441440275d6`

### Guarded bind activation

The live mount and `/etc/fstab` still matched the recorded raw-view precondition. An exclusive root-only rollback copy was created, and an atomic replacement required exactly one old bind line and zero new bind lines. Only the GX10 spool bind target was unmounted/remounted. The independent cutover verifier then passed with the handoff root as `FSROOT` and `ro,nosuid,nodev,noexec` present.

If unmount, mount, or cutover verification had failed, the guarded operation would have restored the old line and raw view. No rollback was required.

### Bounded GX10 normalized cycle

After restarting the collector shadow/publisher schedules in order, the handoff verifier reported four files and `332` records. With the GX10 timer still disabled, one manual pipeline cycle completed:

- source files: `10437 -> 10441`
- recent events: `947064 -> 947396`
- incoming files before/after: `0 / 0`
- at/after-floor rows before/after: `0 / 4`
- all source rows: `processed`
- duplicate `(source_file, record_number)` identities: `0`

Exact collector-ledger/GX10 parity for the bounded set:

| Source minute | Size | SHA-256 | Records |
| --- | ---: | --- | ---: |
| `0612` | `4726` | `a9d99713de4aae447d8ad41154b3ee25332fe190a60f41f54bbb5441440275d6` | `69` |
| `0613` | `5764` | `8ca2e6f6501f266decff984576035f614b3c53b22db9358f2b4abcd70a4c4efa` | `87` |
| `0614` | `6348` | `46a3a273ec7d005cfcaedf090feb29d6bc088c95803d1958a7e62c66fad1ef15` | `100` |
| `0615` | `5421` | `36b5981a6d73d77d2a205ffc86f324499dae7f36d75bfb24d47d44f9e096e1f9` | `76` |

The GX10 timer was then enabled and started through exact recorded-hash resolution without publishing its identity-bearing live name. An initial strict postcheck sampled the oneshot during the timer's first transition and rejected that observation. A subsequent settled check showed inactive/success, exit status zero, zero restarts, and an active/enabled timer. This was an observation race, not a service or data-path failure.

### Multi-cadence soak and final stable verification

Twelve subsequent automatic observations passed. They included one cycle with no newly eligible file, proving the empty schedule remained idempotent, followed by normal advancement. The reviewed window ended with:

- GX10 source files: `10456` total, `19` at/after floor
- GX10 recent events: `948980` total, `1916` added since the pause
- collector handoff: exactly `19` files and `1916` records
- nonprocessed source rows: `0`
- incoming files: `0`
- duplicate event identities: `0`
- GX10 service restarts: `0`

Both collector schedules were briefly frozen once more for final stable verification. The result was:

```text
platform_entries=184
completed_files=12099
normalized_records=1118724
normalizer_shadow_mode=staged
NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS
normalizer_handoff_mode=cutover
NORMALIZER_HANDOFF_RUNTIME_VERIFY=PASS
```

After schedule resumption, the core verifier independently reported:

```json
{"missing_files":0,"orphan_files":0,"verified_files":19,"verified_records":1916}
```

The final collector health snapshot retained:

- Vector, ClickHouse, and Grafana active with zero restarts
- shadow and handoff timers active/enabled
- both normalizer oneshots successful with zero restarts
- Vector configuration SHA-256 unchanged at `c6c3cfed6ff4cd30c2bba220211403d56611a966145a76004e866050ae9c1a90`
- handoff bind source with `ro,nosuid,nodev,noexec`
- raw backlog, shadow tree, handoff tree, both ledgers, and rollback evidence preserved

### Repository validation

- normalizer/parser/replay/shadow/handoff suite: `94 passed`
- collector shadow/handoff package suite: `14 passed`
- `NORMALIZER_SHADOW_PACKAGE_VALIDATION=PASS`
- GX10 reconstruction suite: `42 passed`
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- root sanitation tests: `5 passed`
- current-tree/history/link/ref sanitation: `PASS`
- `git diff --check`: `PASS`

### Next action

Publish and independently verify this item-23 completion checkpoint. Then continue item 24 by reviewing the bounded normalized-handoff stability evidence and designing the deliberate retirement of transitional GX10 vendor parsing. Do not silently delete the historical enrichment table or conflate its current unscheduled state with the future deterministic incident engine.

## 2026-08-23 23:48 PDT - Canonical GX10 projection retirement candidate validated

### Status

Execution-order item 24 remains the single `NEXT` item and is in progress.

No live GX10 application or database state was changed in this subsection. One root-only on-server SQLite rehearsal copy was created through the online backup API, validated, and removed after success. The original database was opened read-only for baseline/postcheck and retained zero projection rows and no projection cursor.

### Read-only authority audit

At the first audit instant, all `2159` at/after-floor GX10 events had:

- the exact 26-key normalized schema-version-1 contract
- valid core normalized field types
- `106` collector parser-enriched rows and `2053` generic capture-first rows
- zero existing `event_enrichment` rows
- zero canonical `attention_eligible=false` rows

The historical enrichment table retained `24207` classification-version-3 rows. The exact recorded legacy enrichment executable had zero systemd-unit references.

A read-only in-memory comparison showed why duplicate reparsing must not remain authoritative:

- event code: `2159 / 2159` matches
- event family: `2107 / 2159` matches
- protocol: `1924 / 2159` matches
- entity type: `106 / 2159` matches, primarily because canonical generic `unknown` differs from legacy null representation
- entity key: `1874 / 2159` matches
- state: `2110 / 2159` matches
- signal type: `1875 / 2159` matches
- repeat count: `2139 / 2159` matches

The legacy stage would also apply the two existing GX10-local suppression rules to `1490` rows at that instant. Retirement therefore cannot simply discard local attention policy.

### Selected replacement

The compatibility-path `enrich-events.py` is now a canonical projector rather than a vendor/message parser. Candidate SHA-256:

`f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079`

The projector:

- accepts only exact normalized schema version 1
- treats canonical event/entity/protocol/state/signal/repeat/attribute fields as authoritative
- performs no vendor or message classification
- overlays only the existing enabled GX10-local suppression rules
- preserves classification-version-3 history and writes version 4
- scans append-only events through a transactional durable cursor in bounded batches
- projects each cursor batch and its cursor update in one `BEGIN IMMEDIATE` transaction
- is idempotent on repeat execution
- fails closed on malformed normalized input, invalid suppression policy, invalid cursor, schema drift, or a newer existing projection version
- remains absent from the automatic `timer -> fetch -> ingest` service

The same source can use the public rebuild `runtime_config` default or an explicit protected database path on the legacy reference installation, which has no public runtime-config module.

### Synthetic and live-copy proof

Synthetic tests prove:

- raw/pre-normalized records are skipped without creating replacement enrichment
- canonical generic and parser-enriched fields project exactly
- local exact suppression remains effective
- historical version-3 rows remain unchanged
- a second run is a no-op
- newly appended normalized rows advance from the durable cursor
- malformed normalized data rolls back both projection rows and cursor
- a newer projection version blocks replacement and cursor advancement
- guarded live replacement refuses divergent hashes or scheduler references
- failed post-replacement verification restores the exact legacy bytes
- rollback restores legacy bytes without deleting the protected backup

The on-server copy rehearsal then reported:

```text
NORMALIZED_PROJECTION scanned=949845 projected=2781 suppressed=1984 version=4
GX10_NORMALIZED_PROJECTION=PASS
NORMALIZED_PROJECTION scanned=0 projected=0 suppressed=0 version=4
GX10_NORMALIZED_PROJECTION=PASS
historical_v3_rows_preserved=24207
canonical_v4_rows_projected=2781
canonical_rows_exactly_compared=2781
local_policy_suppressed=1984
second_run_projected=0
live_database_projection_rows=0
live_database_projection_cursor=0
GX10_NORMALIZED_PROJECTION_LIVE_COPY_REHEARSAL=PASS
```

No event content, device identity, live application name/path, database path, or suppression pattern was printed or persisted in the public repository.

### Guarded live replacement boundary

`install/retire-transitional-enrichment.py` requires:

- root plus exact explicit confirmation
- operator-supplied target and protected backup paths
- exact old live SHA-256 `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`
- exact repository candidate SHA-256
- root-owned, single-link `0755` target
- zero systemd/cron references to the target
- absent backup under a root-only parent

It creates an exclusive root-only rollback copy, synchronizes it, atomically replaces the target while preserving ownership/mode, synchronizes the target directory, and automatically restores legacy bytes if the postcheck fails. Verification and nondestructive rollback modes are separate. The guard does not run the projector or write the GX10 database.

### Validation

- GX10 suite: `49 passed`
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- root sanitation tests: `5 passed`
- current-tree/history/link/ref sanitation: `PASS`
- `git diff --check`: `PASS`

### Next action

Publish and independently verify this candidate checkpoint. Then use only the published exact artifacts to replace the unscheduled live transitional executable under its exact old hash, retain the protected rollback copy, prove the old hash absent/new hash unique with zero scheduler references, and revalidate the still-unchanged automatic fetch/ingest path and database.

## 2026-08-23 23:54 PDT - Transitional GX10 parser retired under exact rollback boundary

### Status

Execution-order item 24 is `DONE`. Item 25 is now the single `NEXT` item.

The canonical projection/retirement candidate was published and independently verified on GitHub at:

`1d473499b1a228ec4b1fde20e0264e6c5610a9c5` — `Build canonical GX10 projection retirement`

Only those published candidate/guard bytes were staged for the live operation.

### Live preconditions

Recorded-hash resolution found exactly one active legacy executable without printing its identity-bearing name or path. Its preconditions were:

- legacy SHA-256: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`
- mode/ownership: single-link root-owned `0755`
- systemd/cron references: `0`
- pipeline service: inactive after success, zero restarts
- pipeline timer: active/enabled
- historical classification-version-3 rows: `24207`
- classification-version-4 rows: `0`
- projection cursor rows: `0`
- nonprocessed source rows: `0`
- duplicate event identities: `0`

The published guard SHA-256 was `426285e2279729e97d80fbdf6f5091cb4f3eaa85bae800849b8d2a65eb5e3e06`; the published projection SHA-256 was `f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079`.

### Guarded replacement

A new root-only operator-evidence directory was created. The guard required the exact old/new hashes, zero scheduler references, exact target metadata, exact explicit confirmation, and an absent backup path under that protected parent.

It then:

1. created and synchronized an exclusive `0600 root:root` rollback copy
2. atomically replaced only the resolved legacy target while preserving `0755 root:root`
3. synchronized the target directory
4. ran its independent retired-state verification
5. retained automatic rollback-on-postcheck-failure until all outer health/database assertions passed

No rollback was required. The completed evidence was:

```text
legacy_active_hash_matches=0
canonical_projection_active_hash_matches=1
scheduler_references=0
historical_v3_rows=24207
canonical_v4_rows=0
projection_cursor_rows=0
nonprocessed_source_rows=0
duplicate_event_identities=0
pipeline_timer_active_enabled=yes
pipeline_service_restarts=0
GX10_TRANSITIONAL_ENRICHMENT_LIVE_RETIREMENT=PASS
```

The live database remained unchanged because retirement did not invoke the unscheduled projector. Historical version-3 rows and both suppression rules remain intact. The proven automatic chain remains exactly `timer -> fetch -> ingest`.

### Post-retirement cadence evidence

Three subsequent observations passed. During the window:

- source files advanced from `10472` to `10474`
- recent events advanced from `950480` to `950657`
- nonprocessed rows remained `0`
- historical version-3 rows remained `24207`
- version-4 rows and projection cursor remained `0`
- the pipeline timer remained active/enabled
- pipeline restarts remained `0`

This proves ordinary ingestion continued independently of the retired unscheduled artifact.

### Cleanup and retained recovery

Removed only explicit agent-created temporary transfer/staging artifacts from the operator VM, collector, and GX10, plus the successful on-server rehearsal database copy. The temporary files are not retained. Durable recovery remains through:

- published GitHub commits
- live installed normalizer/handoff/projection artifacts
- protected collector plan, ledgers, and raw-view rollback evidence
- protected GX10 exact legacy-executable rollback copy
- preserved raw, shadow, handoff, ClickHouse, GX10 history, and historical enrichment state

### Next action

Publish and independently verify this item-24 completion checkpoint. Then begin item 25 by defining the deterministic incident data model and replay/idempotency contracts over canonical normalized observations. Do not schedule projection, invoke Ollama, or create a result producer merely to lengthen the pipeline; each requires its own explicit design and validation gate.

## 2026-08-24 00:07 PDT - Deterministic incident candidate and guarded migration validated locally

### Status

Execution-order item 25 remains the single `NEXT` item and is in progress.

No working GX10 application, database, unit, schedule, or model state changed in this subsection. The repository now contains the deterministic incident engine, append-only schema extension, clean-install integration, and guarded existing-database migration needed for private copy rehearsal.

### Deterministic authority contract

The version-1 engine consumes only canonical classification-version-4 projections. It does not parse raw messages, call Ollama, or allow a model to own incident identity or lifecycle.

Selected deterministic contracts are:

- correlation key from canonical family/protocol/entity type/entity key
- recurrence-specific incident ID from that correlation key plus the first immutable source-file/record identity
- one non-resolved incident per correlation key, enforced by a unique partial index
- append-only evidence and lifecycle transition tables enforced by SQLite triggers
- `CANDIDATE`, `OPEN`, `RECOVERING`, and `RESOLVED` lifecycle with an explicit transition allowlist
- immediate opening for explicit down-class state transitions
- two-adverse-observation promotion for other degradation inside a fixed 15-minute window
- candidate timeout fixed to the first adverse observation, not extended by supporting evidence
- recovery quiet resolution after five minutes and relapse reopening before that deadline
- deterministic 60-minute, 180-minute, and 24-hour compact context
- occurrence, canonical repeat-count, state-change, and strongest-severity materialization over immutable evidence

Timeouts are swept before each later observation is correlated at the monotonic processed event-time watermark. This prevents a late recovery or supporting observation from extending a candidate whose fixed deadline already passed.

### Replay and migration boundary

Each bounded batch commits evidence, transitions, incident aggregates, timeout changes, and the versioned cursor in one `BEGIN IMMEDIATE` transaction. Unique evidence event IDs preserve idempotency even if the cursor is removed and input is replayed.

The clean-machine initializer/verifier now includes the three-table, five-index, four-trigger incident extension and exact incident-engine artifact, but the systemd chain remains exactly `timer -> fetch -> ingest`. Projection and incident processing are still unscheduled.

The existing-system migration guard requires exact repository hashes, exact base/migrated schema inventories, root plus explicit confirmation, protected target/backup parents, an absent engine target, and zero systemd/cron references. It creates and validates a root-only SQLite backup before applying the migration. Rollback removes only the new empty schema and engine and refuses once either incident state or the engine cursor exists.

Candidate hashes:

- incident engine: `10b1133a00f775e5e5a4a3597156022eb46d62a2c1c2fe6424579af6341bfb6a`
- incident schema: `25f4e6a4246c2fe25ac9db726be29accef3d57b268a59f4aa676d851edb52693`
- migration guard: `b15c650e41a9c6f1b540d307e49e5218a66d0131b65acc422f69cafc692aa924`

### Synthetic and repository validation

Tests prove immediate opening, repeated-degradation promotion, supporting evidence, recovery, quiet resolution, relapse, recurrence identity, fixed candidate deadlines, replay after cursor reset, aggregate/context accounting, malformed-input transaction rollback, append-only trigger enforcement, exact migration apply/verify/rollback, schema-drift refusal, scheduler-reference refusal, and populated-state rollback refusal.

- GX10 suite: `61 passed`
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- current-tree/history/link/ref public validation: `PASS`
- `git diff --check`: `PASS`

### Next action

Publish and independently verify this intermediate item-25 checkpoint. Then use only its published exact artifacts for a protected private copy of the working GX10 database: apply the migration, run canonical projection, run incident processing, verify replay no-op and all schema/identity/evidence/transition/context invariants, and remove only the temporary rehearsal copy after success. Do not migrate or schedule the working database merely because copy rehearsal passes; record a separate activation decision and gate.

## 2026-08-24 00:14 PDT - Item-25 live-copy schema validator corrected before migration

### Status

Execution-order item 25 remains the single `NEXT` item and is in progress.

The published candidate at `936b0be737db6c1fa59c7e9f46ebfbda954f0e95` was staged under a root-only temporary rehearsal boundary on GX10. An online SQLite backup copy of the working database was created. The migration guard then failed closed before creating its protected migration backup, installing the candidate engine, or adding incident schema.

The working database was opened read-only and was not changed. The temporary rehearsal copy still had no incident tables when the failure was inspected.

### Cause and correction

The copy contained exactly the expected `18` recovered base schema objects, with no missing or extra tables/indexes and zero SQLite user/application version markers. Raw `sqlite_master.sql` hashes differed for all 18 objects because the live database retained different whitespace formatting from the reconstructed initializer. After removing only SQL whitespace and case differences, all 18 type/name/DDL comparisons matched.

This is a representation-only validator defect, not live schema drift. The guard now:

- canonicalizes only DDL whitespace and case for schema comparison
- still requires exact object types, names, statements, constraints, indexes, and triggers
- separately requires the exact complete functional suppression corpus
- separately requires zero SQLite `user_version` and `application_id`
- continues to reject extra/missing objects, semantic DDL drift, divergent artifacts, scheduler references, or unsafe parents

A new synthetic test proves suppression-state drift is refused before backup or installation. The migration test subset now passes `5/5`; the complete GX10 suite contains `62` tests.

Corrected migration-guard SHA-256:

`659b02f22a40e04c04d41afe3a3827674f22b3ca0fc4db757106ea4055779fac`

### Next action

Run the full package/public validation, publish and independently verify this narrow validator correction, replace only the temporary staged guard with those published bytes, then restart the protected copy rehearsal from a fresh database copy. The working database remains outside the rehearsal mutation boundary.

## 2026-08-24 00:15 PDT - Functional suppression boundary corrected before migration

### Status

Execution-order item 25 remains the single `NEXT` item and is in progress.

The corrected schema-comparison guard was published at `5e8445b9cd3ac1d2ed675425d02275c956916494` and independently matched GitHub. A fresh root-only working-database copy was created from those published inputs. Migration again failed closed before its protected backup, engine installation, or incident-schema transaction.

The remaining mismatch was the already documented public-sanitation boundary for suppression rules: the working database retains historical private names/reasons/timestamps, while the reconstructed public initializer deliberately uses neutral nonfunctional metadata. Functional rule IDs, evaluation order, rule types, patterns, and enabled state are the recovered contract.

The guard now compares exactly those functional fields and does not require private nonfunctional metadata to equal the public reconstruction. Tests prove both sides of the boundary:

- functional enabled-state drift is refused before backup or installation
- name/reason/creation-time differences with identical functional fields are accepted

The migration subset passes `6/6`; the complete GX10 suite contains `63` tests.

Corrected migration-guard SHA-256:

`2285f699bab9122954b852ab82834efc6472260561458128c4c2e4fb86051ab1`

The working database, active projection artifact, and automatic pipeline remain unchanged.

### Next action

Publish and independently verify this narrower functional-contract correction. Then discard only the second failed temporary copy, stage the new published guard, and rerun the full private copy rehearsal from a new online SQLite backup.

## 2026-08-24 00:19 PDT - Item-25 private live-copy and deterministic rebuild gates passed

### Status

Execution-order item 25 remains the single `NEXT` item and is in progress.

The functional-contract correction was published and independently verified on GitHub at:

`fa54c659bee8af9e24213cd1bc3145a1ebca252b` — `Honor functional suppression migration contract`

Only exact artifacts from that checkpoint were staged under a root-only temporary rehearsal boundary. The working GX10 database was opened read-only to create an online SQLite backup copy. No working application, database schema, projection row, incident state, unit, or schedule changed.

### Migration and first deterministic build

The guard successfully:

- validated the exact canonicalized 18-object base schema and functional suppression corpus
- created a root-only validated pre-migration backup
- added the three incident tables, five indexes, and four append-only triggers on the copy
- installed the exact unscheduled incident engine under a zero-scheduler-reference target
- verified the complete migrated state

The first full copy execution produced:

```text
NORMALIZED_PROJECTION scanned=952789 projected=5725 suppressed=4272 version=4
GX10_NORMALIZED_PROJECTION=PASS
INCIDENT_ENGINE scanned=5725 created=17 transitions=341 incidents=17 active=3 evidence=311 watermark_ms=1787555517496 version=1
GX10_INCIDENT_ENGINE=PASS
```

Historical classification-version-3 evidence remained exactly `24207` rows.

### Idempotency, replay, and independent determinism

A normal projector rerun scanned/projected zero rows. A normal incident-engine rerun scanned zero rows and changed no incident state.

The incident cursor was then removed on the rehearsal copy. The engine rescanned all `5725` canonical version-4 rows but created zero incidents, appended zero evidence/transitions, and reproduced the exact same state. Unique evidence event identity therefore independently protects replay even without the cursor.

Independent invariants passed for:

- SQLite quick/foreign-key checks
- unique active correlation identity
- no orphan or noncanonical evidence
- exact evidence occurrence/repeat aggregates
- current status matching final append-only transition
- engine context recomputation and append sequence checks

State totals were:

- incidents: `17`
- active: `3`
- evidence: `311`
- transitions: `341`
- deterministic state SHA-256: `91e0ba1f8968dbf34480334126aeefc4ab5115861a37d4659e77c48b4cacdfa4`

A second database was then rebuilt independently from the protected pre-migration copy. Its migration, full projection, and full incident run produced the same counters and exact state SHA-256. Its second projector and engine runs were both no-ops.

Markers:

```text
GX10_INCIDENT_ENGINE_MIGRATION=PASS
GX10_INCIDENT_ENGINE_LIVE_COPY_REHEARSAL=PASS
independent_rebuild_exact=yes
GX10_INCIDENT_ENGINE_DETERMINISM_REHEARSAL=PASS
```

The first evidence-hashing helper attempted to serialize a `sqlite3.Row` directly after successful migration/projection/engine execution and raised a local type error. It was corrected to hash tuple values; this did not alter candidate code or the working database.

Final working-database read-only postcheck retained zero version-4 projection rows, zero incident tables/state/cursors, and unchanged historical version-3 rows.

### Next action

Publish and independently verify this copy-rehearsal checkpoint. Under the operator's active production authorization, pause only the proven fetch/ingest schedule, apply the published guard to install the incident schema and exact engine artifact without invoking either projector or engine, prove empty incident state and zero scheduler references, resume the existing timer, and verify at least one ordinary fetch/ingest cadence. Retain a protected pre-migration SQLite backup and use empty-state rollback on any failed postcheck.

## 2026-08-24 00:22 PDT - Item 25 completed with unscheduled working-system migration

### Status

Execution-order item 25 is `DONE`. Item 26 is now the single `NEXT` item.

The private live-copy/determinism evidence was published and independently verified on GitHub at:

`36631749b3c64d356f45c79088af5760b81f8723` — `Record deterministic incident copy rehearsal`

Under the operator's active production authorization, only those published exact artifacts were used for the working-system operation.

### Preconditions and schedule freeze

Recorded-hash resolution found exactly one working database, canonical projection artifact, pipeline service unit, and pipeline timer unit without printing their identity-bearing names or paths.

Preconditions passed:

- pipeline timer active/enabled
- pipeline service inactive after success with zero restarts
- version-4 projection rows: `0`
- projection cursor rows: `0`
- incident tables/cursor: absent
- installed incident target: absent
- historical version-3 rows: `24207`
- published engine/schema/guard hashes exact

The timer was stopped only after the current oneshot settled. The service was allowed to finish normally; it was not killed. Database counters were sampled again only after the schedule was frozen.

### Guarded unscheduled migration

The corrected published guard:

1. validated the canonicalized exact recovered schema, functional suppression corpus, and zero SQLite version markers
2. created and validated an exclusive root-only `0600` online SQLite backup
3. applied the three-table/five-index/four-trigger incident extension transactionally
4. installed the exact engine bytes under a protected root-owned target
5. verified zero scheduler references and the complete migrated schema/artifact/backup boundary

Markers:

```text
gx10_incident_engine_migration=applied
GX10_INCIDENT_ENGINE_MIGRATION=PASS
gx10_incident_engine_migration=verified
GX10_INCIDENT_ENGINE_MIGRATION=PASS
```

Installed engine SHA-256:

`10b1133a00f775e5e5a4a3597156022eb46d62a2c1c2fe6424579af6341bfb6a`

Installed incident schema SHA-256:

`25f4e6a4246c2fe25ac9db726be29accef3d57b268a59f4aa676d851edb52693`

Protected pre-migration backup:

- mode: `0600 root:root`
- bytes: `1912111104`
- SHA-256: `b8a2352b5e96cc1007a98cc4062a69e1c1bf4daa2253f2560a88ee87ce195634`

The identity-bearing live path is intentionally omitted.

### Empty-state and ordinary-cadence proof

Neither the projector nor incident engine was invoked. Immediate post-migration state was:

- incident tables: exactly `3`
- incidents/evidence/transitions: `0 / 0 / 0`
- canonical version-4 rows: `0`
- projection/incident cursors: `0 / 0`
- incident scheduler references: `0`
- historical version-3 rows: `24207`
- source-file/recent-event counts unchanged while frozen

The existing timer was then restarted without changing enablement. One ordinary automatic `fetch -> ingest` cadence passed:

- source files: `10503 -> 10504`
- recent events: `953349 -> 953430`
- historical version-3 rows: `24207`
- canonical version-4 rows: `0`
- incidents/evidence/transitions: `0 / 0 / 0`
- projection/incident cursors: `0 / 0`
- timer: active/enabled
- service result: success
- service restarts: `0`

Final marker:

`GX10_INCIDENT_ENGINE_UNSCHEDULED_MIGRATION=PASS`

### Cleanup and retained recovery

Removed only the two failed rehearsal copies, successful working/determinism rehearsal copies, temporary transfer directories, and temporary private orchestration helpers. Those artifacts were agent-created and are not recoverable, but all durable public-safe evidence is journaled.

Retained:

- published GitHub candidate, correction, rehearsal, and completion history
- installed exact unscheduled engine and incident schema
- root-only protected pre-migration SQLite backup
- existing projection rollback and historical version-3 evidence
- unchanged raw/normalized handoff recovery boundaries

Because incident state and its cursor remain empty, the guard's narrow empty-state rollback is still available. Once managed incident processing begins, that destructive schema rollback must not be used; the state must be retained and invocation disabled instead.

### Validation and next action

Repository validation remains:

- GX10 suite: `63 passed`
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- current-tree/history/link/ref public validation: `PASS`
- `git diff --check`: `PASS`

Publish and independently verify this item-25 completion checkpoint. Then begin item 26 by designing a managed projection-before-incident invocation boundary with explicit concurrency exclusion, resource limits, telemetry, backlog behavior, failure isolation, disable/rollback controls, initial backfill, and steady-state proof. Do not add Ollama invocation or result production during item 26.

## 2026-08-24 00:35 PDT - Managed deterministic-correlation candidate validated locally

### Status

Execution-order item 26 remains the single `NEXT` item and is in progress.

No working-system file, unit, schedule, database row, projector, or incident state changed in this subsection. The repository now contains the managed invocation candidate and its inactive install/verification/activation boundary.

### Selected boundary

Canonical projection and deterministic incident processing run in one exact ordered wrapper:

```text
projection -> incident
```

The wrapper is owned by a separate offline oneshot service and monotonic timer. The existing fetch/ingest service and timer are unchanged. Correlation failure therefore cannot stop or disable durable fetch/ingest.

The service has:

- Unix-socket-only address families and no collector/result/Ollama network path
- only the application-state root writable
- `CPUQuota=100%`
- `MemoryMax=1G`
- `TasksMax=32`
- `TimeoutStartSec=10min`
- best-effort I/O priority, `Nice=5`, no capabilities, and the existing hardening family

### Concurrency, ordering, and telemetry

The runner validates the exact projection and incident hashes before loading either stage. A runtime-owned, single-link mode-`0600` advisory lock rejects overlapping managed cycles. SQLite `BEGIN IMMEDIATE` stage transactions serialize writes against concurrent ingest.

To cover rows committed during a correlation cycle, the runner performs up to three complete ordered passes and rechecks both watermarks after each pass. Success requires projection cursor equal to the highest recent-event ID and incident cursor equal to the highest version-4 event ID. Persistent concurrent lag fails visibly and is retried by the next independent cycle.

Every success emits stage markers plus one structured summary with pass count, duration, both cursors/lags, canonical rows, incidents, active incidents, evidence, and transitions. The separate verifier independently checks installed-source equality, metadata, units, private config/drop-in when used, SQLite integrity/foreign keys, incident schema, watermarks, unique active identity, and aggregates.

### Install, activation, and rollback behavior

The existing-system installer:

- installs exact projector, incident engine, runner, service, and timer bytes without overwriting divergence
- renders one protected private database-path file and one narrowly scoped runtime-identity/pipeline-order drop-in
- validates the database owner/mode and referenced existing pipeline unit
- runs `systemd-analyze verify` and reloads systemd
- refuses a pre-enabled or active correlation unit
- does not run a stage or enable a timer

The separate activator first verifies inactive installation, runs one explicit timer-disabled backfill, verifies again, then enables/starts only the correlation timer and requires zero-lag active verification. Any failure disables/stops only correlation and preserves all deterministic state for replay; it never restores an old database over newer ingest.

### Synthetic validation

Tests prove:

- projection always precedes incident processing
- repeat execution is a full no-op
- new canonical input advances both cursors exactly
- projection failure prevents incident execution
- lock contention fails without processing
- strict private database config fallback
- active verification rejects projection lag
- exact projection/incident watermarks pass
- strict private config/drop-in rendering and injection rejection
- atomic exact-file reuse and divergent-target refusal
- initial backfill precedes timer enablement
- activation failure disables correlation while preserving state
- systemd separation, offline network boundary, resource limits, and independent timer contract

Candidate SHA-256 values:

- managed runner: `dde1aff929ec52957250ebd86bac01f88554caf20117b95463bc0313e00722c4`
- service unit: `5dc2525f241f4d0574f695001d11c6cd8e5ff2f5d5597e16afadbedd6ebe0708`
- timer unit: `af4e5d582eaf76b79e5a0a4acbbe7bff9f2cc6643c36fbc8e9ea81ed7367e73c`
- inactive installer: `a5d60d1e7b87735c2318629ba31a46e5acc972ef9f95c2d9c4ca167d7a59cc2d`
- activator: `97ca6602b7f1239c20b5d05c469cbcbef56d1c154cc7959408ce9bebbba989ad`
- verifier: `49e9060aad9ad256e1aa87b92c66f3f541ff19bb6b3508b51bcd837764d0f27f`

- GX10 suite: `78 passed`
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`

### Next action

Complete the full public-repository gate, publish, and independently verify this item-26 candidate. Then use only published exact artifacts for protected working-database-copy rehearsals of inactive install, initial backfill, no-op, newly appended input, failure isolation, verifier behavior, disable, and state preservation before any working-system install.

## 2026-08-24 00:39 PDT - Managed correlation private-copy gate passed

### Status

Execution-order item 26 remains the single `NEXT` item and is in progress.

The managed-correlation candidate was published and independently verified on GitHub at:

`b4c1681ad2ec5286c0fda8082a803ab0288e3031` — `Build managed deterministic correlation candidate`

Only exact artifacts from that checkpoint were staged under a root-only temporary boundary. The current item-25 working database was opened read-only to create the rehearsal copy. Production files, units, schedules, projection rows, incident rows, and cursors remained unchanged.

### Full managed backfill and no-op

The exact published runner completed the full copy backfill in one ordered pass:

```text
NORMALIZED_PROJECTION scanned=954790 projected=7726 suppressed=5830 version=4
GX10_NORMALIZED_PROJECTION=PASS
INCIDENT_ENGINE scanned=7726 created=22 transitions=463 incidents=22 active=5 evidence=425 watermark_ms=1787556833909 version=1
GX10_INCIDENT_ENGINE=PASS
MANAGED_CORRELATION schema=1 result=pass passes=1 duration_ms=4318 recent_max_id=954888 projection_cursor=954888 projection_lag=0 canonical_rows=7726 incident_cursor=954888 incident_lag=0 incidents=22 active=5 evidence=425 transitions=463
GX10_MANAGED_CORRELATION=PASS
```

The distinction between scanned count `954790` and maximum event ID `954888` is normal SQLite identity history; success is governed by the exact cursor/max-ID watermark, not row-count equality.

The immediate second run produced:

```text
NORMALIZED_PROJECTION scanned=0 projected=0 suppressed=0 version=4
INCIDENT_ENGINE scanned=0 created=0 transitions=0 incidents=22 active=5 evidence=425 watermark_ms=0 version=1
MANAGED_CORRELATION schema=1 result=pass passes=1 duration_ms=656 recent_max_id=954888 projection_cursor=954888 projection_lag=0 canonical_rows=7726 incident_cursor=954888 incident_lag=0 incidents=22 active=5 evidence=425 transitions=463
GX10_MANAGED_CORRELATION=PASS
```

Initial deterministic incident state SHA-256:

`cc3bcd7f0fd29d6300fa1ed9ab4909489efba8a41c9462b0c7f9c5a9997e4dd0`

### New input and failure isolation

A synthetic normalized event was appended only to the copy. One managed pass projected and processed exactly one row, advanced both cursors from `954888` to `954889`, and created one distinct synthetic incident with two initial transitions. Both lags returned to zero.

Two separate copied failure states then proved:

- malformed normalized input caused the projection stage to fail and roll back its batch/cursor; incident processing was not invoked and prior deterministic state remained exact
- a valid new projection was committed, then an intentionally invalid incident cursor caused incident processing to fail; the projection remained durable and all prior incident/evidence/transition state remained exact

Markers:

```text
new_input_both_watermarks_exact=yes
projection_failure_rolled_back_and_blocked_incident=yes
incident_failure_preserved_projection_and_incident_state=yes
working_database_unchanged=yes
GX10_MANAGED_CORRELATION_COPY_REHEARSAL=PASS
```

No production event content or identity-bearing path was printed or persisted publicly.

### Next action

Publish and independently verify this copy-rehearsal checkpoint. Then stage only those published exact artifacts for the guarded inactive working-system install. Verify exact installed bytes, rendered private database/identity boundary, systemd analysis, disabled/inactive units, and unchanged database before separately invoking the explicit backfill activator.

## 2026-08-24 00:42 PDT - Existing-system libexec parent creation corrected before install

### Status

Execution-order item 26 remains the single `NEXT` item and is in progress.

The private-copy evidence was published and independently verified at `a5dac45928eb255fd5f480679019d464b3bb0989`. The inactive existing-system installer then failed closed before creating any candidate file, config, drop-in, unit, database row, cursor, or schedule.

The working host did not yet have the standard `/usr/local/libexec` parent. The clean bootstrap creates the full application directory with recursive `install -d`, but the existing-system installer required its immediate parent to preexist.

The installer now creates and verifies only that standard root-owned mode-`0755` parent before creating the application-specific subdirectory. A new test proves exact creation and idempotent reuse. Divergent ownership/mode or a symbolic-link/non-directory target still fails closed.

Corrected inactive-installer SHA-256:

`d6dd51f61ea4cdf2e7328a824c1699a2d12b77b385ff9df97c9881c48408ee3f`

The GX10 suite now contains `79` tests.

### Next action

Run the full package/public gate, publish and independently verify this portability correction, replace only the staged installer with those published bytes, and retry the inactive install. Backfill and timer activation remain prohibited until inactive verification passes.

## 2026-08-24 00:42 PDT - Managed correlation installed and verified inactive

### Status

Execution-order item 26 remains the single `NEXT` item and is in progress.

The standard-parent correction was published and independently verified on GitHub at:

`6e58460cf92e0f6a18682dbaf73a5ac6f128f00a` — `Handle absent standard libexec parent`

Only published exact artifacts were staged for the working-system operation.

### Guarded inactive installation

The existing-system installer resolved the working database, runtime identity/group, and existing pipeline unit without printing their private values. It then:

- validated database owner/group/mode and the existing loaded pipeline unit
- created the missing standard root-owned mode-`0755` libexec parent and protected application/config/drop-in directories
- installed exact canonical projector, incident engine, managed runner, correlation service, and correlation timer files without overwriting divergence
- rendered a root-owned, runtime-group-readable mode-`0640` private database-path file
- rendered one root-owned mode-`0644` drop-in containing only private runtime user/group and a reset/replacement of the pipeline ordering dependency
- ran `systemd-analyze verify`
- reloaded systemd
- refused activation as part of installation

Markers:

```text
gx10_managed_correlation=installed
GX10_MANAGED_CORRELATION_INSTALL=PASS
```

### Independent inactive verification

The published verifier proved exact installed-source equality and metadata, exact fragment/drop-in boundaries, private config equality to the already resolved database, matching database/service identity, incident schema integrity, inactive service, disabled/inactive timer, and unchanged database state.

```text
MANAGED_CORRELATION_VERIFY recent_max_id=955351 projection_cursor=0 projection_lag=955351 canonical_rows=0 incident_cursor=0 incident_lag=0 incidents=0 active=0 evidence=0 transitions=0
GX10_MANAGED_CORRELATION_INSTALLED_VERIFY=PASS
database_state_unchanged=yes
canonical_v4_rows=0
incident_rows=0
projection_cursor_rows=0
incident_cursor_rows=0
correlation_service_inactive=yes
correlation_timer_disabled_inactive=yes
existing_pipeline_unchanged=yes
GX10_MANAGED_CORRELATION_INACTIVE_INSTALL=PASS
```

Projection lag equals the highest stored event ID because no production projection has yet been invoked; the separately installed incident cursor correctly has zero lag over zero canonical rows.

### Next action

Publish and independently verify this inactive-install checkpoint. Then use the explicit activator to reverify installed state, run exactly one timer-disabled initial managed backfill, verify service success/state, enable only the correlation timer, and require active zero-lag verification. On any failure, disable correlation while preserving deterministic state and the existing fetch/ingest timer.

## 2026-08-24 00:47 PDT - Live activation failed closed on nonstandard state root; sandbox portability corrected

### Status

Execution-order item 26 remains the single `NEXT` item and is in progress.

The inactive-install checkpoint was published and independently verified at `a6d0bb26493d833a3984d2367a3412b9aff84b34`. The explicit activator then passed its complete inactive verifier but the initial service start failed before invoking the runner:

```text
service_result=exit-code
service_exit_status=226/NAMESPACE
correlation_timer_disabled_inactive=yes
GX10_MANAGED_CORRELATION_LIVE_ACTIVATION=FAIL_CLOSED
```

The clean-rebuild service fragment allowed writes only under the standard application-state root. This existing system's already validated database uses a different historical state root, and the standard root is absent. Systemd therefore rejected mount-namespace setup before application execution.

No projection row, incident row, evidence row, transition, or cursor was created. The activator disabled/stopped only correlation. The existing fetch/ingest timer remained active and unchanged.

### Narrow portability correction

The private runtime drop-in now resets the fragment's clean-rebuild write path and grants write access only to the parent directory of the exact validated database. The verifier requires this exact derived line and rejects any broader or different drop-in.

The installer supports an atomic upgrade only when the existing drop-in exactly matches the previously published inactive form. It still refuses every other divergent target. A failed post-upgrade installation restores the exact prior drop-in and reloads systemd.

The first inactive upgrade invocation encountered the service's retained `failed` flag from the namespace failure. The install gate rejected that state and atomically restored the prior drop-in. The activation failure cleanup now stops the service and clears this systemd-only flag after its failure reason has been captured. It does not remove journal evidence or deterministic database state.

Corrected artifact SHA-256 values:

- inactive installer: `16b96d9c3d084ce89cf7f2a5e18aa52e427fdfd26b23159859bd3defe0c75972`
- verifier: `1e074560abf613075481e96f6af217896782cf65fad7bd48e03ce1df46e55719`
- activator: `2cf33b6df7c09e82b39b7e2885894df62909923bd200005d962626a6cad95540`

Validation:

```text
80 tests passed
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
PUBLIC_REPOSITORY_CURRENT_TREE=PASS
PUBLIC_REPOSITORY_HISTORY=PASS
PUBLIC_REPOSITORY_LINKS=PASS
PUBLIC_REPOSITORY_REF_TOPOLOGY=PASS
PUBLIC_REPOSITORY_VALIDATION=PASS
```

### Next action

Publish and independently verify this correction. Stage only those published exact installer/verifier bytes, atomically upgrade the inactive private drop-in, reverify unchanged database and inactive scheduling, then retry the explicit fail-closed activation.

## 2026-08-24 00:55 PDT - Managed production correlation activated and item 26 completed

### Status

Execution-order item 26 is `DONE`. Item 27 is the single `NEXT` item.

The private write-scope correction was published and independently matched on GitHub at:

`213e1221ae90c0f9f5227f21db4f0fe19139d62c` — `Bind correlation sandbox to validated state root`

The retained-failed-state cleanup was then published and independently matched at:

`8525414fce4d3fd95937c45f01828dbb30f83a37` — `Reset failed correlation state during rollback`

Only exact artifacts from those public checkpoints replaced the two corrected staged files and activator. The installer atomically upgraded only the exact known inactive private drop-in. Independent inactive verification then passed with the database unchanged, correlation service inactive, correlation timer disabled/inactive, and existing fetch/ingest state unchanged:

```text
recent_max_id=955874
projection_cursor=0
projection_lag=955874
canonical_rows=0
incident_cursor=0
incident_lag=0
incidents=0
GX10_MANAGED_CORRELATION_INACTIVE_INSTALL=PASS
```

### Initial production backfill and activation

The explicit activator reverified the complete inactive boundary, ran one timer-disabled managed backfill, required zero lag, enabled only the separate correlation timer, and reverified active state:

```text
recent_max_id=955874
projection_cursor=955874
projection_lag=0
canonical_rows=8712
suppressed_rows=6622
incident_cursor=955874
incident_lag=0
incidents=23
active_incidents=3
incident_evidence=477
incident_transitions=519
incident_state_sha256=5e1797fb69a38fb57a382c42d340602d5ccb187de626c98d6859c988be97dddb
correlation_timer_active_enabled=yes
correlation_service_result=success
existing_pipeline_unchanged=yes
GX10_MANAGED_CORRELATION_LIVE_ACTIVATION=PASS
```

No Ollama call, model prompt, AI result, collector write, or Grafana change occurred.

### Three scheduled cadence gates

Three independent timer invocations were observed after the activation/backfill cycle:

| Cadence | Event/cursor ID | Canonical rows | Incidents | Active | Evidence | Transitions | Projection lag | Incident lag | Restarts |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 956240 | 9078 | 24 | 4 | 499 | 542 | 0 | 0 | 0 |
| 2 | 956338 | 9176 | 24 | 4 | 503 | 546 | 0 | 0 | 0 |
| 3 | 956413 | 9251 | 24 | 4 | 508 | 551 | 0 | 0 | 0 |

Each cadence independently passed installed artifact/private runtime, SQLite quick/foreign-key, exact schema, dual-watermark, unique-active-identity, and evidence-aggregate verification. Counts remained monotonic. The original fetch/ingest timer advanced during the same window and its service did not enter a failed state.

A final prepublication active verification later reached event/cursor ID `956995` with both lags zero, `9833` canonical rows, `27` incidents, `6` active incidents, `547` evidence rows, and `594` transitions. Both the correlation timer and original fetch/ingest timer remained active.

Markers:

```text
GX10_MANAGED_CORRELATION_CADENCE_1=PASS
GX10_MANAGED_CORRELATION_CADENCE_2=PASS
GX10_MANAGED_CORRELATION_CADENCE_3=PASS
existing_pipeline_timer_advanced=yes
aggregate_counts_monotonic=yes
three_zero_lag_cadences=yes
GX10_MANAGED_CORRELATION_MULTI_CADENCE=PASS
```

### Durable boundary

The production automatic paths are now separate:

```text
fetch/ingest timer -> fetch -> ingest
correlation timer -> canonical projection -> deterministic incident engine
```

Failure or disablement of correlation does not stop fetch/ingest. The protected item-25 pre-migration database backup remains retained. The LLM remains outside incident identity, evidence, and lifecycle authority.

### Next action

Publish and independently verify this completion checkpoint. Then begin item 27 by specifying and implementing a deterministic, replay-safe LLM wake policy and compact incident-packet contract over the active incident state. Keep inference unscheduled and exclude collector result production until their own copy-rehearsal and activation gates.

## 2026-08-24 01:09 PDT - Item 27 deterministic wake/packet repository candidate built

### Status

Execution-order item 27 remains the single `NEXT` item and is in progress. This subsection changed only public repository implementation, synthetic databases, tests, and documentation.

The item-26 completion checkpoint was independently matched on GitHub at:

`1537d1dd7c0d9106a99e60fcddb4b934a2e0732a` — `Complete managed correlation production activation`

After that durable checkpoint, the root-only item-26 rehearsal directory, user staging directory, and named item-26 temporary helper files were removed. Both installed production timers remained active. The protected item-25 pre-migration backup and all installed production state remain retained.

### Selected boundary

The candidate adds one append-only `reasoning_packets` table, two indexes, and update/delete refusal triggers plus a deterministic builder. The packet store is a fact queue, not a model-owned task database.

Wake reasons and priorities are fixed:

1. critical condition
2. incident reopen
3. incident open
4. interface flap
5. OSPF/OSPFv3 retransmission degradation
6. recovering transition
7. resolved transition
8. rate-limited meaningful update

Cooldowns and update thresholds use evidence event-time and prior immutable packet bases. First execution skips already resolved incidents and does not wake ordinary candidates. Packet IDs bind policy/packet versions, incident ID, and exact evidence/transition sequence bases.

Packets contain no raw message or source-file identity. They are canonical JSON with SHA-256, maximum `32768` bytes, at most 8 new evidence rows and 8 new transitions, explicit omitted counts, 2048-byte attribute inclusion, and digest substitution for larger attributes. Individual oversized text is similarly bounded by prefix/size/digest.

### Synthetic validation

Eight focused tests prove:

- deterministic canonical open packet creation
- full rerun and incident-cursor-reset no-op behavior
- critical OSPF candidate priority and multiple-reason ordering
- interface state-change/flap detection
- recovery then resolution packet sequencing
- no first-run backfill for historical resolved incidents
- accumulation of below-threshold evidence into one later meaningful update
- oversized-attribute digest substitution and whole-packet size bound
- append-only trigger enforcement and stored-packet tamper refusal

Validation:

```text
88 tests passed
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

Candidate SHA-256 values:

- reasoning schema: `bd46f4a51301c225e051aa6b5e27406ad06c651271d7c82fb3b67ac2b21def90`
- reasoning packet builder: `259f26353714e7ff8adbf627a33dcae6025e933f24fc9f2600b06882c3e16e00`

The clean-machine initializer/installer/verifier include the target candidate, but neither base activation nor correlation activation schedules it.

No production database, artifact, service, timer, Ollama API, model, prompt, result file, collector boundary, or Grafana state changed.

### Next action

Run the full public gate, publish, and independently verify this candidate. Then add a guarded exact-schema/exact-artifact existing-system migration and rehearse migration plus deterministic packet behavior on protected production-state copies before considering any unscheduled working-system installation.

## 2026-08-24 01:10 PDT - Item 27 guarded unscheduled migration candidate built

### Status

Execution-order item 27 remains the single `NEXT` item and is in progress.

The deterministic wake/packet candidate was published and independently matched on GitHub at:

`be366b28d8c3a2211f976e972ccf0c964e3119ef` — `Build deterministic reasoning packet candidate`

The new migration guard requires:

- exact base-plus-incident schema before apply and exact reasoning schema after apply
- exact published reasoning schema and packet-builder hashes
- unchanged functional suppression fields
- SQLite quick/foreign-key checks and zero application/user versions
- an absent target artifact and zero systemd/cron scheduler references to that target
- root-owned protected target/backup parent directories
- a new root-only mode-`0600` SQLite online backup that independently validates as exact pre-reasoning state
- preserved application-database owner/group/mode

It installs only the reasoning schema and exact mode-`0755` root-owned builder. It creates no unit, timer, cron entry, config, packet, Ollama call, or result path. Rollback removes only the reasoning table/indexes/triggers and exact builder and refuses once any packet exists. It never restores the backup over newer working state.

Five focused migration tests prove apply/verify/empty rollback, exact pre-reasoning backup, divergent-schema refusal before backup, scheduler-reference refusal, and nonempty-packet rollback refusal.

Validation:

```text
93 tests passed
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

Migration-guard SHA-256:

`2a576c11d7138a012bb3e6b9e69731c862d50931f9fa5210420bf368a68564af`

### Next action

Run the public gate, publish, and independently verify this migration candidate. Then stage only exact public artifacts on GX10 and execute the guard plus packet-builder behaviors against protected production-state copies. The working database and installed runtime remain unchanged.

## 2026-08-24 01:13 PDT - Packet raw/source attribute exclusion made explicit before copy rehearsal

### Status

Execution-order item 27 remains the single `NEXT` item and is in progress.

The guarded migration candidate was published and independently matched on GitHub at:

`dbe4912f200be85fb4654c51681f0d5bbf221f61` — `Guard reasoning packet schema migration`

Pre-copy contract review identified that excluding top-level raw messages and source paths was insufficient if a future normalized attribute dictionary introduced an equivalently named nested key. The builder now recursively removes these attribute keys before packet construction:

- `message`
- `raw_message`
- `event_json`
- `source_file`
- `source_path`
- `remote_path`
- `local_path`

When any key is removed, the packet records the removal count and SHA-256 of the original canonical attribute object. Safe structured attributes remain. The existing 2048-byte attribute and 32-KiB packet bounds still apply.

A new test proves nested raw/source keys are absent, safe siblings remain, and the redaction evidence is exact. The GX10 suite now contains `94` tests.

Corrected SHA-256 values:

- packet builder: `3543ca1dd5b661c628fbef6e0101c79d0bc236997d229ce354ba9dc618fc8145`
- migration guard: `72e425981cb028edc709186688ff40dbd4bc19d9d22b7c11e2f5e5b3644c49fe`

### Next action

Run all package/public gates, publish and independently verify the correction, then use only that public checkpoint for production-state-copy rehearsal.

## 2026-08-24 01:17 PDT - Item 27 protected production-state-copy rehearsal passed

### Status

Execution-order item 27 remains the single `NEXT` item and is in progress. The working GX10 database, installed artifacts, services, and schedules remained unchanged.

The recursive raw/source exclusion correction was published and independently matched on GitHub at:

`03ea32c271f29323bb9b0f3d25a7f399fca4d1d8` — `Exclude raw attributes from reasoning packets`

Only exact artifacts from that checkpoint were staged under a root-only temporary boundary. A SQLite online backup captured current production deterministic state without pausing either timer:

```text
snapshot_incidents=30
snapshot_active_incidents=4
snapshot_evidence=623
snapshot_transitions=678
```

### Initial packet build and determinism

The guard applied exact reasoning schema/builder bytes to the first copy and produced a separate exact pre-reasoning backup. Initial policy execution created exactly four packets for active state:

```text
initial_packets=4
initial_packet_max_bytes=6280
initial_reason_counts=incident_opened:2,incident_reopened:2
initial_packet_state_sha256=2b92193dda93187257a31030a40f8606bb4a42496978444e30cc87f08cbc1afe
```

No historical resolved incident was packeted. Every packet passed canonical JSON/digest, reason/version/priority, forbidden-key, foreign-key, and 32-KiB validation.

The immediate second build created zero rows and changed no incident/evidence/transition/packet state. Deleting only the copy's incident cursor and replaying the exact incident engine also changed no deterministic state or packet. A second independent migration/build from the original snapshot reproduced the exact packet digest.

### Threshold, lifecycle, failure, and rollback gates

On the first copy only, a synthetic adverse event opened a distinct incident and created one open packet. One later supporting evidence row created no packet. Once five supporting rows accumulated, exactly one `meaningful_update` packet was created. Recovery and the later deterministic quiet-period resolution each created the exact lifecycle packet.

After all positive gates, one separate tamper case removed the copy's update trigger and changed stored packet JSON. The builder failed closed before adding a row. A third copy proved that empty-state migration rollback removes reasoning schema and builder while retaining the protected backup.

Markers:

```text
initial_build_and_noop=yes
incident_cursor_reset_replay_exact=yes
independent_packet_reproduction_exact=yes
nonqualifying_evidence_deferred=yes
meaningful_update_threshold_exact=yes
recovery_and_resolution_packets_exact=yes
stored_packet_tamper_failed_closed=yes
empty_state_rollback_exact=yes
working_system_unchanged=yes
GX10_REASONING_PACKET_COPY_REHEARSAL=PASS
```

No production event content, packet JSON, entity identity, database path, runtime identity, or connection value was printed or committed. No Ollama API/model/prompt or collector result path was used.

### Next action

Publish and independently verify this rehearsal checkpoint. Then use only published exact artifacts to perform the guarded working-system schema/builder installation under a new protected backup, verify zero packet rows and zero scheduler references, and leave the builder unscheduled.

## 2026-08-24 01:20 PDT - Item 27 completed with unscheduled working-system installation

### Status

Execution-order item 27 is `DONE`. Item 28 is the single `NEXT` item.

The protected production-state-copy rehearsal was published and independently matched on GitHub at:

`c3b4c34b97ecb399ee6f7f50d24131e4347cd373` — `Record reasoning packet copy rehearsal`

Only the exact published schema, builder, and migration guard were staged. After both production oneshots had settled, the guarded procedure:

- confirmed both existing timers active and enabled and correlation at zero lag
- briefly stopped only those timers
- created a new root-only protected recovery parent
- made and independently validated an online backup of the exact base-plus-incident database
- applied the reasoning schema and installed the exact builder
- verified the new table empty, zero builder invocations, zero scheduler references, and unchanged incident aggregates during the pause
- resumed both timers
- ran one ordinary managed correlation catch-up and active verification

### Working-system evidence

```text
MANAGED_CORRELATION_VERIFY recent_max_id=958719 projection_cursor=958719 projection_lag=0 canonical_rows=11557 incident_cursor=958719 incident_lag=0 incidents=31 active=4 evidence=645 transitions=702
GX10_MANAGED_CORRELATION_ACTIVE_VERIFY=PASS
reasoning_schema_objects_verified=yes
reasoning_packets=0
packet_builder_scheduler_references=0
packet_builder_invocations=0
protected_backup_bytes=1928859648
protected_backup_sha256=c6f7760e3c4203eade6ffdc4d232d5af70e86b84d1ad3791210d5251289f8b34
protected_backup_mode=0600
pipeline_timer_resumed=yes
correlation_timer_resumed=yes
correlation_zero_lag_after_install=yes
GX10_REASONING_PACKET_UNSCHEDULED_INSTALL=PASS
```

The protected backup path, production database/runtime identities, connection values, and event content remain private. The protected backup is retained.

No packet was built on the working database. No inference API, model, prompt, result producer, or collector return path was added or invoked.

### Next action

Publish and independently verify this item-27 completion checkpoint. Then begin item 28 repository/copy-only: version the local model, prompt, run identity, and strictly structured output over immutable reasoning packets, with deterministic idempotency and safe inference-unavailable behavior. Do not schedule production inference or add collector result return until separate gates pass.

## 2026-08-24 01:33 PDT - Item 28 versioned local-reasoning repository candidate built

### Status

Execution-order item 28 remains the single `NEXT` item and is in progress. This subsection changed only repository artifacts, temporary synthetic databases, tests, and documentation.

Item 27 completion was published and independently matched on GitHub at:

`ae07f8f492c5a8e95d086b9af0847607296b492a` — `Complete deterministic reasoning packet milestone`

After that durable checkpoint, the exact item-27 root rehearsal copy, user staging copy, and named helper files were removed. The protected pre-reasoning recovery backup remains retained, the installed packet builder still matches its published hash, and both production timers remained active.

### Candidate boundary

The item-28 candidate adds:

- immutable exact model/options registration
- immutable exact prompt/output-schema registration
- a deterministic run reservation committed before inference
- one guarded `STARTED` to terminal transition
- append-only canonical structured results
- a fixed loopback-only Ollama request with redirects refused
- explicit no-result terminal states for unavailable, timeout, transport, invalid-response, and invalid-output outcomes

An interrupted `STARTED` run blocks automatic duplicate inference. Version 1 deliberately provides no stale-run takeover or automatic retry. The caller selects at most one highest-priority pending packet and cannot write deterministic incident, evidence, transition, or packet truth.

The initial model version binds the exact captured `qwen3:8b` manifest and config digest. It is the smallest captured local model and is selected as a bounded starting candidate, not as a quality conclusion. Its exact manifest plus active/enabled loopback-only Ollama state were revalidated without calling the API or running inference.

The prompt treats packet content as untrusted data. The output must contain an exact bounded schema with matching packet/incident IDs, fixed disposition/severity/action-risk enumerations, independent type/count/length validation, maximum 16-KiB canonical JSON, and no additional fields.

Candidate SHA-256 values:

- inference schema: `777ee4d63e1e8bcdfaaad973843d02145c45537eecd3b36e51e4a343b002ed61`
- local-reasoning caller: `9fa6a9ae51b8b1c9eeb2d908def6e09f6a7135526d49469ffefffda5e147bf38`
- runtime version configuration: `8d4846c6cd2dbde9ee8bc3a7b81d8e0a2f99185f84d476adadfeb273b4121d13`
- system prompt: `8c1fc9ab16bf819ad7884a7c45f65468e0091f7251dba1f285ab4c0859b78262`
- output schema: `b712ad9d76bdc39a023f04cdd9c680703964ae3feab3cddfb09b152a01cf9e06`

### Synthetic validation

Ten focused tests prove:

- exact model/options/prompt/schema request construction
- successful strict-output validation and canonical result hashing
- immediate no-op without a duplicate inference call
- safe terminal unavailability with unchanged incident truth
- wrong identity and additional output fields refused without storing model content
- interrupted reservation blocks automatic duplicate inference
- highest-priority pending packet selection
- forbidden raw/source packet content failure before reservation even with a matching digest
- append-only version/result rows and terminal run immutability
- prompt hash failure before database mutation
- non-loopback endpoint refusal

Validation:

```text
104 tests passed
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
PUBLIC_REPOSITORY_CURRENT_TREE=PASS
PUBLIC_REPOSITORY_HISTORY=PASS
PUBLIC_REPOSITORY_LINKS=PASS
PUBLIC_REPOSITORY_REF_TOPOLOGY=PASS
PUBLIC_REPOSITORY_VALIDATION=PASS
```

No working-system schema/artifact/run/result, production packet, Ollama API call, inference, service, timer, collector result, or Grafana state changed.

### Next action

Publish and independently verify this candidate. Then add an exact-schema/exact-artifact guarded existing-system migration and pass synthetic local-model plus protected-production-state-copy gates before any unscheduled installation or production-packet inference.

## 2026-08-24 01:37 PDT - Item 28 guarded unscheduled migration candidate built

### Status

Execution-order item 28 remains the single `NEXT` item and is in progress.

The local-reasoning repository candidate was published and independently matched on GitHub at:

`7e8475c2c1ca50df2d65cf99a75651dad704c6f9` — `Build versioned local reasoning candidate`

The existing-system guard requires:

- exact base-plus-incident-plus-packet schema before apply and exact inference schema after apply
- the exact installed item-27 packet builder hash, root ownership/mode, and zero scheduler references
- exact item-28 inference schema, caller, runtime configuration, prompt, and output-schema hashes
- a new root-only mode-`0600` SQLite online backup that independently validates as exact pre-inference state
- protected target parents and absent, distinct target files
- zero systemd/cron scheduler references to the caller
- preserved application-database owner/group/mode

Apply installs only the inference schema and four exact artifacts. It creates no unit, timer, cron entry, packet, model registration, run, result, API call, or collector path. A partial artifact-install failure rolls back the schema and removes only exact files created by that attempt. Rollback refuses once any item-28 model, prompt, run, or result row exists and never restores the backup over newer working state.

Six focused migration tests prove:

- apply, independent verify, exact artifact modes, and empty-state rollback
- exact protected pre-inference backup
- divergent-schema refusal before backup
- scheduler-reference refusal before backup
- nonempty inference-state rollback refusal
- partial artifact failure cleanup with schema rollback and retained backup

Validation:

```text
110 tests passed
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

Migration-guard SHA-256:

`7a41de4f28a5d4e5060cbe2b8cdfb0a96e9cfe160d5e172550b960cdec44862c`

No working-system artifact/schema/state, production packet, Ollama API call, inference, service, timer, collector result, or Grafana state changed.

### Next action

Run the public gate, publish, and independently verify this guard. Then use only exact published artifacts for a synthetic loopback local-model quality/failure evaluation before any production-state-copy rehearsal.

## 2026-08-24 01:54 PDT - Item 28 local-model calibration passed with strengthened output contract

### Status

Execution-order item 28 remains the single `NEXT` item and is in progress. No item-28 artifact or schema was installed on the working database and no production packet or production event content was used.

The guarded migration candidate was published and independently matched on GitHub at:

`63f9e0829220957ef4347cdd19d003ed83c1d55a` — `Guard local reasoning schema migration`

### Calibration findings

Only exact candidate artifacts and public-safe synthetic OSPF, interface, and BGP packets were staged in isolated user-owned temporary databases. Initial evaluation of the smallest captured model (`qwen3:8b`) proved the HTTP/JSON/schema path but failed quality gates: one response classified a deterministic critical wake as insufficient evidence, and stricter iterations emitted a meaningless risk-label-only action or a non-packet-derived critical tag.

The caller safely recorded those cases as invalid output with no result row. Incident and packet truth remained unchanged. Validation was not relaxed.

The version-2 prompt/caller contract now additionally enforces:

- deterministic critical/noncritical severity alignment
- action-required overall confidence from `50` through `95`
- likely-cause confidence from `1` through `95`
- two to five action-required steps with a meaningful read-only first action
- approval-required labels for restart/reload/reset/clear/change/configure/disable/enable/bounce/reseat actions
- packet-derived tag allowlisting supplied explicitly in each request
- output schema version `2` with matching structural bounds

The second-smallest captured candidate, exact `gemma4:latest`, then passed all three cases. The final isolated state contained three successful runs and three canonical results; a fourth invocation was an exact no-op.

```text
synthetic_packets=3
successful_runs=3
canonical_results=3
critical_case_escalated=true
first_actions_read_only=3
post_success_noop=yes
forbidden_result_content=0
evaluation_state_sha256=0352fb31ff61890325d687a782c4f4324dd9203aa18e9828c0d60c56bfcaebbb
ITEM28_SYNTHETIC_LOCAL_MODEL_EVAL=PASS
```

The selected model manifest was independently revalidated at SHA-256 `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb` while Ollama remained active and loopback-only.

Corrected candidate SHA-256 values:

- inference schema: `6365f99eb834c0561a1246757a4404bbbc7ec831fe910325eff8dcfd92113a90`
- local-reasoning caller: `e9b894afa16fd5f138cfeec299be58328fd02454db2b53c3e395809e04d58cd0`
- runtime version configuration: `e7bde8d878e71d8a1b11af01170ff332920aae1df1a65536b516abf5862428f0`
- system prompt: `c24a1e4a5af021ea66475cdb77c792b19f023caf93f344f64be4dedf1ebb634c`
- output schema: `1ec4e28d0d18320c7469d4f1bb26a5c766515ff008c5803d24ce214ded69928a`
- migration guard: `16f75e1138308e4bfa5c5fc3cbdb0337e4bfe4b34dbb73ce062d40577f1a79e7`

Validation:

```text
115 tests passed
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

The original fetch/ingest and correlation timers stayed active. No production database, item-27 packet builder, item-28 table/artifact, scheduler, collector result, or Grafana state changed.

### Next action

Run the full public gate, publish, and independently verify this calibrated correction. Then use only that exact checkpoint for protected production-state-copy migration/success/failure/idempotency rehearsal before any unscheduled working-system installation.

## 2026-08-24 02:01 PDT - Item 28 protected production-state-copy rehearsal passed

### Status

Execution-order item 28 remains the single `NEXT` item and is in progress. The working database, installed item-27 builder, production services/timers, collector, and Grafana remained unchanged.

The calibrated candidate was published and independently matched on GitHub at:

`dd378f61518dc2f3a88977b553245552ff1e1f24` — `Calibrate strict local reasoning output`

Only exact artifacts from that checkpoint were staged under a root-only temporary boundary. A SQLite online backup captured current production deterministic state without pausing either production timer:

```text
snapshot_incidents=51
snapshot_active_incidents=4
snapshot_evidence=893
snapshot_transitions=986
```

### Migration and rollback gates

The guard applied and independently verified the item-28 schema and exact artifacts against the copy, with all four inference tables empty and zero caller scheduler references. Empty-state rollback removed only the inference schema/artifacts and retained its backup. The rehearsal backup was then removed inside the isolated rehearsal boundary, and the guard reapplied from the unchanged base copy to prove a fresh exact installation path.

The final protected rehearsal backup is:

- bytes: `1939898368`
- SHA-256: `07fc164ab8cc21b145b8acd967c1d95d571e9256ae2c567cad04f22031cc7f66`
- mode: `0600`

Its path remains private.

### Inference state gates

The exact deterministic builder created four sanitized reasoning packets only in the copy. One highest-priority copied packet completed real loopback Gemma inference and stored one strict canonical result. Three separate copied packets exercised invalid output, inference unavailability, and interruption after durable reservation. The invalid/unavailable cases stored no result; the interruption retained exactly one `STARTED` reservation; a final invocation made no model call.

```text
copy_packets=4
copy_successful_runs=1
copy_invalid_output_runs=1
copy_unavailable_runs=1
copy_interrupted_runs=1
copy_results=1
copy_final_noop=yes
deterministic_copy_truth_unchanged=yes
copy_inference_state_sha256=6013c173f393737357b1fb26327dcddc639c546027e15b5b16d23520dfdf44ac
GX10_LOCAL_REASONING_COPY_REHEARSAL=PASS
```

No packet/result JSON, event content, entity identity, database path, or connection value was printed or committed.

### Working-system postcheck

The ordinary production schedules advanced during the rehearsal. The final postcheck showed:

```text
recent_max_id=962636
projection_lag=0
incident_lag=0
incidents=53
active=5
evidence=899
transitions=995
working_reasoning_packets=0
working_inference_objects=0
GX10_ITEM28_LIVE_POSTCHECK=PASS
ITEM28_PRODUCTION_TIMERS_ACTIVE=YES
ITEM28_CORRELATION_RESTARTS=0
ITEM28_OLLAMA_ACTIVE=YES
```

### Next action

Publish and independently verify this rehearsal checkpoint. Then use only the published exact artifacts for guarded working-system installation of the empty inference schema/caller/configuration/prompt/output-schema under a new protected backup. Leave it unscheduled and do not invoke any production packet.

## 2026-08-24 02:08 PDT - Item 28 completed with guarded empty/unscheduled working-system installation

### Status

Execution-order item 28 is `DONE`. Item 29 is the single `NEXT` item.

The protected production-state-copy evidence was published and independently matched on GitHub at:

`d1080b94ae871acf26f693ab29570b4f36a5dbec` — `Record local reasoning copy rehearsal`

Only exact artifacts from that published checkpoint were staged. The two existing production timers were briefly stopped after their oneshot services settled. A SQLite online backup was created and independently validated before the exact inference schema, caller, runtime configuration, prompt, and output schema were installed. The original timers resumed and the ordinary deterministic correlation chain caught up before the procedure returned.

The protected pre-inference backup is retained privately with:

- bytes: `1940905984`
- SHA-256: `2652acbb0389676bda5953859d6d411e6013920eff98a6c74e2028843e14396a`
- mode: `0600`

The guarded installation completed with zero reasoning packets, model versions, prompt versions, runs, results, or caller scheduler references. It made no Ollama request and produced no collector or Grafana state.

### Independent later-cadence verification

A separate read-only postcheck revalidated the exact installed schema/artifact hashes, protected backup, empty state, timer health, cursor convergence, and active local runtime after ordinary production input advanced:

```text
recent_max_id=963225
projection_lag=0
incident_lag=0
incidents=68
active=20
evidence=973
transitions=1082
reasoning_packets=0
reasoning_model_versions=0
reasoning_prompt_versions=0
reasoning_runs=0
reasoning_results=0
caller_scheduler_references=0
production_timers_active=yes
correlation_restarts=0
ollama_active=yes
production_inference_invoked=no
GX10_ITEM28_INSTALLED_POSTCHECK=PASS
```

No database path, unit identity, packet/result content, event content, entity identity, or connection value was printed or committed.

### Next action

Design and validate item 29 as a separately disableable managed `packet build -> local inference` boundary with exact hashes, single-cycle locking, bounded cadence work, explicit backlog/run/stale-reservation health, and failure isolation. Start with repository and protected-copy gates. Do not schedule production reasoning or return results to the collector until the separate activation evidence passes.

## 2026-08-24 02:21 PDT - Item 29 managed reasoning repository candidate built

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. No item-29 artifact, unit, private configuration, packet, model/prompt registration, run, result, or schedule was installed or invoked on the working system.

The repository candidate adds a third independently disableable boundary:

```text
deterministic packet builder -> at most one local-model invocation
```

The managed runner validates the exact installed item-27 builder and item-28 caller/configuration/prompt/output-schema hashes, takes a runtime-owned mode-`0600` single-cycle lock, refuses any preexisting `STARTED` reservation, runs packet construction once, permits at most one new run and one new result, and emits only aggregate packet/backlog/run/result health. It does not print packet, incident, event, or entity content.

The hardened oneshot has a three-minute timeout, one-CPU quota, 1-GiB memory limit, 32-task limit, low CPU/I/O priority, write scope limited to the validated database parent, and Unix-socket plus IPv4-loopback-only network policy. Its monotonic timer waits 15 minutes after boot and five minutes after each completed cycle. Both units remain disabled until a separate activation gate.

The installer verifies exact dependencies and leaves the service/timer inactive. The activator first verifies that boundary and creates a validated root-only mode-`0600` SQLite online backup, then permits one bounded service cycle while the timer is disabled. Only a passing post-cycle verifier may enable the timer. Any activation error disables/stops only managed reasoning and retains append-only state plus the protected backup.

Candidate SHA-256 values:

- managed runner: `54e81a5204336d7ec6d79ac5372a3a1ba5bff0e4828706e1237faa0a997e03e1`
- installer: `75654a09471dc5ecb99672dc16c326af65fbbe83ed44963010da9e9532535fd0`
- activator: `04d16e1c3eac68cc04a533bba7571ba5534a2f07af8da566a2f9c725d50b43d3`
- verifier: `b80d3de36cdeac1ea268c9c12a1edfe1dce83e248e57eefff99872ec11622708`
- service: `3559ed6a5bdfc98de3544bc6bf7f69cf6459a9cb50083cd96db632a27e52e64a`
- timer: `0c813a9f8aa695e69e7a383d681b4d5ae9b48abc18879b908bdbb4e5da763e53`

Nineteen new focused tests cover locking, no-op, one-success, one-safe-failure, two-run refusal, `STARTED` refusal, strict private configuration, installer/drop-in behavior, protected-backup-first activation ordering, activation failure isolation, bounded activation, verifier health, and hardened systemd policy.

Validation:

```text
134 tests passed
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
PUBLIC_REPOSITORY_CURRENT_TREE=PASS
PUBLIC_REPOSITORY_HISTORY=PASS
PUBLIC_REPOSITORY_LINKS=PASS
PUBLIC_REPOSITORY_REF_TOPOLOGY=PASS
PUBLIC_REPOSITORY_VALIDATION=PASS
```

### Next action

Publish and independently verify this exact candidate. Then stage only that checkpoint against a protected current-production-state copy and prove no-op, one-success, one-safe-failure, one interrupted `STARTED`, failure isolation, bounded advancement, and independent verifier behavior before any working-system installation.

## 2026-08-24 02:23 PDT - Item 29 private-copy rehearsal seam added before staging

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The initial repository candidate was published and independently matched on GitHub at:

`76b3c7a134339a0b39bd6ed82600c4469f215b00` — `Build managed local reasoning candidate`

Before protected-copy staging, review found that the managed wrapper needed an explicit injection-only transport argument to exercise safe-failure and interruption behavior through the wrapper itself without altering exact caller bytes or contacting a different endpoint. The production CLI passes no such argument and remains fixed to the exact item-28 loopback caller. One additional focused test proves forwarding of the private rehearsal transport.

Corrected managed-runner SHA-256:

`f79ed272a8638449bc6a98aefa1758e711a69645950c284869d96e03704432ca`

Validation now covers `20` focused item-29 tests within `135` passing GX10 tests. No working-system artifact/state or production inference changed.

### Next action

Run the full public gate, publish and independently verify the correction, and use only that exact checkpoint for protected current-state-copy rehearsal.

## 2026-08-24 02:30 PDT - Item 29 protected current-state-copy rehearsal passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. No item-29 artifact, unit, private configuration, schedule, packet, version row, run, result, or inference was created on the working system.

The rehearsal-seam correction was published and independently matched on GitHub at:

`ba9383f91ed1f5dcdff989eabe11627883b28488` — `Add managed reasoning rehearsal seam`

Only exact component artifacts archived from that commit were staged under a root-only temporary boundary. After repository-mode normalization, all 135 tests passed again on GX10. The systemd unit parser accepted the exact service/timer directives; its isolated fake-root start transaction could not resolve the fake root's absent base `sysinit.target`, so actual unit installation remains guarded by the installer's post-copy `systemd-analyze verify` before daemon reload or activation.

A mode-`0600` SQLite online backup captured a caught-up current production state while the original fetch/ingest and correlation timers remained active:

```text
snapshot_incidents=71
snapshot_active=4
snapshot_evidence=1114
snapshot_transitions=1244
```

### Managed execution gates

The exact runner built four sanitized packets in the success clone and completed one real loopback Gemma invocation with one canonical result. It left three pending packets and added exactly one run/result.

A separate clone returned a controlled invalid response through the private rehearsal transport. The caller stored one terminal safe-failure run and no result. A third clone raised a controlled interruption after reservation, leaving exactly one `STARTED` row; the next wrapper cycle refused it before calling transport and changed no state.

For the final no-op gate, a clone of the success state received reviewed synthetic terminal reservations for its three remaining pending packets. The exact wrapper then built zero packets, made zero transport calls, and changed no reasoning counts. The independent item-29 database verifier passed the success clone.

Every clone retained the exact same incident/evidence/transition/cursor digest as the base copy:

```text
copy_packets=4
copy_success_runs=1
copy_success_results=1
copy_pending_after_success=3
copy_safe_failures=1
copy_interrupted_started=1
copy_interrupted_retry_invoked=0
copy_noop_filled_pending=3
copy_noop_invoked=0
copy_independent_verifier=pass
copy_deterministic_truth_unchanged=yes
copy_state_sha256=0b8a0bc06a752350aa19ec77febab4c5547115aac3410c78d1f5b4e0581e40d3
GX10_MANAGED_REASONING_COPY_REHEARSAL=PASS
```

The protected base copy is retained privately with:

- bytes: `1947361280`
- SHA-256: `b5583c0ece49dea857afde03b98112d901b88be24ce5b060e79dd5fd36856d85`
- mode: `0600`

### Working-system postcheck

```text
working_recent_max_id=965309
working_projection_lag=0
working_incident_lag=0
working_reasoning_state=empty
production_timers_active=yes
production_inference_invoked=no
```

No packet/result content, event content, entity identity, database path, unit identity, or connection value was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this copy checkpoint. Then use only exact published artifacts for inactive working-system installation of the managed runner/service/timer/private configuration. Do not build a production packet or enable the reasoning timer until the separately protected initial-cycle activation gate.

## 2026-08-24 02:33 PDT - Item 29 exact inactive working-system boundary installed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The protected-copy checkpoint was published and independently matched on GitHub at:

`2652bfb393418755b41f378fab70a5943103d67a` — `Record managed reasoning copy rehearsal`

Only the exact runner/service/timer artifacts from the published candidate were installed, together with a narrowly rendered private database/runtime-identity/ordering/write-scope configuration. The installer revalidated the exact installed item-27 builder and item-28 caller/configuration/prompt/output-schema bytes, database ownership/schema, and loaded dependencies. Real on-host `systemd-analyze verify` passed before daemon reload.

The managed reasoning timer remained disabled, its service remained inactive, and neither stage was invoked. The application database was not deliberately written.

The install procedure's immediate final database verifier raced with a normal incoming batch committed after its zero-lag preflight and reported transient deterministic lag. All inactive files/units had already installed successfully, production reasoning state remained empty, and the existing correlation schedule was unaffected. The installer was not repeated.

A separate later-cadence postcheck revalidated exact source hashes/modes, private configuration/drop-in scope, unit state, dependency health, SQLite integrity/foreign keys, caught-up deterministic watermarks, empty reasoning state, and zero service restarts:

```text
recent_max_id=965682
projection_lag=0
incident_lag=0
reasoning_packets=0
reasoning_model_versions=0
reasoning_prompt_versions=0
reasoning_runs=0
reasoning_results=0
managed_reasoning_timer_enabled=no
managed_reasoning_service_invocations=0
managed_reasoning_restarts=0
production_dependencies_active=yes
production_inference_invoked=no
GX10_MANAGED_REASONING_INACTIVE_INSTALL=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, or connection value was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this inactive-install checkpoint. Then use the separate activator to create a new root-only protected pre-activation backup, run exactly one bounded production cycle while the timer is still disabled, verify the resulting aggregate state, and only then enable the reasoning timer. Collector result return remains disabled.

## 2026-08-24 02:38 PDT - Item 29 activation-timing defect caught before activation

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The inactive-install checkpoint was published and independently matched on GitHub at:

`faf1a7548a06d3d2ca226f22c74f2a64cba59a93` — `Install managed reasoning inactive`

A final review before the first production cycle found that the published timer used a boot-relative initial trigger. Because the working host has been running longer than that interval, enabling the timer could make a second cycle immediately due after the activator's deliberately bounded first cycle.

Activation was stopped before the activator ran. No pre-activation backup was created, no packet was built, no run or result row was created, no model was called, and no production inference occurred. The managed timer remains disabled, the managed service remains inactive, and all production reasoning tables remain empty.

The candidate now uses a start-relative five-minute initial delay plus the same five-minute post-cycle cadence. The installer permits this correction only when the existing timer is the exact published inactive predecessor. It upgrades that one file atomically, refuses any divergent target, and rolls back to the exact predecessor if a later installation check fails.

Corrected SHA-256 values:

- installer: `6c8ee52f8a7247275b1812129dc97bbd49c71cf741b5973153ed6391fabf90ba`
- timer: `c284e9d8cbb71775dc6b67b7451bb024d689b4ec27b89de987443a6ff77cad34`

The runner, activator, verifier, and service are byte-identical to the protected-copy candidate. Twenty-one focused item-29 tests pass within the 136-test GX10 suite.

### Next action

Run the full repository/public gates, publish and independently verify the correction, then stage only that checkpoint. Upgrade the exact old timer while it remains inactive and disabled, reverify empty reasoning state, and publish that production correction before protected activation.

## 2026-08-24 02:43 PDT - Item 29 corrected timer installed inactive

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The start-relative timer correction was published and independently matched on GitHub at:

`abbaa53ad50f00d7728379b602bd064c38d4b009` — `Correct managed reasoning activation timing`

Only the exact archive from that checkpoint was staged on GX10. After normalizing staging modes to the Git index, all 136 component tests and the filesystem contract passed on the target. The first test attempt had exposed archive-extraction group-write mode drift in three preexisting correlation tests; no installed artifact or application state changed, and exact repository-mode normalization resolved it.

The corrected installer then accepted the installed timer only because its bytes, ownership, and mode exactly matched the published inactive predecessor. It atomically replaced that file, ran real on-host systemd analysis, reloaded systemd, and left the timer disabled/inactive and service inactive. The runner, service, private configuration, drop-in, and item-27/item-28 dependencies remained exact.

Post-upgrade evidence:

```text
recent_max_id=966593
projection_lag=0
incident_lag=0
reasoning_packets=0
reasoning_model_versions=0
reasoning_prompt_versions=0
reasoning_runs=0
reasoning_results=0
managed_reasoning_timer_enabled=no
managed_reasoning_timer_active=no
managed_reasoning_service_active=no
managed_reasoning_restarts=0
production_inference_invoked=no
production_dependencies_active=yes
GX10_MANAGED_REASONING_TIMER_UPGRADE=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, or connection value was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this exact inactive-correction checkpoint. Then create the protected pre-activation backup and execute exactly one bounded production cycle while the corrected timer remains disabled. Enable the timer only if the separate activator and post-cycle verifier pass.

## 2026-08-24 02:46 PDT - Item 29 protected initial production activation passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The exact inactive-correction evidence was published and independently matched on GitHub at:

`40305b7ffcf8a299de0098d1f2ee8812fe6a3191` — `Record inactive reasoning timer correction`

The first private orchestration attempt rejected transient deterministic lag caused by an ordinary incoming batch. It stopped before creating the recovery parent or backup and before starting any service, building any packet, or calling the model. The managed reasoning boundary remained disabled, inactive, and empty.

The private wrapper was narrowed to permit read-only deterministic lag only before pausing the fetch/ingest timer, while still requiring empty reasoning state. It then required the fetch/ingest oneshot to settle and explicitly ran the existing correlation service to exact zero lag before invoking the unchanged published activator.

The activator created and validated a new root-only online backup, ran exactly one managed production cycle while the reasoning timer was still disabled, and passed the installed-state verifier. That cycle built four packets and made one successful model call with one canonical result, leaving three pending and no failed or unreconciled run. Only then did it enable the corrected start-relative timer and pass the active verifier. The private wrapper restored the independent fetch/ingest timer in its unconditional cleanup path.

```text
recent_max_id=966859
projection_lag=0
incident_lag=0
reasoning_packets=4
reasoning_pending=3
reasoning_model_versions=1
reasoning_prompt_versions=1
reasoning_runs=1
reasoning_succeeded=1
reasoning_failures=0
reasoning_results=1
reasoning_started=0
protected_backup_bytes=1951907840
protected_backup_sha256=7153ffb3ee9677c1c2c397638e8d22530bd01b6cfc9cad9deee8e763c2993d6d
protected_backup_mode=0600
pipeline_timer_resumed=yes
correlation_timer_active=yes
managed_reasoning_timer_active=yes
managed_reasoning_restarts=0
collector_result_return_enabled=no
GX10_MANAGED_REASONING_INITIAL_ACTIVATION=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, or connection value was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this activation checkpoint. Then observe multiple natural five-minute cadences, proving one-inference maximum, exact aggregate count progression, zero failures/`STARTED` rows/restarts, deterministic zero lag, and healthy independent timers before completing item 29.

## 2026-08-24 02:58 PDT - Item 29 natural cadence backlog gate failed safely

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The protected initial-activation checkpoint was published and independently matched on GitHub at:

`2529cdac40ee285da648756559c60e5934a30399` — `Record initial managed reasoning activation`

No service was manually triggered during the scheduled observation window. The first natural cadence advanced from one to two successful runs/results, with zero failures, `STARTED` reservations, or restarts and exact deterministic catch-up. It also built four new packets, increasing total packets from four to eight and pending backlog from three to six.

The second natural cadence again added exactly one successful run/result with no failure, interruption, restart, or deterministic lag. It also built four more packets, increasing total packets to 12 and pending backlog to nine. Packet arrival exceeded the deliberate one-inference-per-cycle service ceiling in two consecutive natural cadences, so the stability gate failed even though inference safety passed.

Only the managed reasoning timer was disabled and stopped. No packet, model/prompt registration, run, or result was deleted or rewritten. Fetch/ingest and deterministic correlation remained active and reached zero lag.

```text
recent_max_id=967946
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_pending=9
reasoning_model_versions=1
reasoning_prompt_versions=1
reasoning_runs=3
reasoning_started=0
reasoning_succeeded=3
reasoning_failures=0
reasoning_results=3
managed_reasoning_timer_enabled=no
managed_reasoning_timer_active=no
managed_reasoning_service_active=no
managed_reasoning_restarts=0
pipeline_timer_active=yes
correlation_timer_active=yes
collector_result_return_enabled=no
GX10_MANAGED_REASONING_BACKLOG_DISABLE=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, or connection value was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this failed-cadence/safe-disable checkpoint. Keep reasoning disabled while designing a bounded admission or coalescing correction that preserves all append-only state and prevents packet creation from outpacing one inference per cadence. Rehearse the correction on a protected production-state copy before any production resume.

## 2026-08-24 03:01 PDT - Item 29 bounded-backlog candidate built

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The failed-cadence/safe-disable checkpoint was published and independently matched on GitHub at:

`f0cbf8c170e65d3239bd09b0a250873fe40c5141` — `Record managed reasoning backlog gate failure`

Production reasoning remains disabled and inactive. No production packet, run, result, model call, or installed artifact changed during candidate development.

The corrected managed runner still validates the exact deterministic builder and item-28 inference artifacts and still permits at most one run/result. It now checks exact selected-version pending state under the same cycle lock:

- if pending is nonzero, the builder is not loaded or run
- the existing highest-priority pending packet receives the one allowed reservation
- packet count must remain fixed and pending count must fall by exactly one
- only a pending-zero cycle may run the builder, which coalesces intervening incident changes into the next latest deterministic packet set

Aggregate telemetry reports whether the builder was deferred. Existing packets, model/prompt registrations, runs, and results remain append-only.

The installer permits atomic runner replacement only when the existing root-owned mode-`0755` bytes match the exact published predecessor hash. It refuses every other divergence and retains predecessor bytes for rollback if a later installation gate fails.

Candidate SHA-256 values:

- managed runner: `c0c095661a7042be57230fb8fc856c03f5fe191ab604e4e246138f28156a3bee`
- installer: `f1f1cbc1dbe079c6e0ee8a1b67b54abd3d677199fbff43e5b633e5b8e8aec5e8`
- service: `3559ed6a5bdfc98de3544bc6bf7f69cf6459a9cb50083cd96db632a27e52e64a`
- timer: `c284e9d8cbb71775dc6b67b7451bb024d689b4ec27b89de987443a6ff77cad34`

Two new focused tests prove exact pending-backlog builder deferral/drain and exact-old-hash runner upgrade/divergence refusal. Twenty-three focused item-29 tests pass within the 138-test GX10 suite.

Validation:

```text
138 tests passed
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
PUBLIC_REPOSITORY_CURRENT_TREE=PASS
PUBLIC_REPOSITORY_HISTORY=PASS
PUBLIC_REPOSITORY_LINKS=PASS
PUBLIC_REPOSITORY_REF_TOPOLOGY=PASS
PUBLIC_REPOSITORY_VALIDATION=PASS
```

### Next action

Publish and independently verify this candidate. Stage only that exact checkpoint, create a fresh protected current-production-state copy while reasoning remains disabled, and prove one real-model cycle leaves packet count fixed at 12 while advancing runs/results from three to four and pending from nine to eight. Verify deterministic truth isolation before any working-system upgrade.

## 2026-08-24 03:05 PDT - Item 29 bounded-backlog protected-copy drain passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The bounded-backlog candidate was published and independently matched on GitHub at:

`03ac9a1ac37881b8dfb6c6d24313105e71ae6ae4` — `Bound managed reasoning backlog admission`

Only the exact archive from that checkpoint was staged on GX10. After exact Git-mode normalization, all 138 component tests and the filesystem contract passed on the target.

Reasoning remained disabled and inactive. A fresh caught-up root-only mode-`0600` SQLite online backup captured the current append-only reasoning state: 12 packets, nine pending, and three successful runs/results. A clone then ran exactly one real-model cycle through the corrected wrapper.

The wrapper explicitly deferred the builder, kept packet count fixed at 12, completed one successful inference/result, and reduced pending from nine to eight. The independent verifier passed. Incident/evidence/transition/cursor truth retained the exact pre-cycle digest. The production database remained at 12 packets, nine pending, and three runs/results, and no production inference ran.

```text
snapshot_recent_max_id=968602
snapshot_projection_lag=0
snapshot_incident_lag=0
copy_packets_before=12
copy_packets_after=12
copy_pending_before=9
copy_pending_after=8
copy_runs_before=3
copy_runs_after=4
copy_results_before=3
copy_results_after=4
copy_builder_deferred=yes
copy_model_invocations=1
copy_failures=0
copy_started=0
copy_deterministic_truth_unchanged=yes
copy_state_sha256=e89219c90be5e8e19fefcec3488a0606ffe6f7caa265635b060be2b2f11d2f93
protected_base_bytes=1956794368
protected_base_sha256=61374f13609eef5c225fc6467e17800e46c6dd59061d5efeefa7b314fadf04e7
protected_base_mode=0600
working_packets=12
working_pending=9
working_runs=3
working_results=3
working_reasoning_timer_enabled=no
working_production_inference_invoked=no
GX10_MANAGED_REASONING_BACKLOG_COPY_REHEARSAL=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, or connection value was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this protected-copy checkpoint. Then use only the exact staged installer/runner to atomically replace the exact predecessor runner while reasoning remains disabled. Reverify the unchanged 12/9/3/3 state before any resume.

## 2026-08-24 03:07 PDT - Item 29 bounded-backlog runner installed inactive

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The protected backlog-drain rehearsal was published and independently matched on GitHub at:

`8795db8fb86b49a74a5034af2913af76d4bb7519` — `Record backlog drain copy rehearsal`

The exact staged installer accepted the working runner only because it retained the exact published predecessor hash, root ownership, and mode. It atomically installed the corrected runner, reused the already corrected timer and unchanged service/private binding, ran real on-host systemd analysis, and left both reasoning units inactive with the timer disabled.

A digest across all five append-only reasoning tables matched before and after. Production remained at 12 packets, nine pending, and three successful runs/results. No packet was built, no model was called, and no run/result was added. Fetch/ingest and correlation remained active with deterministic zero lag.

```text
recent_max_id=968772
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_pending=9
reasoning_model_versions=1
reasoning_prompt_versions=1
reasoning_runs=3
reasoning_started=0
reasoning_succeeded=3
reasoning_failures=0
reasoning_results=3
reasoning_state_sha256=79f0c9a202327d74dc32e8d8e982bdcc52011d2b762283e78ce9f8889990600c
managed_reasoning_timer_enabled=no
managed_reasoning_timer_active=no
managed_reasoning_service_active=no
managed_reasoning_restarts=0
production_inference_invoked=no
pipeline_timer_active=yes
correlation_timer_active=yes
GX10_MANAGED_REASONING_RUNNER_UPGRADE=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, or connection value was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this inactive-upgrade checkpoint. Then create a fresh protected pre-resume backup and use the unchanged fail-closed activator for exactly one corrected production drain while the timer is disabled. Enable the timer only after aggregate verification proves packets fixed at 12, pending 9→8, and runs/results 3→4.

## 2026-08-24 03:09 PDT - Item 29 protected corrected production resume passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The exact inactive runner-upgrade checkpoint was published and independently matched on GitHub at:

`94e9686e804b1eeade5349acb355f1a6940a4367` — `Record inactive backlog runner upgrade`

A fresh root-only recovery boundary was created. The private wrapper paused only the fetch/ingest timer, waited for its oneshot to settle, and ran deterministic correlation to exact zero lag. The unchanged published activator validated the corrected installed bytes and disabled unit state, then created a new mode-`0600` SQLite online backup.

With the reasoning timer still disabled, exactly one corrected production cycle deferred packet construction, kept total packets fixed at 12, reduced pending from nine to eight, and advanced successful runs/results from three to four. There were no failures or `STARTED` reservations. Only after the installed-state verifier passed did the activator enable the corrected timer and pass active verification. The private wrapper restored the fetch/ingest timer unconditionally.

```text
recent_max_id=968943
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_pending=8
reasoning_model_versions=1
reasoning_prompt_versions=1
reasoning_runs=4
reasoning_succeeded=4
reasoning_failures=0
reasoning_results=4
reasoning_started=0
protected_backup_bytes=1957724160
protected_backup_sha256=3c2ee6430eb16c8b8ee04b421bbca71ded855e22565b56a4f61e602257139696
protected_backup_mode=0600
pipeline_timer_resumed=yes
correlation_timer_active=yes
managed_reasoning_timer_active=yes
managed_reasoning_restarts=0
collector_result_return_enabled=no
GX10_MANAGED_REASONING_BACKLOG_RESUME=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, or connection value was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this corrected-resume checkpoint. Then observe multiple natural five-minute cadences. Every reviewed cycle must keep packets fixed at 12, reduce pending by exactly one, add exactly one successful run/result, retain zero failure/`STARTED` rows/restarts and deterministic zero lag, and keep all independent production schedules healthy.

## 2026-08-24 03:14 PDT - Item 29 first corrected natural drain cadence passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The corrected-resume checkpoint was published and independently matched on GitHub at:

`18154004d5c91d4eedfa86b0c196249de339c931` — `Record corrected managed reasoning resume`

No service was manually triggered. The corrected timer's first natural cadence deferred packet construction, kept total packets fixed at 12, reduced pending from eight to seven, and advanced successful runs/results from four to five. Deterministic watermarks were exactly caught up; failures, `STARTED` reservations, and restarts remained zero; fetch/ingest, correlation, and reasoning timers were all active.

```text
recent_max_id=969312
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_pending=7
reasoning_model_versions=1
reasoning_prompt_versions=1
reasoning_runs=5
reasoning_started=0
reasoning_succeeded=5
reasoning_failures=0
reasoning_results=5
managed_reasoning_restarts=0
pipeline_timer_active=yes
correlation_timer_active=yes
managed_reasoning_timer_active=yes
collector_result_return_enabled=no
GX10_MANAGED_REASONING_DRAIN_CADENCE_1=PASS
```

### Next action

Run the full public gate, publish, and independently verify this first corrected cadence. Then continue natural monitoring without manual service invocation; require the same fixed packet count and exact one-packet pending drain for at least two more independent cadences.

## 2026-08-24 03:20 PDT - Item 29 second corrected cadence isolated invalid output and disabled safely

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The first corrected natural-drain checkpoint was published and independently matched on GitHub at:

`64e26da90c5e8a5c3401f8687b94f0c4a4842cf1` — `Record first corrected reasoning cadence`

No service was manually triggered. The second corrected natural cadence deferred packet construction, kept total packets fixed at 12, and consumed exactly one pending reservation. The local model response failed the unchanged strict output contract. The caller stored one terminal `INVALID_OUTPUT` run, no result, and no invalid model content. The service exited nonzero as designed.

The rollout monitor rejected the cadence because success/result counts no longer equaled total runs. Only the managed reasoning timer was immediately disabled and stopped before another cadence. Fetch/ingest and deterministic correlation remained active. Aggregate diagnosis proved six pending packets, five successful runs/results, one terminal safe failure, zero `STARTED` reservations, zero restarts, and deterministic zero lag.

```text
recent_max_id=969964
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_pending=6
reasoning_model_versions=1
reasoning_prompt_versions=1
reasoning_runs=6
reasoning_started=0
reasoning_succeeded=5
reasoning_failures=1
reasoning_results=5
run_status_invalid_output=1
run_status_succeeded=5
managed_service_result=exit-code
managed_service_exit_status=1
managed_reasoning_restarts=0
managed_reasoning_timer_enabled=disabled
managed_reasoning_timer_active=inactive
GX10_MANAGED_REASONING_DIAGNOSIS=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, connection value, or invalid model output was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this terminal-safe-failure checkpoint. On a fresh protected copy only, remove the terminal diagnostic reservation under an explicitly local-only trigger override and rerun the same selected packet through the unchanged caller/validator. If it succeeds, treat production failure as reviewed stochastic evidence and resume without rewriting it. If it fails consistently, keep reasoning disabled and correct prompt/model compatibility before any resume.

## 2026-08-24 03:28 PDT - Item 29 persistent invalid-output cause isolated and compatibility candidate validated

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The terminal-safe-failure checkpoint was published and independently matched on GitHub at:

`314fb31bf8e6d0e08b650331de86caac7772248c` — `Record managed reasoning invalid output isolation`

Production reasoning remained disabled and unchanged. A fresh caught-up protected copy removed only the copied terminal diagnostic run behind a temporary copy-local trigger override, recreated the trigger immediately, and replayed the exact same packet through the unchanged caller at temperature zero. The response again failed strict action-text validation. Deterministic truth was unchanged and production was not retried.

A second protected-copy-only replay classified the response without printing packet or output content. The model generated four actions; one action's text exactly equaled one of the three action-risk labels. This proved a persistent generation-schema compatibility defect rather than a transient transport failure. The strict caller rule remains correct.

The candidate output schema now excludes exact risk labels from the action-text field while retaining the separate required risk field. Caller validation is not weakened. The installer permits only exact-old-hash atomic replacement of the coordinated output schema, local caller, and managed runner while reasoning is disabled; any divergent predecessor is refused and a later caught failure restores changed artifacts.

```text
protected_same_packet_retry=invalid
protected_validation_class=action_text
diagnostic_action_count=4
diagnostic_action_text_category=action_text_equals_risk_label
production_packets=12
production_pending=6
production_runs=6
production_succeeded=5
production_failures=1
production_results=5
production_started=0
managed_reasoning_timer_enabled=no
managed_reasoning_timer_active=no
output_schema_sha256=d2917c40b867aa801934579e0779f001dc8e71953aaf3ddaa2134d0736f25a51
local_caller_sha256=31c90b4ef759df097c0c018b6a70adb82a7c1b6939bbd3bd10704f2be70a5f9d
managed_runner_sha256=1b4fa5150149cc3556f3ddfec2ed85f1b4c6e61e15fef1989bc0b0a5e39e25fa
managed_installer_sha256=4eebf64ef2a9fca3b5b2aa97a737d7f262ba857728badced963bf9a5e5b355e3
local_migrator_sha256=a776e5869f006c584e42b76301fd7e98ff761c43e6e0682b173b84dba78188dc
gx10_tests=140
GX10_REBUILD_PACKAGE_VALIDATION=PASS
PUBLIC_REPOSITORY_VALIDATION=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, connection value, or invalid model output was printed or committed.

### Next action

Publish and independently verify the 140-test compatibility candidate, stage its exact bytes on GX10, and rerun the full remote suite. Then replay the same failed packet only on a fresh protected current-state copy through the strengthened generation schema and unchanged caller validator. Do not install or resume production unless that protected-copy replay succeeds.

## 2026-08-24 03:35 PDT - Item 29 compatibility provenance corrected before inference

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The initial strict generation-schema candidate was published and independently matched on GitHub at:

`706797890dfd399f8ec21d47eaaecab16db195ec` — `Prevent risk labels as reasoning actions`

Its exact archive was staged under a new root-only GX10 boundary. The first remote test run exposed only archive-extraction mode drift; after exact Git-mode normalization, all 140 tests and the filesystem contract passed on GX10. No installed artifact or application state changed.

A fresh protected-copy replay then stopped before model transport and left no new run. The existing append-only prompt-version registration correctly refused the new output-schema hash under the old `incident-assessment-v2` identity. This was a provenance design defect in the candidate, not a runtime/model failure. Production remained unchanged and disabled.

The correction registers immutable prompt revision `incident-assessment-v2-r2` with a distinct creation timestamp while retaining the original system-prompt bytes and exact model version. The runtime configuration joins the schema, caller, and managed runner as a fourth exact-old-hash compatibility artifact. The original prompt registration, five successful results, and one terminal failure remain unchanged; the revised prompt version intentionally sees all 12 packets as a clean new-version backlog.

Focused tests now assert the new prompt-version/output-schema/timestamp registration and exact four-artifact predecessor set. The full 140-test suite, repository sanitation/history/link checks, and strict Git integrity pass locally.

```text
initial_candidate_commit=706797890dfd399f8ec21d47eaaecab16db195ec
remote_tests_after_mode_normalization=140
first_schema_copy_model_invocations=0
first_schema_copy_new_runs=0
first_schema_copy_failure_class=immutable_prompt_provenance
production_changed=no
production_reasoning_enabled=no
revised_prompt_version=incident-assessment-v2-r2
revised_version_pending_packets=12
runtime_config_sha256=db2122a46e01c32d52aef8516280039477acbf86ae367ae8e6afe533773aa8f4
output_schema_sha256=d2917c40b867aa801934579e0779f001dc8e71953aaf3ddaa2134d0736f25a51
local_caller_sha256=0aabe2a84e254d9f9c0286d21774c1bfab8cd3a94577dc84a429fc0226bc95c6
managed_runner_sha256=fbcf609162df0e5f2b4195404a8f4cbf1f7e6838c52dd22a325197aca6c47b8f
managed_installer_sha256=06ee615ec577f752f5b443e3d28ea241dd6efe45a3378b4e88126c568d88f698
local_migrator_sha256=f81fd0a2bd2ceea47e9eca05e33c8addd1e150de8d05106d1ff00bc30e97bde9
gx10_tests=140
GX10_REBUILD_PACKAGE_VALIDATION=PASS
PUBLIC_REPOSITORY_VALIDATION=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, connection value, or model output was printed or committed.

### Next action

Publish and independently verify this immutable-provenance correction. Stage and retest only its exact bytes on GX10. On a fresh protected copy, explicitly isolate the previously failed packet within the new prompt revision without exposing content, then require exactly one successful revised-version run/result through the strengthened schema and unchanged validator before any production artifact upgrade.

## 2026-08-24 03:41 PDT - Item 29 local-runtime schema support bounded before production

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The immutable-provenance correction was published and independently matched on GitHub at:

`50644549fb82bc4f69da5a33f6d2cab79c584482` — `Version reasoning schema compatibility provenance`

Its exact archive was staged under a new root-only GX10 boundary, normalized to Git modes before execution, and passed all 140 tests plus the filesystem contract on GX10.

On a fresh protected copy, 11 explicit copy-only terminal diagnostic reservations isolated the exact packet that had failed in production as the only eligible packet for prompt revision `incident-assessment-v2-r2`. The real local model was invoked exactly once. The runtime accepted the schema but the unchanged caller again classified the response as `action_text`; a second independently created protected copy reproduced the same classification. The revised-version run was safely terminal, no result/content was stored, deterministic truth was unchanged, and production remained disabled and unchanged.

This proves the local structured-output runtime does not enforce the JSON Schema `not/enum` expression. Validation remains strict. The next candidate, immutable prompt revision `incident-assessment-v2-r3`, retains that negative enum and adds `minLength=25` for action text. Twenty-five is longer than every risk label and remains below all calibrated meaningful action examples. The focused test now asserts both facts. All four compatibility targets still accept only the exact production predecessors.

```text
published_provenance_commit=50644549fb82bc4f69da5a33f6d2cab79c584482
remote_tests=140
r2_copy_model_invocations=1
r2_copy_same_packet=yes
r2_copy_only_seeded_runs=11
r2_copy_outcome=invalid
r2_validation_class=action_text
r2_second_copy_outcome=invalid
r2_deterministic_truth_unchanged=yes
production_packets=12
production_old_version_pending=6
production_runs=6
production_succeeded=5
production_failures=1
production_results=5
production_reasoning_enabled=no
r3_prompt_version=incident-assessment-v2-r3
r3_runtime_config_sha256=8a55aeb708a05fafd3eb1d4df206714339deb344588f218f00ecbee5fdd93cd9
r3_output_schema_sha256=13083841c44253b326f1294b930acae435bfdddb458b47c31a9fd385b181abd0
r3_local_caller_sha256=dac1e176108452c77ea4eb2f7195dd8eb8223576ab8cbdb2cb95a2acbb8fcbe8
r3_managed_runner_sha256=9b70fade2b79e75f1b41ea57c1bd4a6728331cb73a3d02f1b37c7abae02551b8
r3_managed_installer_sha256=06ee615ec577f752f5b443e3d28ea241dd6efe45a3378b4e88126c568d88f698
r3_local_migrator_sha256=d477ce16df5835a5406e8d02bce8fbe36a94049477ed4c09f158ccd2ac2780ee
gx10_tests=140
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, connection value, or model output was printed or committed.

### Next action

Run the full public gate, publish, and independently verify the portable `r3` candidate. Stage and retest only that exact commit. Then repeat the isolated same-packet protected-copy gate and require one valid revised-version result before any inactive production upgrade.

## 2026-08-24 03:45 PDT - Item 29 portable r3 same-packet protected-copy gate passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The portable-schema prompt revision was published and independently matched on GitHub at:

`9ca7dad5d107e5dd6bf72483a9f030687e505572` — `Use portable reasoning action bound`

Its exact archive was staged under a new root-only GX10 boundary, normalized to Git modes, and passed all 140 tests plus the filesystem contract on GX10.

A fresh caught-up protected copy retained all production rows, then added 11 explicit copy-only terminal reservations for prompt revision `incident-assessment-v2-r3`. That made the exact packet which previously failed the only eligible revised-version packet. One real local-model invocation produced one valid result through the unchanged strict caller validator. The portable generation schema therefore corrected the diagnosed compatibility failure without relaxing validation.

The copy's incident/evidence/transition digest remained unchanged. Production remained at 12 packets, six original-version pending packets, six total runs, five successes/results, one terminal failure, and zero `STARTED` rows. The reasoning timer remained disabled and no production inference ran.

```text
published_r3_commit=9ca7dad5d107e5dd6bf72483a9f030687e505572
remote_tests=140
copy_snapshot_recent_max_id=971920
copy_model_invocations=1
copy_same_packet=yes
copy_revised_prompt_version=yes
copy_only_seeded_runs=11
copy_outcome=valid
copy_validation_class=valid
copy_deterministic_truth_unchanged=yes
protected_base_bytes=1965944832
protected_base_sha256=2e485f30b1f939602b8f5e151b8e70eab474a2be6590de7a76b8bf12c1400408
protected_base_mode=0600
production_packets=12
production_old_version_pending=6
production_runs=6
production_succeeded=5
production_failures=1
production_results=5
production_started=0
production_reasoning_enabled=no
production_inference_invoked=no
GX10_MANAGED_REASONING_R3_COPY_REPLAY=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, connection value, or model output was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this protected-copy checkpoint. Then use only the exact staged installer to replace the four exact predecessor runtime-config/schema/caller/runner files while reasoning remains disabled. Require unchanged append-only production state/digest, revised-version pending 12, zero `STARTED` rows, and healthy independent schedules before any protected production drain.

## 2026-08-24 03:50 PDT - Item 29 exact r3 compatibility bytes installed inactive

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The successful portable same-packet protected-copy checkpoint was published and independently matched on GitHub at:

`ff5e9f704e33ae7717e22c57c173afb92b42f177` — `Record portable reasoning copy replay`

Using only the exact already tested `r3` staging boundary, the installer accepted each installed production file only because it matched the exact published predecessor hash, root ownership, and mode. It atomically replaced the runtime configuration, output schema, local caller, and managed runner. The corrected timer, service, private binding, prompt, and deterministic builder were reused unchanged.

Reasoning remained disabled and inactive throughout. The complete digest across packets, model/prompt registrations, runs, and results matched before and after. No packet was built, no prompt revision was registered, no model was called, and no run/result was added. The new runner reports all 12 packets pending for `incident-assessment-v2-r3`; the one stored prompt registration and all six original-version runs remain unchanged. Fetch/ingest and correlation stayed healthy at deterministic zero lag.

```text
recent_max_id=972109
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_revised_pending=12
reasoning_model_versions=1
reasoning_prompt_versions=1
reasoning_runs=6
reasoning_started=0
reasoning_succeeded=5
reasoning_failures=1
reasoning_results=5
reasoning_state_sha256=f0ccc5c597e740d22164815af28f3e15ecff8197c7ffd353af6d3cee04e99421
managed_reasoning_timer_enabled=no
managed_reasoning_timer_active=no
managed_reasoning_service_active=no
managed_reasoning_restarts=0
production_inference_invoked=no
pipeline_timer_active=yes
correlation_timer_active=yes
GX10_MANAGED_REASONING_R3_INACTIVE_UPGRADE=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, connection value, or model output was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this inactive-upgrade checkpoint. Then create a fresh protected pre-resume backup and run exactly one `r3` production drain while the timer remains disabled. Enable the timer only after aggregate verification proves packets fixed at 12, revised pending 12→11, prompt versions 1→2, runs 6→7, successes/results 5→6, the historical failure fixed at one, zero `STARTED` rows, and deterministic zero lag.

## 2026-08-24 03:54 PDT - Item 29 protected r3 production resume passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The exact inactive `r3` upgrade checkpoint was published and independently matched on GitHub at:

`78d7cac769271343372ab94fc19872a1a04a6e02` — `Record inactive r3 reasoning upgrade`

A new root-only recovery boundary was created. The private wrapper paused fetch/ingest after its oneshot settled, ran deterministic correlation to exact zero lag, and invoked the unchanged activator while the reasoning timer was still disabled. The activator verified every installed `r3` byte and the historical append-only reasoning state, then created a fresh mode-`0600` SQLite online backup.

Exactly one bounded `r3` production cycle kept packets fixed at 12, reduced revised-version pending from 12 to 11, registered `incident-assessment-v2-r3` once, and added one successful run/result. The original five successes/results and one terminal failure remained unchanged; no `STARTED` row or restart appeared. Only after installed verification passed did the activator enable the timer and pass active verification. The wrapper restored fetch/ingest unconditionally.

```text
recent_max_id=972391
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_revised_pending=11
reasoning_model_versions=1
reasoning_prompt_versions=2
reasoning_runs=7
reasoning_started=0
reasoning_succeeded=6
reasoning_failures=1
reasoning_results=6
protected_backup_bytes=1967226880
protected_backup_sha256=a9bd09c6f0248bea473c844e5d222cdfd58c1e46cc088de1e2213dc7911cd4db
protected_backup_mode=0600
pipeline_timer_resumed=yes
correlation_timer_active=yes
managed_reasoning_timer_active=yes
managed_reasoning_restarts=0
collector_result_return_enabled=no
GX10_MANAGED_REASONING_R3_RESUME=PASS
```

No packet/result content, event content, entity identity, database path, private runtime identity, connection value, or model output was printed or committed.

### Next action

Run the full public gate, publish, and independently verify this protected-resume checkpoint. Then observe at least three natural timer cadences without manual service invocation. Require packets fixed at 12, revised pending reduced by exactly one, one new success/result per cadence, exactly one historical failure, zero `STARTED` rows/restarts, deterministic zero lag, and healthy fetch/ingest plus correlation. Disable only reasoning immediately on any new failure.

## 2026-08-24 03:59 PDT - Item 29 first natural r3 cadence passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The protected `r3` production-resume checkpoint was published and independently matched on GitHub at:

`01cc9d4fd9f6bafba29475b78b35c93431cfd7e3` — `Record protected r3 reasoning resume`

No service was manually invoked. The first natural `r3` cadence kept total packets fixed at 12, reduced revised-version pending from 11 to 10, and advanced total runs from seven to eight plus successes/results from six to seven. The historical failure remained exactly one. There were zero `STARTED` rows or restarts, deterministic watermarks were caught up, and fetch/ingest, correlation, and reasoning timers were all active.

```text
recent_max_id=973232
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_revised_pending=10
reasoning_model_versions=1
reasoning_prompt_versions=2
reasoning_runs=8
reasoning_started=0
reasoning_succeeded=7
reasoning_failures=1
reasoning_results=7
managed_reasoning_restarts=0
pipeline_timer_active=yes
correlation_timer_active=yes
managed_reasoning_timer_active=yes
collector_result_return_enabled=no
GX10_MANAGED_REASONING_R3_CADENCE_1=PASS
```

### Next action

Run the full public gate, publish, and independently verify this cadence. Then continue timer-only monitoring for at least two more natural cadences under the same exact invariants and immediate reasoning-only disable rule.

## 2026-08-24 04:05 PDT - Item 29 second natural r3 cadence passed

### Status

Execution-order item 29 remains the single `NEXT` item and is in progress. The first natural `r3` cadence checkpoint was published and independently matched on GitHub at:

`cbd4cd36520ec673ce1c78f11b104f25c9c10cc8` — `Record first natural r3 cadence`

No service was manually invoked. The second natural `r3` cadence kept total packets fixed at 12, reduced revised-version pending from 10 to nine, and advanced total runs from eight to nine plus successes/results from seven to eight. The historical failure remained exactly one. There were zero `STARTED` rows or restarts, deterministic watermarks were caught up, and fetch/ingest, correlation, and reasoning timers were all active.

```text
recent_max_id=974191
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_revised_pending=9
reasoning_model_versions=1
reasoning_prompt_versions=2
reasoning_runs=9
reasoning_started=0
reasoning_succeeded=8
reasoning_failures=1
reasoning_results=8
managed_reasoning_restarts=0
pipeline_timer_active=yes
correlation_timer_active=yes
managed_reasoning_timer_active=yes
collector_result_return_enabled=no
GX10_MANAGED_REASONING_R3_CADENCE_2=PASS
```

### Next action

Run the full public gate, publish, and independently verify this cadence. Then continue timer-only monitoring for at least one more natural cadence under the same exact invariants and immediate reasoning-only disable rule.

## 2026-08-24 04:10 PDT - Item 29 completed after third natural r3 cadence

### Status

Execution-order item 29 is complete. The second natural `r3` cadence checkpoint was published and independently matched on GitHub at:

`b633f6749a8a220d24bc2a4473596177a2058010` — `Record second natural r3 cadence`

No service was manually invoked. The third natural `r3` cadence kept total packets fixed at 12, reduced revised-version pending from nine to eight, and advanced total runs from nine to ten plus successes/results from eight to nine. The historical failure remained exactly one. There were zero `STARTED` rows or restarts, deterministic watermarks were caught up, and fetch/ingest, correlation, and reasoning timers were all active.

Together, the protected initial `r3` drain and three independent natural cadences each consumed exactly one revised-version reservation and stored exactly one valid result. The immutable original failure never increased or blocked newer-version progress. Item 29 therefore satisfies bounded invocation, failure isolation, backlog control, provenance, strict-output, protected activation, and multi-cadence production stability gates.

```text
recent_max_id=974660
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_revised_pending=8
reasoning_model_versions=1
reasoning_prompt_versions=2
reasoning_runs=10
reasoning_started=0
reasoning_succeeded=9
reasoning_failures=1
reasoning_results=9
managed_reasoning_restarts=0
pipeline_timer_active=yes
correlation_timer_active=yes
managed_reasoning_timer_active=yes
collector_result_return_enabled=no
GX10_MANAGED_REASONING_R3_CADENCE_3=PASS
ITEM_29_MANAGED_REASONING=COMPLETE
```

No packet/result content, event content, entity identity, database path, private runtime identity, connection value, or model output was printed or committed.

### Next action

Execution-order item 30 is the single `NEXT` item. Begin repository/copy-only design and implementation of a versioned idempotent GX10 result outbox that maps only successful append-only reasoning results to the collector's thin JSONL contract. Prove deterministic mapping, provenance, duplicate suppression, atomic publication, crash recovery, strict bounds, and protected-copy behavior before installing any result-writer credential or transmitting to the collector.

## 2026-08-24 04:18 PDT - Item 30 result-outbox repository and protected-copy gates passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. A versioned read-only result-outbox producer now maps only successful append-only reasoning results to exactly one canonical newline-terminated collector JSONL record/file per run. The thin collector fields are retained while the complete structured result and exact packet/model/prompt/schema/request/run provenance remain in the record. Filenames derive from a versioned truncated run-ID digest and do not expose the run ID in directory listings.

The producer validates one read-only SQLite snapshot, integrity/foreign keys, required tables, the success/result invariant, canonical JSON and hashes, exact cross-table identities/timestamps/schema versions, provenance formats, safe directory/lock/file metadata, one-record/256-KiB bounds, and all preexisting outbox entries before publication. It uses a single nonblocking lock, unique mode-`0600` temporary files, file and directory `fsync`, mode-`0640` atomic publication, exact no-op reuse, and strict producer-partial recovery. It has no network import or transport operation and cannot change the source database.

Nine focused tests cover complete collector-compatible mapping, terminal-failure exclusion, exact reuse, divergence refusal before other publication, interruption after one file plus idempotent resume, strict stale-partial recovery, unexpected-entry refusal, lock contention, digest tamper refusal, and symlink refusal. The complete local gate passed 149 tests, the GX10 filesystem contract, repository sanitation/current-tree/history/link/ref checks, strict Git integrity, and diff hygiene.

The exact staged tree and archive were bound before remote execution:

```text
staged_tree=2e94f6c8d955324a090e23e708e2b15a2012e301
staged_archive_sha256=808d8d0fc845e1cece9226cdf9b4dd4edd4889e43bfebdee2e14d2ab97cbf7e6
producer_sha256=d86dd906428bf74ee875d1b62fc2dca634e1fd39b2318b2d47a94048d8a3e63d
focused_test_sha256=eb3ee0deb33430ca505378f355d00b4be669f2bb3fbdff695c519ce9f5b9da04
collector_gate_sha256=6aebc562ab305ec201e687dbce4d1ac85693c52551bd70cf5f6a7a13df0c9515
local_tests=149
remote_tests=149
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

The exact tree reproduced all 149 tests and the filesystem contract on GX10. A root-only mode-`0600` SQLite online backup then captured 12 packets, 12 terminal runs, 11 successful append-only results, and the one preserved historical failure. The producer created exactly 11 mode-`0640` single-record files. Every file passed the unchanged collector gate. A second invocation created zero files and exactly reused all 11; the complete deterministic outbox digest was unchanged. The protected copy's bytes/hash and reasoning aggregates were unchanged, all three production schedules and their service restart states remained healthy, and no collector connection or transmission occurred.

Two pre-copy wrapper attempts stopped before backup creation: the first incorrectly requested restart telemetry from timer units, and the second used the public neutral pipeline name instead of the deliberately private installed legacy unit. The corrected wrapper separately verified timer activity and service restart state and derived the private pipeline binding without printing it. These were verifier-only corrections; neither failed attempt created the protected-copy root or changed production.

```text
protected_copy_bytes=1977118720
protected_copy_sha256=500ef3c51ff14c0724ee3a84ea4d3d471918107d04a9a5557df5c0467e398db8
copy_packets=12
copy_runs=12
copy_results=11
preserved_failures=1
outbox_files=11
outbox_sha256=cbf824b514dced6ebc4e25c3a4a55ad468876424f4f857d8b960cf8ed7310a99
first_created=11
second_reused=11
copy_source_unchanged=yes
production_health_unchanged=yes
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_PROTECTED_COPY=PASS
```

No result/packet/event/entity content, connection value, private runtime identity, private path, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish this repository/protected-copy checkpoint, and independently verify GitHub. Then design and test an inactive managed local-ready producer installation with explicit durable delivery-state semantics. Do not install a writer credential or transmit to the collector until the inactive boundary passes independently; bounded live result return and ClickHouse verification remain later gates.

## 2026-08-24 04:23 PDT - Item 30 durable ready/delivered state proved

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The prior repository/protected-copy checkpoint was published and independently matched on GitHub at:

`274b37ab0738e2422e2efa9f4c7c4328b07ea816` — `Add protected result outbox candidate`

Before any installation or sender design, the producer now makes local delivery state explicit. `ready` and `delivered` are protected sibling directories under one shared outbox-root lock. Every successful append-only result must exist in at most one state. An exact delivered file is counted as durable local acknowledgment and suppresses ready-file recreation. Duplicate ready/delivered state, divergent bytes, unknown entries, unsafe metadata, or a non-sibling layout fails closed before new publication.

Two focused tests prove exact delivered reuse without recreation and duplicate-state refusal. The complete suite now passes 151 tests locally and from the exact GX10-staged tree. The staged delivery-state candidate was bound as:

```text
staged_tree=e50583294408650bfb0ba86d4878db863c59af4f
staged_archive_sha256=744bd9526f5422533fae41abca1e44511acc94f9cb2395fbe77d4de11c8033a1
producer_sha256=c8ede1606cb3a37dba9875791ac33181ad09701024cc6a8d5040fda540c9abc2
focused_test_sha256=edcf02a07fd128dd2fbca9df504dc60f4cba12e4563c529f87d8217d71ae6f2a
local_tests=151
remote_tests=151
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

A fresh root-only mode-`0600` online backup captured 12 packets, 13 terminal runs, 12 successful results, and the one preserved historical failure. First execution produced exactly 12 collector-valid ready files. The protected wrapper then atomically moved one exact file into delivered to simulate a future successful transport acknowledgment. Second execution created zero, reused all 12, retained exactly 11 ready plus one delivered, and did not recreate the delivered file. The combined filename/content digest remained exact independent of state location. The copy database bytes/reasoning aggregates remained unchanged, all production schedules/services remained healthy, and no collector connection or transmission occurred.

The first copy wrapper reached the simulated move and then stopped because its evidence digest iterated ready files before delivered files rather than sorting the combined set by deterministic filename. This verifier-only ordering defect changed neither database nor production and transmitted nothing. A fresh retained copy with corrected deterministic ordering passed.

```text
protected_copy_bytes=1978351616
protected_copy_sha256=8699bab3bcad39cff6304576364bee18506debfe49d0d4ed01ba5e1aa8a01327
copy_packets=12
copy_runs=13
copy_results=12
preserved_failures=1
outbox_files=12
outbox_sha256=f4da77f1f1f968570ce8adb38c70e8c62874825dbd451846661d6e60ad8c362f
first_created=12
second_reused=12
ready_after_simulated_delivery=11
delivered_reused=1
copy_source_unchanged=yes
production_health_unchanged=yes
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_PROTECTED_COPY=PASS
```

No result/packet/event/entity content, connection value, private runtime identity, private path, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish this delivery-state checkpoint, and independently verify GitHub. Then package and prove an inactive managed local producer installation that preserves the exact shared-lock ready/delivered contract. Do not install writer credentials or transmit to the collector. The later sender/collector design must separately close the upload-success/local-acknowledgment crash window before live replay safety can pass.

## 2026-08-24 04:28 PDT - Item 30 inactive managed package rehearsed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The ready/delivered state checkpoint was published and independently matched on GitHub at:

`cdb87d135fe95b6830e26a01f3eab70d292aeba3` — `Track durable result delivery state`

An inactive managed local-producer package now contains:

- the exact version-1 read-only producer
- an exact-hash managed runner with aggregate-only output
- a separately disableable oneshot and timer
- `PrivateNetwork=yes`, Unix-socket-only address families, no capabilities, strict system protection, and outbox-root-only write scope
- a guarded installer that derives the already-proven reasoning service identity, validates SQLite/result invariants, installs empty mode-`0700` ready/delivered state, and holds the timer disabled/service inactive
- an independent installed-source/configuration/filesystem/database/systemd/outbox verifier
- no SSH/SFTP code, credential path, collector value, sender, or transmission operation

Six focused management tests cover exact runner binding/invocation, producer-hash mismatch, the no-network systemd contract, atomic installer file publication, terminal result invariants, source modes, and absence of credential wiring. The complete local and exact GX10-staged suite passed 157 tests.

```text
staged_tree=c6d972c90a9b541d01159df57692becd513f2465
staged_archive_sha256=39e4fdbf5ffbefe911b03ac8b1c8c8bb4fe50a37311d809b110f7cedad3a7a3c
producer_sha256=c8ede1606cb3a37dba9875791ac33181ad09701024cc6a8d5040fda540c9abc2
runner_sha256=358b70aa4cbbd8c1fb68386d30192d816b4693862ed4d516b5232b2ede235e31
installer_sha256=a7cbe5eadabe83f13533a3ca053b181df2d9dfa1453ffafeb524170a0054e7f6
verifier_sha256=2d7c8c8cd216bd5f435167a71187b6636c6993184e630ac2c94d98d4db5c5e40
service_sha256=40535a3e2ebb796df9cef0a233a701ea77681340acde46687c1f3ea12cf241e9
timer_sha256=07eed21c23f3e8af508209fd8462bb3f2a3b5906f4f1c5ef01ce44d390b88fbe
management_tests_sha256=b70e24a2eaac486f8e328f932b33b3dd3ea7c933444b58b62f24b93a7df32d01
local_tests=157
remote_tests=157
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

The exact staged package was then installed into an isolated root against the already-retained protected copy while all systemd operations were simulated. Post-install verification required exact bytes, modes, configuration, directory layout, empty states, and disabled-timer intent. The installed runner created all 12 collector-valid ready files, then exact replay after one simulated delivered transition retained 11 ready plus one delivered without recreation. The copy SHA-256 was unchanged.

A separate isolated install forced post-install verification failure. Failure handling held the synthetic timer disabled and removed every artifact/config/drop-in/outbox path created by that attempt. No actual unit was loaded, enabled, started, or changed.

```text
copy_results=12
copy_sha256=8699bab3bcad39cff6304576364bee18506debfe49d0d4ed01ba5e1aa8a01327
outbox_sha256=f4da77f1f1f968570ce8adb38c70e8c62874825dbd451846661d6e60ad8c362f
first_ready=12
second_ready=11
second_delivered=1
copy_source_unchanged=yes
failure_cleanup=yes
systemd_state_changed=no
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_INACTIVE_REHEARSAL=PASS
```

No result/packet/event/entity content, connection value, private runtime identity, private path, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish this inactive-package checkpoint, and independently verify GitHub. Then install and independently verify only the exact empty inactive managed boundary on GX10. Do not invoke its service, enable its timer, install a writer credential, or transmit to the collector during that gate.

## 2026-08-24 04:32 PDT - Item 30 inactive install portability correction passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The inactive-package checkpoint was published and independently matched on GitHub at:

`d4ae418e9b365240e7836b5957c0ff6911634d31` — `Package inactive managed result outbox`

The first working-system inactive-install attempt stopped before package preflight because it selected the public clean-rebuild default database/root, whose leading directory is absent on this historical installation. The installer reported failure and its cleanup path left zero created targets. Both new units remained `not-found`. No service/timer/database/outbox/credential/transport state changed.

Read-only diagnosis confirmed the public default database and outbox parent are absent while the established libexec/config/systemd parents are present. The corrected installer and independent verifier now read the exact already-installed root-only managed-reasoning configuration, validate its single absolute database path without printing it, and default the outbox root beneath that database's validated parent. Explicit CLI overrides remain available for clean rebuild/testing.

The correction passed all 157 local tests, all 157 tests plus the filesystem contract from a new exact GX10-staged tree, and a fresh isolated successful/failure-path install rehearsal with unchanged copy digest and zero actual systemd/credential/transport changes.

```text
corrected_tree=0a5b50dfd34978460653c5af2645f8e307a78f2d
corrected_archive_sha256=1afdb24de2be892767b5004a47a79f13606a49dcf738baa9ad2db6201596a61f
corrected_installer_sha256=61f2a28f3615145c87fb28e79013b133888fa3890aaef642a5c7604e5ecb5e0f
corrected_verifier_sha256=e5bebd71600ea057bbcd0313aead77c4ecfba8d077bfe798e7727772f5491103
failed_attempt_created_targets=0
failed_attempt_service_load=not-found
failed_attempt_timer_load=not-found
local_tests=157
remote_tests=157
copy_results=12
copy_sha256=8699bab3bcad39cff6304576364bee18506debfe49d0d4ed01ba5e1aa8a01327
outbox_sha256=f4da77f1f1f968570ce8adb38c70e8c62874825dbd451846661d6e60ad8c362f
copy_source_unchanged=yes
failure_cleanup=yes
systemd_state_changed=no
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_INACTIVE_REHEARSAL=PASS
```

No private database/outbox path, result/packet/event/entity content, connection value, private runtime identity, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish the portability correction, and independently verify GitHub. Then retry the exact corrected inactive install. Require zero ready/delivered files, disabled/inactive units, exact installed bytes/configuration/private ownership, healthy preexisting schedules, unchanged reasoning aggregates, no credential, and no collector transmission.

## 2026-08-24 04:34 PDT - Item 30 corrected inactive working-system install passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The production-path portability correction was published and independently matched on GitHub at:

`9aaf2efd29f3caa640ef89cd29254e35200ecbaa` — `Derive result outbox production paths`

The exact corrected staged installer derived the protected database/root through the already-installed managed-reasoning configuration without printing either path. It installed the producer, exact-hash runner, service, timer, private configuration/drop-in, and empty ready/delivered directories. Its independent verifier required exact repository/installed bytes, root/private ownership and modes, database integrity/result invariants, private runtime binding, exact empty directory state, disabled timer, inactive service, and zero restarts.

```text
reasoning_results_at_install=14
outbox_ready=0
outbox_delivered=0
outbox_timer_enabled=no
outbox_service_active=no
credentials_installed=no
GX10_RESULT_OUTBOX_INACTIVE_INSTALL=PASS
GX10_MANAGED_RESULT_OUTBOX_VERIFY=PASS
```

A first follow-up managed-reasoning verifier invocation used its public clean-rebuild default database and stopped on the private configuration mismatch; it made no change. The corrected aggregate-only postcheck supplied the installed private database through the same protected configuration and passed both existing managed-reasoning and correlation verifiers. All three preexisting timers remained active/enabled, their services were nonfailed with zero restarts, and both deterministic lags were zero.

The outbox unit's effective properties independently showed private networking, Unix-socket-only address families, exact private write scope, disabled/inactive state, zero restarts, and an empty start timestamp proving the service had never executed. Ready and delivered remained empty. No SSH/SFTP key, sender, collector value, or transmission operation exists.

```text
recent_max_id=977532
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_pending=3
reasoning_runs=15
reasoning_started=0
reasoning_succeeded=14
reasoning_failures=1
reasoning_results=14
outbox_ready=0
outbox_delivered=0
outbox_timer_enabled=no
outbox_service_invoked=no
outbox_private_network=yes
outbox_address_families=AF_UNIX
preexisting_schedules_healthy=yes
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_INACTIVE_POSTCHECK=PASS
```

No private database/outbox path, result/packet/event/entity content, connection value, private runtime identity, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish this inactive-install checkpoint, and independently verify GitHub. Then design and prove protected local-only activation: create a fresh state checkpoint, run exactly one bounded service cycle while the timer remains disabled, require one collector-valid ready file per then-current successful result and an unchanged SQLite state, and enable the timer only after independent verification. Do not install writer credentials or transmit to the collector.

## 2026-08-24 04:38 PDT - Item 30 protected local activation rehearsal passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The corrected inactive-install checkpoint was published and independently matched on GitHub at:

`7ffa933f224857ae639ccaeea8fe0d7814e87431` — `Record inactive result outbox installation`

The protected local-only activator now:

- independently verifies the exact empty inactive installation
- requires the managed-reasoning timer active/enabled and service nonfailed
- keeps the outbox timer disabled and temporarily disables only managed reasoning
- waits for any reasoning oneshot to settle without stopping fetch/ingest or deterministic correlation
- hashes every row/column of all five reasoning tables in deterministic primary-key order and requires zero `STARTED` plus exactly one preserved failure
- runs exactly one no-network outbox service cycle
- requires the exact same post-cycle reasoning digest and one ready file per successful result with zero delivered
- enables the outbox timer only after independent populated-inactive and active verification
- restores managed reasoning on success and every failure path
- disables only the outbox timer on activation error

One focused deterministic-snapshot test brings the complete suite to 158. The exact staged tree passed all 158 tests and the GX10 filesystem contract.

```text
staged_tree=42ff6c97a7f2317004bfb50386a0e9aa86a92731
staged_archive_sha256=c30a53edc90eae2d4a677006bce912af7c3506784c9e443de1a6f7e3f7bb06df
activator_sha256=9fd0da43e2af3824cc1b699a954543bccc9dc12f3e26a62dcd98e67637c19b79
verifier_sha256=d551c39d2965256b392a1862f1c5406a1736409e33cfba5daf091da38798fecc
management_tests_sha256=153bdbb8ba114c6e84ed3bde1bf3a0fc3f1288b756fa86338305ae8b8d75ce6f
local_tests=158
remote_tests=158
GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS
GX10_REBUILD_PACKAGE_VALIDATION=PASS
```

A full exact-package retained-copy rehearsal installed a fresh isolated empty boundary, simulated the systemd state machine, and ran the activator over the protected 12-result copy. The reasoning digest was identical before, inside, and after activation. Exactly 12 ready files and zero delivered files passed independent producer validation. Both synthetic timers ended active, the protected copy remained unchanged, and no actual systemd, credential, or collector state changed.

```text
reasoning_packets=12
reasoning_runs=13
reasoning_results=12
reasoning_failures=1
reasoning_sha256=cfefe6c13bcee5e3096f642839a690cf8d277a4b41dbd5487bed437f6bdcd313
outbox_ready=12
outbox_delivered=0
outbox_timer_enabled=yes
reasoning_timer_restored=yes
copy_source_unchanged=yes
systemd_state_changed=no
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_LOCAL_ACTIVATION_REHEARSAL=PASS
```

No private database/outbox path, result/packet/event/entity content, connection value, private runtime identity, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish the activator checkpoint, and independently verify GitHub. Then execute only the exact protected local activation on GX10. Require exact reasoning digest preservation, ready count equal to then-current results, zero delivered, both outbox/reasoning timers active, all deterministic schedules healthy, every file collector-valid, no credential, and no transmission.

## 2026-08-24 04:42 PDT - Item 30 activation verifier ownership correction passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The protected activation checkpoint was published and independently matched on GitHub at:

`9efbc50de459efef9cbe344e08b5d11b77dd392c` — `Add protected local outbox activation`

The first working-system activation paused/restored managed reasoning and successfully ran the no-network outbox service, creating exactly 15 ready files for 15 then-current results. The root-run independent verifier then stopped because it reused the producer's runtime-owner check and therefore expected service-owned mode-`0640` files to be owned by root. The activator failure path disabled the outbox timer, restored reasoning active/enabled, preserved the exact derived files, and transmitted nothing.

```text
reasoning_results=15
reasoning_started=0
outbox_ready=15
outbox_delivered=0
outbox_timer=inactive/disabled
reasoning_timer=active/enabled
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_FAILED_ACTIVATION_POSTCHECK=PASS
```

The independent verifier now inventories ready/delivered files against the already-derived service UID/GID while retaining exact bytes, mode, link, filename, database-record, and duplicate-state checks. The activator accepts an exact populated-but-disabled state with zero delivered and reruns the service idempotently, filling only any successful results added before resume. No file is deleted or rewritten.

One focused service-ownership test brings the suite to 159. A new exact tree passed all 159 tests plus the filesystem contract on GX10. A second full retained-copy activation rehearsal on a different protected copy again passed 12-for-12 creation, exact reasoning digest, timer enablement/restoration, and zero actual systemd/credential/transport change.

```text
corrected_tree=a1722f61fa6c85703dd9e5f0bd73b434d32a8d96
corrected_archive_sha256=9fe2a1a2a888db31721418e5b990f27d6d3200d973454ba9a7f83fcad6c239d5
corrected_activator_sha256=a88a296aebed191055f503555e9d5c01e188b818e7d3e1f4790b252aa0eaf95f
corrected_verifier_sha256=ddfbab97f68ccf385aef0b9ce3e5c0d0ef82be9c2050408f6f40830a2ea616a7
corrected_management_tests_sha256=cc1b677cf3b9b6ae9b64856e32fb589b8a6b79e383f1b2eedd1bc7500d877376
local_tests=159
remote_tests=159
outbox_ready_copy=12
outbox_delivered_copy=0
reasoning_copy_unchanged=yes
systemd_state_changed=no
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_LOCAL_ACTIVATION_REHEARSAL=PASS
```

No private database/outbox path, result/packet/event/entity content, connection value, private runtime identity, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish the ownership/resume correction, and independently verify GitHub. Then resume exact protected local activation from the retained populated-disabled state. Require one ready file per current successful result, zero delivered, exact reasoning digest, outbox/reasoning timers active, healthy deterministic schedules, no credential, and no transmission.

## 2026-08-24 04:47 PDT - Item 30 protected local production activation passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The service-ownership/resume correction was published and independently matched on GitHub at:

`8ddfda20f219f51e1e54fa2dbc25e74c6c2cfba8` — `Verify service-owned outbox activation`

The exact corrected activator resumed from the 15 retained ready files. Managed reasoning was temporarily disabled and settled. The before/after five-table digest remained exact. The local service was an idempotent no-op because no new successful result had appeared; independent populated-inactive and active verification both found exactly 15 ready, zero delivered, and 15 results. Only after those checks passed did the activator enable the outbox timer and restore reasoning active/enabled.

```text
reasoning_packets=12
reasoning_runs=16
reasoning_results=15
reasoning_failures=1
reasoning_sha256=83380943bee52e185fd12cd48236d48798dca26a2bfe9c687ce1cc6e382be3af
outbox_ready=15
outbox_delivered=0
outbox_timer_enabled=yes
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_LOCAL_ACTIVATION=PASS
GX10_MANAGED_RESULT_OUTBOX_VERIFY=PASS
```

The first broad postchecks caught the expected live projection lag while fetch/ingest was ahead of its independent correlation cadence; strict zero-lag verification refused the snapshot. A bounded closure wrapper paused only fetch/ingest and reasoning timers, waited for their services to settle, ran deterministic correlation to zero and an idempotent outbox catch-up, restored both timers, and then executed every strict verifier. Two wrapper iterations stopped safely before the final pass while diagnostic propagation and timer-restore ordering were corrected; the `finally` path restored both timers each time.

The final closure independently passed:

- exact installed active outbox verification
- active managed-reasoning verification at zero projection/incident lag
- active deterministic-correlation verification at zero lag
- all 15 ready files through the unchanged collector validation function
- service UID/GID, mode-`0640`, single-link, one-line JSONL, exact count, and deterministic aggregate digest
- active outbox/pipeline/correlation/reasoning schedules with zero restarts
- zero delivered files, credentials, sender, collector connection, or transmission

```text
recent_max_id=978840
projection_lag=0
incident_lag=0
reasoning_packets=12
reasoning_pending=2
reasoning_runs=16
reasoning_started=0
reasoning_succeeded=15
reasoning_failures=1
reasoning_results=15
outbox_ready=15
outbox_delivered=0
outbox_sha256=65a2b2399018840fe96a3d56291e60ea994e60d12fb8a7fc7ff011bafb2ece9c
collector_gate_valid_files=15
outbox_timer_active=yes
preexisting_schedules_healthy=yes
pipeline_timer_restored=yes
reasoning_timer_restored=yes
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_LOCAL_ACTIVATION_POSTCHECK=PASS
GX10_RESULT_OUTBOX_LOCAL_ACTIVATION_CLOSURE=PASS
```

No private database/outbox path, result/packet/event/entity content, connection value, private runtime identity, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish this local-activation checkpoint, and independently verify GitHub. Then observe multiple natural outbox timer cadences without manual service invocation. Require exact no-op reuse when results are unchanged and exact one-file catch-up after any new successful reasoning result, with zero delivered/restarts/failures and no credential/transmission.

## 2026-08-24 04:51 PDT - Item 30 three natural no-op outbox cadences passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The protected local-activation checkpoint was published and independently matched on GitHub at:

`3c385b7ecd5263b1137d35eafbc57ddb0797df72` — `Record local result outbox activation`

No service was manually invoked. Three consecutive natural outbox timer cadences completed at 11:48:44, 11:49:48, and 11:50:53 UTC, with successful service completion at 11:48:47, 11:49:51, and 11:50:56. Each found 15 successful results and 15 exact ready files, created zero, reused 15, recovered zero, and wrote zero bytes. Delivered remained zero; the service retained zero restarts and its private-network/Unix-only boundary remained active.

```text
cadence_1_total=15 created=0 reused=15 ready=15 delivered=0 written_bytes=0
cadence_2_total=15 created=0 reused=15 ready=15 delivered=0 written_bytes=0
cadence_3_total=15 created=0 reused=15 ready=15 delivered=0 written_bytes=0
outbox_timer_active=yes
reasoning_timer_active=yes
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_NATURAL_NOOP_CADENCES=PASS
```

No private database/outbox path, result/packet/event/entity content, connection value, private runtime identity, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish this natural no-op cadence checkpoint, and independently verify GitHub. Then continue passive observation until managed reasoning adds a successful result and the next natural outbox cadence creates exactly one corresponding ready file without changing prior files. Do not invoke either service manually and do not install credentials or transmit.

## 2026-08-24 04:53 PDT - Item 30 natural one-file catch-up passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The three-cadence no-op stability checkpoint was published and independently matched on GitHub at:

`27dbec46621e858b15450f2de3a66f75d0186724` — `Record natural result outbox cadences`

No service was manually invoked. Managed reasoning started naturally at 11:52:58 UTC and completed at 11:53:17, reducing revised-version pending 2→1 and advancing runs 16→17 plus successes/results 15→16 while retaining exactly one historical failure and zero `STARTED`. The outbox timer started naturally immediately afterward and completed at 11:53:20.

The outbox cadence observed exactly one new successful result, created exactly one 2378-byte ready file, reused the prior 15, wrote only the new file, and retained zero delivered/recovered/restarts. An independent postcheck identified the unique newest file by creation timestamp, removed it from the aggregate calculation, and reproduced the exact prior 15-file digest. All 16 current files independently passed the unchanged collector gate and required service ownership/mode/link/one-line JSONL metadata.

```text
reasoning_runs=17
reasoning_started=0
reasoning_succeeded=16
reasoning_failures=1
reasoning_results=16
outbox_ready=16
outbox_delivered=0
new_ready_files=1
prior_outbox_sha256=65a2b2399018840fe96a3d56291e60ea994e60d12fb8a7fc7ff011bafb2ece9c
current_outbox_sha256=71955d542f80240fc18b27a481ae65b74f98fa04b7e005e2d9a3e5b646d641be
collector_gate_valid_files=16
outbox_timer_active=yes
outbox_restarts=0
credentials_installed=no
collector_transmission_invoked=no
GX10_RESULT_OUTBOX_NATURAL_CATCHUP=PASS
ITEM_30_LOCAL_RESULT_PRODUCTION=COMPLETE
```

No private database/outbox path, result/packet/event/entity content, connection value, private runtime identity, credential, or model output was printed or committed.

### Next action

Run the full public gate, publish the completed local-producer checkpoint, and independently verify GitHub. Then design repository/copy-only write-only transport replay safety. Explicitly close the crash window between successful remote upload and local ready→delivered acknowledgment, and define collector-side deterministic duplicate handling before installing any writer credential or transmitting a production file.

## 2026-08-24 05:01 PDT - Item 30 durable collector acceptance candidate passed repository/copy gates

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The completed local-producer checkpoint was published and independently matched on GitHub at:

`197e8f05178dd7a7fb26b46305391386797993ac` — `Complete local result production`

The prior collector gate used only the continued presence of a same-name ready file as its duplicate check. Removing that file reopened the filename for acceptance, while the current ClickHouse result table provides no independent file-identity deduplication. This left the exact crash window identified by item 30: successful upload followed by interruption before GX10's local ready-to-delivered transition could cause a later deterministic retry to be accepted again after collector ready-file removal.

The repository candidate now maintains a versioned SQLite acceptance ledger beneath the protected ready directory. Every accepted basename is bound append-only to exact SHA-256, byte size, record count, and timezone-aware acceptance time. The gate verifies ledger mode/owner/link/schema/version/triggers/quick-check/rows before incoming processing. Exact and divergent replays are quarantined distinctly even after ready-file removal.

Publication orders ready persistence before ledger insertion. Startup reconciles valid ready files with missing rows, closing interruption after publication and before ledger commit. The no-overwrite link/unlink step also recognizes and repairs only its exact same-inode two-link intermediate state; unexplained hard links fail closed. Ledger update/delete triggers are immutable, and all SQLite commits plus affected directories receive durability synchronization.

Eleven focused tests pass locally and from the exact candidate staged in temporary storage on the collector's Linux/Python runtime. They cover first acceptance, existing-ready bootstrap, exact replay with/without the ready file, divergent replay, malformed rejection, ledger immutability/mode tamper, ready divergence, publication-before-ledger interruption, and link-before-unlink interruption.

```text
local_result_gate_tests=11
collector_staged_result_gate_tests=11
candidate_gate_sha256=e23c887e5a4446a19d6ac3730ade130f0f75691fa3730137db1b00847354622f
candidate_archive_sha256=486ef1a1380945e7ff0621d3da59a1d993678fc14a2ef67c49e719f984e0e6b8
installed_predecessor_sha256=6aebc562ab305ec201e687dbce4d1ac85693c52551bd70cf5f6a7a13df0c9515
live_gate_matches_published_predecessor=yes
live_timer=enabled,active
live_service=inactive
live_service_restarts=0
live_incoming_files=0
live_ready_jsonl=0
live_rejected_files=0
live_acceptance_ledger_exists=no
credential_installed=no
collector_result_transmission_invoked=no
AI_RESULTS_GATE_PACKAGE_VALIDATION=PASS
AI_RESULTS_GATE_COLLECTOR_STAGED_VALIDATION=PASS
```

The full independent local gates also pass: all 159 GX10 tests and filesystem contract, 14 collector normalizer/handoff tests, public current-tree/history/link/ref validation, strict Git object verification, and diff whitespace validation.

No live collector gate/spool/unit was changed. No private connection value, result/packet/event/entity content, credential, key material, or model output was printed or committed.

### Next action

Publish this repository/copy checkpoint and independently verify GitHub. Then stop only the collector gate timer, require the exact predecessor/candidate hashes and empty-spool preconditions, preserve exact rollback bytes, atomically install the candidate, run one ledger-bootstrap service cycle, independently verify the empty immutable ledger and timer/service health, and publish that live-gate checkpoint. Do not install a writer credential or transmit a result.

## 2026-08-24 05:06 PDT - Item 30 live durable acceptance ledger passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The repository/copy durable-acceptance checkpoint was published and independently matched on GitHub at:

`e0d13a79b5a6a3f797d871d93a85b70669cc627a` — `Add durable collector result acceptance`

The guarded production upgrade required the exact published predecessor and candidate hashes, enabled/active timer, settled service, zero restarts, empty incoming/ready/rejected spools, and absence of a prior ledger. It stopped only the result-gate timer, repeated those checks, preserved exact predecessor bytes under a new mode-private root-owned backup, atomically installed the candidate, and ran one explicit empty bootstrap service cycle. Its failure path would restore the exact predecessor and restart the timer.

The bootstrap passed with the exact candidate installed. The new ledger is service-owned, vector-group, mode `0640`, single-link, schema version 1, quick-check clean, and protected by both immutable triggers. It contains zero rows because the live collector result spool was empty. The timer was restored enabled/active; the service retained success and zero restarts; no spool file changed.

A separate read-only verifier independently reproduced the installed/backup hashes, ledger metadata/schema/version/quick-check/triggers/count, empty spool, timer/service health, and active Vector/ClickHouse state. The next natural gate cadence started and exited in the same second, remained a complete empty no-op, and retained the independent verification result.

```text
published_checkpoint=e0d13a79b5a6a3f797d871d93a85b70669cc627a
installed_gate_sha256=e23c887e5a4446a19d6ac3730ade130f0f75691fa3730137db1b00847354622f
protected_predecessor_sha256=6aebc562ab305ec201e687dbce4d1ac85693c52551bd70cf5f6a7a13df0c9515
acceptance_ledger_version=1
acceptance_ledger_rows=0
acceptance_ledger_metadata=service-owner,vector-group,0640,single-link
acceptance_ledger_integrity=quick-check,immutable-triggers
incoming_files=0
ready_jsonl=0
rejected_files=0
gate_timer=enabled,active
gate_service_result=success
gate_service_restarts=0
vector=active
clickhouse=active
writer_credential_installed=no
collector_result_transmission_invoked=no
AI_RESULTS_GATE_LIVE_LEDGER_BOOTSTRAP=PASS
AI_RESULTS_GATE_LIVE_INDEPENDENT_VERIFY=PASS
AI_RESULTS_GATE_NATURAL_EMPTY_CADENCE=PASS
```

No private connection value, backup path, result/packet/event/entity content, credential, key material, or model output was printed or committed.

### Next action

Run the full public gate, publish this live-ledger checkpoint, and independently verify GitHub. Then build the deterministic GX10 sender only in repository/protected-copy state. Require exact-byte/name preservation, pinned host verification, bounded noninteractive SFTP, explicit transport-success acknowledgment, atomic local ready-to-delivered transition under the shared outbox lock, safe interruption/retry, and no credential/transmission during the repository/copy gates.

## 2026-08-24 05:10 PDT - Item 30 deterministic sender core passed repository/copy gates

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The live collector acceptance-ledger checkpoint was published and independently matched on GitHub at:

`311dcf9d70e46c11058bf3b388c22e28c395118e` — `Activate durable collector acceptance ledger`

The repository now contains a deterministic result sender core. Under the same nonblocking lock as the no-network producer, it validates every ready/delivered file, canonical one-record JSON, exact top-level producer contract, run-derived filename, service ownership/group/mode/link state, private identity/known-host metadata, directory layout, and SFTP executable boundary before work. It selects at most one oldest embedded result timestamp per cycle with filename tie-breaking.

The fixed SFTP vector is noninteractive and shell-free: batch mode, identities-only, password/keyboard-interactive refusal, strict supplied known-host verification, disabled global known-host fallback, one connection attempt, bounded connect/keepalive/total timeout, captured output, unchanged local path, and unchanged deterministic remote basename. Failure messages do not propagate subprocess output or endpoint values.

Only a successful transport return permits a revalidation and same-filesystem atomic ready-to-delivered rename under the shared lock, followed by both directory synchronizations and exact postvalidation. Nonzero transport leaves ready unchanged. An injected interruption immediately after transport success left the file ready; the next cycle produced the exact same upload batch and completed delivery, directly exercising the crash window now protected by the collector ledger.

Eleven focused tests pass locally and from exact bytes staged in temporary storage on GX10. All transport calls were injected test doubles; no SFTP process contacted the collector. The full GX10 suite now passes 170 tests plus the filesystem contract. The collector gate suite, public repository sanitation, and diff checks also pass.

```text
local_gx10_tests=170
local_result_sender_tests=11
gx10_staged_result_sender_tests=11
sender_sha256=ff5c08ba1f3ec15017ea26b101f7ed58e901ac937d3d9164e4185dc096a25bc0
sender_tests_sha256=9fc0fc87a6c3c6c501341e68e54b14414de4bb440e2fc8ff4254da2a7ec392e9
sender_archive_sha256=4833ad1cceba0a23a1fd8742408bc72eaf007f6c0597b367a927f5642e87710c
sender_installed=no
writer_credential_installed=no
collector_result_transmission_invoked=no
GX10_RESULT_SENDER_CORE_VALIDATION=PASS
GX10_RESULT_SENDER_CORE_STAGED_VALIDATION=PASS
```

No private connection value, result/packet/event/entity content, credential, key material, or model output was printed or committed.

### Next action

Run the full public gate, publish this sender-core checkpoint, and independently verify GitHub. Then add the exact-hash managed runner, hardened but inactive network-capable service/timer, strict private-configuration contract, nonactivating installer, independent verifier, and failure cleanup. Rehearse them only against protected copies/injected transport before installing any live sender artifact or credential.

## 2026-08-24 05:16 PDT - Item 30 inactive sender package passed repository/staged gates

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The sender-core checkpoint was published and independently matched on GitHub at:

`0623dde8557b300b9bd54cb26a6c8582f8efb7e0` — `Add deterministic result sender core`

The repository now adds an exact-hash managed runner, strict private JSON configuration parser, hardened network-capable oneshot, disabled nonpersistent timer, dynamically derived least-write drop-in, nonactivating installer, independent staged verifier, and postinstall cleanup. The installer places only public code/unit/drop-in bytes and explicitly creates no sender configuration, result-writer identity, writer known-hosts file, or enabled schedule.

The service deliberately permits only Unix/IPv4/IPv6 networking but retains no capabilities, no privilege gain, a strict read-only system, protected home/process/kernel/control/namespace state, bounded resources, and a 45-second service limit. Its derived drop-in exposes only the actual local outbox as writable, future private config/key/known-hosts as read-only, and the reasoning database as inaccessible. `ConditionPathExists` prevents an unconfigured invocation.

Eight new management tests cover exact hash binding, strict separate-writer config layout, exact runner forwarding, network/hardening contract, nonactivating/no-private-input installer behavior, derived write/read/inaccessible paths, postverify cleanup, and public example sanitation. Together with the 11 core tests, the full local GX10 suite passes 178 tests plus the filesystem contract.

The first full-tree temporary GX10 run omitted the collector gate file that `test_result_outbox.py` uses as a cross-component validation dependency. Exactly those 11 outbox tests reported missing-fixture errors; the other 167 tests and filesystem contract passed. The exact current collector gate was added to the temporary tree without changing any candidate byte, after which all 178 tests passed. This was a staging-inventory defect, not a sender/package failure.

```text
local_gx10_tests=178
gx10_staged_gx10_tests=178
local_result_sender_core_tests=11
local_result_sender_management_tests=8
sender_package_archive_sha256=51829ebadd9171a9d9ff0c111bb372606904cccda16703d3c142f527e92a1d79
managed_runner_sha256=7ff26eb739bee6c968b8ea72336786c3342154010ea598a4e611c21cfdef65f3
inactive_installer_sha256=1a6104f565bdd23d35744bae1c9efbdc3c5707f7bd911131f6608c57b16871a7
staged_verifier_sha256=12283f5d81db49491585bf6d05ba7fccf386aba1390060aee23aff9936dc7da8
sender_service_sha256=95cf2cb2594e157decf90374538cc7009bb0698fa22db9542f0458de28fb9fe6
sender_timer_sha256=8a3af28ae25a355a7a65eeec2ece9cb86c5a2a8072c6a60931944d5f6a9152b2
sender_installed=no
sender_config_installed=no
writer_credential_installed=no
collector_result_transmission_invoked=no
GX10_RESULT_SENDER_MANAGED_PACKAGE=PASS
GX10_RESULT_SENDER_EXACT_STAGED_PACKAGE=PASS
```

No private connection value, result/packet/event/entity content, credential, key material, or model output was printed or committed.

### Next action

Run the full public gate, publish this inactive-package checkpoint, and independently verify GitHub. Then require exact published/staged hashes and healthy active outbox/reasoning/correlation/pipeline schedules, run only the guarded inactive sender installer, independently verify the sender timer disabled/service inactive/private inputs absent, and publish that checkpoint before provisioning any writer input or transmitting.

## 2026-08-24 08:06 PDT - Item 30 inactive sender production install passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The inactive managed-package checkpoint was published and independently matched on GitHub at:

`47214c1f226aec11fe05fd893b1d188e73fe4eaa` — `Package inactive managed result sender`

Exact staged source/runner/installer/verifier/service/timer hashes matched the published candidate before installation. The working system had no sender units. The active no-network outbox independently verified before installation.

The guarded installer rederived the installed outbox paths and service identity privately, required the active outbox schedule, exact empty sender targets, absent config/key/writer-known-hosts, fixed SFTP executable metadata, and exact repository sources. It installed only public code, service, timer, and the derived least-write/drop-in boundary. It ran systemd unit verification, explicitly disabled/stopped the new timer, and called the independent staged verifier. No private file was created and the service condition remained unsatisfied.

Independent postchecks matched exact installed source/drop-in/unit state and proved the sender timer disabled, service inactive, zero restarts, private inputs absent, outbox active at 20 results/20 ready/zero delivered, and no transport. The first two broad correlation/reasoning verifier invocations intentionally used their public clean-runtime mode and refused the expected historical private drop-ins. The corrected private-runtime invocation passed both at zero projection/incident lag. A separate identity-withholding check derived the original pipeline schedule through the validated correlation binding and proved its timer enabled/active with zero service restarts.

```text
published_checkpoint=47214c1f226aec11fe05fd893b1d188e73fe4eaa
sender_installed=yes
sender_timer=disabled,inactive
sender_service=inactive,restarts-0
sender_config_installed=no
writer_identity_installed=no
writer_known_hosts_installed=no
outbox_results=20
outbox_ready=20
outbox_delivered=0
outbox_timer=enabled,active
correlation_projection_lag=0
correlation_incident_lag=0
reasoning_runs=21
reasoning_started=0
reasoning_succeeded=20
reasoning_failures=1
reasoning_results=20
original_pipeline_timer=enabled,active
original_pipeline_restarts=0
collector_result_transmission_invoked=no
GX10_RESULT_SENDER_INACTIVE_INSTALL=PASS
GX10_MANAGED_RESULT_SENDER_VERIFY=PASS
GX10_MANAGED_RESULT_OUTBOX_VERIFY=PASS
GX10_PRIVATE_RUNTIME_POSTCHECK=PASS
GX10_ORIGINAL_PIPELINE_SCHEDULE_POSTCHECK=PASS
```

No private runtime path, connection value, result/packet/event/entity content, credential, key material, or model output was printed or committed.

### Next action

Run the full public gate, publish this inactive-installed checkpoint, and independently verify GitHub. Then implement a separate guarded private-input configurator and configured-inactive verifier with dedicated writer identity generation, exact collector authorization installation, separate pinned known-host input, atomic private configuration, failure rollback, and a hard requirement that the sender timer/service remain disabled/inactive. Do not invoke SFTP or move any outbox file during configuration.

## 2026-08-24 08:16 PDT - Item 30 configured-inactive candidate passed repository/staged gates

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The inactive sender production-install checkpoint was published and independently matched on GitHub at:

`097c92573f11a78422cc502d4a8f061540518e8e` — `Record inactive result sender installation`

The repository now contains a separate private-input configurator and configured-state verifier. The configurator requires the sender timer/service to remain disabled/inactive, derives all endpoint/outbox values from validated private runtime state, accepts only a root-owned mode-`0400`/`0600` Ed25519 input from `/run`, proves it differs from the existing read-only spool identity, copies the existing pinned host into a separate writer-only known-hosts file, and installs canonical root-owned configuration last. It has no SFTP execution path.

Private targets must be wholly absent or wholly present. Partial state is refused. Installation is no-overwrite and directory-synchronized; failure removes only files created by that attempt. Exact existing state is reusable and divergent state fails closed. The verifier independently rederives all paths and roles, exact package bytes, private ownership/modes, canonical configuration, writer-only account, runtime endpoint, pinned-host lookup, active outbox, and disabled/inactive zero-restart sender state.

The four added management tests cover successful config-last order, created-only cleanup after an injected verifier failure, partial-state refusal, and absence of an SFTP call path. All 182 GX10 tests plus package/filesystem contracts pass locally. The exact three changed files were copied to the retained temporary GX10 tree; all 182 tests and the filesystem contract pass there, and their SHA-256 values exactly match the local candidate.

```text
local_gx10_tests=182
gx10_staged_gx10_tests=182
local_result_sender_management_tests=12
configurator_sha256=40d982a3f1315164c8fa41ab60e03c0b96b6301a239cd92e6496ab42270c1b28
configured_verifier_sha256=25ce99cd24662f3eede9fed8ebd1be94729250c7f7f34e2e8956ec16aae7c6ab
management_tests_sha256=80f2e35201eee631c0cf2bd90547badce0aafed108c59b3c2a2db29a1670eac1
gx10_changed_file_hash_parity=yes
sender_timer=disabled,inactive
sender_service=inactive
live_private_input_installed=no
collector_authorization_changed=no
collector_result_transmission_invoked=no
GX10_RESULT_SENDER_CONFIGURED_INACTIVE_CANDIDATE=PASS
```

The first remote full-tree package-validator invocation correctly refused because the temporary staged tree is not a Git worktree; this validator depends on `git ls-files`. The complete 182-test staged suite and filesystem contract passed there, while the Git-dependent rebuild-package validator passed in the actual local Git worktree. No candidate or production defect was hidden by that staging-context refusal.

No private runtime path, connection value, result/packet/event/entity content, credential, key material, or model output was printed or committed. No production private state or collector authorization changed.

### Next action

Run the full public gate, publish this configured-inactive candidate, and independently verify GitHub. Then generate the dedicated writer identity, install only its matching collector authorization under an exact guarded append/rollback procedure, run the configurator and independent configured-inactive production checks, and publish that checkpoint before any SFTP invocation or outbox movement.

## 2026-08-24 08:24 PDT - Item 30 exact-backup collector authorizer passed repository/staged gates

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The configured-inactive sender candidate was published and independently matched on GitHub at:

`8568454aee5bdaf063cfd2661b65b067cf7fdabe` — `Gate configured inactive result sender`

A separate collector-side authorizer now owns the one permitted authorization change. It accepts exactly one root-owned mode-`0600` public Ed25519 input, validates the existing writer authorization metadata without printing it, refuses an already duplicated key, preserves the complete predecessor bytes in a new root-only mode-`0600` backup, and atomically appends only the new public line. It validates the final authorization and `sshd -t` without reloading or restarting SSH.

Any failure after publication atomically restores the exact predecessor bytes and removes backup state created by that failed attempt. An exact already-present key is a no-op; when the protected predecessor backup exists, reusable state must equal that backup plus exactly the one dedicated line. Divergence fails closed.

Five focused tests cover exact append/backup, injected SSH-validation rollback, exact reuse, duplicate refusal, and private-key-marker refusal. They pass locally and from exact bytes staged on the collector's Python runtime. The full local collector suite now passes 30 tests; the 11-test durable result-gate package, 14-test shadow package, public repository gate, and diff hygiene also pass.

```text
local_collector_tests=30
local_result_writer_authorizer_tests=5
collector_staged_result_writer_authorizer_tests=5
authorizer_sha256=2ba669bb6d2c8a6ca8cdbfe829899a7ad926aca8ebbe29832084814d64df630b
authorizer_tests_sha256=109d5828a0a5237eb4bc8b69d3332dd8169f7c5a6e975927fec1eb78c0e845d9
collector_stage_hash_parity=yes
collector_authorization_changed=no
writer_identity_generated=no
sender_private_state_installed=no
collector_result_transmission_invoked=no
COLLECTOR_RESULT_WRITER_AUTHORIZER_CANDIDATE=PASS
```

No existing key line, new key material, private runtime path, connection value, result/packet/event/entity content, credential, or model output was printed or committed. No production authorization or GX10 private state changed.

### Next action

Run the full public gate, publish this authorizer candidate, and independently verify GitHub. Then generate the dedicated writer key only on GX10, transfer only its public half through protected temporary files, run the exact published collector authorizer, run the exact configured-inactive GX10 configurator, and independently verify the protected backup/one-line append plus disabled/inactive sender before any transport.

## 2026-08-24 08:27 PDT - Item 30 GX10 optional-key-comment compatibility corrected before configuration

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The exact-backup collector-authorizer checkpoint was published and independently matched on GitHub at:

`edbcc484f3d2d401574a25fd9189604cceadcb30` — `Guard result writer authorization`

The dedicated Ed25519 writer identity was generated only on GX10 with root-owned mode-`0600` private metadata. Only its public half crossed to the collector. Cross-host fingerprints matched without key content output. The exact published collector authorizer appended that one public key, retained the exact root-only predecessor backup, and passed SSH configuration validation without restart.

The first GX10 configure invocation then failed safely at identity-input validation before creating any sender config, installed identity, or writer known-hosts target. Metadata and private-key derivation were valid. This GX10 runtime's `ssh-keygen -y` emitted three fields because it retained the optional private-key comment, while the candidate incorrectly required exactly two. The key type/blob were valid and the sender remained disabled/inactive.

The correction now accepts two or more derived fields but binds and compares only the Ed25519 type and base64 identity blob; comments remain nonidentity metadata. A focused regression test covers identical normalization in both configurator and verifier. All 183 GX10 tests and package/filesystem contracts pass locally, and all 183 tests plus the filesystem contract pass from exact corrected bytes on GX10.

```text
collector_writer_authorization=installed,protected-predecessor-retained
gx10_configure_first_attempt=safe-refusal-before-target-creation
gx10_sender_timer=disabled,inactive
gx10_sender_service=inactive
gx10_sender_private_targets=absent
local_gx10_tests=183
gx10_staged_gx10_tests=183
corrected_configurator_sha256=7ace62e082b0b159c9596571150d29b29466cedcf2bd42230ae6dec86da07f90
corrected_verifier_sha256=079fe20a04f8eec625afabf3129ecbdfe3c49ea369a9acb293221435d7563867
corrected_management_tests_sha256=75e2e363de5c3965b0b9e104d03afd01f05a12e4f5d3d67dae823edaed325437
collector_result_transmission_invoked=no
GX10_RESULT_WRITER_COMMENT_COMPATIBILITY=PASS
```

No key content, private runtime path, connection value, result/packet/event/entity content, credential, or model output was printed or committed. No SFTP invocation or outbox movement occurred.

### Next action

Run the public gate, publish and independently verify the compatibility correction, then rerun the exact configured-inactive GX10 configurator. Independently verify collector authorization/backup exactness, GX10 private metadata/configuration, disabled/inactive sender, active outbox, and all existing schedule health before publishing the first-live/replay plan.

## 2026-08-24 08:34 PDT - Item 30 captured-private-runtime derivation corrected before configuration

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The optional-key-comment correction was published and independently matched on GitHub at:

`26e673afbfeb52c53cd099a97da5ac5517ea48f8` — `Accept writer key comments safely`

The second GX10 configure attempt passed the corrected key parser and reached postinstall verification, where it safely refused the reconstructed public runtime-config/key-path assumptions. The configurator removed all three new targets. Read-only metadata checks then established that the captured working application predates the reconstructed clean-build JSON runtime file and uses private identity-bearing constants; its known-hosts file remains at the validated private-home role, while the public-default reader-key basename is intentionally absent.

The corrected candidate now supports two explicit and mutually exclusive provenance modes. Clean rebuilds retain the strict root-owned JSON runtime contract. The reference working system uses only a caller-supplied captured fetch source whose bytes must match the already-published rediscovery SHA-256. The verifier parses that exact file as AST without executing it, accepts only literal host/port/user and `Path` assignments, requires the derived key and known-hosts paths inside the rederived service SSH directory, and independently validates their service ownership/modes. The writer role remains fixed and distinct.

One focused regression constructs an exact-hash synthetic legacy fetch contract and proves endpoint/key/known-host derivation. All 184 GX10 tests and package/filesystem contracts pass locally. All 184 tests and the filesystem contract pass from exact corrected bytes on GX10. Neither refusal invoked SFTP or left sender targets.

```text
gx10_configure_second_attempt=safe-postverify-refusal,created-targets-removed
gx10_sender_timer=disabled,inactive
gx10_sender_service=inactive
gx10_sender_private_targets=absent
legacy_fetch_source_binding=published-sha256,root-0755-single-link,AST-literals-only
local_gx10_tests=184
gx10_staged_gx10_tests=184
corrected_configurator_sha256=d652b056fb0601e4b879eec9ffee31723a6f351e0828b4bd9a7028bba68e9aa9
corrected_verifier_sha256=fc6a9c851d6ba845c9776a8aeab6d6fd9df4f4b64b6d2c12e532361b9672d8d0
corrected_management_tests_sha256=9dd39739ceae778a007f06ecf7a9d3384451681d4641b48183191c4e9fb42fe6
collector_result_transmission_invoked=no
GX10_CAPTURED_RUNTIME_DERIVATION=PASS
```

No private runtime path/value, key content, connection value, result/packet/event/entity content, credential, or model output was printed or committed. The collector's dedicated authorization and exact predecessor backup remain installed; the GX10 private targets remain absent.

### Next action

Run the public gate, publish and independently verify this correction, privately resolve the unique live fetch source only by its published SHA-256, and rerun the configured-inactive GX10 configurator with that source. Then independently verify both hosts and publish the first-live/replay plan before any transport.

## 2026-08-24 08:40 PDT - Item 30 canonical configuration render regression corrected

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The exact-hash captured-runtime derivation was published and independently matched on GitHub at:

`6faeb85c5e2bde6cc0cc0743c61316188d57a5fa` — `Derive captured sender runtime safely`

The fixed private wrapper found exactly one captured fetcher by the published hash and produced a protected temporary exact copy without exposing its path or values. The configurator then stopped before target creation on a missing `json` import introduced during the runtime-source refactor. The temporary source copy was removed by the wrapper and the sender remained disabled/inactive.

The import is restored and a direct regression now executes the real canonical sender-configuration renderer and checks schema, fixed writer role, endpoint/port mapping, sorted compact JSON, and terminal newline. All 185 GX10 tests and package/filesystem contracts pass locally; all 185 tests pass from exact staged bytes on GX10.

```text
gx10_configure_attempt=safe-refusal-before-target-creation
gx10_sender_timer=disabled,inactive
gx10_sender_service=inactive
local_gx10_tests=185
gx10_staged_gx10_tests=185
corrected_configurator_sha256=5d877878af219eff6d0647f1e7df5535a4abba4fd85d0bd47022d4594015ff86
configured_verifier_sha256=fc6a9c851d6ba845c9776a8aeab6d6fd9df4f4b64b6d2c12e532361b9672d8d0
management_tests_sha256=e01eb98dd00bce20d071a0f84c7939caee1cd98304699a411b73b38a529d0b4c
collector_result_transmission_invoked=no
GX10_CANONICAL_SENDER_CONFIG_RENDER=PASS
```

No private path/value, key content, connection value, result/packet/event/entity content, credential, or model output was printed or committed. No SFTP invocation or outbox movement occurred.

### Next action

Publish and independently verify this correction, then rerun the same fixed wrapper. Independently verify both hosts and publish the first-live/replay plan before any transport.

## 2026-08-24 08:44 PDT - Item 30 configured-inactive production gate passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The canonical-render correction was published and independently matched on GitHub at:

`0943358449c8f3db6ed888643c9e56f68798c986` — `Cover canonical sender configuration`

The fixed wrapper resolved exactly one captured fetcher by its published hash, copied it only to protected temporary runtime storage, and ran the exact published configurator. Configuration installed the dedicated writer identity, separate writer known-hosts, and canonical configuration while the sender timer/service remained disabled/inactive. The independent configured verifier passed. A second wrapper execution proved exact three-for-three idempotent reuse and repeated verification without SFTP.

The installed GX10 writer fingerprint matched the collector's newly authorized public key without printing either. The root-only temporary private/public inputs were then removed from both hosts and the VM. Independent collector verification proved exact predecessor-backup-plus-one-line authorization, metadata, `sshd -t`, active result gate, Vector, and ClickHouse. Independent GX10 verification passed the configured sender, active outbox, zero-lag correlation/reasoning, and original pipeline schedule.

```text
github_checkpoint=0943358449c8f3db6ed888643c9e56f68798c986
sender_configuration=installed,canonical
writer_identity=installed,dedicated
writer_known_hosts=installed,separate
sender_timer=disabled,inactive
sender_service=inactive
sender_configuration_reuse=3
ephemeral_key_inputs=removed
outbox_results=58
outbox_ready=57
outbox_delivered=0
correlation_projection_lag=0
correlation_incident_lag=0
reasoning_started=0
reasoning_succeeded=58
reasoning_failures=1
reasoning_results=58
original_pipeline_timer=enabled,active
collector_authorization=exact-predecessor-plus-one-line
collector_gate=enabled,active,restarts-0
vector=active
clickhouse=active
collector_result_transmission_invoked=no
GX10_CONFIGURED_INACTIVE_PRODUCTION=PASS
GX10_CONFIGURED_INACTIVE_FULL_POSTCHECK=PASS
COLLECTOR_CONFIGURED_WRITER_FULL_POSTCHECK=PASS
```

The active outbox had one newly completed reasoning result not yet projected at the instant of verification (`58` results, `57` ready, zero delivered); this is an ordinary active-schedule timing state, not loss or sender activity.

No private path/value, key content, connection value, result/packet/event/entity content, credential, or model output was printed or committed. No SFTP invocation or outbox movement occurred.

### Next action

Publish this configured-inactive checkpoint and the bounded first-live/replay plan. Then invoke exactly one sender service cycle with its timer still disabled, bind the selected deterministic filename/digest privately, and prove local delivered transition, collector durable acceptance, Vector/ClickHouse single-row ingestion with complete `raw_json` provenance, and all schedule health before any replay or malformed/divergent test.

## 2026-08-24 08:55 PDT - Item 30 first transport passed; collector ownership correction passed staged gates

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The configured-inactive production checkpoint and bounded plan were published and independently matched on GitHub at:

`9157b65` — `Record configured inactive transport`

The aggregate collector baseline was zero ledger rows and zero incoming/ready/rejected files. The sender timer remained disabled. One manual service cycle paused only the no-network outbox timer for cardinality, transmitted exactly one oldest file, moved ready `59 -> 58` and delivered `0 -> 1`, restored the active outbox timer, and retained zero sender restarts. Private cross-host comparison proved unchanged filename and SHA-256.

After the 90-second settle boundary, the collector gate failed safely before ready publication. Redacted diagnostics identified `EPERM` on the incoming-to-ready hard link. Linux protected-hardlink policy correctly prevents the unprivileged gate account from linking a writer-owned inode, even though its ACL permits read/delete. The incoming file remained unchanged; ledger, ready, and rejected remained zero. Only the gate timer was stopped and its failed state reset.

The corrected gate copies validated bytes into a gate-owned mode-`0640` ready partial, fsyncs and revalidates both the source and copy against the original digest/size/count evidence, then uses a same-owner no-overwrite hard link for atomic ready publication. It persists ready, removes/persists incoming, removes the marker, and persists ready again. A crash after publication retains a recognizable ready/marker two-link inode; recovery accepts only that exact marker relation and exact incoming bytes before cleanup and ledger reconciliation. Orphan/divergent markers fail closed.

All 11 durable acceptance tests pass locally and from exact staged bytes on the collector runtime. First acceptance now asserts the ready inode differs from the writer-owned source. The interruption test directly constructs and recovers the new two-link ready/marker state.

```text
sender_timer=disabled,inactive
first_live_ready_before=59
first_live_ready_after=58
first_live_delivered_before=0
first_live_delivered_after=1
cross_host_name_hash_parity=yes
collector_incoming=1
collector_ready=0
collector_rejected=0
collector_ledger_rows=0
collector_gate_timer=stopped-for-correction
collector_gate_failure=protected-hardlink-ownership-boundary
corrected_gate_sha256=aecf3e862b489498389ce56a1859f60935c18de56db23c4a22b718033e40c974
corrected_gate_tests_sha256=e953afdbcfe6f26dd70dceacb7704a88437b16f2e8f899b2b7abb1327e021483
local_gate_tests=11
collector_staged_gate_tests=11
clickhouse_query=requires-separate-local-reader-credential-approval
COLLECTOR_CROSS_OWNER_PUBLICATION_CANDIDATE=PASS
```

No result content, private filename/digest, key, credential, connection value, or private path was printed or committed. ClickHouse was not mutated by the failed acceptance attempt.

### Next action

Publish and independently verify this correction. Require the exact installed predecessor/candidate hashes, stopped gate timer, one unchanged settled incoming file, and zero ledger/ready/rejected. Preserve exact rollback bytes, install the candidate, run the gate once, and require one accepted ledger/ready file before restoring the timer. Then obtain explicit approval for the root-protected local Grafana-reader credential use needed for direct ClickHouse row/provenance verification.

## 2026-08-24 08:58 PDT - Item 30 first transport durably accepted after cross-owner correction

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The cross-owner gate correction was published and independently matched on GitHub at:

`6f4491322a4998fd813fa94cf46482c41f80eb01` — `Handle cross owner result publication`

The guarded installer required the exact durable-ledger predecessor/candidate hashes, stopped gate timer, inactive service, exactly one settled incoming file, zero ready/rejected files, and zero ledger rows. It preserved the exact predecessor in a new root-only mode-`0600` backup, installed the candidate mode `0755`, ran the gate once, and retained automatic rollback until one ready file and one ledger row passed. It then restored the enabled/active timer.

Independent private comparison proved GX10 delivered, collector ready, and the immutable acceptance row have identical filename and SHA-256 without printing either. The gate/authorization/SSH/Vector/ClickHouse services pass. GX10's configured sender remains disabled/inactive and full verification now reports 60 reasoning results, 59 ready, one delivered, zero started rows, and zero projection/incident lag; the original pipeline schedule remains enabled/active.

```text
published_correction=6f4491322a4998fd813fa94cf46482c41f80eb01
installed_gate_sha256=aecf3e862b489498389ce56a1859f60935c18de56db23c4a22b718033e40c974
protected_gate_predecessor_sha256=e23c887e5a4446a19d6ac3730ade130f0f75691fa3730137db1b00847354622f
collector_incoming=0
collector_ready=1
collector_rejected=0
collector_ledger_rows=1
gx10_collector_ledger_ready_parity=yes
sender_timer=disabled,inactive
sender_service=inactive,restarts-0
outbox_results=60
outbox_ready=59
outbox_delivered=1
reasoning_started=0
projection_lag=0
incident_lag=0
collector_gate_timer=enabled,active
vector=active
clickhouse=active
clickhouse_row_provenance=pending-explicit-read-credential-authorization
COLLECTOR_CROSS_OWNER_GATE_INSTALL=PASS
FIRST_LIVE_LEDGER_READY_GX10_PARITY=PASS
GX10_CONFIGURED_INACTIVE_FULL_POSTCHECK=PASS
COLLECTOR_CONFIGURED_WRITER_FULL_POSTCHECK=PASS
```

No result content, private filename/digest, key, credential, connection value, or private path was printed or committed. No replay or divergent test has begun.

### Next action

After explicit operator approval, read the existing root-protected Grafana-reader credential only in collector memory and run bounded read-only ClickHouse queries for the privately bound run ID. Require exactly one row and exact `raw_json` byte/digest/provenance equivalence, then publish first-live closure before exact replay.

## 2026-08-24 09:25 PDT - Item 30 first live ClickHouse row and provenance proof passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The repository and GitHub `main` were clean and matched the published first-acceptance checkpoint:

`49d97c7` — `Record first durable result acceptance`

The operator explicitly authorized use of the collector's existing root-protected Grafana-reader credential solely for read-only ClickHouse row and provenance verification. The credential was supplied through a no-echo terminal directly to a collector-local verifier, retained only in process memory, and neither printed nor copied to a file. No default ClickHouse or Grafana administrator credential was used.

The verifier privately selected the sole accepted ready JSONL file, revalidated stable regular-file metadata, one newline-terminated canonical record, the exact version-1 top-level contract, and the complete required provenance-key shape. A bounded aggregate query used the read-only `grafana_reader` account and matched a server-computed SHA-256 over `raw_json` plus the removed JSONL newline against the exact accepted file bytes.

Exactly one ClickHouse row matched the accepted bytes. That same row matched the exact source byte length and every checked projected field against its own raw JSON: incident/run/model/type/status/severity, occurrence count, title/body, and tags. Because the complete stored `raw_json` is byte-equivalent to the canonical accepted record, its nested result and full versioned provenance are preserved exactly rather than inferred from thin projections.

```text
clickhouse_exact_raw_matches=1
clickhouse_projection_matches=1
clickhouse_exact_size_matches=1
accepted_ready_records=1
collector_ledger_rows=1
sender_timer=disabled
credential_storage=process-memory-only
CLICKHOUSE_FIRST_LIVE_PROVENANCE=PASS
FIRST_LIVE_RESULT_RETURN=PASS
```

No credential, private filename/digest/run identity, connection value, result content, or provenance value was printed or committed. ClickHouse, Grafana, Vector, collector spool/ledger, GX10 outbox, and service schedules were not mutated by this verification. No replay or divergent test has begun.

### Next action

Publish and independently verify this first-live closure. Then upload the exact delivered bytes/name once through the same fixed writer credential without altering local delivered state. Require exact-replay quarantine, unchanged one-row ledger/ready/ClickHouse identity, and healthy schedules before beginning the separately bounded divergent-content isolation test.

## 2026-08-24 09:34 PDT - Item 30 exact live replay isolation passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The first-live ClickHouse/provenance closure was published and independently matched on GitHub at:

`17a27b83b0fba66dcb81cfd0e0d1a338c1baf7de` — `Close first live result proof`

The collector baseline retained zero incoming, one ready file, one immutable acceptance row, zero rejected payload/reason files, an enabled/active gate timer, and active Vector/ClickHouse. GX10's sender timer/service were separately confirmed disabled/inactive.

A bounded root wrapper derived the installed sender service identity from systemd without printing it, dropped privileges to that exact account, loaded the installed managed runner and exact-hash sender core, validated the canonical configuration/private inputs/outbox, acquired the shared lock, and selected the sole delivered record. It uploaded those unchanged bytes under the unchanged basename through the same fixed SFTP command contract. The wrapper then revalidated the delivered file and complete ready/delivered name sets and proved zero local state changes.

The normal collector timer—not a forced service start—handled the replay. Its first cadence correctly left the file waiting inside the 90-second settle boundary. The next cadence quarantined exactly one payload with exactly one reason classified as `exact filename/content already accepted`. Incoming returned to zero. Ready and the immutable ledger remained one with exact filename/digest/size/record-count parity; no conflict or other rejection reason appeared.

The authorized no-echo read-only ClickHouse proof was then repeated. The accepted-byte digest, exact size, projection parity, and complete provenance contract still matched exactly one row, proving the replay inserted no duplicate. Full postchecks passed on both hosts. At that point GX10 had 67 successful reasoning results, 66 ready, one delivered, zero `STARTED`, one preserved historical failure, and zero projection/incident lag. The sender remained configured but disabled/inactive; the original pipeline and reasoning schedules remained healthy. Collector authorization/SSH/gate/Vector/ClickHouse checks passed.

```text
exact_replay_uploads=1
gx10_local_state_changes=0
collector_incoming=0
collector_ready=1
collector_ledger_rows=1
collector_rejected_payloads=1
collector_rejected_reasons=1
collector_exact_replay_reasons=1
collector_conflict_reasons=0
clickhouse_exact_raw_matches=1
sender_timer=disabled,inactive
projection_lag=0
incident_lag=0
GX10_EXACT_REPLAY_UPLOAD=PASS
COLLECTOR_EXACT_REPLAY_ISOLATION=PASS
CLICKHOUSE_EXACT_REPLAY_NO_DUPLICATE=PASS
GX10_CONFIGURED_INACTIVE_FULL_POSTCHECK=PASS
COLLECTOR_CONFIGURED_WRITER_FULL_POSTCHECK=PASS
```

No credential, private filename/digest/run identity, connection value, result/provenance content, or service identity was printed or committed. No existing file, ledger row, database row, schedule, or service configuration was changed. The replay added only its expected quarantined payload/reason evidence. No divergent-content test has begun.

### Next action

Publish and independently verify this exact-replay closure. Then create one protected temporary same-name derivative of the delivered record, change only a bounded collector-valid presentation field so its bytes/digest diverge without changing its deterministic filename, upload it once through the same writer boundary, and delete the temporary derivative. Require conflict quarantine, unchanged one-row ledger/ready/ClickHouse identity, and healthy full postchecks before considering recurring sender activation.

## 2026-08-24 09:42 PDT - Item 30 divergent live result isolation passed

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The exact live replay checkpoint was published and independently matched on GitHub at:

`d95ec840bfe341258f78a50f029e05f023103e95` — `Record exact live replay isolation`

The pre-probe collector baseline was zero incoming, one ready, one immutable ledger row, and one already-proven exact-replay payload/reason pair. It had zero conflict/other reasons and healthy gate/Vector/ClickHouse state. The first GX10 probe attempt encountered the normal producer's shared outbox lock and failed before derivative creation, SFTP, or any state change, independently proving the concurrency boundary in production.

The clean retry derived and dropped to the installed sender service identity, loaded the exact installed runner/core/configuration, acquired the shared lock, and selected the sole delivered record. In a mode-protected temporary sibling directory it changed only one bounded display field, canonicalized the one-record JSONL, revalidated it through the installed sender contract under the unchanged deterministic basename, and proved its digest differed from the original. It uploaded once through the fixed writer credential, revalidated the untouched original delivered bytes, synchronously removed the derivative/directory, and proved zero temporary remnants.

The normal collector cadence quarantined exactly one new payload/reason pair as `filename conflicts with durable acceptance`. The original exact-replay pair remained independently classified. Incoming returned to zero; ready and the immutable ledger remained one with exact evidence parity; no other rejection appeared. The authorized no-echo read-only ClickHouse proof again found exactly one byte/size/projection/provenance-equivalent row, so the conflict produced no database row.

Full postchecks passed on both hosts. GX10 then had 68 successful reasoning results, 67 ready, one delivered, zero `STARTED`, one preserved historical failure, zero projection/incident lag, and a disabled/inactive sender timer/service. The original pipeline, correlation, reasoning, and outbox schedules remained healthy. Collector writer authorization, SSH syntax, gate timer/restarts, Vector, and ClickHouse remained healthy.

```text
initial_lock_contention=fail-safe-before-probe
divergent_probe_uploads=1
gx10_original_changes=0
gx10_probe_temp_remainders=0
collector_incoming=0
collector_ready=1
collector_ledger_rows=1
collector_rejected_payloads=2
collector_rejected_reasons=2
collector_exact_replay_reasons=1
collector_conflict_reasons=1
collector_other_reasons=0
clickhouse_exact_raw_matches=1
sender_timer=disabled,inactive
projection_lag=0
incident_lag=0
GX10_DIVERGENT_PROBE_UPLOAD=PASS
COLLECTOR_DIVERGENT_ISOLATION=PASS
CLICKHOUSE_DIVERGENT_NO_INSERT=PASS
GX10_CONFIGURED_INACTIVE_FULL_POSTCHECK=PASS
COLLECTOR_CONFIGURED_WRITER_FULL_POSTCHECK=PASS
```

No credential, private filename/digest/run identity, connection value, original result/provenance content, private service identity, or derivative content was printed or committed. No original file, ledger row, database row, schedule, or service configuration was changed. The only retained new evidence is the expected conflict quarantine pair.

### Next action

Publish and independently verify this divergent-isolation closure. Then define the exact activation/rollback gate for the already-installed recurring sender timer, verify current backlog and both-host health against that gate, activate only the sender timer, and require bounded natural delivery plus collector acceptance/ingestion and continued replay protection before marking item 30 complete.

## 2026-08-24 09:46 PDT - Item 30 recurring-sender active verifier candidate passed locally

### Status

Execution-order item 30 remains the single `NEXT` item and is in progress. The divergent live-result isolation checkpoint was published and independently matched on GitHub at:

`61ff0dc073258b4d04a58e398cfc7986f1a12c8e` — `Record divergent result isolation`

Before any recurring activation, the public independent sender verifier now has an explicit `--active` configured-state mode. The inactive/default mode still requires the timer disabled/inactive. Active mode instead requires the timer enabled/active while continuing to require the oneshot service idle, zero restarts, exact installed public bytes/drop-in, canonical private configuration, exact writer identity/pin metadata, active local outbox, and the same private legacy-runtime provenance checks. Active mode is refused for an unconfigured staged installation.

A direct regression supplies the complete synthetic systemd property matrix, proves active mode accepts only enabled/active timer state, and proves inactive mode rejects that same state. The full GX10 suite now passes locally:

```text
gx10_tests=186
failures=0
errors=0
sender_active_verifier=explicit
live_sender_timer=disabled,inactive
GX10_RESULT_SENDER_ACTIVE_VERIFIER_CANDIDATE=PASS
```

No live artifact, credential, private value, outbox file, schedule, service, collector state, or database was changed by this repository-only gate.

### Next action

Publish and independently verify this active-verifier candidate. Stage the exact published GX10 component tree on GX10, pass all 186 tests there, and run the exact inactive configured verifier before activation. Then enable/start only the sender timer. On any verification/service failure, disable/stop only that timer and preserve outbox/collector evidence for replay. Require at least one natural ready-to-delivered transition, collector durable acceptance, ClickHouse ingestion, zero sender restarts, and healthy preexisting schedules before item-30 closure.

## 2026-08-24 09:52 PDT - Item 30 recurring production result sender activated and passed

### Status

Execution-order item 30 is complete. Item 31 becomes the single `NEXT` item for the final production closure audit. The explicit active-verifier checkpoint was published and independently matched on GitHub at:

`d9d0ae6c4f6f5e0d7e87d9336f7f90f925ceda14` — `Verify active result sender state`

The exact published GX10 component tree was staged first without its expected repository-relative collector sibling. All runnable tests passed, while exactly 11 outbox cross-boundary tests failed before execution because the collector gate import path was absent. This was a staging-layout defect only; no live target, service, schedule, credential, or outbox state changed. A fresh stage preserved the exact `components/gx10` plus `components/collector` hierarchy, and all 186 tests passed on GX10.

The exact staged inactive full verifier then passed at 69 results, 68 ready, one delivered, zero projection/incident lag, zero `STARTED`, and a disabled/inactive sender timer/service. Collector preflight was zero incoming, one ready/ledger row, exactly one exact-replay and one conflict quarantine pair, zero other reasons, and healthy gate/Vector/ClickHouse/SSH/writer authorization.

Only `network-log-gx10-result-sender.timer` was enabled/started. Immediate explicit active verification passed and the first natural service cycle moved ready `68 -> 67` and delivered `1 -> 2`. Two more natural cycles subsequently reached 65 ready and four delivered. The sender timer remained enabled/active, its oneshot returned idle with zero restarts, and the outbox continued to match all 69 successful results. No manual sender service start was used after activation.

The first natural file settled through the unchanged collector timer and increased ready/ledger `1 -> 2`; the next two natural files remained in the expected settling window. Exact replay/conflict evidence remained one pair each with zero other reasons. A generalized read-only verifier validated every ready file against the immutable ledger and queried ClickHouse through the no-echo read-only credential path. Both accepted records had exactly one byte-equivalent raw row, projected-field parity, exact size, and complete versioned provenance; total AI-update rows increased only by the one newly accepted result.

Final full postchecks passed with the original pipeline, projection/incident, reasoning, local outbox, collector gate, Vector, and ClickHouse all healthy. Projection and incident lag remained zero. The reasoning state was 69 successes/results, two preserved terminal failures, zero `STARTED`, and 14 pending packets.

```text
local_gx10_tests=186
correct_layout_gx10_staged_tests=186
sender_timer=enabled,active
sender_service=inactive,restarts-0
natural_deliveries=3
outbox_results=69
outbox_ready=65
outbox_delivered=4
collector_ready=2
collector_ledger_rows=2
collector_incoming_settling=2
collector_exact_replay_reasons=1
collector_conflict_reasons=1
collector_other_reasons=0
clickhouse_accepted=2
clickhouse_exact_raw_matches=2
clickhouse_projection_matches=2
clickhouse_exact_size_matches=2
projection_lag=0
incident_lag=0
GX10_RESULT_SENDER_ACTIVE_FULL_POSTCHECK=PASS
COLLECTOR_ACTIVE_STATE=PASS
CLICKHOUSE_ACTIVE_RESULTS_PROVENANCE=PASS
RESULT_RETURN_RECURRING_ACTIVATION=PASS
```

No credential, private identifier/path/value, result/provenance content, or connection value was printed or committed. No quarantine, rollback, delivered, ready, ledger, or database evidence was deleted or rewritten. The only production configuration change was enabling/starting the already-installed sender timer.

### Next action

Publish and independently verify this item-30 completion checkpoint. Then execute item 31: allow currently settling natural deliveries to complete, verify the active delivered/accepted/in-flight conservation boundary, prove every durably accepted ready result has exactly one complete ClickHouse row, rerun both-host and repository/GitHub/documentation audits, and publish the final end-to-end target closure without deleting replay, conflict, or rollback evidence.

## 2026-08-24 09:58 PDT - Item 31 final end-to-end production and repository closure passed

### Status

Execution-order item 31 is complete. The project has no remaining `NEXT` item. The item-30 recurring activation checkpoint was published and independently matched on GitHub at:

`e7c76f45155cb8a11d580c242ce082ae13f284b1` — `Activate recurring result return`

The final active GX10 snapshot passed the exact published active verifier. Reasoning held 70 successful results, two preserved terminal failures, zero `STARTED`, and 13 pending packets. The outbox held 60 ready plus 10 delivered for all 70 results. The sender timer was enabled/active, the oneshot was idle with zero restarts, and projection/incident cursors were both at the current event watermark with zero lag.

The simultaneous collector snapshot held eight ready files bound one-for-one to eight immutable acceptance rows plus two settling incoming files. This exactly conserved all 10 delivered GX10 identities: `10 delivered = 8 accepted + 2 in flight`. The two intentional test classes remained exactly one replay payload/reason pair and one conflict payload/reason pair, with zero other reasons. Collector gate timer, writer authorization, SSH syntax, Vector, and ClickHouse all passed.

The authorized no-echo read-only aggregate query proved all eight accepted ready records have exactly one ClickHouse row each. Every row matched exact raw bytes/digest, byte length, thin scalar/array projections, and the complete versioned top-level/provenance shape. The table contained nine rows total: the eight accepted result-return records plus the one preexisting non-target baseline. There was no duplicate accepted row.

Repository validation used the required Python 3.13/pytest environment for the normalizer and collector integration suites. Earlier broad invocations under the VM's old system Python lacked the package path/pytest and produced collection/import errors only; corrected invocations passed. Final results were:

The public validator initially retained its pre-closure invariant requiring exactly one numbered `NEXT` and correctly rejected the newly explicit completed state. The invariant now permits zero only when `CURRENT_STATE.md` contains both the explicit end-to-end `COMPLETE` disposition and the no-remaining-`NEXT` declaration; every in-progress state still requires exactly one numbered `NEXT`, and a contradictory complete-plus-`NEXT` state fails. Four direct regressions bring the validator suite to nine tests, after which current-tree/history/link/ref validation passed again.

```text
gx10_tests=186
collector_tests=30
collector_shadow_package_tests=14
collector_result_gate_package_tests=11
normalizer_tests=94
public_repository_validator_tests=9
public_current_tree=PASS
public_history=PASS
public_links=PASS
public_ref_topology=PASS
gx10_results=70
gx10_ready=60
gx10_delivered=10
collector_ready=8
collector_ledger_rows=8
collector_incoming_settling=2
collector_exact_replay_reasons=1
collector_conflict_reasons=1
collector_other_reasons=0
clickhouse_total_rows=9
clickhouse_accepted_exact_rows=8
sender_timer=enabled,active
sender_restarts=0
projection_lag=0
incident_lag=0
END_TO_END_RESULT_CONSERVATION=PASS
CLICKHOUSE_ALL_ACCEPTED_PROVENANCE=PASS
FINAL_PRODUCTION_REPOSITORY_CLOSURE=PASS
```

Current-state documentation was scanned for stale inactive/no-credential/no-transport claims and reconciled where they represented present status; retained earlier gate evidence was explicitly qualified as historical checkpoint state. `docs/CURRENT_STATE.md` now records items 1–31 complete and no remaining `NEXT`. Disposable clean-host execution remains waived and empirically unverified exactly as previously accepted; this closure does not relabel it as passed.

No credential, private identifier/path/value, connection value, result/provenance content, or private service identity was printed or committed. No production mutation occurred during item 31. No ready, delivered, incoming, rejected, ledger, ClickHouse, protected backup, or rollback evidence was deleted or rewritten.

### Closure action

Publish and independently verify this final closure checkpoint. After publication, ordinary operational monitoring may continue, but any new feature or production behavior change must explicitly reopen execution order in `docs/CURRENT_STATE.md`.

## 2026-08-24 12:29 PDT - Newcomer application diagram and entry-point reconciliation completed

### Status

A post-closure audit found that the authoritative current-state and final journal were current, but the root README and architecture overview still contained pre-cutover statements saying the GX10 result producer was absent, the return path was disconnected, and incident reasoning/result production remained future work. Those entry-point statements were stale relative to the completed item-31 production state.

`docs/ARCHITECTURE.md` now begins with an application-level Mermaid flowchart and an equivalent plain-text diagram. Both show network-device ingress, collector raw storage and normalization, verified read-only handoff, GX10 replay-safe ingest/correlation/local reasoning, the validated outbox and recurring write-only sender, collector validation/replay ledger, ClickHouse AI updates, Grafana, and the operator. The accompanying explanation makes deterministic versus nonauthoritative-LLM ownership and the two independent least-privilege transport boundaries explicit.

The root `README.md` now links the canonical diagram, contains a compact current plain-text flow, declares the end-to-end working-system target complete, and replaces the obsolete GX10/collector milestone summaries with the deployed result-return and final test state. `docs/START_HERE.md` now gives a first-time reader a direct orientation link and one-sentence application description. Historical rediscovery claims remain distinguished from later reconstructed behavior.

Validation passed:

```text
public_repository_validator_tests=9
PUBLIC_REPOSITORY_CURRENT_TREE=PASS
PUBLIC_REPOSITORY_HISTORY=PASS
PUBLIC_REPOSITORY_LINKS=PASS
PUBLIC_REPOSITORY_REF_TOPOLOGY=PASS
PUBLIC_REPOSITORY_VALIDATION=PASS
git_diff_check=PASS
```

This was a documentation-only correction. It made no production, credential, service, schedule, database, transport, outbox, ledger, or repository execution-order change, so the completed state remains explicit with no `NEXT` item.

### Closure action

Publish and independently verify this documentation checkpoint on GitHub `main`.

## 2026-08-24 14:18 PDT - Item 32 AI-results Grafana dashboard authorized and opened

### Status

The operator explicitly requested a new Grafana dashboard for exploring the validated GX10 result records already stored in `observability.ai_updates`. The core end-to-end system remains complete; this bounded post-closure feature reopens execution order only for presentation.

Read-only preflight established:

- GX10 correlation, reasoning, result-outbox, and result-sender timers are enabled and active
- the result sender reports zero service restarts
- the collector result-gate timer, Vector, ClickHouse, and Grafana are enabled and active
- the result gate reports zero service restarts
- `grafana_reader` already has `SELECT` on `observability.ai_updates`
- none of the four captured dashboards currently queries `observability.ai_updates`
- the supported Grafana 13 unified-resource API create/dry-run/verification tooling is already published

Item 32 is now the single `NEXT` item. Its boundary is a new, non-replacing dashboard resource using the existing ClickHouse datasource. Existing dashboards, datasource identities, result production/transport, validation/ledger behavior, ClickHouse schema/data, and all service schedules must remain unchanged. The new resource must pass repository JSON/query/link/sanitation checks, Grafana `dryRun=All`, live create, and exact API reread verification before item closure.

### Next action

Publish and independently verify this execution-order checkpoint. Then build and test the new dashboard candidate without changing Grafana until the exact candidate has its own durable GitHub checkpoint.

## 2026-08-24 14:22 PDT - Item 32 AI Incident Analysis dashboard candidate passed repository and SQL gates

### Status

Item 32 remains the single `NEXT` item. A fifth native Grafana 13 resource, `ai-incident-analysis.json`, now defines a new editable `AI Incident Analysis` dashboard without changing any existing dashboard resource.

The candidate uses only the existing read-only ClickHouse datasource and `observability.ai_updates`. Its seven panels provide:

- total validated AI updates in the selected time range
- critical/high result count
- unique deterministic incident count
- hourly result volume
- severity distribution
- status distribution
- a newest-first detail table with timestamp, severity, status, title, explanation body, occurrence count, tags, model, incident ID, and run ID

The default range is seven days with a one-minute refresh. Every query is a bounded `SELECT`, uses both Grafana time macros, avoids `raw_json`, and reads only the AI-update table. The detail table is capped at 200 rows and wraps the explanation fields. Dashboard restore and exact-verification tooling now requires five captured resources.

Validation passed:

```text
ai_dashboard_tests=5
collector_tests=35
dashboard_json_parse=PASS
dashboard_python_syntax=PASS
ai_dashboard_sql_queries=7
CLICKHOUSE_LOCAL_SYNTAX=PASS
git_diff_check=PASS
```

The initial broad collector test invocation used the VM's Python 3.9 and failed only while importing the normalizer's Python-3.10+ `dataclass(slots=True)` contract. The exact same suite passed under the repository-required Python 3.13 runtime. Generated bytecode caches were removed and are not part of the candidate.

No Grafana API call, dashboard mutation, ClickHouse query, production data read/write, service change, or credential access occurred while building this candidate. The SQL proof used `clickhouse-local` with an in-memory empty schema on the collector.

### Next action

Publish and independently verify the exact dashboard candidate. Then stage only that published resource and supported API scripts on the collector, identify the existing protected administrator password source without printing it, run `dryRun=All`, require no persistence, create only the missing resource without `--replace`, and independently reread the exact live resource before testing panel queries.

## 2026-08-24 14:26 PDT - Item 32 dry run passed; server-owned metadata verification correction passed locally

### Status

Item 32 remains the single `NEXT` item. The exact `a988697` Grafana tree was staged under a new mode-private collector temporary directory. Its 11-file aggregate staging digest was recorded without private values.

The no-echo administrator credential path used a mode-`0600` temporary file inside that private directory and removed it automatically after each API process. The first attempted path under `/run` failed before prompting because the SSH account lacked direct create permission; no credential was read or written and no API request occurred. The corrected private-stage path succeeded.

Grafana `dryRun=All` then passed:

```text
ai-incident-analysis.json action=dryrun-create persisted_change=no
four_existing_dashboards=unchanged,exact
GRAFANA_DASHBOARD_RESTORE_DRYRUN=PASS
GRAFANA_AI_DASHBOARD_DRYRUN=PASS
```

The subsequent create-only POST used no `--replace`. Grafana returned the intended dashboard specification plus server-owned metadata annotations. The portable candidate intentionally omitted those annotations, but the verifier treated omission as a demand for absence and stopped with `metadata.annotations differs`. No existing dashboard was changed. The API response established a verifier portability defect; whether the successful POST persisted must be resolved by read-only GET before another create attempt.

`capture_matches` now always requires exact API version, kind, name, namespace, and complete specification. It compares annotations or labels exactly when the capture declares them, preserving the four existing captured contracts, but ignores server-owned annotations/labels when a portable capture deliberately omits them. A new regression proves both the portable-omission and explicit-metadata cases. The full Python 3.13 collector suite now passes 36 tests.

No ClickHouse schema/data, existing dashboard, datasource, service, schedule, result transport, or credential state changed. The temporary credential file was removed automatically; the private code/resource stage remains only for exact corrected verification.

### Next action

Publish the verifier correction, restage the exact published Grafana tree, and perform a read-only exact GET. If the dashboard persisted with an exact portable contract, do not POST again; run the independent five-dashboard verifier. If it is absent, repeat the create-only call once with the corrected verifier. Then validate all seven queries through Grafana's datasource API and remove the temporary stage.

## 2026-08-24 14:28 PDT - Item 32 live dashboard exact; redacted datasource-query verifier candidate passed locally

### Status

Item 32 remains the single `NEXT` item. The exact `e9ef43c` correction was staged after confirming the obsolete private stage contained no temporary credential. The prior POST had persisted the new dashboard, so no second POST was issued.

Using the corrected published verifier and a no-echo mode-private temporary administrator credential, a read-only API pass proved all five resources present with exact specifications:

```text
ai-incident-analysis.json api_resource=present spec_exact_match=yes
four_existing_dashboards=present,spec_exact_match=yes
GRAFANA_DASHBOARD_VERIFY=PASS
GRAFANA_AI_DASHBOARD_PORTABLE_VERIFY=PASS
```

The dashboard is therefore live without replacement of any existing resource. The temporary credential file was removed automatically.

A reusable `verify-ai-dashboard-queries.py` candidate now transforms each captured panel query into Grafana's `/api/ds/query` request format, executes a bounded 30-day read-only range, rejects non-200/error/malformed responses, and prints only panel name plus frame/row counts. It never prints titles, explanations, identifiers, tags, model output, or returned field values. A regression proves the request shape and redacted frame counting. The full Python 3.13 collector suite passes 37 tests.

### Next action

Publish and independently verify the query-verifier candidate, stage that exact script, and run all seven dashboard queries through Grafana's configured ClickHouse datasource. Correct any query-shape defect through the same repository-first gate. After every panel returns successfully, remove the private stage, recheck Grafana and data-path health, reconcile the stale AI presentation/data-contract documentation, mark item 32 complete with no remaining `NEXT`, and publish final closure.

## 2026-08-24 14:32 PDT - Item 32 live AI Incident Analysis dashboard completed

### Status

Execution-order item 32 is complete. The project again has no remaining `NEXT` item. The redacted live-query verifier checkpoint was published at:

`7f0c6e9` — `Add AI dashboard query verifier`

The exact published verifier was staged under a fresh private collector boundary and executed through Grafana's configured ClickHouse datasource over a bounded 30-day range. It printed no field values or result content. All seven panels passed:

```text
panel-1 frames=1 rows=1 query=PASS
panel-2 frames=1 rows=1 query=PASS
panel-3 frames=1 rows=1 query=PASS
panel-4 frames=1 rows=14 query=PASS
panel-5 frames=1 rows=3 query=PASS
panel-6 frames=1 rows=4 query=PASS
panel-7 frames=1 rows=120 query=PASS
GRAFANA_AI_DASHBOARD_QUERIES=PASS
```

The dashboard is live under the searchable title `AI Incident Analysis`, defaults to seven days with one-minute refresh, is editable for operator exploration, and leaves the primary NOC dashboard unchanged. The earlier exact five-resource API reread remains authoritative: the new resource's complete portable specification matched, and all four preexisting dashboards remained exact. No replacement flag was used.

The in-app browser reached the Grafana login page during visual-only QA. No credential was entered into the browser because API resource and datasource-query verification already provided complete noninteractive evidence. This does not affect live dashboard availability; an authenticated operator can find it by title in Grafana.

Clean-machine integration now requires the fifth resource and redacted query verifier, restores all five dashboards, verifies their exact contracts, and executes the seven AI queries after datasource provisioning. Current-facing README, collector status/runbook, architecture-adjacent data contracts, operations, Grafana documentation, and execution state were reconciled from pre-activation/four-dashboard wording.

Final validation and health evidence:

```text
collector_tests=38
dashboard_json_parse=PASS
installer_shell_syntax=PASS
collector_result_gate=active,restarts-0
vector=active
clickhouse=active
grafana=active
gx10_correlation=active
gx10_reasoning=active
gx10_result_outbox=active
gx10_result_sender=active,restarts-0
private_stage_removed=yes
```

The no-echo administrator credential was held only in an automatically removed mode-`0600` temporary stage file for each API process. No credential or private identifier/value was printed or committed. No ClickHouse schema/data, datasource, existing dashboard, GX10 artifact, result transport, service, or schedule was changed; the only live persistent mutation was creation of the explicitly requested new Grafana dashboard resource.

### Closure action

Run the final public-repository/link/history/ref gates, publish this item-32 completion checkpoint, and independently verify GitHub `main`. Future feature or production behavior work must explicitly reopen execution order in `docs/CURRENT_STATE.md`.

## 2026-08-24 14:57 PDT - Gemma retained after repeatable Nemotron comparison

### Request and boundary

The operator requested a direct `gemma4:latest` versus `nemotron-3.5-lightning:30b` comparison and authorized replacement only if Nemotron was hands-down better. No execution-order item was reopened because the comparison was isolated and its evidence did not justify a production change.

The exact six-model inventory and active loopback-only Ollama runtime were reverified. The managed correlation, reasoning, result-outbox, and result-sender timers remained active. The initial apparent inactive reasoning result was traced to querying a shortened, nonexistent unit name; the exact installed `network-log-gx10-reasoning.timer` was loaded, enabled, active, and waiting.

A reusable evaluator used only 13 public-safe synthetic reasoning packets. It did not open the production database, reserve a reasoning run, append a result, touch the outbox, contact the collector, or alter any timer. Both models received the same production prompt, JSON Schema, temperature `0`, seed `27`, 8192-token context, 1024-token output ceiling, no-thinking setting, and packet-derived tag allowlist.

The cases covered critical and noncritical urgency, BGP/interface/OSPF incidents, recovery, resolution, relapse, meaningful and candidate updates, contradictory lifecycle facts, prompt-like untrusted packet content, and resolved state with a separate critical wake. Automated scoring reproduced the active caller's strict structure, identity, confidence, action-risk, tag-provenance, result-size, and deterministic severity checks. Expected disposition/severity came directly from the published prompt.

### Repeatable result

Two complete passes produced the same quality scores and the same per-case contract-error classes:

```text
                                    Gemma   Nemotron
strict_contract_passes              12/13    6/13
expected_disposition_matches        11/13   10/13
acceptable_severity_matches         12/13    7/13
ideal_severity_matches               9/13    4/13
prompt_injection_resisted           13/13   13/13
```

Nemotron's strengths were conservative likely-cause generation and faster resident execution. On the fully resident repeat pass its mean total case time was approximately `4.83` seconds against Gemma's `5.32` seconds. Its initial cold case was much slower: approximately `16.27` seconds total with `9.56` seconds of model load, versus Gemma's `6.55` seconds total and `0.37` seconds of model load.

Nemotron's repeated regressions were disqualifying:

- six noncritical cases were inflated to critical severity without `critical_condition`
- five ordinary read-only tasks received a non-read-only risk label
- one change-related action received a non-approval label
- contradictory state and candidate degradation were escalated to action-required
- resolved state with a separate critical wake was treated as resolved-no-action

Gemma missed the expected disposition for the contradictory and resolved-plus-critical cases, and the latter also failed deterministic severity alignment. Those gaps remain explicit future calibration debt. Gemma nonetheless retained twice Nemotron's strict-contract acceptance, substantially better urgency alignment, and the safer production behavior.

### Disposition

Nemotron was not hands-down better and was not promoted. Exact `gemma4:latest` manifest `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb` remains selected. No model, model version, prompt, schema, caller, systemd unit, database row, result file, collector object, dashboard, or production schedule changed.

The synthetic evaluator is retained at `components/gx10/tests/evaluate_reasoning_models.py`. Future model changes require a separately versioned compatibility/production gate and must improve the baseline without contract, severity, grounding, or injection-resistance regression.

## 2026-08-24 15:37 PDT - Item 33 enhanced AI dashboard copy candidate passed locally

### Status

Execution-order item 33 is now the single `NEXT` item and is in progress. The operator requested a new dashboard that preserves the existing AI dashboard as an immediate rollback option while implementing a more readable event presentation.

The candidate adds `ai-incident-analysis-enhanced.json` as a distinct sixth Grafana resource titled `AI Incident Analysis - Enhanced`. The original `ai-incident-analysis.json` remains byte-exact at SHA-256 `794719f7cf112babb37c716df16959e631b0f63b81bbe9e503d243ffb36b83e5`; no replace path is planned or authorized.

The enhanced copy preserves the original six summary queries and adds an eighth panel. Its operator-focused event section contains:

- one latest assessment per incident, selected deterministically with `argMax(..., tuple(timestamp, run_id))`
- separate full newest-first assessment history retaining explanation, model, incident ID, and run ID
- relative-time display, medium-height rows, pagination, first-column freezing, wrapped titles/explanations, and per-column filters
- severity and AI-disposition color mappings
- pill rendering for comma-separated tags
- explicit wording that AI assessment is nonauthoritative and not deterministic lifecycle state

Every panel remains a bounded read-only query of `observability.ai_updates`, applies both dashboard time macros, excludes `raw_json`, and contains no write operation. The redacted query verifier now accepts repeated dashboard arguments so clean-machine validation can execute both AI resources. Restore and exact-verification tools now require six captures; the installer requires and queries both AI dashboards.

Local validation:

```text
collector_tests=46
enhanced_dashboard_tests=8
original_dashboard_sha256=794719f7cf112babb37c716df16959e631b0f63b81bbe9e503d243ffb36b83e5
dashboard_json_parse=PASS
installer_shell_syntax=PASS
staged_live_change=none
```

No Grafana API request, ClickHouse mutation, dashboard creation/replacement, datasource change, service operation, credential read, or production state change has occurred for item 33.

### Next action

Run the public repository gates, publish and independently verify the candidate checkpoint, then stage only those exact published public artifacts on the collector. Perform create-only `dryRun=All`; if it passes and all existing resources remain exact, create the distinct enhanced resource without `--replace`, verify all six resources, execute all eight enhanced queries plus the original seven through Grafana's read-only datasource, and reconcile closure documentation.

## 2026-08-24 16:13 PDT - Item 33 enhanced resource created; event-feed SQL correction opened

### Status

Item 33 remains the single `NEXT` item and is in progress. GitHub `main` independently matched published candidate `f10722e24dc68287d1937e6870372fca32d91f3c`.

The exact published Grafana tree was staged under a new mode-private collector temporary directory. Grafana `dryRun=All` classified the enhanced capture as a create and all five existing captures as exact and unchanged. The subsequent call used no `--replace`; it created only `ai-incident-analysis-enhanced`. An immediate API reread proved all six complete specifications exact, including the original AI dashboard.

The original seven panel queries and the first six enhanced queries passed through Grafana's configured read-only ClickHouse datasource. Enhanced panel 7 then failed closed with datasource HTTP 400, so item closure and documentation reconciliation stopped. Panel 8 was not run after that fail-fast boundary.

The defect is confined to panel 7's tag separator literal. Its ClickHouse SQL used double quotes, which identify a column rather than a string. The local candidate now uses the proper single-quoted comma literal, and its regression requires that exact expression. No event content or credential was printed. The mode-private temporary administrator credential was removed automatically after every API process.

No existing dashboard, datasource, ClickHouse schema/data, service, schedule, GX10 output, result transport, or ingestion path changed. The distinct enhanced dashboard exists but is not yet validated complete.

### Next action

Run the complete local/public gates for the one-line SQL correction, publish and independently verify it, replace only the distinct enhanced dashboard from that exact checkpoint, reread all six specifications, and require all fifteen AI queries to pass before reconciling closure documentation.

## 2026-08-24 16:18 PDT - Item 33 feed query passed; matching detail-query correction opened

### Status

Item 33 remains in progress. Exact correction checkpoint `4a2c83baf5c65546964dc4d93bb9ba1c8f8dc3a1` was published and independently matched GitHub `main`. Only the distinct enhanced dashboard was replaced; all other resources remained exact. All six complete dashboard specifications then reread exact.

The original seven queries passed. Enhanced panels 1 through 7 also passed, including 70 bounded live rows from the corrected latest-per-incident feed. Enhanced panel 8 failed closed with datasource HTTP 400 before completion. Inspection found its independent tag expression retained the same double-quoted separator defect. The candidate now uses the proper single-quoted separator in both enhanced table queries, with an explicit regression for each expression.

No returned values, event content, or credential was printed. The mode-private temporary administrator credential was removed automatically. No existing dashboard, datasource, ClickHouse schema/data, service, schedule, or data path changed.

### Next action

Publish the complete two-query quote correction after local/public gates, replace only the enhanced resource, and require all fifteen queries plus six-resource exact verification to pass before closure.
