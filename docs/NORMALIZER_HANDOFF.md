# Normalizer-to-GX10 Forward-Only Handoff

## Status and authority

Repository design and synthetic rehearsal: `DONE`.

Live collector/GX10 staging and activation: `DONE` on 2026-08-24.

This document records the selected file-identity contract, completed preflight/activation evidence, and retained rollback sequence. `docs/CURRENT_STATE.md` remains the authority for execution order.

## Problem resolved

The current GX10 fetcher accepts only:

```text
/spool/YYYY/MM/DD/HH/syslog-YYYYMMDD-HHMM.jsonl.zst
```

Shadow outputs intentionally use:

```text
YYYY/MM/DD/HH/syslog-YYYYMMDD-HHMM.normalized.jsonl.zst
```

A direct bind-mount switch to the shadow root would expose filenames that the current GX10 fetcher ignores. Renaming every historical shadow output to the raw pattern would instead create a second historical replay namespace or collide with the existing `source_files.remote_path` keys.

The selected solution is a forward-only handoff view with one immutable inclusive floor.

## Selected identity contract

Let `F` be the protected plan's `first_normalized_source_path`.

- source paths lexically before `F` remain represented by the raw spool already consumed by GX10
- verified completed shadow outputs at or after `F` are copied into a separate handoff root
- the handoff copy uses the original raw relative path and filename, without the `.normalized` marker
- no file before `F` may appear in the handoff root
- the original raw and shadow files remain untouched
- the current GX10 filename matcher and `/spool/...` remote-path identity remain unchanged
- the plan and initialized handoff ledger may not be repointed to a different floor

The resulting transport identity is continuous:

```text
before F  -> raw bytes        -> /spool/<source_path>
at/after F -> normalized bytes -> /spool/<same source_path>
```

GX10's existing primary key on `source_files.remote_path` and uniqueness key on `(source_file, record_number)` therefore remain the replay boundary. A successfully processed normalized file is not reingested from the raw view after rollback because it has the same remote path. A failed ingest rolls back its event transaction and remains eligible for the existing retry behavior.

## Repository implementation

The repository-only candidate consists of:

- `components/normalizer/src/network_log_normalizer/handoff.py`
- `components/normalizer/tests/test_handoff.py`
- `components/collector/normalizer/network-log-normalizer-handoff`
- `components/collector/normalizer/handoff-plan.example.json`
- `components/collector/normalizer/systemd/network-log-normalizer-handoff.service`
- `components/collector/normalizer/systemd/network-log-normalizer-handoff.timer`

These artifacts remain deliberately absent from the active shadow package manifest. The separate handoff-only exact-hash manifest, guarded non-activating installer, and independent runtime verifier are repository-validated and installed on the collector. Staging added new handoff artifacts without mutating the already verified live shadow package in place; the handoff timer was activated only after the protected plan, empty ledger, unit portability, and GX10 pause gates passed.

The publisher:

- reads only completed rows from the existing shadow ledger
- requires exact shadow output path, size, SHA-256, Zstandard integrity, cardinality, mode, and runtime ownership
- publishes only paths at or after the immutable floor
- copies bytes to a temporary same-directory file, synchronizes them, verifies the copy, and uses no-overwrite atomic publication
- never hard-links shadow and handoff files
- adopts an exact preexisting copy after interruption and rejects divergence
- records each publication in a separate versioned SQLite ledger
- fails on plan, schema, hash, mode, ownership, cardinality, orphan, missing-file, or unexpected-path divergence

The publisher has no network access, source-spool write access, ClickHouse path, SSH credential, GX10 credential, or AI-result path.

## Required private runtime layout

The later guarded staging step must create or verify:

| Purpose | Path | Required boundary |
|---|---|---|
| immutable plan | `/etc/network-log-normalizer/handoff-plan.json` | `0640 root:network-log-normalizer` |
| handoff root | `/var/spool/network-log-normalizer-handoff` | `0750 network-log-normalizer:network-log-normalizer` plus read/traverse ACL for `ai_spool_readers` |
| handoff ledger | `/var/lib/network-log-normalizer/handoff.sqlite3` | `0640 network-log-normalizer:network-log-normalizer` |
| SFTP view | `/srv/ai-spool-reader/spool` | read-only bind with `nosuid,nodev,noexec` |

The handoff root needs a default ACL so future partitions and files remain readable through the restricted SFTP account. No write permission is granted to that account.

## Production preflight

The documented cutover is complete. This sequence is retained for a future
separately authorized handoff change or rollback rehearsal; it is not current
execution authority. Before any live action, resolve the production
fetch/ingest unit from operator-private host configuration. The public
clean-machine unit name must not be assumed to be the live unit name.

After authorization, perform these checks before changing the live bind mount:

1. Verify GitHub `main`, repository sanitation, the exact handoff package manifest, and the recorded live shadow package hashes.
2. Verify Vector, ClickHouse, Grafana, the shadow timer, the raw bind mount, and the GX10 pipeline are healthy with no unexplained restart or failed-file state.
3. Run the complete active shadow verifier and require zero pending, incomplete, missing, orphaned, mutated, or parser-error evidence at the observation boundary.
4. Select a future UTC minute for `F` that leaves enough time for the 120-second source settle boundary plus two complete shadow/publisher schedules. Render the exact canonical source path into the protected plan.
5. Stage the exact-hash handoff artifacts, empty handoff root, ACL, plan, and empty handoff ledger. Leave the handoff timer disabled.
6. On GX10, disable the resolved production fetch/ingest timer and wait for
   its paired oneshot service to become inactive before any path at or after
   `F` becomes settled and fetchable.
7. Record public-safe GX10 baselines: total `source_files`, total `recent_events`, status counts, last remote scan time, incoming/processed queue counts, and the highest remote path. Do not publish connection values or event content.
8. Prove that GX10 contains no `source_files.remote_path` at or after `/spool/<F>`. Any such row is a cutover blocker; choose a later floor and reinitialize the still-empty handoff plan/ledger rather than deleting GX10 state.
9. Enable the publisher only after GX10 is stopped. Wait for settled shadow output at or after `F`, then temporarily stop both the shadow and publisher timers and wait for both oneshots to become inactive. Run the complete handoff verifier against that stable snapshot.
10. Require the restricted SFTP account to have read/list access to the handoff root and no write access before mounting it into the chroot.

No preflight step deletes, renames, truncates, or rewrites raw, shadow, handoff, or GX10 state.

## Activation sequence

With GX10 still stopped:

1. Record the exact current `/etc/fstab` and bind-mount source hashes plus a rollback copy in the operator-private evidence directory.
2. Replace only the GX10 spool bind entry:

   ```text
   /var/spool/vector-ai /srv/ai-spool-reader/spool none bind,ro,nosuid,nodev,noexec 0 0
   ```

   with:

   ```text
   /var/spool/network-log-normalizer-handoff /srv/ai-spool-reader/spool none bind,ro,nosuid,nodev,noexec 0 0
   ```

3. Remount only `/srv/ai-spool-reader/spool`; do not restart SSH, Vector, ClickHouse, Grafana, or the normalizer shadow service.
4. Verify the exact bind source and `ro,nosuid,nodev,noexec` options, handoff-root metadata/ACL, restricted SFTP listing, and a representative remote-file SHA-256 against the handoff ledger.
5. Run the handoff verifier again and require exact shadow/ledger/tree completeness.
6. Restart the shadow and publisher timers and verify one successful ordered publication cycle.
7. Start one manual GX10 pipeline cycle. Require successful download/ingest for a path at or after `F`, matching downloaded SHA-256 and expected file record count, with no failed rows.
8. Re-enable the GX10 timer only after that bounded cycle passes.
9. Confirm raw spool growth, ClickHouse ingestion, Vector health, shadow publication, handoff publication, and GX10 processing continue independently.

## Immediate post-activation acceptance

The activation checkpoint must record:

- exact plan hash and public-safe floor path
- exact installed handoff package manifest hash
- raw, shadow, and handoff file/count totals without private content
- handoff verifier totals and zero missing/orphaned files
- GX10 `source_files`/`recent_events` before and after counts
- first normalized handoff remote path, downloaded hash parity, and record-count parity
- unchanged Vector configuration, raw spool, ClickHouse, Grafana, and existing GX10 application hashes
- exact bind source/options and service/timer states

The transition is not accepted if a raw path at or after `F` was already present in GX10 before activation, if a normalized path is ignored, if history before `F` is exposed, or if record/hash/cardinality evidence differs.

## Live activation evidence

The authorized production activation completed on 2026-08-24 with inclusive floor:

```text
2026/08/24/06/syslog-20260824-0612.jsonl.zst
```

Public-safe immutable evidence:

- protected plan SHA-256: `5cd4d29d4675b706db348845168b7f5c319004db90ed3342acb860d35e92464c`
- installed handoff-package manifest SHA-256: `26b52aa0a75318ee6c2e768bffd91a8bf37c13b836c3f5b81691c687f8bb61d7`
- pre-cutover `/etc/fstab` SHA-256: `37244f78ab8701d0375de18dda408060e1a519838a1351d8fe281e2258d07189`
- post-cutover `/etc/fstab` SHA-256: `9f42af9d43124d66c3cb02cc20b23b7ee7272e02fd1afef428dcddd0e9e98259`
- stable pre-switch shadow verification: `12,082` completed files and `1,117,167` records
- stable pre-switch handoff verification: exactly one file at the floor, `69` records, zero missing/orphaned/pre-floor files
- first-file SHA-256: `a9d99713de4aae447d8ad41154b3ee25332fe190a60f41f54bbb5441440275d6`
- first ordered publication state after schedules resumed: `4` verified files and `332` records
- GX10 bounded cycle: source files `10,437 -> 10,441`; recent events `947,064 -> 947,396`
- all four GX10 file sizes, SHA-256 values, and record counts exactly matched the independent collector handoff ledger
- all GX10 source rows remained `processed`; incoming files and duplicate `(source_file, record_number)` identities remained zero
- the GX10 timer, shadow timer, and handoff timer resumed enabled/active with successful inactive oneshots and zero restarts at the acceptance instant
- twelve subsequent automatic observations, including one idempotent no-new-file cycle, advanced both systems to exactly `19` at/after-floor files and `1,916` records; final complete stable verification covered `12,099` shadow files and `1,118,724` records with zero missing/orphaned handoff files
- the live bind source is the handoff root with `ro,nosuid,nodev,noexec`; the protected raw-view definition and operator-private rollback copy remain available

During staging, the collector reported that `ConditionPathIsRegularFile` was unsupported by its systemd version. Activation stopped while the timer was still disabled and the raw bind remained live. The unit was changed to portable `ConditionPathExists`; strict application-level regular-file, symlink, mode, ownership, and plan-content validation remains mandatory. The corrected artifact passed exact old-hash replacement, clean `systemd-analyze verify`, and the independent staged verifier before activation.

## Rollback sequence

Rollback remains a mount/view change, not a data rewrite:

1. Disable the GX10 timer and wait for the oneshot pipeline service to become inactive.
2. Record current queue/status counts. Do not delete a downloaded normalized file or edit a `source_files` row.
3. Restore the exact prior raw-spool `/etc/fstab` bind entry and remount only `/srv/ai-spool-reader/spool`.
4. Verify the raw bind source/options and restricted SFTP read-only behavior.
5. Run one manual GX10 cycle. Already processed at/after-floor paths must skip because their remote identity is unchanged. Failed paths may redownload raw bytes under the existing retry contract; their prior event transaction must have rolled back.
6. Verify no duplicate `(source_file, record_number)` rows, no unexplained event-count jump, and no failed/processing residue.
7. Re-enable the GX10 timer after verification. Disable the handoff publisher timer, but preserve its plan, ledger, handoff tree, shadow tree, and raw tree for investigation.

Rollback never attempts to reverse already-ingested normalized rows in place.

## Synthetic rehearsal evidence

The repository rehearsal uses three sequential source paths with the middle path as `F`. It proves:

- the pre-floor file is absent from the handoff view
- both at/after-floor files use raw-style names accepted by the unchanged GX10 matcher
- `.normalized` shadow names remain rejected by that matcher
- bounded publication advances durably and an empty retry is idempotent
- exact crash-window copies are adopted while divergent files fail closed
- shadow and handoff files are byte-identical but separate single-link inodes
- plan mutation and handoff-byte mutation fail closed
- the exact handoff ledger schema and file inventory verify
- raw-view rollback of already processed at/after-floor remote paths creates no duplicate GX10 identities or events

Validation after the authorized staging-package implementation reports `94` normalizer/worker tests and `14` collector-package tests passing. No live collector or GX10 state was changed by the rehearsal or package implementation.
