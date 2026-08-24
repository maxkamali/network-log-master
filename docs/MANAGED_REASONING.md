# Managed GX10 Reasoning Boundary

## Status

Execution-order item 29 has a repository candidate and passing synthetic tests. It is not installed or scheduled on the working system. Production remains at zero reasoning packets, model versions, prompt versions, runs, and results, and no production inference has run.

The candidate manages exactly this separately disableable chain:

```text
deterministic packet builder -> one bounded local-model invocation
```

It does not modify incident identity/lifecycle, change the existing fetch/ingest or correlation schedules, return results to the collector, or write Grafana state.

## Isolation and bounded execution

`components/gx10/sbin/run-managed-reasoning.py` validates exact hashes for the installed packet builder, caller, model configuration, prompt, and output schema before work. It then takes a single-link mode-`0600` advisory lock owned by the runtime identity.

Each cycle:

1. validates SQLite integrity, foreign keys, reasoning-table presence, run/result consistency, and current reasoning health
2. refuses to continue if any `STARTED` reservation remains after the cycle lock is acquired
3. runs the deterministic packet builder once
4. calls the item-28 reasoning boundary once, which reserves at most one highest-priority pending packet
5. proves that the cycle added at most one run and at most one result
6. emits aggregate health without packet, incident, event, or entity content

Packet construction may append deterministic facts for currently qualifying incidents, but the expensive and untrusted model boundary is limited to one invocation per cycle. The oneshot service has a three-minute timeout, one-CPU quota, 1-GiB memory limit, 32-task limit, low CPU/I/O priority, write access only to the validated database parent, and network policy limited to Unix sockets plus IPv4 loopback. The caller itself still hard-codes the loopback Ollama endpoint and refuses redirects.

## Scheduling

The candidate timer waits 15 minutes after boot and then five minutes after each completed oneshot, with 15-second accuracy. It has no `OnCalendar` catch-up behavior. The reasoning schedule is independent of the existing fetch/ingest and correlation timers and can be disabled without changing deterministic or model-result state.

The service is ordered after the managed correlation service and Ollama, but it does not start or stop either dependency. Private installation binds the actual runtime identity and database parent through a narrowly rendered drop-in. Active verification separately requires the correlation timer and Ollama to be healthy.

## Health and failure behavior

Every completed cycle reports:

- deterministic packets created in that cycle
- whether an inference reservation was made
- total packet count and exact selected-version pending backlog
- model/prompt version counts
- total, `STARTED`, successful, and terminal-failure run counts
- append-only result count
- cycle duration and pass/safe-failure state

An acquired cycle lock makes every preexisting `STARTED` reservation an unreconciled interruption. The runner fails before building another packet or invoking the model. There is no automatic stale-run takeover or hidden retry.

| Failure | Durable effect | Safe response |
|---|---|---|
| Artifact/config/lock/health validation | No stage runs | Correct the boundary and verify again |
| Packet-builder failure | Its transaction rolls back; inference does not run | Correct deterministic state and retry |
| Model unavailable/timeout/transport/invalid response | One explicit terminal run, no result | Keep other schedules active; inspect aggregate health |
| Interruption after reservation | One append-only `STARTED` run | Stop automatic reasoning and reconcile explicitly |
| Managed service/timer failure | Fetch/ingest and correlation remain independent | Disable only reasoning; retain packet/run/result state |
| Activation failure | Reasoning remains disabled and the pre-activation backup is retained | Correct and repeat guarded verification; never restore over newer ingest blindly |

## Installation and activation gates

`components/gx10/install/install-managed-reasoning.py` requires:

- the validated application database, runtime identity, and exact installed item-27/item-28 dependency bytes
- loaded correlation and Ollama dependencies
- safe absolute database and unit names
- absent or exact managed runner/service/timer/configuration/drop-in targets
- inactive and disabled managed reasoning units

It installs only the managed runner, service/timer, private database-path configuration, and runtime-identity/ordering/write-scope drop-in. It runs `systemd-analyze verify` and reloads systemd but does not build packets, call Ollama, or enable the timer.

`components/gx10/install/activate-managed-reasoning.py` is a separate confirmation gate. It verifies the complete installed/inactive boundary, creates and validates a new root-only mode-`0600` SQLite online backup, runs exactly one initial bounded service cycle while the timer is disabled, verifies the post-cycle state, and only then enables the timer. Any error disables/stops only managed reasoning and retains its append-only state plus protected backup.

`components/gx10/install/verify-managed-reasoning.py` verifies exact installed bytes/modes, private configuration and drop-in scope, service/timer state, dependency health, deterministic zero-lag watermarks, SQLite integrity/foreign keys, exact selected-version backlog, run-status counts, zero unreconciled `STARTED` reservations, and the success/result invariant.

## Candidate validation

Nineteen focused tests currently prove:

- strict private database configuration
- exact dependency hashes and file metadata
- one runtime-owned cycle lock
- empty no-op behavior
- exactly one successful or terminal-failure reservation per cycle
- refusal of two-run behavior
- explicit `STARTED` interruption refusal
- aggregate backlog/run/result health
- canonical private config/drop-in rendering
- atomic exact-file reuse and divergence refusal
- protected-backup-first activation order
- activation failure isolation and bounded-cycle enforcement
- separately disableable, hardened, loopback-only service/timer policy

The full GX10 suite currently passes `134` tests. Protected current-production-state-copy rehearsal, unscheduled working-system installation, initial production activation, and multiple scheduled-cadence evidence remain separate gates. Collector result return is outside item 29.

## Exact candidate artifacts

- managed runner SHA-256: `54e81a5204336d7ec6d79ac5372a3a1ba5bff0e4828706e1237faa0a997e03e1`
- installer SHA-256: `75654a09471dc5ecb99672dc16c326af65fbbe83ed44963010da9e9532535fd0`
- activator SHA-256: `04d16e1c3eac68cc04a533bba7571ba5534a2f07af8da566a2f9c725d50b43d3`
- verifier SHA-256: `b80d3de36cdeac1ea268c9c12a1edfe1dce83e248e57eefff99872ec11622708`
- service SHA-256: `3559ed6a5bdfc98de3544bc6bf7f69cf6459a9cb50083cd96db632a27e52e64a`
- timer SHA-256: `0c813a9f8aa695e69e7a383d681b4d5ae9b48abc18879b908bdbb4e5da763e53`

These hashes describe the initial repository candidate. Any correction requires new hashes, a new validated checkpoint, and restaging before protected-copy or production work.
