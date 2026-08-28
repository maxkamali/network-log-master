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
10. `docs/TWO_SERVER_REBUILD.md` for any clean or coordinated two-host reconstruction
11. component-specific documentation for the task at hand
12. verify repository reality with `git log -10 --oneline` and `git status --short`

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

Do not maintain a second current-state summary in this file. Read
[`CURRENT_STATE.md`](CURRENT_STATE.md) for the production baseline, residual
risk, and execution authority. Read [`NOC_WORKFLOW.md`](NOC_WORKFLOW.md) for
operator queue behavior, [`OPERATIONS.md`](OPERATIONS.md) for runtime behavior,
and the latest [`PROJECT_JOURNAL.md`](PROJECT_JOURNAL.md) entries for exact
validation and deployment evidence.

The only handoff-level disposition retained here is that the numbered project
sequence is complete with no numbered `NEXT`, while disposable clean-host
execution remains waived and empirically unverified. If either statement
disagrees with `CURRENT_STATE.md`, stop and reconcile this file rather than
copying additional current details into it.

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
- use `docs/DOCUMENTATION_GUIDE.md` to update only the documents that own the changed facts
- run `docs/PUBLICATION_CHECKLIST.md` before public commits
- independently verify GitHub after every published checkpoint
