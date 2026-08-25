# AI Handoff

Use this file to resume the project safely in a fresh engineering or AI session.

## Mandatory read order

1. `docs/START_HERE.md`
2. `docs/ARCHITECTURE.md`
3. `docs/CURRENT_STATE.md`
4. `components/collector/REBUILD_STATUS.md`
5. `components/gx10/REBUILD_STATUS.md`
6. the latest entries in `docs/PROJECT_JOURNAL.md`
7. `docs/DECISIONS.md`
8. `docs/DATA_CONTRACTS.md`
9. `docs/OPERATIONS.md`
10. component-specific documentation for the task at hand
11. verify repository reality with `git log -10 --oneline` and `git status --short`

`docs/CURRENT_STATE.md` is the execution authority. Do not infer a different work order from older journal entries or historical runbooks.

## Source precedence

When sources disagree, use this order:

1. live verified system/configuration and current checked-out code/tests
2. `docs/CURRENT_STATE.md` and the component `REBUILD_STATUS.md` files
3. current repository implementation and component documentation
4. architecture/decision documents
5. older journal entries or planning documents

Stop and reconcile meaningful disagreement instead of guessing.

## Current durable state

The end-to-end working system is complete through execution-order item 37. There is no remaining numbered `NEXT` item. The forward-only 24-hour OSPF/BGP monitoring policy, backward-compatible lifecycle producer version 2 recurrence projection, additive collector column, enhanced-dashboard `MONITORING`/issue-occurrence presentation, and isolated NOC Viewer access boundary are active under protected predecessors.

- The collector normalization shadow path and forward-only verified handoff are active; raw history and the exact rollback boundary remain preserved.
- GX10 fetch/ingest, canonical projection, deterministic incident correlation, managed Gemma reasoning, AI-result projection, deterministic incident-lifecycle projection, and the recurring one-file write-only sender are active under independent schedules.
- The collector validation gate and immutable acceptance ledger accept strict AI-result and lifecycle record families. Vector routes them exclusively to `observability.ai_updates` and `observability.incident_updates`.
- Six Grafana 13 dashboard resources are captured and live. The original `AI Incident Analysis` resource remains byte-exact. `AI Incident Analysis - Enhanced` is the deterministic NOC queue with Active Events, Interface Flaps, and Resolved Events windows.
- The item-34 production closure began with 804 lifecycle incidents in nine batches and passed 26 active non-flap, 10 active flap, 768 resolved, complete Device identity, clean timestamp invariants, and zero lifecycle rows in the AI table. Natural scheduled updates continued through the same path.
- Item-35 aggregate diagnosis proved 22 active interface incidents with zero state changes were appearing in Active Events because the original presentation used the narrower `interface_flap` evidence flag. The protected enhanced-only correction is now live and exact: two non-interface incidents remain in Active Events, all 34 active interface incidents appear in Interface Flaps, and the two current Active rows use deterministic detail fallback because no stored AI summary exists for them yet.
- Item 36 leaves the 15-minute unconfirmed-candidate rule and five-minute non-OSPF/BGP recovery quiet period unchanged. Confirmed BGP/OSPF/OSPFv3 recovery instead retains the same incident in `RECOVERING` for 24 continuous healthy hours; Grafana labels that state `MONITORING`. A relapse returns the same correlation identity to `OPEN`; producer version 2 derives `recurrence_count` from append-only relapse transitions while legacy version-1 lifecycle files remain valid. Production closure reconciled 853 latest version-2 incidents and an exact recurrence sum of 3,037 across 526 recurring incidents; existing resolved BGP/OSPF/OSPFv3 rows remained resolved.
- Item 36 passed 205 GX10 tests, 56 collector tests, nine public-validator tests, the GX10 filesystem contract, all public current-tree/history/link/ref gates, exact six-resource Grafana reread, and all thirteen live dashboard queries. No confirmed protocol incident entered recovery during activation, so the 24-hour timing proof remains deterministic test evidence rather than a synthetic production row.
- Item 37 adds a separate Grafana NOC organization with one dedicated Viewer, only `NOC View` and `AI Incident Analysis - Enhanced`, and only their two read-only datasource copies. The Viewer home/star settings, non-scoped dashboard denial, save denial, Explore compatibility, all fourteen NOC panel queries, exact unchanged six-dashboard main organization, Grafana database integrity, and service health passed. Grafana OSS cannot enforce the requested exact per-user navigation allowlist; do not represent organization/resource isolation as custom menu enforcement.
- Clean-machine execution on disposable collector and GX10 hosts remains waived by the operator and empirically unverified. Do not relabel that qualification as passed.

For NOC queue behavior, search/filter semantics, state movement, and the deliberate absence of manual resolution, read `docs/NOC_WORKFLOW.md`.

## Protected boundaries

- Do not publish credentials, connection values, private device identities, raw production events, or private keys.
- Direct host access is not blanket authorization for destructive changes.
- Preserve protected predecessor/rollback copies unless an explicit retirement decision is approved.
- Grafana is presentation, not the incident state database. Manual resolution requires a separately designed authenticated override contract.
- Deterministic incident state remains authoritative; AI output is explanatory and stays outside the NOC queue.
- GX10 never writes directly to ClickHouse.

## Working method

- inspect verified behavior before changing it
- keep each change bounded and reversible
- use repository-first implementation and exact published artifacts for production work
- exercise negative, replay, idempotency, and fail-closed paths
- use dry-run API validation before dashboard replacement
- update `docs/CURRENT_STATE.md`, component status files, and append-only `docs/PROJECT_JOURNAL.md` with every completed validated subsection
- run `docs/PUBLICATION_CHECKLIST.md` before public commits
- independently verify GitHub after every published checkpoint
