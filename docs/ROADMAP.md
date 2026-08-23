# Roadmap

The project advances through deterministic, validated gates. `docs/CURRENT_STATE.md` is the authority for the exact current execution order and the single `NEXT` item. This roadmap describes the broader milestone sequence.

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

Production cutover remains a later controlled migration task and is not required to finish the rebuild-documentation milestone.

## Milestone 2 - Collector rebuild package

Status: `DONE` for the public rebuild package and documentation; clean-machine end-to-end validation is deferred pending a disposable Debian 13 amd64 system.

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

The installer structural, credential-exposure, public-safety, operator-documentation, and final sanitation gates are complete. Clean-machine collector rebuild validation remains deferred.

Exit gate: another engineer/AI can reconstruct the current collector on a clean server from the repository plus operator-supplied environment values without undocumented implementation memory.

## Milestone 3 - GX10 rebuild capture

Status: `IN PROGRESS` — live-system rediscovery is complete and public reconstruction is next.

Goal: capture and reconstruct the currently functional GX10 implementation before adding new incident-engine architecture.

Required capture includes:

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

Status: `NOT STARTED`

1. reconcile collector and GX10 rebuild assumptions
2. document the complete operator-supplied environment-value contract
3. document service installation/start order and cross-server dependencies
4. validate public examples and fixtures
5. run final repository sanitation/publication gates
6. perform clean two-server rebuild validation when practical
7. verify no undocumented memory is required

Exit gate:

> Two clean servers, this public repository, and operator-supplied environment values are sufficient to reconstruct the current functional system.

## Milestone 5 - Production normalizer integration

Status: `DEFERRED UNTIL REBUILD CAPTURE IS CLOSED`

After the current system is reconstructable:

1. design collector-side normalizer production integration
2. establish explicit rollback behavior
3. run shadow/parallel validation where practical
4. promote only after replay and production validation remain clean
5. retire transitional GX10 vendor parsing deliberately

## Milestone 6 - Deterministic incident engine on GX10

Status: `FUTURE IMPLEMENTATION`

1. implement canonical incident identity and lifecycle
2. implement append-only transitions/evidence
3. implement repeat/burst accounting
4. implement rolling compact context summaries
5. implement replay/idempotency tests
6. exercise against stored prepared observations

Exit gate: replaying the same input cannot create duplicate canonical incidents or contradictory state.

## Milestone 7 - Steady-state local reasoning

Status: `FUTURE IMPLEMENTATION`

1. package correlation as a managed service
2. add health/backlog telemetry
3. implement deterministic LLM wake policy
4. assemble compact incident packets
5. track model/prompt versions
6. require structured model output
7. keep deterministic facts separate from model interpretation
8. preserve safe failure behavior when inference is unavailable

## Milestone 8 - AI presentation refinement

Status: `FUTURE IMPLEMENTATION`

1. present validated incident/AI records in Grafana after contracts stabilize
2. preserve drilldown to underlying raw observations
3. keep Grafana stateless with respect to incident truth
4. avoid turning the primary NOC view into a raw-log wall

## Continuity gate

After every completed project sub-section:

1. validate the intended checkpoint
2. append the result to `docs/PROJECT_JOURNAL.md`
3. push the journal update to GitHub
4. update `docs/CURRENT_STATE.md` when execution order/current state changes
5. only then proceed materially into the next sub-section

For long or risk-heavy sub-sections, publish intermediate validated recovery checkpoints when useful, while keeping the current `NEXT` item unchanged until the sub-section is complete.
