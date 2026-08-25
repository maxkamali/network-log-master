# Deterministic GX10 Incident Engine

## Status and authority boundary

The version-1 incident engine completed execution-order item 25. Its private working-database-copy, cursor-reset replay, independent deterministic rebuild, and guarded unscheduled working-system migration gates pass. Item 26 later completed the separate managed production invocation gate: initial backfill and three scheduled zero-lag cadences passed while the original fetch/ingest timer continued advancing. The protected pre-migration backup remains retained. Item 36 advances the repository candidate to engine version 2 solely for the forward-only protocol-monitoring policy; production remains on the verified predecessor until that candidate is published and protected deployment passes.

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
- confirmed BGP, OSPF, and OSPFv3 recovery remains `RECOVERING` for 24 continuous healthy hours from the recovery transition; the dashboard presents this as `MONITORING`
- other recovering incidents retain the five-minute quiet-period rule
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

The operator-facing issue-occurrence count is distinct from evidence count. Lifecycle producer version 2 derives `recurrence_count` from append-only `RECOVERING -> OPEN` `adverse_relapse` transitions and presents total issue episodes as `recurrence_count + 1`. A relapse inside the 24-hour monitoring window therefore increments the same incident; only an adverse event after deterministic resolution creates a new incident instance.

## Transactions, replay, and failure behavior

The engine reads version-4 projections in source event-ID order in bounded batches. Each batch, all incident/evidence/transition changes, timeout sweeps, and the durable cursor update commit in one `BEGIN IMMEDIATE` transaction.

Replay protection has two layers:

- a durable versioned event-ID cursor prevents rescanning completed input
- a unique evidence event ID prevents duplication even if that cursor is lost or deliberately reset

Malformed canonical projection data, schema drift, invalid cursor state, contradictory transitions, database integrity failure, or aggregate/context mismatch fails closed. A failed batch rolls back its incident changes and cursor together.

## Schema and installation boundary

`components/gx10/sql/incident-v1.sql` adds three tables, five explicit indexes, and four append-only enforcement triggers without rewriting the five recovered base tables or their historical rows.

`components/gx10/install/migrate-incident-engine.py` is the existing-system guard. It requires exact repository hashes, canonicalized exact pre/post schema inventories, the exact functional suppression fields (ID, rule type, pattern, order, and enabled state), zero SQLite version/application markers, explicit root confirmation, an absent engine target, zero scheduler references, and protected destination parents. Canonicalization ignores only DDL whitespace representation; names, statements, constraints, indexes, and triggers must still match. Historical suppression names, reasons, and creation timestamps are nonfunctional metadata and may differ from the deliberately neutral public reconstruction. The guard creates and validates a root-only SQLite backup before applying the schema and installing the engine. Empty-state rollback removes only the new schema and engine; it refuses rollback after an incident or engine cursor exists.

The clean-machine initializer and runtime verifier include the incident schema, and the application installer includes the engine. Base activation keeps the original `fetch -> ingest` service unchanged; the separate correlation installer/activator controls `projection -> incident` backfill and scheduling.

## Initial working-system unscheduled migration

The copy-rehearsal checkpoint was published and independently verified at `36631749b3c64d356f45c79088af5760b81f8723`. Under explicit production authorization, the existing timer was paused only after its oneshot settled. The published guard then installed the exact incident schema and engine without invoking either projector or engine.

Postconditions were:

- exactly three installed incident tables, all empty
- zero version-4 projection rows
- zero projection and incident cursors
- zero scheduler references to the incident engine
- all `24207` historical version-3 rows preserved
- root-only validated pre-migration backup retained
- existing timer active/enabled after migration
- one ordinary fetch/ingest cadence advanced by one source file and 81 recent events
- pipeline result successful with zero restarts

The protected SQLite backup is `1912111104` bytes with SHA-256 `b8a2352b5e96cc1007a98cc4062a69e1c1bf4daa2253f2560a88ee87ce195634`. Its identity-bearing live path is intentionally not published.

## Managed-invocation completion

Item 26 completed every managed-invocation gate:

1. exact managed order is canonical projection before incident processing
2. the original fetch/ingest service and failure boundary remain unchanged
3. deterministic success/failure, both cursor lags, counts, duration, and watermarks are emitted and independently verified
4. the service has explicit CPU/memory/time limits, one-cycle locking, and bounded convergence against concurrent ingest
5. copy rehearsal passed backfill, no-op, new input, projection failure, incident failure, disable, and state-preservation cases
6. live invocation used separately published, verified, explicitly authorized inactive-install/backfill/activation gates
7. the first production backfill and three scheduled cadences ended with both cursor lags at zero and zero service restarts

Incident state is now durable production working state. Do not use the destructive empty-state rollback; disable only the correlation schedule and retain state if rollback is needed.

An Ollama caller, deterministic wake policy, compact incident packet, AI-result producer, and result-return schedule remain later milestones.
