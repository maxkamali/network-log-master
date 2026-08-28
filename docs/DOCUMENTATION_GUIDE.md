# Documentation Guide

## Purpose

This repository is designed to be resumed by an engineer or an AI without
private conversational memory. Keep documentation small, current, and linked
to its authority instead of repeating changing facts in many files.

## Read by role

| Need | Start with | Then read only if needed |
|---|---|---|
| Understand the application | `README.md` | `docs/ARCHITECTURE.md` |
| Resume or change work | `docs/START_HERE.md` | `docs/CURRENT_STATE.md`, relevant component/status files |
| Operate the running system | `docs/OPERATIONS.md` | `docs/NOC_WORKFLOW.md`, `docs/GRAFANA.md` |
| Rebuild both hosts | `docs/TWO_SERVER_REBUILD.md` | component runbooks and `docs/ACCEPTANCE.md` |
| Understand a subsystem | its dedicated document | source README and tests |
| Understand why a choice exists | `docs/DECISIONS.md` | the linked journal checkpoint |
| Review historical evidence | latest `docs/PROJECT_JOURNAL.md` entries | older entries only when required |

## Authority map

| Fact type | Canonical owner | Update when |
|---|---|---|
| Plain-language purpose and operator value | `README.md` | user-visible behavior changes |
| Current production state, open work, and residual risk | `docs/CURRENT_STATE.md` | deployment, closure, rollback, or execution-order changes |
| Stable data flow, boundaries, and ownership | `docs/ARCHITECTURE.md` | architecture changes |
| Operational procedures and failure behavior | `docs/OPERATIONS.md` | service behavior or operator workflow changes |
| Future/deferred work | `docs/ROADMAP.md` | a proposal is accepted, deferred, started, or completed |
| Durable design choice | `docs/DECISIONS.md` | an architecture decision is accepted, superseded, or reversed |
| Evidence, commands, validation, and rollback record | `docs/PROJECT_JOURNAL.md` | every completed bounded change |
| Component implementation and clean rebuild details | component README/status files | component code, installer, or verifier changes |

Do not copy a changing status, test count, production inventory, or pending
item into several documents. Link to the canonical owner instead. Historical
journal entries remain historical evidence and are not rewritten to sound
current.

## Change checklist

Before merging a bounded change, update only the rows that apply:

| Change | Required documentation |
|---|---|
| Code/configuration behavior | relevant component README and subsystem contract |
| Live deployment or rollback | `CURRENT_STATE`, `OPERATIONS` when operator behavior changes, and journal |
| Dashboard/access workflow | `NOC_WORKFLOW` and/or `GRAFANA`, plus journal |
| Data schema/transport contract | `DATA_CONTRACTS` plus affected subsystem contract |
| Architecture decision | `ARCHITECTURE`, `DECISIONS`, and journal |
| Future idea with no implementation | `ROADMAP` only |
| New agent orientation or safety boundary | `README` and/or `START_HERE` |

## Writing rules

- Lead with current behavior, then link to details.
- Use **current**, **historical**, **deferred**, and **waived** precisely.
- Put mutable operational counts and exact hashes in the journal unless an
  operator must act on them.
- Use public-safe examples only; never include credentials, private addresses,
  private hostnames, customer identifiers, or raw production logs.
- Keep a document within its scope. Prefer a link over duplicating a section.
- When a decision supersedes another, state that directly in the newer ADR.

## Required validation

Run before publishing documentation changes:

```text
python3 scripts/validate-documentation.py
python3 scripts/validate-public-repository.py
python3 -m unittest scripts/test_documentation_validator.py scripts/test_public_repository_validator.py
git diff --check
```

The documentation validator checks the entry-path contract, required authority
references, local Markdown links and anchors, and known stale summary wording.
The public validator checks public safety, execution authority, history, links,
and permitted rollback-tag topology.

## Journal entry template

```text
## YYYY-MM-DD - Short change title

### Scope
What changed and what explicitly did not change.

### Validation
Tests, read-only checks, and meaningful outcomes.

### Rollback and follow-up
Protected rollback boundary, remaining risk, and any deferred work.
```

## Decision template

```text
## ADR-NNN - Decision title

**Status:** Accepted | Superseded | Reversed

Decision, rationale, consequences, and links to the validating journal entry.
```
