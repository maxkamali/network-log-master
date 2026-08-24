# Deterministic GX10 Incident Engine

## Status and authority boundary

The version-1 incident engine is a validated repository candidate under execution-order item 25. It is not yet scheduled or active on the working GX10 system.

The engine consumes only classification-version-4 rows created by the canonical normalized-field projector. It does not parse raw messages, infer identity with an LLM, call Ollama, or emit AI results. Canonical normalized records remain observation authority; deterministic SQLite state remains incident identity and lifecycle authority.

## Identity

An incident correlation key is the SHA-256 of a canonical JSON tuple containing:

- contract label and version
- event family
- protocol
- entity type
- entity key

At most one non-resolved incident may exist for one correlation key. SQLite enforces that invariant with a unique partial index.

An incident instance ID is derived from the correlation key plus the immutable source-file and record-number identity of the first adverse observation. A later recurrence after resolution therefore receives a distinct deterministic incident ID, while replay of the same input receives the same ID.

## Evidence and lifecycle

Each accepted input becomes one append-only evidence row linked to its source event. An event can belong to at most one incident. Evidence records preserve the projected event code, signal, state, repeat count, attributes, and observed time used by the engine.

The lifecycle is:

```text
CANDIDATE -> OPEN -> RECOVERING -> RESOLVED
     |          ^          |
     +----------+----------+
```

The permitted transitions are deliberately narrower than the diagram's visual grouping:

- the first adverse observation creates `CANDIDATE`
- an explicit down/failed/disabled/idle state transition opens immediately
- other degradation requires a second adverse observation within 15 minutes of the first
- a candidate with no qualifying second adverse observation resolves at its fixed 15-minute deadline
- recovery evidence moves an open incident to `RECOVERING`
- adverse evidence during recovery reopens the same incident as a relapse
- five minutes of quiet after the latest recovery-period evidence resolves the incident
- adverse evidence after resolution creates a new deterministic incident instance

Every lifecycle transition is append-only. Timeout transitions use their deterministic event-time deadline rather than wall-clock execution time. Before each later event is correlated, deadlines at or before the current event-time watermark are resolved, so a late recovery or supporting observation cannot extend an expired candidate.

## Repeat, burst, and context state

The mutable incident row is a compact materialization over immutable evidence. It records:

- accepted evidence occurrence count
- total canonical repeat count
- observation-state change count
- strongest observed severity
- first/last observed time and lifecycle timestamps
- latest source event ID
- deterministic rolling context

Context contains exact evidence, repeat, adverse, recovery, and supporting counts for 60-minute, 180-minute, and 24-hour windows. It is canonical compact JSON and can later be supplied to a local model, but model output cannot modify these facts or lifecycle state.

## Transactions, replay, and failure behavior

The engine reads version-4 projections in source event-ID order in bounded batches. Each batch, all incident/evidence/transition changes, timeout sweeps, and the durable cursor update commit in one `BEGIN IMMEDIATE` transaction.

Replay protection has two layers:

- a durable versioned event-ID cursor prevents rescanning completed input
- a unique evidence event ID prevents duplication even if that cursor is lost or deliberately reset

Malformed canonical projection data, schema drift, invalid cursor state, contradictory transitions, database integrity failure, or aggregate/context mismatch fails closed. A failed batch rolls back its incident changes and cursor together.

## Schema and installation boundary

`components/gx10/sql/incident-v1.sql` adds three tables, five explicit indexes, and four append-only enforcement triggers without rewriting the five recovered base tables or their historical rows.

`components/gx10/install/migrate-incident-engine.py` is the existing-system guard. It requires exact repository hashes, canonicalized exact pre/post schema inventories, the exact functional suppression corpus, zero SQLite version/application markers, explicit root confirmation, an absent engine target, zero scheduler references, and protected destination parents. Canonicalization ignores only DDL whitespace representation; names, statements, constraints, indexes, and triggers must still match. The guard creates and validates a root-only SQLite backup before applying the schema and installing the engine. Empty-state rollback removes only the new schema and engine; it refuses rollback after an incident or engine cursor exists.

The clean-machine initializer and runtime verifier include the incident schema, and the application installer includes the engine, but the systemd service remains exactly `fetch -> ingest`. Installing the candidate does not run the projector or engine.

## Remaining activation gate

Before the working GX10 database or invocation chain changes:

1. publish and independently verify the exact candidate hashes
2. rehearse base-schema migration, canonical projection, incident processing, replay, and invariants on a protected SQLite backup copy
3. confirm the working database and installed artifacts still match the recorded preconditions
4. stage only published exact-hash artifacts
5. install the schema and engine unscheduled under a protected rollback boundary
6. separately authorize and validate any one-time projection/incident backfill or recurring schedule
7. retain incident state if populated; do not use destructive empty-state rollback after processing begins

An Ollama caller, wake policy, AI-result producer, and result-return schedule remain later milestones.
