# Managed GX10 Reasoning Boundary

## Status

Execution-order item 29 has a published repository candidate, passing synthetic tests, passing protected current-production-state-copy rehearsal, and exact inactive working-system installation. The runner/service/timer/private binding is installed, but the timer is disabled and the service is inactive. A final pre-activation review caught that the initial boot-relative timer could fire immediately when enabled on a long-running host. Activation was not attempted. The corrected candidate uses a start-relative initial delay and an exact-old-hash inactive upgrade. Production remains at zero reasoning packets, model versions, prompt versions, runs, and results, and no production inference has run.

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

The corrected candidate timer waits five minutes after it is enabled and then five minutes after each completed oneshot, with 15-second accuracy. It has no boot-relative or `OnCalendar` catch-up trigger, so enabling it on a long-running host cannot cause an immediate unreviewed second inference after the activator's one bounded initial cycle. The reasoning schedule is independent of the existing fetch/ingest and correlation timers and can be disabled without changing deterministic or model-result state.

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
- absent or exact managed runner/service/timer/configuration/drop-in targets; the timer alone may also be the exact published inactive boot-relative predecessor and is then atomically upgraded
- inactive and disabled managed reasoning units

It installs only the managed runner, service/timer, private database-path configuration, and runtime-identity/ordering/write-scope drop-in. It runs `systemd-analyze verify` and reloads systemd but does not build packets, call Ollama, or enable the timer.

`components/gx10/install/activate-managed-reasoning.py` is a separate confirmation gate. It verifies the complete installed/inactive boundary, creates and validates a new root-only mode-`0600` SQLite online backup, runs exactly one initial bounded service cycle while the timer is disabled, verifies the post-cycle state, and only then enables the timer. Any error disables/stops only managed reasoning and retains its append-only state plus protected backup.

`components/gx10/install/verify-managed-reasoning.py` verifies exact installed bytes/modes, private configuration and drop-in scope, service/timer state, dependency health, deterministic zero-lag watermarks, SQLite integrity/foreign keys, exact selected-version backlog, run-status counts, zero unreconciled `STARTED` reservations, and the success/result invariant.

## Candidate validation

Twenty-one focused tests currently prove:

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
- exact-old-hash timer upgrade and divergent-old refusal
- protected-backup-first activation order
- activation failure isolation and bounded-cycle enforcement
- separately disableable, hardened, loopback-only service/timer policy
- explicit private-rehearsal transport forwarding without changing the production CLI path

The full GX10 suite currently passes `136` tests. Protected current-production-state-copy rehearsal and unscheduled working-system installation have passed. The corrected timer checkpoint, exact inactive timer upgrade, initial production activation, and multiple scheduled-cadence evidence remain separate gates. Collector result return is outside item 29.

## Protected current-state-copy evidence

Only exact artifacts from published commit `ba9383f91ed1f5dcdff989eabe11627883b28488` were staged under a root-only boundary. The 135-test suite passed again on GX10. A SQLite online backup captured caught-up production deterministic state while both existing production timers remained active:

```text
snapshot_incidents=71
snapshot_active=4
snapshot_evidence=1114
snapshot_transitions=1244
```

Four isolated clones exercised the complete managed boundary:

- the exact runner built four sanitized packets and completed one real loopback Gemma inference with one canonical result
- a controlled invalid response produced one explicit terminal safe failure and no result
- a controlled interruption left one `STARTED` reservation; the next locked cycle refused it before transport and changed no state
- a success clone with reviewed synthetic terminal reservations for its remaining backlog produced a true no-op with zero transport calls and unchanged counts

The independent item-29 database verifier passed the success clone. Every clone preserved the same incident/evidence/transition/cursor digest as the base copy.

```text
copy_packets=4
copy_success_runs=1
copy_success_results=1
copy_pending_after_success=3
copy_safe_failures=1
copy_interrupted_started=1
copy_interrupted_retry_invoked=0
copy_noop_filled_pending=3
copy_noop_invoked=0
copy_independent_verifier=pass
copy_deterministic_truth_unchanged=yes
copy_state_sha256=0b8a0bc06a752350aa19ec77febab4c5547115aac3410c78d1f5b4e0581e40d3
GX10_MANAGED_REASONING_COPY_REHEARSAL=PASS
```

The protected base copy is mode `0600`, `1947361280` bytes, and SHA-256 `b5583c0ece49dea857afde03b98112d901b88be24ce5b060e79dd5fd36856d85`. Its path and all packet/result content remain private.

The final working-system check reached recent event ID `965309` with zero projection and incident lag, zero packet/model/prompt/run/result rows, both production timers active, and no production inference.

## Inactive working-system installation

Only the exact published runner/service/timer plus a narrowly rendered private database/runtime binding were installed. The installer revalidated all installed item-27/item-28 dependency bytes and database ownership/schema, ran real on-host `systemd-analyze verify`, reloaded systemd, and proved the new timer disabled and both new units inactive. It did not write the database or invoke either stage.

The immediate post-install database check raced with an ordinary incoming batch and observed temporary deterministic lag after all files had safely installed. No reasoning state existed. The existing correlation cadence caught up normally; a separate later check then passed the complete exact-source/private-binding/unit/database verifier:

```text
recent_max_id=965682
projection_lag=0
incident_lag=0
reasoning_packets=0
reasoning_model_versions=0
reasoning_prompt_versions=0
reasoning_runs=0
reasoning_results=0
managed_reasoning_timer_enabled=no
managed_reasoning_service_invocations=0
managed_reasoning_restarts=0
production_dependencies_active=yes
production_inference_invoked=no
GX10_MANAGED_REASONING_INACTIVE_INSTALL=PASS
```

Before activation, review found that the installed `OnBootSec` timer could become immediately due when enabled on this long-running host. No activator, backup, packet builder, model call, or reasoning unit was invoked. The timer remains disabled, the service remains inactive, and all reasoning tables remain empty. The corrected candidate replaces that boot-relative trigger with `OnActiveSec=5min` and permits only an exact-byte inactive upgrade of the published predecessor, with rollback if any later installation check fails.

The corrected timer must be published, independently verified, and upgraded while still inactive before the protected pre-activation backup, one bounded initial production cycle, timer enablement, and scheduled-cadence gates.

## Exact candidate artifacts

- managed runner SHA-256: `f79ed272a8638449bc6a98aefa1758e711a69645950c284869d96e03704432ca`
- installer SHA-256: `6c8ee52f8a7247275b1812129dc97bbd49c71cf741b5973153ed6391fabf90ba`
- activator SHA-256: `04d16e1c3eac68cc04a533bba7571ba5534a2f07af8da566a2f9c725d50b43d3`
- verifier SHA-256: `b80d3de36cdeac1ea268c9c12a1edfe1dce83e248e57eefff99872ec11622708`
- service SHA-256: `3559ed6a5bdfc98de3544bc6bf7f69cf6459a9cb50083cd96db632a27e52e64a`
- timer SHA-256: `c284e9d8cbb71775dc6b67b7451bb024d689b4ec27b89de987443a6ff77cad34`

These hashes describe the corrected pre-activation candidate. The runner, activator, verifier, and service are byte-identical to the protected-copy candidate; only the installer and timer changed. The exact corrected checkpoint must be staged and the old inactive timer upgraded before activation.
