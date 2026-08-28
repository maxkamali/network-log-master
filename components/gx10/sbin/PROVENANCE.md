# GX10 Application Source Provenance

## Captured reconstruction baseline

The original three public application files in this directory were captured from the working GX10 reference system after rediscovery closed.

Live SHA-256 checkpoints:

- `fetch-spool.py`: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- `ingest-spool.py`: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- `enrich-events.py`: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

The public copies intentionally do not have those byte hashes because deployment-specific literals were removed and the resulting AST was rendered into neutral public formatting.

The capture changed only configuration binding:

- database, spool, SSH key, and known-hosts paths now come from `runtime_config.py`
- SFTP host, port, and user now come from a protected rendered runtime configuration
- the already-public `/spool/%Y/%m/%d/%H` chroot path contract remains fixed
- public system executable paths for `sftp` and `zstd` remain fixed

At the reconstruction checkpoint, all 27 function ASTs matched the live sources exactly after excluding the Python 3.12-only `type_params` metadata field. The comparison included every fetch, ingest, and transitional deterministic-enrichment function.

The public capture gate also verified that no deployment IPv4 literal or non-public absolute path survived.

The source capture did not execute any application, open the production database, contact SFTP, or write to the reference system.

## Post-cutover canonical projection

After the verified normalized handoff became authoritative on 2026-08-24, item 24 deliberately replaced the repository's transitional vendor/message reparser at the compatibility filename `enrich-events.py` with a schema-version-1 canonical projector.

Repository and active live projection SHA-256:

`f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079`

The original live transitional-enrichment SHA-256 remains the exact rollback identity:

`6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

The projector:

- accepts only the exact normalized schema-version-1 key/type contract
- treats collector-normalized event, entity, protocol, state, signal, repeat, and attribute fields as authoritative
- performs no vendor or message classification
- retains the existing GX10-local enabled suppression-rule overlay
- preserves historical classification-version-3 rows
- writes classification version 4 for canonical projections
- advances an atomic `agent_state` cursor with each projection batch
- is idempotent and fails closed on malformed canonical input or newer projection state
- remains absent from the original automatic `timer -> fetch -> ingest` chain and runs only through the separate item-26 correlation schedule

The candidate was rehearsed twice against an on-server SQLite backup: the first run scanned `949845` events and projected `2781` canonical rows while preserving `24207` historical version-3 rows; the second projected zero rows. All projected fields matched an independent re-read, `1984` rows received the existing local suppression policy, and the live database remained unchanged.

The live unscheduled legacy executable was then replaced under its exact old hash and zero-scheduler-reference precondition. The active legacy hash count is zero, the projection hash count is one, and the protected root-only rollback copy retains the exact legacy hash. The live database still has zero version-4 rows and no projection cursor because retirement did not invoke the projector.

Item 26 later activated the exact projector only through the separate managed correlation boundary after protected-copy and inactive-install gates. That later state does not change the item-24 retirement evidence above.

## Deterministic incident and managed correlation additions

`incident-engine.py` and `run-correlation.py` are deliberate post-rediscovery implementation artifacts. They are not represented as captured historical applications.

The incident engine owns deterministic identity/lifecycle over classification-version-4 rows. The managed runner validates exact projector/engine hashes, enforces a runtime-owned single-cycle lock, invokes projection before incidents, retries bounded complete passes for cursor convergence with concurrent ingestion, and emits explicit watermark/state telemetry. Neither source imports an Ollama client or implements result return.

## Deterministic packets and managed reasoning additions

`build-reasoning-packets.py`, `run-local-reasoning.py`, and `run-managed-reasoning.py` are deliberate post-rediscovery implementation artifacts. They are not represented as captured historical applications.

The packet builder owns deterministic wake selection and compact append-only facts. The local caller binds one immutable packet to exact model/prompt/output versions and records only strict canonical interpretation. The item-29 wrapper validates all stage hashes, holds an independent cycle lock, refuses unreconciled `STARTED` state, runs the packet builder once, permits at most one inference reservation, and emits only aggregate backlog/run/result health. Protected-copy, activation, and scheduled-cadence gates passed; this managed reasoning/triage owner is active.

## Stable outbox snapshot addition

`create-outbox-snapshot.py` and `run-outbox-snapshot.py` are deliberate item-42
reliability artifacts. They are not rediscovered historical applications.

The exact-hash runner binds private source/snapshot paths through a root-owned
configuration and invokes only the local snapshot producer. The producer opens
the validated service-owned WAL source in one read transaction, validates its
integrity, copies only the ten tables used by result/lifecycle projection,
validates the copied schema and terminal-state invariants, and publishes the
rollback-journal projection atomically. It cannot open a network socket, make
incident/model decisions, copy raw-event bulk, or alter result/lifecycle
records. Production activation passed; the active outbox reads the resulting
selective rollback-journal projection rather than the mutable source database.

## Current application artifact matrix

| Artifact group | Origin | Installer/verifier owner | Active boundary | Rollback behavior |
| --- | --- | --- | --- | --- |
| fetch and replay-safe ingest | captured | base installer/runtime verifier | base fetch/ingest timer | preserve processed state; repair only on a clean host |
| canonical projection and incidents | reconstructed | correlation installer/verifier | correlation timer | disable timer and retain working state |
| packets, reasoning, and hidden triage | reconstructed | managed-reasoning installer/verifier | reasoning timer | disable timer and retain append-only packet/run truth |
| selective snapshot and result/lifecycle outbox | reconstructed | snapshot/outbox installers and verifiers | snapshot before outbox timer | disable extension; retain snapshot, files, and cursors |
| write-only result sender | reconstructed | sender installer/configurator/verifier | sender timer | disable timer; retain ready/delivered files and collector evidence |

`run-managed-ai.py` coordinates the active reasoning/triage policy;
`build-result-outbox.py` and `build-incident-outbox.py` are the two local
producers; `send-result-outbox.py` performs only bounded transport. Exact
commands and markers are in `CLEAN_MACHINE_RUNBOOK.md`.
