# Start Here

Use this file as the canonical entry point when resuming the project after a context reset, handoff, or long pause.

## First-time orientation

If you are new to the application, begin with the root [`README.md`](../README.md). It explains what the platform does, what a NOC operator sees, the role and limits of AI, and the complete two-server flow. Then read [`docs/ARCHITECTURE.md#application-at-a-glance`](ARCHITECTURE.md#application-at-a-glance) for the detailed ownership and trust boundaries.

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
9. `docs/DETECTION_COVERAGE_BACKLOG.md` — review important captured event types that still require deterministic parser and incident-lifecycle coverage.
10. `docs/AI_DETECTION_SIDE_CHANNEL.md` — review the active hidden AI review of uncovered important events and the guarded severity 0-3 learned-coverage boundary.
11. `docs/DOCUMENTATION_GUIDE.md` — when changing documentation, use the authority map and update checklist rather than duplicating current facts.
12. Verify repository reality with `git log -10 --oneline` and `git status --short` before making changes.

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
- Use `docs/DOCUMENTATION_GUIDE.md` to decide which documents a change updates.
- Do not weaken safety or validation gates merely to make a commit pass.
- Do not execute clean-machine rebuild installers against the working reference systems unless the installer explicitly supports that mode.

## Current operating baseline

The numbered project sequence is complete with no numbered `NEXT` item.
Collector capture/normalization, the verified GX10 handoff, deterministic
incidents, local reasoning, hidden uncovered-event triage, validated result
return, the isolated NOC organization, compact one-click drilldowns, 24-hour
protocol monitoring, the rolling interface-flap filter, the transactional
outbox snapshot, the protocol-candidate monitoring correction, and the Vector
descriptor-limit protection are active.

Read `docs/CURRENT_STATE.md` before reopening scope or changing production
behavior. The append-only journal contains historical intermediate states and
must not be used to infer a newer execution order.
