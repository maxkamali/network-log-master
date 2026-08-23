# Start Here

Use this file as the canonical entry point when resuming the project after a context reset, handoff, or long pause.

## Recovery order

Read and verify in this order before changing implementation:

1. `docs/ARCHITECTURE.md` — understand the intended two-server system and ownership boundaries.
2. `docs/CURRENT_STATE.md` — establish what is actually complete, what is incomplete, and the strict execution order. This file is the authority for the single `NEXT` item.
3. The relevant component rebuild statuses — `components/collector/REBUILD_STATUS.md` and `components/gx10/REBUILD_STATUS.md`; both component reconstruction milestones are closed and cross-system reconciliation is active.
4. The latest entries in `docs/PROJECT_JOURNAL.md` — understand recent decisions, failed approaches, validation evidence, and checkpoint history.
5. `docs/DECISIONS.md` — review durable architecture decisions that constrain implementation choices.
6. `docs/DATA_CONTRACTS.md` and `docs/OPERATIONS.md` — confirm data and operational contracts for the area being changed.
7. Component-specific documentation for the active task.
8. Verify repository reality with `git log -10 --oneline` and `git status --short` before making changes.

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
- Keep `docs/CURRENT_STATE.md` synchronized with execution order and maintain exactly one item marked `NEXT`.
- Do not weaken safety or validation gates merely to make a commit pass.
- Do not execute clean-machine rebuild installers against the working reference systems unless the installer explicitly supports that mode.

## Current project sequence

The current high-level order is:

1. finish the collector rebuild package and documentation
2. capture and reconstruct the GX10 implementation
3. perform final two-server rebuild documentation and validation
4. close the project only when the acceptance criterion is satisfied

For the exact current task, read `docs/CURRENT_STATE.md`.
