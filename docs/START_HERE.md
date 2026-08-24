# Start Here

Use this file as the canonical entry point when resuming the project after a context reset, handoff, or long pause.

## Recovery order

Read and verify in this order before changing implementation:

1. `docs/ARCHITECTURE.md` — understand the intended two-server system and ownership boundaries.
2. `docs/CURRENT_STATE.md` — establish what is actually complete, what is incomplete, and the strict execution order. This file is the authority for the single `NEXT` item while work remains and the completed state when none remains.
3. The relevant component rebuild statuses — `components/collector/REBUILD_STATUS.md` and `components/gx10/REBUILD_STATUS.md`; both component reconstruction milestones are closed.
4. The latest entries in `docs/PROJECT_JOURNAL.md` — understand recent decisions, failed approaches, validation evidence, and checkpoint history.
5. `docs/DECISIONS.md` — review durable architecture decisions that constrain implementation choices.
6. `docs/DATA_CONTRACTS.md`, `docs/OPERATIONS.md`, and `docs/TWO_SERVER_REBUILD.md` — confirm data, operational, and cross-host rebuild contracts.
7. `docs/ACCEPTANCE.md` — confirm what passed and which unavailable disposable-host executions were waived with residual risk.
8. Component-specific documentation for the area being reviewed. For the completed result-return boundary, read `docs/RESULT_OUTBOX.md`, `docs/RESULT_TRANSPORT.md`, `components/gx10/README.md`, and `components/collector/REBUILD_STATUS.md`.
9. Verify repository reality with `git log -10 --oneline` and `git status --short` before making changes.

Do not infer a new execution order from the journal. `docs/CURRENT_STATE.md` is the execution authority.

## Project acceptance criterion

The rebuild/documentation project is complete only when:

> Two clean servers, this public repository, and operator-supplied environment values are sufficient for another engineer or AI to reconstruct the current functional system without undocumented implementation memory.

Environment-specific values such as credentials, addresses, usernames, SSH keys, certificate private keys, and similar identity-bearing values are intentionally supplied by the operator at rebuild time and are not part of the public repository.

## Public-repository boundary

Never publish:

- credentials, passwords, API tokens, private keys, or secret files
- production IP addresses or firewall allowlists
- private hostnames or operator identity
- customer/device-identifying raw logs
- certificate private keys
- generated databases or runtime state
- restricted historical branding or organization identifiers

Use synthetic fixtures and documentation address space when examples require identities or addresses.

## Working rules

- Inspect and preserve verified live behavior before changing it.
- Change one bounded sub-section at a time.
- Validate each sub-section before declaring it complete.
- After each completed sub-section, append the result to `docs/PROJECT_JOURNAL.md` and push that journal update to GitHub before materially entering the next sub-section.
- Keep `docs/CURRENT_STATE.md` synchronized with execution order; maintain exactly one `NEXT` while work remains and none after explicit end-to-end closure.
- Do not weaken safety or validation gates merely to make a commit pass.
- Do not execute clean-machine rebuild installers against the working reference systems unless the installer explicitly supports that mode.

## Current project sequence

The current high-level order is:

1. preserve the completed two-server rebuild package and validated raw production path
2. advance production normalization only through the documented shadow, handoff, authorization, and rollback gates
3. activate deterministic projection/incident processing only through the managed invocation, telemetry, failure-isolation, and rollback gate
4. build local-model orchestration after deterministic incident state is operational
5. integrate result return/dashboard behavior and close the end-to-end target only after its acceptance evidence passes

All five stages are complete on the working systems. Read `docs/CURRENT_STATE.md` before reopening scope or changing production behavior.
