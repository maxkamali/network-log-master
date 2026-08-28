# Architecture Decision Log

This file records durable project decisions and the reasoning behind them. New entries are append-only unless a later decision explicitly supersedes an earlier one.

## ADR-001 - Capture first

**Status:** Accepted

All legitimate observations are retained even when no vendor parser recognizes them.

Why:

- unknown events are often the events most worth investigating
- parser coverage evolves over time
- replay requires preserved raw evidence
- admission allowlists create silent blind spots

Consequence: parser mismatch, malformed vendor payloads, and future event codes fall back to generic observations rather than being dropped.

## ADR-002 - Deterministic normalization belongs on the collector

**Status:** Accepted

Vendor decoding, event-envelope extraction, platform trust boundaries, suppression rules, and other deterministic observation normalization belong on the collector/log server.

Why:

- normalization should happen once near durable capture
- deterministic behavior is easier to test and replay centrally
- GX10 should receive prepared observations rather than repeatedly decode vendor syntax
- the reasoning host remains replaceable

Consequence: transitional vendor enrichment on GX10 is retained only as a migration/parity reference until collector-side replay parity is proven.

## ADR-003 - Incident correlation belongs on GX10

**Status:** Accepted

Compact incident identity, lifecycle, repeat/burst evidence, rolling context, and reasoning wake policy belong on GX10.

Why:

- those functions operate on prepared observations rather than raw vendor syntax
- incident working state is compact enough for the reasoning host
- it keeps large/long-lived raw stores on the collector while placing inference-adjacent state next to the local model runtime

Consequence: moving normalization to the collector does not imply moving the entire deterministic incident engine there.

## ADR-004 - The LLM is not the source of truth

**Status:** Accepted

The local model may explain, summarize, rank, and suggest, but it does not own canonical identity, deduplication, incident lifecycle, or deterministic state transitions.

Why:

- incident behavior must be replayable and testable
- model output is probabilistic
- outages or model changes must not corrupt canonical state

Consequence: the system remains operational and state-consistent even when inference is unavailable.

## ADR-005 - GX10 does not write directly to ClickHouse

**Status:** Accepted

AI results cross a write-only transport and collector-side validation gate before durable ingestion.

Why:

- least privilege
- malformed model output is isolated before storage
- the collector remains the durable data authority

Consequence: result files are validated, accepted atomically, or quarantined with a reason.

## ADR-006 - File backlog is the V1 transport

**Status:** Accepted

Prepared/backlog observations are transferred through durable files rather than introducing a message bus in the first production design.

Why:

- existing throughput and latency requirements do not justify additional infrastructure
- file replay and catch-up semantics are straightforward to inspect
- the transport already supports durable recovery

Consequence: streaming infrastructure is deferred until measured requirements demand it.

## ADR-007 - Public master repository

**Status:** Accepted

This repository is the durable public engineering record and eventual consolidated home for project components.

Why:

- one front door reduces documentation drift and recovery cost
- architecture, implementation state, and operational rules remain versioned together
- future AI-assisted sessions can resume from a compact verified record

Consequence: public-safety gates are mandatory, and live system state must still be verified before consequential production changes.

## ADR-008 - Platform selection uses a private trusted inventory

**Status:** Accepted

Vendor/platform eligibility for deterministic parsers is supplied by a private operator-maintained inventory keyed by the deployment's stable syslog `source_ip` identity.

Message fingerprints may be used to bootstrap and audit that inventory, but they are not runtime platform authority.

Why:

- multiple network operating systems can use superficially similar syslog event syntax
- legacy and partially structured syslog envelopes cannot safely establish vendor identity
- collector envelope-parser labels describe decoding paths rather than device platform
- vendor-specific parsers should run only after an independent trust decision
- unknown inventory entries must remain observable instead of being guessed

Consequence: the collector injects trusted `vendor_hint` and `os_family_hint` before vendor-specific normalization. Unmapped sources remain on the generic capture-first path. Production device identities and the private inventory are never committed to this public repository.

## ADR-009 - Migration parity is semantic, not textual

**Status:** Accepted

Collector-to-GX10 migration parity is judged on deterministic event semantics rather than byte-for-byte equality of transitional parser formatting.

Why:

- equivalent parsers may retain different harmless delimiters or presentation text
- collector parsing should not be degraded merely to reproduce transitional formatting
- real differences in protocol, identity, state, signal type, or structured meaning must still fail parity
- intentional collector improvements must be explicitly documented rather than hidden

Consequence: parity checks may normalize narrowly understood representation-only differences. Unexpected semantic differences remain migration failures.

## ADR-010 - Rebuildability is a project acceptance criterion

**Status:** Accepted

The reconstruction/documentation effort is complete only when two clean servers, this public repository, and operator-supplied environment values are sufficient for another engineer or AI to reconstruct the current functional system without undocumented implementation memory.

Why:

- conversational context and individual operator memory are not durable dependencies
- the current system contains working implementation knowledge that would be expensive to rediscover
- implementation, validation, and rebuild order should be versioned with the project
- future maintenance should begin from reproducible artifacts rather than reverse engineering live servers again

Consequence:

- real non-sensitive implementation and configuration belong in the repository
- rebuild/install/verification tooling is a first-class project deliverable
- environment-specific credentials, addresses, usernames, SSH keys, certificate private keys, and other private identity remain operator-supplied rather than publicly committed
- current working components should be captured before they are substantially redesigned

## ADR-011 - Grafana dashboards are rebuilt through the supported resource API

**Status:** Accepted

Grafana dashboard reconstruction uses the Grafana `dashboard.grafana.app/v2` resource API rather than direct writes to Grafana's SQLite database.

Why:

- the API is the supported application boundary
- captured dashboard resources round-trip through the API with exact `spec` parity
- Grafana 13.1.1 exposes explicit POST create and PUT replace operations
- `dryRun=All` allows non-persistent validation before writes
- server-owned metadata should be generated by Grafana rather than copied blindly from a database snapshot

Consequence:

- repository dashboard resources preserve semantic dashboard content while excluding server-owned creation/resource metadata from restore payloads
- restore tooling creates missing resources, refuses unexpected replacement by default, and verifies persisted results
- direct manipulation of Grafana SQLite state is not part of the rebuild contract

## ADR-012 - GitHub is the durable continuity mechanism for project execution

**Status:** Accepted

Project continuation must not depend on one chat session or undocumented operator memory.

Why:

- the project spans multiple long-running implementation and discovery sessions
- context loss could otherwise force expensive rediscovery
- a chronological decision/validation trail makes fresh-session recovery auditable

Consequence:

- `docs/CURRENT_STATE.md` is the authority for strict execution order and must contain exactly one `NEXT` item
- `docs/PROJECT_JOURNAL.md` is append-only historical context
- every completed validated sub-section is journaled and pushed to GitHub before materially proceeding into the next sub-section
- `docs/START_HERE.md` defines the canonical recovery/read order
- architecture/current-state/component rebuild documents have distinct source-of-truth roles rather than duplicating one another
## ADR-013 - Long-running subsections use intermediate durable checkpoints

**Status:** Accepted

Long-running, risk-heavy, or multi-step project sub-sections should use intermediate validated GitHub checkpoints instead of relying only on the final sub-section commit.

Why:

- conversational context is finite and may be lost before a large sub-section is finished
- validated implementation state can be expensive to reconstruct from live systems or terminal history
- intermediate commits create explicit rollback and recovery points
- non-obvious failed approaches and corrections should survive independently of chat memory
- waiting for a large sub-section to finish can leave too much correct but unpublished work vulnerable to loss

Consequence:

- after a meaningful implementation state passes bounded structural, syntax, safety, or behavioral validation, commit and push it when doing so creates a useful recovery point
- intermediate checkpoints must be clearly identified as incomplete when additional validation remains
- append a project-journal checkpoint when the intermediate state contains decisions, corrections, failure analysis, or resume information that would otherwise need to be rediscovered
- `docs/CURRENT_STATE.md` remains the execution authority and does not advance an item from `NEXT` to `DONE` merely because an intermediate checkpoint was published
- the existing rule still applies: every fully completed validated sub-section must receive its completion journal entry and push before the next sub-section begins

## ADR-014 - Remaining execution moves to a direct-access operator VM

**Status:** Accepted

The remaining project work will be executed from an operator-controlled VM that provides the executing AI with direct authenticated access to the collector reference system, GX10, and GitHub, rather than using the human operator as the routine shell-command copy/paste relay.

Why:

- the copy/paste relay adds substantial latency to bounded discovery, validation, repository updates, and iterative corrections
- direct access allows the same read-only checks and reversible implementation work to be executed and validated without transcription errors between chat and terminal sessions
- the project now has sufficient durable GitHub state to resume safely from a new execution environment
- the human operator should be able to supervise the agentic workflow and intervene primarily when judgment, credentials, or risk approval are genuinely required

Consequence:

- credentials, SSH keys, private addresses, usernames, and other environment-specific identity remain outside the public repository
- the new VM must verify GitHub state and authenticated connectivity to both reference systems before materially continuing
- direct credential availability is not blanket authorization for destructive or difficult-to-reverse actions
- destructive/high-risk production changes, material architecture/scope decisions, and unresolved ambiguity requiring operator intent still require human involvement
- existing publication, sanitation, validation, journal, and single-`NEXT` continuity rules remain unchanged
- item 12N was partial at the environment transition because its first external-tool detector missed previously proven SFTP and Zstandard use; the corrected detector and dependency/provenance rerun later passed, so item 12N is complete
- the durable transition/resume evidence is recorded in `docs/VM_HANDOFF.md`

## ADR-015 - Reconstruction preserves absent orchestration

**Status:** Accepted as a rediscovery/reconstruction boundary; later extensions were separately authorized and implemented

Public rebuild artifacts and current-state documentation must reproduce only the runtime connections proven during rediscovery. The presence of an executable, service, model store, or transport boundary is not sufficient evidence that another component calls it.

Why:

- GX10 rediscovery proved the automatic chain `timer -> fetch -> ingest`
- deterministic enrichment exists but has no discovered automatic invocation
- Ollama is active with six complete models but has no discovered application-specific observability-pipeline caller
- the collector result-return boundary exists but has no discovered GX10 producer
- silently connecting these separately present capabilities would create new architecture and mislabel it as recovered current behavior

Historical reconstruction consequence:

- the initial GX10 base rebuild installed deterministic enrichment but did not schedule it
- the initial Ollama base rebuild reproduced infrastructure/model state but created no pipeline caller
- the initial collector base rebuild reproduced the write-only result boundary while the GX10 base rebuild installed no result-writer key or producer
- architecture, data-contract, operations, and rebuild documents distinguish rediscovered behavior from deliberately added behavior
- the later incident engine, wake policy, Ollama caller, result producer, and sender received their own decisions, tests, migrations, activation evidence, and rollback gates; their current state is recorded in `docs/CURRENT_STATE.md`

## ADR-016 - Unavailable clean-host execution is waived with residual risk

**Status:** Accepted by operator

The rebuild/documentation milestone may advance without disposable clean collector and GX10 execution because suitable systems are unavailable and the operator explicitly accepted the residual risk on 2026-08-23.

Why:

- repository-only, synthetic, component-test, sanitation, Git-integrity, and read-only-reference gates pass
- both rebuild packages contain guarded installers, verifiers, rollback boundaries, and complete operator documentation
- no suitable disposable Debian 13 amd64 and Ubuntu 24.04 arm64 GX10-class pair is available
- indefinite blocking would not create additional evidence without the missing external systems

Consequence:

- clean collector, clean GX10, and clean two-server execution are recorded as `WAIVED BY OPERATOR`, not `PASS`
- the rebuild/documentation milestone is accepted with explicit residual risk for project-sequencing purposes
- this waiver allowed the project to proceed to production-normalizer integration design; that later integration and handoff work is complete
- no installer may be run against a working reference system merely to replace the missing disposable-host evidence
- if suitable disposable systems become available later, the runbooks should still be executed and the qualification removed only after successful evidence is recorded

## ADR-017 - Production normalization begins at a durable shadow boundary

**Status:** Accepted

The collector-side Python normalizer will first run as a separate unprivileged durable-file shadow worker over settled `/var/spool/vector-ai` files. It will not be inserted inline between Vector and the existing ClickHouse or backlog sinks.

Why:

- raw capture and ClickHouse delivery must survive normalizer failure
- the current compressed backlog is durable, replayable, and already operationally proven
- file hashes and exact line counts provide independently auditable completeness and idempotency
- private platform inventory can remain in a local protected file rather than entering Vector configuration or the public repository
- a separate shadow root permits comparison and rollback before the GX10 handoff changes
- a best-effort socket loop would add weaker delivery semantics and more coupling than the existing file boundary

Consequence:

- shadow operation cannot change the current Vector sinks or GX10 backlog view
- every completed source file has an atomic normalized output plus durable source/output/inventory/version evidence
- the runtime account has read-only source access and no network, ClickHouse, SSH-key, Ollama, or AI-result credentials
- promotion changes only the verified GX10 handoff view and requires a separately reviewed file-identity/idempotency plan
- live shadow deployment and cutover remain explicit approval gates
- transitional GX10 parsing was retired only after normalized handoff stability was proven

## ADR-018 - GX10 normalized promotion uses a forward-only identity-preserving handoff view

**Status:** Accepted and implemented

Normalized promotion will not directly expose the shadow-output tree and will not replay normalized history under a new remote namespace. A protected immutable plan selects one inclusive first normalized source path. Only verified completed shadow outputs at or after that floor are copied into a separate handoff root, using their original raw relative paths and filenames.

Why:

- the current GX10 fetcher rejects the shadow tree's `.normalized.jsonl.zst` filenames
- accepting those suffixed names would give previously consumed historical files new `source_files.remote_path` identities and duplicate observations
- renaming all normalized history to raw names would collide with already processed paths and make the effective transition boundary ambiguous
- one forward-only floor lets pre-cutover observations remain raw and post-cutover observations become normalized without changing the strict SFTP path contract
- a separate handoff tree preserves raw and shadow evidence and permits an exact bind-view rollback

Consequence:

- files before the floor may never appear in the normalized handoff tree
- at/after-floor normalized copies use the unchanged `/spool/<source_path>` identity expected by GX10
- the plan is bound into a separate versioned handoff ledger and cannot be repointed after initialization
- publication requires exact shadow-ledger path, hash, Zstandard, cardinality, mode, and ownership evidence and uses synchronized atomic no-overwrite copies rather than hard links
- successfully ingested at/after-floor files remain idempotent after raw-view rollback because their GX10 remote identities do not change
- production staging, timer activation, bind switching, and rollback execution require a separate explicit operator authorization and the preflight in `docs/NORMALIZER_HANDOFF.md`
- item 22 remained repository-only; the separately authorized item-23 production activation completed on 2026-08-24 with exact collector/GX10 parity and a retained raw-view rollback boundary

## ADR-019 - Post-handoff GX10 enrichment projects canonical fields instead of reparsing messages

**Status:** Accepted and implemented

After the normalized handoff stability gate, GX10 no longer keeps a second vendor/message parser as an active executable authority. The compatibility-path enrichment artifact is an unscheduled projector from exact normalized schema version 1 into the existing `event_enrichment` working table.

Why:

- all reviewed post-floor events have the exact canonical normalized schema
- a read-only audit proved that legacy reparsing diverges from canonical family, protocol, entity, state, signal, and repeat fields
- retaining two parsers would make downstream incident behavior depend on which representation was consulted
- the existing GX10-local suppression rules are policy rather than vendor parsing and must survive retirement
- historical version-3 enrichment rows remain useful migration evidence and must not be deleted or rewritten

Consequence:

- canonical normalized fields are authoritative for new projection rows
- the projector performs no vendor or message classification
- enabled local suppression rules are overlaid deterministically in existing rule order
- new projected rows use classification version 4; historical version-3 rows remain unchanged
- a transactional cursor makes projection append-only, bounded, resumable, and idempotent
- projection remained absent from the proven automatic `timer -> fetch -> ingest` chain until item 26 made a later explicit scheduling decision
- the live retirement used exact old/new hashes, zero-scheduler-reference preconditions, atomic replacement, a root-only rollback copy, and an unchanged-database postcheck
- item 26 later made that explicit scheduling decision through a separate managed correlation unit without altering the original fetch/ingest chain

## ADR-020 - Incident truth is deterministic, event-sourced, and independent of the LLM

**Status:** Accepted and implemented

GX10 incident identity, evidence membership, lifecycle, repeat accounting, and rolling context are owned by a deterministic SQLite engine over canonical classification-version-4 projections. A local model may explain or summarize this state but cannot create identity or mutate lifecycle truth; item 29 now invokes that model through a separately managed, nonauthoritative schedule.

Why:

- canonical normalized records now provide one authoritative event/entity/protocol representation
- replay and recurrence require stable identities derived from immutable source observations
- lifecycle decisions must remain testable and reproducible without model availability or nondeterministic output
- append-only evidence and transitions preserve why an incident exists and how it changed
- model context must be compact and bounded without replacing durable facts

Consequence:

- correlation keys are deterministic hashes of canonical family/protocol/entity identity
- incident instance IDs also include the first adverse source-file/record identity, so recurrence after resolution is distinct
- evidence and transition tables are append-only, while one mutable incident row materializes current aggregates and 60-minute, 180-minute, and 24-hour context
- explicit adverse state transitions may open immediately; other degradations require repeated evidence inside a fixed event-time window
- transactionally coupled cursor and evidence uniqueness make processing resumable and replay-safe
- schema migration, installation, historical projection, recurring scheduling, Ollama invocation, and result return remain separately gated operations

## ADR-021 - Deterministic correlation runs in a separate offline managed unit

**Status:** Accepted and implemented

Canonical projection and deterministic incident processing will run in one exact ordered wrapper behind a separate oneshot service and timer. The existing fetch/ingest service remains unchanged.

Why:

- projection must complete before incident processing sees new canonical rows
- correlation failure must not stop durable fetch/ingest
- independent disable/rollback controls are safer than extending the recovered pipeline unit
- SQLite transactions already serialize writers, while bounded cursor convergence can absorb rows committed during a cycle
- local deterministic processing needs no network access or spool write permission
- explicit wrapper telemetry can expose both stage watermarks and state counts without adding a new telemetry database

Consequence:

- the correlation service invokes only exact-hash projector and incident artifacts in that order
- a runtime-owned single-instance lock prevents overlapping correlation cycles
- up to three ordered passes may run to converge with concurrent ingestion; nonzero lag after that is a visible failure
- the service has an independent timer, CPU/memory/time/task limits, Unix-socket-only address families, and private write access limited to the validated database parent
- activation performs one verified timer-disabled backfill before enabling the timer
- activation failure disables only correlation and preserves deterministic state for replay
- Ollama, wake policy, result production, and collector result return remain out of scope
- production activation completed after inactive installation, one zero-lag initial backfill, and three independent zero-lag scheduled cadences; the original fetch/ingest timer advanced throughout

## ADR-022 - Reasoning wakes and packets are deterministic append-only facts

**Status:** Accepted and active through the separately managed item-29 reasoning schedule

LLM wake selection and compact incident-packet construction are owned by a deterministic versioned builder over incident/evidence/transition state. The builder records immutable packet facts before any inference caller exists.

Why:

- the model must not decide when it is called or manufacture its own context
- replay, retry, and incident-cursor reset must not duplicate reasoning work
- urgent critical/open/flap/retransmission changes need explicit priority, while ordinary updates need deterministic rate limits
- production incident state includes resolved history that must not create a first-deployment inference storm
- prompts need compact bounded facts without raw-log or source-path exposure
- later model/prompt/output changes must not rewrite why an earlier reasoning packet existed

Consequence:

- policy and packet versions are stored independently of any model/prompt version
- packet IDs derive from incident ID plus exact evidence/transition sequence bases
- the packet table and existing incident evidence/transitions are append-only
- critical, lifecycle, interface-flap, OSPF-retransmission, and meaningful-update rules use fixed priorities and event-time cooldowns
- initially resolved incidents are skipped; candidates require an independently qualifying critical or OSPF condition
- each packet is canonical JSON, SHA-256 bound, maximum 32 KiB, and contains bounded fact slices without raw messages or source paths
- at item-27 closure, protected copy/migration gates passed with the exact schema/builder installed and zero packets, invocations, or scheduler references; item 29 later activated the separately managed builder/inference schedule and item 30 activated result return

## ADR-023 - Local reasoning runs are version-bound, crash-safe, and nonauthoritative

**Status:** Accepted and active through the separately managed item-29 reasoning schedule

Each local-model invocation is bound to one immutable reasoning packet, exact captured model manifest/config, exact prompt/output-schema hashes, and an attempt number. A durable run reservation is committed before contacting loopback Ollama; only strict structured output may become an append-only result.

Why:

- retries and crashes must not silently duplicate inference
- model and prompt changes must not rewrite or obscure the provenance of prior interpretation
- model output is untrusted and must not mutate deterministic incident or packet truth
- unavailable inference must leave an explicit safe no-result state
- the local runtime must not become a general outbound-network client

Consequence:

- calibration first tried the smallest captured model but rejected its under-escalated/meaningless output without weakening validation; the exact second-smallest Gemma candidate passed the bounded synthetic quality set and is the selected version
- one deterministic `STARTED` reservation blocks duplicate calls; interruption requires later explicit reconciliation rather than automatic takeover
- a run may transition once to success or a bounded terminal failure status
- model/prompt registrations and successful canonical results are append-only
- packet/incident IDs, schema, enumerations, types, counts, lengths, and digests are independently validated
- after protected-copy reproduction proved the model could place a risk label in the action-text field, immutable prompt revision `r2` retained a negative enum but proved the local runtime does not enforce `not/enum`; revision `incident-assessment-v2-r3` therefore also requires action text longer than every risk label, while the caller's independent rejection rule remains unchanged
- the caller is fixed to loopback HTTP, refuses redirects, applies request/response/time bounds, and stores no invalid model content
- repository, migration, synthetic local-model, protected-copy, and guarded empty/unscheduled-install gates passed independently
- item 29 owns managed invocation and retains its one reviewed terminal invalid-output run as immutable evidence; collector result return remains out of scope

## ADR-024 - Managed reasoning is separately scheduled, bounded, and fail-closed

**Status:** Accepted and active after portable-r3 multi-cadence validation

Packet construction and local inference use a third independently disableable oneshot/timer boundary after deterministic correlation. Each locked cycle runs deterministic packet construction once and permits at most one exact-version inference reservation.

Why:

- model latency and failure must not delay or disable fetch/ingest or deterministic correlation
- one inference per cadence bounds local-model load and makes production advancement observable
- an interrupted durable `STARTED` reservation must stop automatic reasoning instead of causing a hidden retry
- backlog and run/result health must be visible without exposing packet, incident, event, or entity content
- production activation needs a fresh protected state checkpoint before the first packet or model call

Consequence:

- the runner validates exact builder/caller/configuration/prompt/output hashes and owns a separate mode-`0600` cycle lock
- any preexisting `STARTED` reservation fails the cycle before new work
- each cycle can add at most one run and one result; terminal inference failure remains explicit and nonauthoritative
- packet construction is deferred whenever selected-version backlog exists; that drain cycle must keep packet count fixed and reduce pending count by exactly one reservation before construction can resume at pending zero
- the service can write only beside the validated database and can connect only to IPv4 loopback plus Unix sockets
- the timer's first scheduled cycle is relative to enablement, not host boot; an exact published inactive predecessor may be atomically upgraded, while any divergent target is refused
- compatibility upgrades are permitted only for the exact predecessor runtime config, output schema, caller, and managed runner while the units are disabled; divergent files are refused and later failure rolls back changed artifacts
- inactive installation, protected-copy rehearsal, protected initial production cycle, timer enablement, and multi-cadence evidence remain separate gates
- collector result return remains outside item 29

## ADR-025 - Result projection is read-only, one-run-per-file, and provenance-complete

**Status:** Accepted and active through the item-30 result-return path and item-42 snapshot hardening

Successful append-only reasoning results are projected through a separate versioned read-only producer. Version 1 emits exactly one canonical newline-terminated JSON record per file and derives the public filename from a truncated SHA-256 of the run ID.

Why:

- terminal failures and in-progress reservations must never appear as results
- one record per file makes the collector's file/record limits and retry unit explicit
- a hash-derived filename avoids exposing the run ID through directory listing while retaining deterministic duplicate identity
- the thin collector columns are insufficient to preserve every structured model field and exact inference provenance
- result publication must not become a write path back into incident, packet, run, or result truth
- installation, writer credentials, sender acknowledgment, and live transport require independent failure/replay analysis

Consequence:

- the producer opens SQLite read-only in one snapshot and validates integrity, canonical JSON, hashes, identities, statuses, timestamps, and model/prompt/request/run provenance before writing anything
- the complete canonical result plus versioned provenance remain inside the record; Vector's existing `raw_json` capture preserves the complete line after collector acceptance
- ready and delivered are protected sibling states under one shared lock; an exact delivered file suppresses recreation, duplicate state fails closed, exact existing files are no-ops, divergence fails before new publication, and only strictly validated ready-state producer partials are recoverable
- publication is lock-protected, same-directory atomic, file/directory `fsync`-backed, size-bounded, and postvalidated
- the repository/exact GX10 stage and protected-copy gates pass with 151 tests, 12-for-12 result generation, one simulated delivered transition, and exact 11-ready/one-delivered replay
- the separately managed package adds an exact-hash runner, private-network/Unix-only oneshot, disabled timer, guarded empty installer, independent verifier, and complete failure cleanup; its isolated exact-tree rehearsal passes with 157 tests
- exact producer/runner/service/timer/configuration plus ready/delivered directories are installed; corrected protected activation retains 15 exact collector-valid ready files, zero delivered, and an active no-network timer
- at the inactive item-30 staging boundary, no writer credential or sender was installed and no collector transmission had occurred
- local activation paused only managed reasoning, bound all five reasoning tables to one before/after digest, ran exactly one producer cycle with the outbox timer disabled, enabled that timer only after cardinality verification, and restored reasoning on every path
- local production passed multiple natural exact-no-op cadences and one natural reasoning-success/outbox-file catch-up while preserving all prior file bytes
- ADR-027 and item 30 later supplied and activated the separately gated durable-acknowledgment sender; ADR-030 and item 42 hardened the producer's read snapshot without changing this projection contract

## ADR-026 - Collector acceptance identity is durable beyond ready-file retention

**Status:** Accepted and active after cross-owner publication correction

The collector validation gate records every accepted result filename, SHA-256 digest, byte size, record count, and acceptance time in a versioned append-only SQLite ledger under the protected ready boundary. A filename can be accepted only once for one exact payload, even after its ready file is removed.

Why:

- a deterministic sender must retry the same filename after interruption
- successful remote upload can occur before GX10 records its local delivered transition
- retaining a ready file is not a durable acceptance identity because retention or operations may later remove it
- ClickHouse's current result table does not independently deduplicate replayed files
- collector rejection must distinguish exact replay from same-name divergent content without re-ingesting either

Consequence:

- the gate reconciles valid preexisting ready files into the ledger before processing incoming files
- first acceptance copies validated writer-owned bytes into gate-owned protected temporary storage and revalidates source/copy evidence before publishing ready and committing its ledger row
- a same-owner no-overwrite ready/marker link provides atomic publication; a crash in the two-link state is recovered only with the exact marker inode and exact incoming bytes
- ledger rows have immutable update/delete triggers, strict schema/version/content checks, synchronous commits, and directory `fsync`
- exact and divergent replays are both quarantined with different reasons and never republished to ready
- the ledger remains authoritative after a ready file is removed, so deterministic sender replay cannot create a second ClickHouse ingestion
- the sender may move a local ready file to delivered after successful transport completion; collector acceptance/rejection remains independently observable
- installation and production sender transmission were separate gates; item 30 later completed the recurring sender and end-to-end acceptance/provenance gates

## ADR-027 - Result sending is single-file, exact-byte, and transport-acknowledged

**Status:** Accepted and active through item 30

The GX10 sender transmits at most one oldest ready result per cycle under the same lock used by the no-network producer. It uploads the existing canonical file under its unchanged deterministic basename and moves it locally to delivered only after the bounded SFTP process returns success.

Why:

- exact filename/content replay is the recovery unit protected by the collector acceptance ledger
- generating a new remote identity or rewriting a record during retry would defeat collector replay suppression
- one file per cadence bounds transport load and makes progress/failure observable
- successful upload does not eliminate the interruption window before local acknowledgment
- private result-writer identity and pinned host material must remain separately provisioned operator input

Consequence:

- the sender independently validates canonical one-record JSONL bytes, run-derived filename, metadata, ready/delivered inventories, and private-file metadata before transport
- the oldest embedded result timestamp, then filename, provides deterministic starvation-resistant selection
- SFTP is noninteractive, batch-only, identities-only, password/keyboard authentication disabled, strict known-host checking, connection-attempt/time bounded, and invoked without a shell
- stderr/stdout and endpoint values are not propagated through application failure output
- nonzero/timeout/launch failure preserves the ready file unchanged
- interruption after successful transport but before local rename leaves the ready file for an identical retry; the collector ledger suppresses second acceptance
- local ready-to-delivered rename is atomic within the shared outbox filesystem and both directories are durability-synchronized
- delivered means transport completion, while collector acceptance, ingestion, and replay proof remain independent gates
- the exact-hash managed runner and hardened service/timer are packaged behind a nonactivating installer and strict staged verifier
- the service is deliberately network-capable but has no capabilities, a strict read-only system, write scope only to the derived outbox, no database access, fixed address families, bounded resources/time, and a required private config condition
- inactive installation creates no private config, identity, known-hosts file, or enabled schedule
- the sender package is installed with its timer disabled, service inactive, and all private inputs absent; no credential or live transport is authorized by this decision alone
- the separate configurator accepts only a root-owned Ed25519 input, proves it differs from the read-only spool identity, copies the existing pinned host into a distinct writer file, and atomically installs canonical configuration last
- partial or divergent private state is refused; postinstall verification failure removes only newly created inputs; exact existing state is reusable
- configured verification requires exact private metadata/values/pin plus the unchanged disabled/inactive package and active outbox, and neither configuration nor verification invokes SFTP
- collector authorization appends only the matching public Ed25519 key after preserving exact predecessor bytes in a root-only backup; duplicate/divergent state is refused, SSH configuration is validated without restart, and a later failure restores the predecessor exactly
- item 30 subsequently passed first-live, exact-replay, divergent-conflict, recurring-schedule, natural-delivery, collector-acceptance, and ClickHouse-provenance gates; the current sender is active

## ADR-028 - Gemma remains selected after repeatable Nemotron comparison

**Status:** Accepted; no production change

The exact selected `gemma4:latest` version remains the local incident-assessment model after two identical 13-case comparisons with the already-captured `nemotron-3.5-lightning:30b` candidate.

Why:

- a model replacement must improve operator-facing quality without weakening the active strict-output, urgency, provenance, or prompt-injection boundary
- both candidates can be compared locally with the exact production prompt/schema/options and public-safe packets, without opening production state
- Nemotron was faster when resident and more conservative about likely causes, but these advantages do not compensate for unsafe severity inflation or output rejection
- two complete passes reproduced the same quality scores and contract-error classes

Consequence:

- Gemma retains 12/13 strict-contract passes, 12/13 acceptable-severity matches, 11/13 disposition matches, and 13/13 prompt-injection resistance on the expanded set
- Nemotron's 6/13 strict-contract passes and 7/13 acceptable-severity matches disqualify it; it inflated six noncritical cases to critical and repeatedly mislabeled action risk
- known Gemma misses on contradictory and resolved-plus-critical packets remain explicit calibration debt rather than being hidden by a weaker replacement
- the evaluator is retained for future candidates, but production model/version changes still require a separate versioned compatibility, state-copy, activation, and rollback gate
- no production model, prompt, caller, schedule, database, result, collector, or dashboard state changed

## ADR-029 - Outbox projection reads an atomic rollback-journal snapshot

**Status:** Superseded by ADR-030 after the first production cycle; retained as failure-safe design evidence

The result and deterministic-lifecycle outbox producers read a fresh SQLite
online-backup snapshot rather than opening the mutable WAL database directly
inside their strict read-only service sandbox.

Why:

- the source database remains healthy and passes integrity checks
- every reviewed failure is `unable to open database file`, not corruption,
  schema divergence, or lock contention
- SQLite WAL readers may need writable-directory access for shared-memory
  sidecars even when the database URI is opened read-only
- granting the existing complex outbox producers write scope over the live
  database directory would weaken their established least-privilege boundary
- `immutable=1` is unsafe for a database that may change concurrently, and a
  global rollback-journal conversion would alter all database writers

Consequence:

- a separate exact-hash, no-network oneshot uses SQLite's online-backup API
  under the existing runtime identity
- only that narrow helper receives write scope over the validated source
  directory needed for WAL sidecar cooperation
- the helper validates the copied schema/invariants, converts the copy to
  rollback-journal mode, flushes it, and atomically replaces the last snapshot
- recognized open/busy failures receive at most four bounded retries; schema,
  integrity, metadata, and path failures remain immediate hard failures
- failed generation leaves the last valid snapshot untouched, and the outbox
  service is ordered after and requires successful fresh snapshot generation
- the existing outbox keeps network isolation and write scope only to its own
  ready/delivered state; sender, collector, schema, model, and dashboards do not
  change
- production acceptance requires a protected predecessor, explicit first run,
  at least 15 natural error-free cadences, conservation/catch-up verification,
  and sanitized publication evidence

## ADR-030 - Snapshot only the outbox projection tables

**Status:** Accepted; supersedes ADR-029's full-database-copy mechanism

The stable outbox snapshot contains only the ten tables read by the result and
deterministic-lifecycle producers. It is built inside one source read
transaction rather than copying the full working database.

Why:

- the full-backup candidate correctly solved WAL readability but copied roughly
  2.8 GB and took 51 seconds on its first production cycle
- repeating that I/O on the outbox cadence is disproportionate to roughly
  8.6 MB of actual projection state
- the two unchanged producers have a closed, testable table dependency set:
  incidents, transitions, five reasoning tables, and three optional triage
  tables that must be present as a complete group
- a single WAL read transaction gives those tables one consistent source view
  without copying raw observations or unrelated application state

Consequence:

- source `quick_check`, foreign-key integrity, required-table presence, and the
  optional all-or-none triage group are verified before copying
- every source column and value from the selected tables is copied into a new
  private rollback-journal SQLite projection; no source SQL text is reused as
  destination DDL and no unselected table is copied
- the destination independently passes integrity, required-table, and
  run/result invariant checks before atomic replacement
- the existing result and lifecycle producers remain byte-exact and validate
  their normal contracts against the projection
- protected-copy evidence reduces 2,815,123,456 source bytes to 8,572,928 bytes
  in two seconds while reproducing 652 results and 1,473 incidents
- the guarded upgrader must wait for the long-boot timer's immediate first
  scheduled cycle rather than assuming enablement is quiescent
- the sender remains unable to access the original live database; its installer
  and verifier resolve that isolation target through the validated snapshot
  configuration without changing the installed sender sandbox

## ADR-031 - Hidden AI review admits only bounded uncovered-event positives

**Status:** Accepted and active

The managed reasoning owner may review important canonical events only after
deterministic incident ownership has established that they are uncovered. A
validated positive can bridge into an ordinary deterministic incident; model
output never owns that incident's identity, lifecycle, recurrence, or
resolution.

Why:

- deterministic coverage cannot anticipate every meaningful event code;
- a bounded side channel provides human-visible coverage without creating a new
  operator-facing event class or bypassing the existing NOC workflow;
- preserving strict admission and replay rules keeps model failure from
  fabricating incident truth.

Consequence:

- eligibility is limited to canonical events with no deterministic incident
  evidence; deterministic correlation remains first in the flow;
- batches are signature-bounded, invoke at most one local model call per
  cadence, and remain pending when Gemma is unavailable or invalid;
- only validated positive decisions enter the fixed ordinary incident bridge;
  negative and insufficient decisions remain raw-log evidence only;
- learned exact-event coverage is limited to severity 0–3 after repeatable,
  consistent positive decisions and can select only the same fixed bridge;
- `docs/AI_DETECTION_SIDE_CHANNEL.md` owns the detailed contract and
  `docs/NOC_WORKFLOW.md` owns the resulting operator presentation.
