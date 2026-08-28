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

The numbered project sequence is complete with no remaining numbered `NEXT`
item. The rolling interface-flap filter, forward-only 24-hour OSPF/BGP
monitoring policy, backward-compatible lifecycle producer version 2 recurrence
projection, additive collector column, enhanced-dashboard `MONITORING`/issue-
occurrence presentation, isolated NOC Viewer access boundary, one-minute NOC
rotation playlist, compact one-click Explore drilldowns, protocol-candidate
monitoring correction, and Vector descriptor-limit protection are active under
protected predecessors.

- The collector normalization shadow path and forward-only verified handoff are active; raw history and the exact rollback boundary remain preserved.
- GX10 fetch/ingest, canonical projection, deterministic incident correlation, managed Gemma reasoning, AI-result projection, deterministic incident-lifecycle projection, and the recurring one-file write-only sender are active under independent schedules.
- The collector validation gate and immutable acceptance ledger accept strict AI-result and lifecycle record families. Vector routes them exclusively to `observability.ai_updates` and `observability.incident_updates`.
- Six Grafana 13 dashboard resources are captured and live. The original `AI Incident Analysis` resource remains byte-exact. `AI Incident Analysis - Enhanced` is the deterministic NOC queue with Active Events, Interface Flaps, and Resolved Events windows.
- The item-34 production closure began with 804 lifecycle incidents in nine batches and passed 26 active non-flap, 10 active flap, 768 resolved, complete Device identity, clean timestamp invariants, and zero lifecycle rows in the AI table. Natural scheduled updates continued through the same path.
- Item-35 aggregate diagnosis proved 22 active interface incidents with zero state changes were appearing in Active Events because the original presentation used the narrower `interface_flap` evidence flag. The protected enhanced-only correction is now live and exact: two non-interface incidents remain in Active Events, all 34 active interface incidents appear in Interface Flaps, and the two current Active rows use deterministic detail fallback because no stored AI summary exists for them yet.
- Item 36 leaves the 15-minute unconfirmed-candidate rule and five-minute non-OSPF/BGP recovery quiet period unchanged. Confirmed BGP/OSPF/OSPFv3 recovery instead retains the same incident in `RECOVERING` for 24 continuous healthy hours; Grafana labels that state `MONITORING`. A relapse returns the same correlation identity to `OPEN`; producer version 2 derives `recurrence_count` from append-only relapse transitions while legacy version-1 lifecycle files remain valid. Production closure reconciled 853 latest version-2 incidents and an exact recurrence sum of 3,037 across 526 recurring incidents; existing resolved BGP/OSPF/OSPFv3 rows remained resolved.
- Item 36 passed 205 GX10 tests, 56 collector tests, nine public-validator tests, the GX10 filesystem contract, all public current-tree/history/link/ref gates, exact six-resource Grafana reread, and all thirteen live dashboard queries. No confirmed protocol incident entered recovery during activation, so the 24-hour timing proof remains deterministic test evidence rather than a synthetic production row.
- Item 37 adds a separate Grafana NOC organization with one dedicated Viewer, only `NOC View` and `AI Incident Analysis - Enhanced`, and only their two read-only datasource copies. The Viewer home/star settings, non-scoped dashboard denial, save denial, Explore compatibility, all fourteen NOC panel queries, exact unchanged six-dashboard main organization, Grafana database integrity, and service health passed. Grafana OSS cannot enforce the requested exact per-user navigation allowlist; do not represent organization/resource isolation as custom menu enforcement.
- Item 38 adds one `NOC Rotation` playlist in the isolated NOC organization: stable dashboard UIDs in `NOC View` then enhanced-analysis order, one minute per dashboard, and a validated auto-fit play route. Viewer read/start access and create denial passed, `NOC View` remains the login home, the main organization contains no playlist, and all six main dashboard resources remain exact.
- Item 39 added `View matching logs` to every cell in all three enhanced event tables. Item 41 retains that incident-ID lookup for Active and Resolved and replaces the flap lookup with the exact device/interface rolling-hour query. Every current target is compact, read-only, organization-local, newest first, and capped at 1,000 rows.
- Item 40 starts every enhanced and NOC View Explore lookup with its SQL editor collapsed and makes the four existing NOC View links single-click. Main and isolated NOC copies retain organization 1 and 2 respectively. All affected link queries remain read-only and unchanged; protected replacement, main exact reread, organization-scoped NOC reread, database integrity, query execution, and service-health gates passed.
- Item 41 excludes interface entities from both incident windows and derives Interface Flaps directly from `observability.grafana_logs`: one exact NX-OS interface-down transition is one observation, grouped by device/interface across the rolling preceding 60 minutes, with a visible threshold of 10. Persistent single-down ports and lower-rate bounces stay hidden; rows leave automatically below threshold. The flap row's compact one-click Explore link uses hidden hex row keys and the same rolling hour. Main and NOC dry-runs/replacements, exact rereads, all queries/drilldowns, database integrity, two-resource-only change scope, and service health passed. No lifecycle, GX10, schema, ingestion, or model change occurred.
- Clean-machine execution on disposable collector and GX10 hosts remains waived by the operator and empirically unverified. Do not relabel that qualification as passed.

For NOC queue behavior, search/filter semantics, state movement, and the deliberate absence of manual resolution, read `docs/NOC_WORKFLOW.md`.

## Protected boundaries

- Do not publish credentials, connection values, private device identities, raw production events, or private keys.
- Direct host access is not blanket authorization for destructive changes.
- Preserve protected predecessor/rollback copies unless an explicit retirement decision is approved.
- Grafana is presentation, not the incident state database. Manual resolution requires a separately designed authenticated override contract.
- Deterministic incident state remains authoritative. Ordinary assessment output is explanatory; only the validated hidden side channel may admit an uncovered important event as a generic incident, after which deterministic lifecycle owns it.
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
