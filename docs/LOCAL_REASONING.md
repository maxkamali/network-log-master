# Local Reasoning Execution Boundary

## Status

Execution-order item 28 has a published repository candidate and a guarded existing-system migration candidate. The working GX10 system does not contain the item-28 inference schema, caller, prompt/configuration artifacts, run rows, or result rows. No production reasoning packet has been built and no model inference has been invoked by this project.

The candidate consumes only immutable item-27 packets. It cannot change incidents, evidence, transitions, packets, collector state, or Grafana state.

## Selected version set

The initial bounded candidate uses the smallest model in the captured six-manifest local inventory:

- provider: `ollama`
- model reference: `qwen3:8b`
- model version: `ollama-qwen3-8b-500a1f06-v1`
- model manifest SHA-256: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
- model config digest: `sha256:05a61d37b08453e59290add468e3bb2f688e23a01e967fecb0e2fa41218cea76`
- prompt version: `incident-assessment-v1`
- output schema version: `1`

The manifest was revalidated on the working system, with Ollama active/enabled and listening only on loopback. No inference was run. This is a resource-bounded starting selection, not yet an empirical quality claim; synthetic and protected-copy inference gates remain mandatory.

Request options are versioned and deterministic: temperature `0`, seed `27`, context `8192`, and maximum prediction `1024` tokens. The caller sets `stream=false`, disables thinking output, and sends a JSON Schema response format.

Exact repository artifacts:

- inference schema: `components/gx10/sql/inference-v1.sql`
- caller: `components/gx10/sbin/run-local-reasoning.py`
- runtime version configuration: `components/gx10/config/reasoning-runtime-v1.json`
- system prompt: `components/gx10/prompts/incident-assessment-v1.txt`
- output schema: `components/gx10/prompts/incident-assessment-output-v1.json`
- migration guard: `components/gx10/install/migrate-local-reasoning.py`

Candidate SHA-256 values:

- inference schema: `777ee4d63e1e8bcdfaaad973843d02145c45537eecd3b36e51e4a343b002ed61`
- caller: `9fa6a9ae51b8b1c9eeb2d908def6e09f6a7135526d49469ffefffda5e147bf38`
- runtime configuration: `8d4846c6cd2dbde9ee8bc3a7b81d8e0a2f99185f84d476adadfeb273b4121d13`
- system prompt: `8c1fc9ab16bf819ad7884a7c45f65468e0091f7251dba1f285ab4c0859b78262`
- output schema: `b712ad9d76bdc39a023f04cdd9c680703964ae3feab3cddfb09b152a01cf9e06`
- migration guard: `7a41de4f28a5d4e5060cbe2b8cdfb0a96e9cfe160d5e172550b960cdec44862c`

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

Packet and incident IDs must match the immutable input exactly. Enumerations, types, counts, string lengths, tags, action risk, and the 16-KiB result ceiling are independently validated in application code even though the same constraints are supplied to Ollama as JSON Schema. Invalid or oversized output is never stored as a result.

The prompt treats the packet as untrusted data, prohibits invented observations and raw/source content, separates hypotheses from facts, and requires read-only actions before reversible or approval-required changes.

## Local-only transport and safe failure

The endpoint is fixed to `http://127.0.0.1:11434/api/chat`. Redirects are refused. The response is capped at 128 KiB and the request timeout is 120 seconds. No remote endpoint or credential is configurable.

Unavailable, timed-out, transport-error, invalid-response, and invalid-output outcomes become explicit terminal run statuses with bounded canonical diagnostics. They produce no result and do not affect packet or incident truth. An immediate rerun makes no second inference call for that versioned reservation.

## Item-28 gates

1. `DONE` — publish and independently verify the repository candidate
2. `DONE` — add an exact-schema/exact-artifact existing-system migration with protected backup, zero scheduler references, and empty-state-only rollback
3. run synthetic structured-output quality and failure-path evaluation against the loopback local model without production packet data
4. rehearse migration, version registration, one-packet success, interruption, invalid output, unavailable runtime, and deterministic rerun on protected production-state copies
5. install the exact inference schema/caller/configuration/prompt artifacts unscheduled under a new protected backup only after the earlier gates pass
6. do not invoke a production packet or create a reasoning schedule until a separate managed-invocation gate passes
7. keep collector result return outside item 28

The original fetch/ingest and correlation timers remain independent of this candidate.
