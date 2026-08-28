# Managed GX10 Correlation Boundary

## Status

Execution-order item 26 is complete. The published candidate passed private working-database-copy rehearsal, verified inactive working-system installation, fail-closed production activation, full initial backfill, active zero-lag verification, and three independent scheduled zero-lag cadences. The correlation timer is active; the original `timer -> fetch -> ingest` chain remains independently active and unchanged.

The candidate manages only two deterministic stages in this exact order:

```text
canonical projection -> incident engine
```

It does not call Ollama, implement a model wake policy, produce AI results, write to the collector, or alter the existing fetch/ingest unit.

## Isolation and concurrency

Correlation uses a separate oneshot service and monotonic timer. A failure in this service cannot stop or disable the existing fetch/ingest timer. The service has no network address family, no spool write access, and no capabilities. Its private working-system drop-in resets the clean-rebuild write path and grants write access only to the parent directory of the already validated database.

The runner opens a single-link mode-`0600` advisory lock owned by the runtime identity. This prevents overlapping timer/manual correlation cycles. Projection and incident batches retain their existing SQLite `BEGIN IMMEDIATE` transactions and five-second busy timeouts, which serialize them against any concurrent ingest writer.

Because a fetch/ingest cycle may commit new rows between managed stages, the runner rechecks both watermarks after every projection/incident pass. It performs at most three complete ordered passes and succeeds only when:

- projection cursor equals the highest stored recent-event ID
- incident cursor equals the highest classification-version-4 event ID

Continued arrivals that prevent convergence fail the cycle visibly; the next independent timer cycle retries from durable cursors.

## Exact artifacts and execution

`components/gx10/sbin/run-correlation.py` validates the exact canonical-projector and incident-engine hashes before loading them. It injects the already selected database path into both stages explicitly, so stage import cannot silently select a different database.

On a clean public rebuild, the standard protected runtime configuration supplies the fixed public database path. The existing working system uses a separately rendered root-owned `correlation.json` because its historical path is intentionally private. That file permits exactly one absolute `database_path` key, is limited to 4096 bytes, and is not committed.

The service resource boundary is:

- timeout: 10 minutes
- CPU quota: 100 percent
- memory maximum: 1 GiB
- task maximum: 32
- `Nice=5`
- best-effort I/O priority 6
- network families: Unix sockets only
- write scope: validated database parent only

## Telemetry and health

Every successful stage emits its own existing marker. The wrapper then emits one `MANAGED_CORRELATION` line containing:

- pass count and duration
- recent-event maximum, projection cursor, and projection lag
- canonical row count
- incident cursor and incident lag
- total/active incidents
- evidence and transition counts

Success ends with `GX10_MANAGED_CORRELATION=PASS`. Failure includes a UTC timestamp, a bounded generic reason, and `GX10_MANAGED_CORRELATION=FAIL` on standard error.

`components/gx10/install/verify-correlation.py` independently checks installed-source equality, file metadata, unit state, private configuration/drop-in boundaries when applicable, SQLite integrity/foreign keys, exact incident schema objects, both watermarks, active-identity uniqueness, and evidence aggregates.

## Failure behavior

| Failure | Durable effect | Next safe action |
|---|---|---|
| Artifact/hash/config/lock validation | No stage runs | Correct the boundary; retry |
| Canonical projection failure | Its current batch and cursor roll back; incident stage does not run | Retry after correcting canonical input/state |
| Incident failure | Projection may already be durable; incident batch and cursor roll back together | Retry; incident resumes from its cursor |
| Continued concurrent arrivals | Up to three passes run; cycle then fails with lag | Existing fetch/ingest continues; next correlation cycle retries |
| Timer/service failure | Fetch/ingest timer is unaffected | Disable only the correlation timer and inspect evidence |
| Activation/postcheck failure | Correlation timer is disabled; any deterministic state is preserved | Correct and resume; do not restore an old database over new ingest |

## Installation, activation, and disable gates

`install/install-correlation.py` installs exact projector, incident engine, runner, service, timer, private database-path configuration, and a narrowly rendered runtime-identity/ordering/write-scope drop-in. The write-scope override is required when an existing system's validated database is outside the clean-rebuild state root. The installer permits only the exact known inactive pre-write-scope drop-in to be upgraded atomically; every other divergent target remains a hard failure. It refuses unsafe names/paths, incorrect database ownership/mode, missing pipeline unit, pre-enabled correlation state, or unsafe filesystem metadata. Installation does not run a stage or enable a timer.

`install/activate-correlation.py` requires a separate explicit confirmation. It:

1. verifies the complete installed/inactive boundary
2. starts one initial backfill service while the timer is disabled
3. verifies service success and preserved installed boundary
4. enables/starts only the correlation timer
5. requires active verification with zero projection and incident lag

Any activation error disables/stops only correlation and clears the failed unit flag after the durable journal retains the failure reason. Projection/incident state is retained because both stages are replay-safe and fetch/ingest may continue independently.

Disabling correlation stops/disables its timer and stops its oneshot without removing schema, cursors, incident truth, the existing fetch/ingest chain, or the protected item-25 pre-migration backup.

## Production activation evidence

The first production start failed before application execution because the clean-rebuild write path was absent on the historical installation. The fail-closed activator disabled correlation and preserved the unchanged database. A published correction reset the service write scope and allowed only the parent of the already validated database; a second cleanup correction clears stale failed-unit state after journal evidence is retained.

The successful initial backfill ended at event ID `955874` with zero projection and incident lag, `8712` canonical version-4 rows, `23` incidents, `477` evidence rows, `519` transitions, and `3` active incidents. Only after this verification did activation enable the correlation timer.

Three later scheduled gates ended at event IDs `956240`, `956338`, and `956413`. Every gate independently passed SQLite/schema/unit/private-runtime verification with zero projection lag, zero incident lag, and zero service restarts. Counts were monotonic, third-gate state contained `9251` canonical rows, `24` incidents, `508` evidence rows, `551` transitions, and `4` active incidents, and the original fetch/ingest timer advanced during the observation window. A final prepublication verification later reached event ID `956995` with both lags still zero and both timers active.

At item-26 closure, the next gate was deterministic LLM wake selection and
compact incident-packet construction; item 26 itself added no inference or
result-return schedule. Items 27 through 30 later completed the separately
gated packet, inference, result-production, and recurring result-return path.
