# Roadmap

The project advances through deterministic, validated gates. `docs/CURRENT_STATE.md` is the authority for the exact current execution order and contains one `NEXT` only while work remains; a completed state has none. This roadmap describes the broader milestone sequence.

## Milestone 1 - Deterministic normalizer consolidation

Status: `DONE`

Completed:

- consolidated active normalizer development into `components/normalizer/`
- preserved standalone repository history during import
- implemented and tested selected EOS, IOS XR, NX-OS ETHPORT, OSPF, and OSPFv3 normalization
- established trusted private platform-resolution boundary
- completed selected stored-observation replay/parity
- preserved unknown/unmapped capture-first behavior
- reached 73 passing tests

Exit gate completed: replay/parity finished with 21 strict matches, 3 intentional OSPFv3 differences, and 0 unexpected differences.

The later production cutover completed under Milestone 5 without changing this historical replay/parity result.

## Milestone 2 - Collector rebuild package

Status: `DONE` for the public rebuild package and documentation; clean-machine end-to-end validation was unavailable and explicitly waived by the operator with residual risk retained.

Goal: reconstruct the working collector from public artifacts plus operator-supplied environment values.

Completed capture includes:

- package versions and package verification
- configuration rendering
- Vector ingest, transforms, ClickHouse sinks, AI-result ingestion, and GX10 spool output
- ClickHouse schema, users, grants, and settings profile
- Grafana ClickHouse datasources
- Grafana HTTPS/TLS behavior
- Certbot renewal behavior
- SFTP/chroot transport, ACLs, and bind mounts
- AI-result validation gate
- spool retention
- independent collector runtime verification
- Grafana 13 dashboard resource capture
- proven API-based dashboard restoration and verification tooling
- secure Grafana administrator bootstrap wiring with loopback-only first start and stdin password reset
- dashboard restore/verification wiring in the clean-machine runtime installer
- package-install no-autostart protection with synthetic systemd behavior proof

The installer structural, credential-exposure, public-safety, operator-documentation, and final sanitation gates are complete. Clean-machine collector rebuild validation remains empirically unverified.

Exit gate: another engineer/AI can reconstruct the current collector on a clean server from the repository plus operator-supplied environment values without undocumented implementation memory.

## Milestone 3 - GX10 rebuild capture

Status: `DONE` for the public rebuild package and documentation; clean-machine end-to-end validation was unavailable and explicitly waived by the operator with residual risk retained.

Goal: capture and reconstruct the currently functional GX10 implementation before adding new incident-engine architecture.

Completed capture includes:

- Ubuntu/runtime package requirements
- NVIDIA/GB10 environment dependencies
- Ollama runtime and model configuration
- read-only backlog fetcher
- local durable SQLite state schema
- replay-safe/idempotent ingest implementation
- current deterministic enrichment/classification
- systemd services/timers
- collector result-return boundary and the verified absence of a discovered GX10 producer
- restricted transport configuration
- validation/verifier scripts
- operator rebuild documentation

Exit gate: another engineer/AI can reconstruct the current functional GX10 on a clean server from the repository plus operator-supplied environment values.

## Milestone 4 - Two-server rebuild acceptance

Status: `ACCEPTED WITH RESIDUAL RISK`; repository-only and read-only-reference acceptance passed, while unavailable disposable clean-two-server execution was explicitly waived by the operator.

1. `DONE` — reconcile collector and GX10 rebuild assumptions
2. `DONE` — document the complete operator-supplied environment-value contract
3. `DONE` — document service installation/start order and cross-server dependencies
4. `DONE` — distinguish reconstructed current behavior from target architecture
5. `DONE` — validate public examples/fixtures and run final repository sanitation/publication gates
6. `WAIVED BY OPERATOR` — clean two-server rebuild validation was unavailable and remains empirically unverified
7. `DONE` — publish final repository acceptance status without concealing deferred external validation
8. `WAIVED BY OPERATOR` — do not block subsequent milestones on unavailable disposable hosts; retain the missing evidence as residual risk

Exit gate:

> Two clean servers, this public repository, and operator-supplied environment values are sufficient to reconstruct the current functional system.

The operator accepted this exit gate for project-sequencing purposes based on repository-only, synthetic, and read-only-reference evidence. Actual clean-host execution remains unproven and should still be performed if suitable systems later become available.

## Milestone 5 - Production normalizer integration

Status: `DONE`

After the current system is reconstructable:

1. `DONE` — design collector-side normalizer production integration
2. `DONE` — implement the repository-side durable shadow worker, validation, packaging, and rollback safeguards
3. `DONE` — the explicitly authorized private-inventory shadow deployment is active; complete catch-up, steady-state, concurrency, isolation, and unchanged-production validation passed
4. `DONE` — designed and synthetically rehearsed the immutable-floor, identity-preserving forward handoff and rollback without changing the live handoff
5. `DONE` — staged the exact-hash handoff package and completed the immutable-floor, identity-preserving production cutover with exact collector/GX10 hash and cardinality parity plus retained mount-only rollback
6. `DONE` — collected the multi-cadence stability window and retired transitional GX10 vendor/message reparsing through an exact-hash, rollback-protected replacement with an unscheduled canonical-field projector while preserving local suppression policy and historical enrichment rows

## Milestone 6 - Deterministic incident engine on GX10

Status: `DONE`

1. `DONE` — design and implement canonical incident identity and lifecycle
2. `DONE` — implement append-only transitions/evidence
3. `DONE` — implement repeat/burst accounting
4. `DONE` — implement rolling compact context summaries
5. `DONE` — implement replay/idempotency tests
6. `DONE` — exercise against stored prepared observations, reproduce the exact state independently, and install schema/engine unscheduled under protected rollback

Exit gate: replaying the same input cannot create duplicate canonical incidents or contradictory state.

## Milestone 7 - Steady-state local reasoning

Status: `DONE`

1. `DONE` — packaged canonical projection and incident correlation behind a managed, observable, rollback-protected invocation boundary and activated it through backfill plus multi-cadence gates
2. `DONE` — added independent watermark/backlog, integrity, incident-aggregate, restart, and timer-health verification for the managed correlation boundary
3. `DONE` — implemented deterministic LLM wake policy and completed protected-copy plus guarded unscheduled working-system installation gates
4. `DONE` — implemented compact, versioned, append-only incident packets and deterministic replay/threshold/lifecycle/tamper gates
5. `DONE` — track exact model/prompt/run versions behind durable crash-safe reservation and idempotency
6. `DONE` — independently validate strict structured model output through synthetic and protected-copy real-model gates
7. `DONE` — keep deterministic facts separate from model interpretation through append-only packet/result boundaries
8. `DONE` — preserve safe no-result behavior when inference is unavailable, invalid, or interrupted
9. `DONE` — packaged packet building and bounded inference behind a separately disableable, observable managed boundary; passed protected activation, compatibility correction, exact upgrade, and multi-cadence production gates while preserving one reviewed terminal failure

## Milestone 8 - Validated AI result return

Status: `DONE`

1. `DONE` — build a versioned deterministic outbox projection from successful append-only reasoning results
2. `DONE` — prove idempotent mapping, duplicate suppression, atomic local publication, crash recovery, strict output bounds, and protected-copy behavior
3. `DONE` — package, rehearse, and install an independently managed inactive no-network local producer boundary
4. `DONE` — activate the no-network local producer through protected initial-cycle, three no-op cadences, and natural one-file catch-up gates
5. `DONE` — separately installed the least-privilege write-only transport identity only after local producer verification passed
6. `DONE` — activated bounded live result return and proved collector validation, ClickHouse ingestion, exact provenance, exact replay, divergent-conflict isolation, and recurring natural delivery
7. `DONE` — retained GX10 without direct ClickHouse access and kept ordinary model assessments nonauthoritative

## Milestone 9 - AI presentation refinement

Status: `DONE`

1. `DONE` — added the original AI assessment-history dashboard without replacing existing resources
2. `DONE` — added a distinct enhanced deterministic NOC queue with Active, Interface Flaps, and Resolved windows
3. `DONE` — preserved one-click compact drilldown to bounded read-only raw observations
4. `DONE` — kept Grafana stateless with respect to incident truth and isolated a read-only NOC Viewer organization
5. `DONE` — added 24-hour BGP/OSPF/OSPFv3 recovery monitoring and same-incident recurrence accounting
6. `DONE` — added the one-minute two-dashboard NOC rotation playlist
7. `DONE` — replaced interface lifecycle noise with a rolling 60-minute threshold of 10 exact down transitions while retaining raw and lifecycle history

## Milestone 10 - Hidden AI coverage for uncovered important events

Status: `DONE`

1. `DONE` — selected deterministic signatures only from events not already owned by incident evidence
2. `DONE` — added bounded severity 0–4 and novel/repeated severity-5 local-model review without a new operator-facing event type
3. `DONE` — retained pending work and created no incident when Gemma was unavailable, invalid, or interrupted
4. `DONE` — bridged validated positives into ordinary deterministic incidents and the existing Active/Resolved workflow
5. `DONE` — guarded automatic exact-event learned coverage to severity 0–3 with three consistent confidence-70+ decisions spanning at least 30 minutes and no contradiction
6. `DONE` — activated through protected migration, shadow proof, exact staged validation, existing result/lifecycle transport, and collector acceptance

## Deferred hardening - Delivery-confirmed AI-result archive

Status: `DEFERRED`; this is not a current `NEXT` item.

The collector deliberately preserves immutable accepted AI-result payloads in
its ready directory. Vector tails that directory and keeps a descriptor per
file. The active service limit is explicitly 65,536 descriptors, which safely
corrects the former inherited 1,024-descriptor limit without removing evidence.

Before any automatic archival or deletion is introduced:

1. `TODO` — design a per-file, idempotent delivery proof that binds the
   acceptance-ledger filename/digest/record count to the exact ClickHouse raw
   record or records produced by that file.
2. `TODO` — build a reversible archive workflow that acts only after that proof,
   preserves original bytes and metadata, and retains a protected rollback
   boundary.
3. `TODO` — prove restart, partial-ingestion, duplicate/replay, failed sink,
   ledger-integrity, and rollback behavior on an isolated copy before live use.
4. `TODO` — add bounded descriptor/cache telemetry and a documented capacity
   review threshold, then deploy under a separate protected production gate.

Global Vector acknowledgements are not the solution by themselves: the live
UDP source does not support them and Vector reports that enabling them could
allow silent loss. The current ready-file preservation plus descriptor-limit
override remains the safe operational policy until this milestone is complete.

## Continuity gate

After every completed project sub-section:

1. validate the intended checkpoint
2. append the result to `docs/PROJECT_JOURNAL.md`
3. push the journal update to GitHub
4. update `docs/CURRENT_STATE.md` when execution order/current state changes
5. use `docs/DOCUMENTATION_GUIDE.md` to update each affected canonical document
6. only then proceed materially into the next sub-section

For long or risk-heavy sub-sections, publish intermediate validated recovery checkpoints when useful, while keeping the current `NEXT` item unchanged until the sub-section is complete.
