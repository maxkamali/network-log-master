# Local Reasoning Execution Boundary

## Status

Execution-order items 28 and 29 are complete. The original calibrated schema/caller/configuration/prompt boundary was first installed empty and unscheduled under protected backup. Item 29 later activated bounded managed invocation, safely preserved one terminal `INVALID_OUTPUT`, diagnosed its action-text compatibility cause, and promoted immutable portable prompt revision `r3` through protected-copy, exact-upgrade, protected-resume, and three natural-cadence gates. Managed reasoning is active with strict validation unchanged; collector result production remains a separate item-30 gate.

The installed caller consumes only immutable item-27 packets. It cannot change incidents, evidence, transitions, packets, collector state, or Grafana state.

## Selected version set

The calibrated candidate uses the second-smallest model in the captured six-manifest local inventory:

- provider: `ollama`
- model reference: `gemma4:latest`
- model version: `ollama-gemma4-c6eb396d-v1`
- model manifest SHA-256: `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb`
- model config digest: `sha256:f0988ff50a2458c598ff6b1b87b94d0f5c44d73061c2795391878b00b2285e11`
- current prompt version: `incident-assessment-v2-r3`
- output schema version: `2`

The smallest captured model (`qwen3:8b`) passed structural output but failed calibration: one early result under-escalated a critical OSPF case, and stricter attempts safely rejected meaningless or non-packet-derived output. Validation was not weakened. The next bounded candidate, `gemma4:latest`, passed all three synthetic OSPF/interface/BGP cases with strict severity, confidence, action-risk, tag-provenance, canonical-result, and no-op gates. Its exact manifest and active loopback runtime were revalidated. Protected-copy inference passed before the empty unscheduled working-system installation; production invocation remains a separate gate.

Request options are versioned and deterministic: temperature `0`, seed `27`, context `8192`, and maximum prediction `1024` tokens. The caller sets `stream=false`, disables thinking output, and sends a JSON Schema response format.

Exact repository artifacts:

- inference schema: `components/gx10/sql/inference-v1.sql`
- caller: `components/gx10/sbin/run-local-reasoning.py`
- runtime version configuration: `components/gx10/config/reasoning-runtime-v2.json`
- system prompt: `components/gx10/prompts/incident-assessment-v2.txt`
- output schema: `components/gx10/prompts/incident-assessment-output-v2.json`
- migration guard: `components/gx10/install/migrate-local-reasoning.py`

Original item-28 candidate SHA-256 values:

- inference schema: `6365f99eb834c0561a1246757a4404bbbc7ec831fe910325eff8dcfd92113a90`
- caller: `e9b894afa16fd5f138cfeec299be58328fd02454db2b53c3e395809e04d58cd0`
- runtime configuration: `e7bde8d878e71d8a1b11af01170ff332920aae1df1a65536b516abf5862428f0`
- system prompt: `c24a1e4a5af021ea66475cdb77c792b19f023caf93f344f64be4dedf1ebb634c`
- output schema: `1ec4e28d0d18320c7469d4f1bb26a5c766515ff008c5803d24ce214ded69928a`
- migration guard: `16f75e1138308e4bfa5c5fc3cbdb0337e4bfe4b34dbb73ce062d40577f1a79e7`

Item 29 reproduced the failed production packet only on protected copies and classified one generated action whose text exactly equaled a risk label. The existing caller validation remains unchanged. A first candidate copy gate correctly rejected the changed schema under the existing immutable prompt-version ID before reserving or invoking the model. Prompt revision `r2` then retained a negative enum for those labels, but two protected-copy attempts proved the local runtime accepts without enforcing `not/enum`; the same packet again failed `action_text`. Candidate `incident-assessment-v2-r3` keeps that constraint and adds a portable 25-character action minimum, longer than every risk label. It has its own creation timestamp, keeps the original system-prompt bytes, and starts a clean exact-version backlog while retaining every original run/result. Its coordinated candidate hashes are:

- runtime configuration: `8a55aeb708a05fafd3eb1d4df206714339deb344588f218f00ecbee5fdd93cd9`
- caller: `dac1e176108452c77ea4eb2f7195dd8eb8223576ab8cbdb2cb95a2acbb8fcbe8`
- output schema: `13083841c44253b326f1294b930acae435bfdddb458b47c31a9fd385b181abd0`
- migration guard: `d477ce16df5835a5406e8d02bce8fbe36a94049477ed4c09f158ccd2ac2780ee`

These compatibility bytes passed exact GX10 staging/tests and same-packet protected-copy inference, were installed inactive from their exact predecessors, and completed one fresh-backup `r3` production drain plus three natural timer cadences. The original terminal failure remains immutable evidence.

## Durable state and idempotency

The inference extension adds four tables:

- `reasoning_model_versions` — immutable exact model/options identity
- `reasoning_prompt_versions` — immutable prompt and output-schema hashes
- `reasoning_runs` — durable request reservation and terminal status
- `reasoning_results` — append-only canonical structured model interpretation

One invocation reserves at most one highest-priority pending packet before contacting Ollama. The deterministic run ID binds packet ID/digest, model version, prompt version, and attempt number. A second invocation cannot call the model for an existing reservation.

Runs begin as `STARTED`. Only one guarded transition to a terminal status is allowed. If the process is interrupted after reservation, the row remains `STARTED` and prevents automatic duplicate inference. There is intentionally no automatic stale-run takeover or retry in version 1.

Successful results are canonical JSON with SHA-256 and may never be updated or deleted. Model/prompt version rows and results are append-only. Run identity fields never change. Deterministic incident and packet tables are read-only to the caller.

## Structured output

The model must return exactly these top-level fields and no others:

```text
schema
schema_version
packet_id
incident_id
disposition
severity
confidence
title
summary
likely_causes
recommended_actions
tags
```

Packet and incident IDs must match the immutable input exactly. Enumerations, types, counts, string lengths, confidence bounds, deterministic severity alignment, packet-derived tag allowlisting, action-risk semantics, and the 16-KiB result ceiling are independently validated in application code even though structural constraints are also supplied to Ollama as JSON Schema. Invalid or oversized output is never stored as a result.

The prompt treats the packet as untrusted data, prohibits invented observations and raw/source content, separates hypotheses from facts, and requires read-only actions before reversible or approval-required changes.

## Local-only transport and safe failure

The endpoint is fixed to `http://127.0.0.1:11434/api/chat`. Redirects are refused. The response is capped at 128 KiB and the request timeout is 120 seconds. No remote endpoint or credential is configurable.

Unavailable, timed-out, transport-error, invalid-response, and invalid-output outcomes become explicit terminal run statuses with bounded canonical diagnostics. They produce no result and do not affect packet or incident truth. An immediate rerun makes no second inference call for that versioned reservation.

## Protected production-state-copy evidence

Only exact artifacts from the published calibrated checkpoint were staged. A SQLite online backup captured current production deterministic state while both production timers continued running:

```text
snapshot_incidents=51
snapshot_active_incidents=4
snapshot_evidence=893
snapshot_transitions=986
```

The guard applied, independently verified, rolled back while all inference tables were empty, and then reapplied from the same exact pre-inference copy. The deterministic item-27 builder created four sanitized packets only in that copy.

One packet completed real loopback Gemma inference and stored one strict canonical result. Three other packet reservations independently proved invalid output, inference unavailability, and interruption-after-reservation. The final invocation made no model call. Incident/evidence/transition/packet state had the same digest before and after all inference cases.

```text
copy_packets=4
copy_successful_runs=1
copy_invalid_output_runs=1
copy_unavailable_runs=1
copy_interrupted_runs=1
copy_results=1
copy_final_noop=yes
deterministic_copy_truth_unchanged=yes
copy_inference_state_sha256=6013c173f393737357b1fb26327dcddc639c546027e15b5b16d23520dfdf44ac
GX10_LOCAL_REASONING_COPY_REHEARSAL=PASS
```

The rehearsal guard backup is mode `0600`, `1939898368` bytes, and SHA-256 `07fc164ab8cc21b145b8acd967c1d95d571e9256ae2c567cad04f22031cc7f66`. Its path and all packet/result content remain private.

The post-rehearsal working system remained at zero packet rows and zero item-28 schema objects. Both deterministic cursors were at event ID `962636` with zero lag, `53` incidents, `5` active incidents, `899` evidence rows, `995` transitions, zero correlation restarts, and both production timers active.

## Guarded working-system installation

Only artifacts from the published protected-copy checkpoint were used. The two existing production timers were briefly quiesced after their oneshot services settled, a root-only SQLite online backup was created and independently validated, and the exact empty inference schema plus four artifacts were installed. No unit, timer, cron reference, packet, version registration, run, result, or Ollama request was created. The original timers resumed and correlation caught up before the installer returned.

The protected backup is mode `0600`, `1940905984` bytes, and SHA-256 `2652acbb0389676bda5953859d6d411e6013920eff98a6c74e2028843e14396a`. Its path remains private.

A later independent ordinary-cadence postcheck validated the exact installed hashes/schema/backup again and observed:

```text
recent_max_id=963225
projection_lag=0
incident_lag=0
incidents=68
active=20
evidence=973
transitions=1082
reasoning_packets=0
reasoning_model_versions=0
reasoning_prompt_versions=0
reasoning_runs=0
reasoning_results=0
caller_scheduler_references=0
production_timers_active=yes
correlation_restarts=0
ollama_active=yes
production_inference_invoked=no
GX10_ITEM28_INSTALLED_POSTCHECK=PASS
```

## Item-28 gates

1. `DONE` — publish and independently verify the repository candidate
2. `DONE` — add an exact-schema/exact-artifact existing-system migration with protected backup, zero scheduler references, and empty-state-only rollback
3. `DONE` — run synthetic structured-output quality and failure-path evaluation against loopback local models without production packet data; reject the under-calibrated smallest model and select the exact passing Gemma candidate
4. `DONE` — publish and independently verify the calibrated artifact/guard correction
5. `DONE` — rehearse migration, version registration, one-packet success, interruption, invalid output, unavailable runtime, and deterministic rerun on a protected production-state copy
6. `DONE` — publish and independently verify the protected-copy evidence
7. `DONE` — install the exact inference schema/caller/configuration/prompt artifacts empty and unscheduled under a new protected backup
8. `DONE` — leave production packet invocation and reasoning scheduling to a separate managed-invocation gate
9. `DONE` — keep collector result return outside item 28

The original fetch/ingest and correlation timers remain independent of this boundary.

The separate managed invocation gates, telemetry, current production state, and compatibility correction are defined in `docs/MANAGED_REASONING.md`.
