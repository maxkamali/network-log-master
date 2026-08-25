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

The end-to-end working system is complete through execution-order item 34. Item 35 is the single `NEXT`: publish, validate, and deploy only the enhanced-dashboard correction that routes every active interface entity to Interface Flaps, adds latest-AI-summary/deterministic-fallback Active Event detail, and shortens the resolved statistic label.

- The collector normalization shadow path and forward-only verified handoff are active; raw history and the exact rollback boundary remain preserved.
- GX10 fetch/ingest, canonical projection, deterministic incident correlation, managed Gemma reasoning, AI-result projection, deterministic incident-lifecycle projection, and the recurring one-file write-only sender are active under independent schedules.
- The collector validation gate and immutable acceptance ledger accept strict AI-result and lifecycle record families. Vector routes them exclusively to `observability.ai_updates` and `observability.incident_updates`.
- Six Grafana 13 dashboard resources are captured and live. The original `AI Incident Analysis` resource remains byte-exact. `AI Incident Analysis - Enhanced` is the deterministic NOC queue with Active Events, Interface Flaps, and Resolved Events windows.
- The item-34 production closure began with 804 lifecycle incidents in nine batches and passed 26 active non-flap, 10 active flap, 768 resolved, complete Device identity, clean timestamp invariants, and zero lifecycle rows in the AI table. Natural scheduled updates continued through the same path.
- Item-35 aggregate diagnosis later proved 22 active interface incidents with zero state changes were appearing in Active Events because the original presentation used the narrower `interface_flap` evidence flag. The repository candidate uses `entity_type = interface` for queue placement; production remains unchanged until its public checkpoint and protected enhanced-only replacement pass.
- Current repository suites pass 200 GX10 tests, 55 collector tests, nine public-validator tests, the GX10 filesystem contract, and all public current-tree/history/link/ref gates.
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
