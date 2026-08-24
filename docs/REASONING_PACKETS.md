# Deterministic Wake Policy and Incident Packets

## Status and authority boundary

Execution-order item 27 has a repository-only candidate including a guarded existing-system migration. The schema, builder, migration guard, and synthetic tests pass; no reasoning schema or packet-builder artifact is installed on the working GX10 system, no packet has been built from production state, and no service or timer invokes the builder.

The candidate converts deterministic incident state into an append-only queue of compact reasoning packets. It does not call Ollama, select a model, define a prompt, accept model output, write to the collector, or alter incident identity/lifecycle truth.

## Deterministic wake policy

Policy version 1 evaluates only incident rows plus their append-only evidence and transitions. Reasons have a fixed priority:

| Priority | Reason | Deterministic condition |
|---:|---|---|
| 100 | `critical_condition` | New evidence exists while strongest incident severity is critical or higher; five-minute event-time cooldown unless an open/reopen transition also occurred |
| 95 | `incident_reopened` | New transition to `OPEN` with reason `adverse_relapse` |
| 90 | `incident_opened` | Any other new transition to `OPEN` |
| 85 | `interface_flap` | Interface incident state-change count advanced beyond the prior packet basis |
| 80 | `ospf_retransmission` | New OSPF/OSPFv3 degradation evidence has state `retransmissions`; fifteen-minute event-time cooldown unless an open/reopen transition also occurred |
| 65 | `incident_recovering` | New transition to `RECOVERING` |
| 60 | `incident_resolved` | New transition to `RESOLVED` after a prior packet exists |
| 40 | `meaningful_update` | Active incident accumulates at least 5 evidence rows, 10 canonical repeats, or 15 minutes of new event-time since its prior packet |

All simultaneous reasons are retained in priority/name order. The highest is the primary reason. Cooldowns use durable evidence event-time, never wall-clock invocation time.

An already resolved incident with no prior packet is not backfilled. A candidate wakes only for an independently qualifying critical or OSPF retransmission condition. This prevents first deployment from manufacturing reasoning work for every historical or short-lived candidate.

## Packet identity and replay

Packet identity is a SHA-256-derived value over:

- contract label
- policy version
- packet version
- deterministic incident ID
- highest included evidence sequence
- highest included transition sequence

The database also enforces a unique constraint across the same incident/version/basis tuple. Normal rerun, delayed retry, or incident-cursor reset therefore cannot create a duplicate packet.

`reasoning_packets` is append-only. Update/delete triggers prevent a later inference stage from rewriting why a packet was created. Every row stores canonical JSON and its SHA-256; the builder revalidates all existing packet JSON, reasons, versions, priority, identity, and digest before adding anything.

## Compact packet contract

Packet version 1 contains only deterministic facts:

- packet/policy versions, ID, deterministic creation event-time
- ordered wake reasons and priority
- incident identity, status, entity/protocol/family, severity, lifecycle times, repeat/state-change aggregates, and exact rolling context
- deltas since the prior packet basis
- up to 8 newest evidence records since the prior packet
- up to 8 newest lifecycle transitions since the prior packet
- explicit omitted-row counts when a delta exceeds those slices

Raw messages and source-file identities are excluded. Attribute keys for message/raw-message/event JSON and local/remote/source paths are recursively removed; the packet records the removed-key count and original canonical attribute digest. Remaining evidence attributes are included only when their canonical JSON is at most 2048 bytes; larger attributes are represented by byte count and SHA-256. Any other individual text value over 1024 UTF-8 bytes becomes a bounded prefix plus byte count and SHA-256. The complete canonical packet may not exceed 32 KiB.

## Transaction and failure behavior

One `BEGIN IMMEDIATE` transaction validates incident/evidence aggregates and inserts all newly eligible packets. Schema drift, malformed/noncanonical incident context or attributes, existing-packet tamper, aggregate mismatch, integrity failure, or size overflow rolls back the entire invocation.

No cursor is required: append-only sequence bases and unique deterministic packet identities are the replay boundary. Evidence that does not yet meet a wake threshold accumulates relative to the last packet and remains eligible for a later meaningful-update decision.

## Repository artifacts

- schema: `components/gx10/sql/reasoning-v1.sql`
- packet builder: `components/gx10/sbin/build-reasoning-packets.py`
- existing-system migration guard: `components/gx10/install/migrate-reasoning-packets.py`
- synthetic contract: `components/gx10/tests/test_reasoning_packets.py`

Candidate SHA-256 values:

- schema: `bd46f4a51301c225e051aa6b5e27406ad06c651271d7c82fb3b67ac2b21def90`
- builder: `3543ca1dd5b661c628fbef6e0101c79d0bc236997d229ce354ba9dc618fc8145`
- migration guard: `72e425981cb028edc709186688ff40dbd4bc19d9d22b7c11e2f5e5b3644c49fe`

The clean-machine initializer/installer/verifier include the candidate, but base and correlation activation still do not schedule it.

## Remaining item-27 gates

1. publish and independently verify this repository candidate
2. `DONE` — add a guarded existing-system schema/artifact migration with protected backup and no scheduler reference
3. rehearse schema migration, first packet build, no-op, new qualifying/nonqualifying evidence, lifecycle packets, tamper failure, and deterministic independent reproduction on protected production-state copies
4. install schema/builder unscheduled only after exact published artifacts and copy gates pass
5. do not schedule packet construction or inference until a later explicit managed-invocation gate

Model selection, prompt versioning, structured output, inference failure handling, and collector result return remain separate later items.
