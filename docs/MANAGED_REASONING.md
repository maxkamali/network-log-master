# Managed GX10 Reasoning Boundary

## Status

Execution-order item 29 has passed protected-copy, inactive-install/correction, and protected initial-activation gates. Two natural cadences each completed exactly one successful inference, but each also built four new packets; pending backlog grew from three to six to nine. This failed the stability gate, and the reasoning timer was disabled with all append-only state preserved. The published 138-test bounded-backlog candidate defers packet construction whenever any selected-version packet is pending and requires the one allowed inference attempt to reduce pending count by exactly one. It passed a protected current-production-state-copy real-model drain with deterministic truth unchanged. Fetch/ingest, deterministic correlation, and Ollama remain healthy while the correction awaits exact inactive installation.

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
3. runs the deterministic packet builder once only when the exact selected-version pending backlog is empty; otherwise reports explicit builder deferral
4. calls the item-28 reasoning boundary once, which reserves at most one highest-priority pending packet
5. proves that the cycle added at most one run and at most one result
6. when backlog existed at cycle start, proves packet count did not grow and pending count fell by exactly one reservation
7. emits aggregate health without packet, incident, event, or entity content

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
- absent or exact managed runner/service/timer/configuration/drop-in targets; the timer may also be the exact published inactive boot-relative predecessor, and the runner may be the exact published pre-backlog-correction version, for atomic upgrade only
- inactive and disabled managed reasoning units

It installs only the managed runner, service/timer, private database-path configuration, and runtime-identity/ordering/write-scope drop-in. It runs `systemd-analyze verify` and reloads systemd but does not build packets, call Ollama, or enable the timer.

`components/gx10/install/activate-managed-reasoning.py` is a separate confirmation gate. It verifies the complete installed/inactive boundary, creates and validates a new root-only mode-`0600` SQLite online backup, runs exactly one initial bounded service cycle while the timer is disabled, verifies the post-cycle state, and only then enables the timer. Any error disables/stops only managed reasoning and retains its append-only state plus protected backup.

`components/gx10/install/verify-managed-reasoning.py` verifies exact installed bytes/modes, private configuration and drop-in scope, service/timer state, dependency health, deterministic zero-lag watermarks, SQLite integrity/foreign keys, exact selected-version backlog, run-status counts, zero unreconciled `STARTED` reservations, and the success/result invariant.

## Candidate validation

Twenty-three focused tests currently prove:

- strict private database configuration
- exact dependency hashes and file metadata
- one runtime-owned cycle lock
- empty no-op behavior
- exactly one successful or terminal-failure reservation per cycle
- refusal of two-run behavior
- explicit `STARTED` interruption refusal
- aggregate backlog/run/result health
- pending-backlog builder deferral and exact one-reservation drain
- canonical private config/drop-in rendering
- atomic exact-file reuse and divergence refusal
- exact-old-hash timer upgrade and divergent-old refusal
- exact-old-hash runner upgrade and divergent-old refusal
- protected-backup-first activation order
- activation failure isolation and bounded-cycle enforcement
- separately disableable, hardened, loopback-only service/timer policy
- explicit private-rehearsal transport forwarding without changing the production CLI path

The full GX10 suite currently passes `138` tests. Protected current-production-state-copy rehearsal, unscheduled working-system installation, the exact inactive timer correction, protected initial production activation, and the bounded-backlog correction's current-state-copy rehearsal have passed. The first two natural cadences passed per-cycle inference safety but failed bounded-backlog stability. The corrected runner must be installed while disabled and pass new production drain cadences. Collector result return is outside item 29.

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

The correction was published at `abbaa53ad50f00d7728379b602bd064c38d4b009`, independently matched on GitHub, staged exactly on GX10, and passed all 136 tests there after repository-mode normalization. The installer accepted only the exact inactive predecessor and atomically upgraded it. Post-upgrade verification proved the corrected timer still disabled/inactive, the service inactive, zero restarts, zero reasoning rows of every type, caught-up deterministic watermarks, healthy dependencies, and no production inference.

## Protected initial production activation

The first activation attempt failed closed before backup creation or service execution because ordinary incoming input created transient deterministic lag during the pre-stop observation. The private orchestration wrapper was narrowed to accept that read-only pre-stop lag while still requiring empty reasoning state, then require exact catch-up after pausing only the fetch/ingest timer. The published activator itself did not change.

The corrected attempt paused the fetch/ingest timer, waited for its oneshot to settle, ran deterministic correlation to zero lag, and created a new root-only mode-`0600` SQLite online backup. With the reasoning timer still disabled, exactly one managed cycle built four packets and completed one successful inference/result, leaving three pending. The activator verified zero failures and zero `STARTED` reservations before enabling the corrected timer. It then restored the fetch/ingest timer; the correlation and Ollama dependencies remained healthy.

```text
recent_max_id=966859
projection_lag=0
incident_lag=0
reasoning_packets=4
reasoning_pending=3
reasoning_model_versions=1
reasoning_prompt_versions=1
reasoning_runs=1
reasoning_succeeded=1
reasoning_failures=0
reasoning_results=1
reasoning_started=0
protected_backup_bytes=1951907840
protected_backup_sha256=7153ffb3ee9677c1c2c397638e8d22530bd01b6cfc9cad9deee8e763c2993d6d
protected_backup_mode=0600
pipeline_timer_resumed=yes
correlation_timer_active=yes
managed_reasoning_timer_active=yes
managed_reasoning_restarts=0
collector_result_return_enabled=no
GX10_MANAGED_REASONING_INITIAL_ACTIVATION=PASS
```

The protected backup path and all packet/result content remain private.

## Natural-cadence backlog failure and safe disable

The first natural cadence reached event ID `967397`, created four new packets, completed exactly one additional successful run/result, and left six pending. The second reached event ID `967860`, again created four packets and completed exactly one run/result, leaving nine pending. Both cadences retained zero deterministic lag, failures, `STARTED` reservations, or restarts, and all independent timers were healthy.

Because packet arrival exceeded bounded inference throughput in two consecutive natural cadences, item 29 did not pass stability. Only the managed reasoning timer was disabled and stopped. A later verifier at event ID `967946` proved 12 packets, nine pending, three successful runs/results, zero failures/`STARTED` rows/restarts, disabled/inactive reasoning units, zero deterministic lag, and healthy fetch/ingest plus correlation schedules. No state was deleted or rewritten.

The correction defers the deterministic builder whenever any selected-version packet is pending. The cycle still validates the exact builder bytes, but it spends its single model reservation on existing backlog and fails unless packet count stays fixed and pending falls by exactly one. Only pending-zero cycles may build current latest-state packets, coalescing all intervening incident changes into the next deterministic packet per qualifying incident rather than admitting another set during every drain cycle.

The installer permits an atomic runner replacement only when the installed predecessor has exact SHA-256 `f79ed272a8638449bc6a98aefa1758e711a69645950c284869d96e03704432ca` and exact root ownership/mode. Any later install failure restores the captured exact predecessor. Existing packets/runs/results are not rewritten.

Only exact artifacts from published commit `03ac9a1ac37881b8dfb6c6d24313105e71ae6ae4` were staged on GX10. All 138 tests and the filesystem contract passed there after exact Git-mode normalization. A fresh caught-up protected copy of disabled production state then ran one real-model cycle through the corrected wrapper:

```text
snapshot_recent_max_id=968602
snapshot_projection_lag=0
snapshot_incident_lag=0
copy_packets_before=12
copy_packets_after=12
copy_pending_before=9
copy_pending_after=8
copy_runs_before=3
copy_runs_after=4
copy_results_before=3
copy_results_after=4
copy_builder_deferred=yes
copy_model_invocations=1
copy_failures=0
copy_started=0
copy_deterministic_truth_unchanged=yes
copy_state_sha256=e89219c90be5e8e19fefcec3488a0606ffe6f7caa265635b060be2b2f11d2f93
protected_base_bytes=1956794368
protected_base_sha256=61374f13609eef5c225fc6467e17800e46c6dd59061d5efeefa7b314fadf04e7
protected_base_mode=0600
working_packets=12
working_pending=9
working_runs=3
working_results=3
working_reasoning_timer_enabled=no
working_production_inference_invoked=no
GX10_MANAGED_REASONING_BACKLOG_COPY_REHEARSAL=PASS
```

The protected copy paths and all packet/result content remain private. Production was not invoked or changed.

## Exact candidate artifacts

- managed runner SHA-256: `c0c095661a7042be57230fb8fc856c03f5fe191ab604e4e246138f28156a3bee`
- installer SHA-256: `f1f1cbc1dbe079c6e0ee8a1b67b54abd3d677199fbff43e5b633e5b8e8aec5e8`
- activator SHA-256: `04d16e1c3eac68cc04a533bba7571ba5534a2f07af8da566a2f9c725d50b43d3`
- verifier SHA-256: `b80d3de36cdeac1ea268c9c12a1edfe1dce83e248e57eefff99872ec11622708`
- service SHA-256: `3559ed6a5bdfc98de3544bc6bf7f69cf6459a9cb50083cd96db632a27e52e64a`
- timer SHA-256: `c284e9d8cbb71775dc6b67b7451bb024d689b4ec27b89de987443a6ff77cad34`

These hashes describe the bounded-backlog candidate. The activator, verifier, service, and corrected timer are byte-identical to the activation candidate; only the runner and installer changed. The working system still has the exact predecessor runner and corrected timer installed inactive.
