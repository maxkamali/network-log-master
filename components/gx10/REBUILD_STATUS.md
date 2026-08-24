# GX10 Rebuild Status

## Status

Live-system rediscovery is `DONE`.

Public clean-machine reconstruction and operator documentation are `DONE` under execution-order item 12.

Clean-machine GX10 validation is `WAIVED BY OPERATOR` because no disposable Ubuntu 24.04 arm64 GX10-class target is available. It remains empirically unverified.

The later collector-normalizer production integration completed its forward-only GX10 handoff cutover on 2026-08-24. The unchanged fetch/ingest pipeline reached exact collector-ledger parity across the reviewed multi-cadence window. Item 24 then replaced the unscheduled live transitional vendor/message reparser under its exact captured hash with the canonical schema-version-1 projector. The replacement has zero scheduler references, the live database was unchanged, all historical version-3 rows remain, and a root-only exact legacy rollback copy is retained.

Item 25 is complete. The deterministic incident engine passed private working-database-copy rehearsal, cursor-reset replay, and an independent exact-state rebuild. Its three-table append-only extension and exact engine artifact were installed on the working GX10 system under a protected pre-migration backup before the separately gated item-26 activation.

Item 26 is complete. The separately managed offline `projection -> incident` service/timer passed private working-database-copy rehearsal, inactive working-system installation, fail-closed activation handling, full initial production backfill, active verification, and three independent scheduled zero-lag cadences. It preserves fetch/ingest unchanged, enforces exact stage hashes and single-cycle locking, converges both cursors in bounded passes, exposes structured health counts, and retains guarded backfill-before-enable activation, verification, and state-preserving disable controls.

Item 27 has a published deterministic wake-policy/compact-packet candidate, guarded existing-system migration, and passing protected production-state-copy rehearsal. Initial execution over a current snapshot built four bounded packets for the four active incidents, immediate rerun and incident-cursor replay were exact no-ops, a second copy reproduced the exact packet digest, and synthetic threshold/lifecycle/tamper/empty-rollback behavior passed. The migration requires the exact base-plus-incident schema and candidate hashes, creates a protected pre-reasoning SQLite backup, installs no schedule, and rolls back only while packets remain empty. Fourteen focused tests pass within the 94-test GX10 suite. No item-27 artifact, schema, packet, invocation, Ollama call, or result producer exists on the working system.

The private copy full backfill scanned `954790` stored events, projected `7726` canonical rows, suppressed `5830`, and produced `22` incidents, `425` evidence rows, `463` transitions, and `5` active incidents in one 4.3-second managed pass with zero cursor lag. The next pass was a complete no-op. A synthetic appended canonical event advanced both exact watermarks. Malformed projection input rolled back its batch and prevented incident execution; forced incident failure preserved the durable projection and all prior incident state. The working database remained unchanged.

The working-system inactive install placed and verified exact projector, incident, runner, service, and timer bytes plus a protected private database/identity binding. The first activation attempt failed before application execution because the clean-rebuild write path did not exist on this historical installation. Correlation remained disabled and the database unchanged. A published portability correction atomically bound write scope only to the validated database parent; a separate cleanup correction cleared stale failed-unit state after preserving the failure evidence.

The production backfill then projected `8712` canonical rows, applied suppression to `6622`, and created `23` incidents, `477` evidence rows, and `519` transitions with `3` active incidents. Both watermarks reached event ID `955874` with zero lag before the new timer was enabled. Three later scheduled gates reached event IDs `956240`, `956338`, and `956413`, each with zero projection/incident lag and zero service restarts. Third-gate state contained `9251` canonical rows, `24` incidents, `508` evidence rows, `551` transitions, and `4` active incidents. A final prepublication verification later reached event ID `956995` with both lags still zero and both timers active. The existing fetch/ingest timer advanced during the same window.

This document is the component recovery authority for the active GX10 milestone. `docs/CURRENT_STATE.md` remains the authority for project-wide execution order and the single `NEXT` item.

## Reconstruction progress

Completed:

- public-safe operator-input template
- neutral dedicated runtime identity and fixed path-role contract
- guarded clean-machine filesystem/SSH-material bootstrap
- structural and public-safety validator
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- public-safe fetch/ingest sources plus the canonical normalized-field projector
- protected runtime configuration loader and fail-closed renderer
- 27/27 live-to-public function AST parity
- deterministic SQLite initializer matching all 5 recovered table DDL hashes, 13 indexes, and 3 foreign keys
- exact two-pattern functional suppression seed with neutral nonfunctional metadata
- captured ingest schema migrator and canonical projection schema validator proven non-mutating against the initialized schema
- 18 synthetic configuration/application/database tests passing
- complete sanitized service/timer capture preserving fetch-then-ingest order, cadence, and all live hardening directives
- clean-machine application/unit installer with no-overwrite, ownership/mode preflight, systemd verification, and no automatic activation
- canonical projection and deterministic incident processing use a separate managed offline schedule
- deterministic incident schema/engine candidate with stable instance identity, append-only evidence/transitions, event-time lifecycle, repeat accounting, rolling context, and two-layer replay protection
- guarded existing-database migration with exact schema/artifact hashes, protected SQLite backup, zero-scheduler-reference enforcement, and empty-state-only rollback
- clean-machine initialization and verification include the incident extension; existing-system managed correlation installation/activation is separately gated
- exact pinned application-package installer and fail-closed platform verifier
- exact operator-supplied Ollama binary installer with no automatic activation
- guarded offline model-store importer with source/target content hashing, no overwrite, and resumable exact reuse
- sanitized Ollama unit preserving the captured service contract
- offline six-manifest/model-blob verifier and active loopback runtime verifier
- live read-only `GX10_PLATFORM_VERIFY=PASS` and `GX10_OLLAMA_VERIFY=PASS`
- complete preactivation verifier with reference-like/nonempty-state refusal
- exact installed-source, configuration, SQLite, filesystem, systemd, and effective-limit verification
- dual-confirmation activator with full offline blob hashing, ordered enablement, and failure rollback
- Ollama, the original fetch/ingest timer, and the separately disableable correlation timer are active; no local-reasoning caller is scheduled
- complete clean-machine operator runbook
- final structural, syntax, generated/private-artifact, IPv4/public-safety, unit-test, and filesystem-contract audit
- 94 synthetic tests passing
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`

The bootstrap refuses an existing application database and is not executed against the working reference system.

The activation flow also refuses nonempty spool directories, any application-state rows including incident state, SQLite sidecar state, altered schema or suppression state, active/enabled runtime units, unexpected unit drop-ins, and installed artifacts that differ from the repository. Clean-machine activation has not been executed because no disposable GX10-class validation target is available.

## Public-safety boundary

The repository intentionally omits deployment-specific addresses, usernames, private hostnames, SSH keys, known-hosts contents, credentials, private paths, and production event data.

Reconstruction must use operator-supplied values and public-safe templates. Historical identity-bearing names should not be copied into the public implementation.

## Rediscovery closure

Items 12A through 12N are durably journaled in `docs/PROJECT_JOURNAL.md`.

The final live closure audit passed with:

- exactly one match for each of the three known application executable hashes
- exactly one match for the pipeline service-unit hash
- exactly one match for the pipeline timer-unit hash
- the timer active and enabled
- the service static and `Type=oneshot`
- the service still directly referencing fetch and ingest
- zero systemd or cron references to deterministic enrichment
- both required external executables present and package-owned
- unchanged post-audit hashes
- `gx10_rediscovery_live_closure_audit=PASS`

No pipeline component was executed and neither reference system was modified.

## Platform and runtime contract

Captured baseline:

- Ubuntu 24.04.4 LTS
- arm64
- NVIDIA GB10 platform
- captured NVIDIA driver and CUDA runtime/compiler versions in the item-12A journal entry
- Python `3.12.3`
- Python SQLite runtime `3.45.1`
- `python3.12-minimal` version `3.12.3-1ubuntu0.15`
- zero third-party Python imports across the three custom applications

Required external application tools:

- `sftp` from `openssh-client` version `1:9.6p1-3ubuntu13.18`
- `zstd` from `zstd` version `1.5.5+dfsg2-2build1.1`

## Scheduling and service contract

The original recovered automatic chain remains:

`timer -> fetch -> ingest`

The separately implemented production chain is:

`correlation timer -> canonical projection -> deterministic incident engine`

The pipeline service is a hardened non-root oneshot with:

- static enablement state
- `DynamicUser=no`
- `PrivateTmp=yes`
- `ProtectHome=yes`
- `ProtectSystem=strict`
- `NoNewPrivileges=yes`
- `UMask=0027`
- exactly two writable path roles: application state and spool
- no inline environment values or environment files

The timer contract includes:

- `OnBootSec=2min`
- `OnUnitInactiveSec=1min`
- `AccuracySec=5s`
- no calendar schedule
- no randomized delay
- `Persistent=no`
- `RemainAfterElapse=yes`

Known provenance:

- fetch: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- ingest: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- deterministic enrichment: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`
- canonical projection candidate: `f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079`
- service unit: `0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`
- timer unit: `5371995539846d4cca6014a70548e95c942e9f601d0736b06f4bda61c1ccc0f5`

## Fetch and ingest contract

The fetch component contract includes:

- read-only SFTP backlog discovery and retrieval
- bounded catch-up by remote hour
- strict filename eligibility
- known-hosts and dedicated private-key inputs
- temporary download followed by Zstandard integrity verification
- SHA-256 calculation
- atomic publication into the incoming spool
- durable scan cursor/state in SQLite

The ingest component contract includes:

- streaming Zstandard decompression
- JSONL validation and byte-oriented record limits
- replay-safe source-file and record identity
- transactional/idempotent ingest behavior
- processed/failed state handling captured in items 12F and 12M

Exact private paths and transport identities remain operator-supplied.

## SQLite contract

The effective application schema is fully captured from read-only immutable SQLite metadata:

- 5 application tables
- 13 explicit indexes
- 3 foreign-key relationships
- 0 unexpected schema objects

Tables:

- `agent_state`
- `source_files`
- `recent_events`
- `event_enrichment`
- `suppression_rules`

No surviving base-schema/bootstrap initializer was found in the bounded search, and SQLite carries no nonzero application or migration version identifier.

Reconstruction must create the captured effective schema directly. It must not invent historical migration provenance and present it as discovered behavior.

The item-25 target-state extension is deliberately separate from that recovered baseline. It adds `incidents`, `incident_evidence`, and `incident_transitions`, five explicit indexes, and four append-only triggers. The existing-system guard requires the exact recovered base before applying the extension and does not rewrite historical rows.

## Historical deterministic enrichment and canonical projection

The captured deterministic classifier is version 3. Its source behavior, schema writes, vendor/event classification, repeat handling, and complete two-rule active suppression corpus are captured in items 12G and 12H.

The executable exists, but rediscovery found:

- no reference from the fetch/ingest service
- no other systemd reference
- no cron reference
- no retained direct invocation evidence in bounded shell history

The normalized production handoff made reparsing those same vendor messages a duplicate and potentially divergent authority. The item-24 replacement therefore projects exact normalized event fields as classification version 4, retains the two local enabled suppression rules, preserves all version-3 history, and advances through an atomic cursor. It remained unscheduled until item 26 added the separately validated managed correlation chain.

An on-server copy rehearsal scanned `949845` stored events, projected `2781` exact canonical rows, preserved `24207` historical version-3 rows, applied local suppression to `1984` rows, and projected zero rows on the second run. The live database was unchanged.

## Deterministic incident candidate

The version-1 candidate consumes only classification-version-4 projections. Correlation identity is derived from canonical family/protocol/entity identity; each recurrence receives a deterministic instance ID bound to its first immutable source observation. Evidence and transitions are append-only, one active instance per correlation key is enforced by SQLite, and mutable incident rows materialize repeat totals, state changes, strongest severity, and 60-minute/180-minute/24-hour context.

Lifecycle is deterministic and event-time based: explicit down-class transitions open immediately, degradation requires repeated adverse evidence within 15 minutes, recovery enters a five-minute quiet state, relapse reopens, and later recurrence creates a new instance. Cursor advancement and incident changes share one transaction, while unique evidence event IDs preserve idempotency even after cursor reset.

The engine neither parses messages nor calls Ollama. Its artifact/schema first passed the unscheduled item-25 installation; item 26 later added only the separate managed runner/service/timer reference.

The private live-copy gate migrated an online SQLite backup, projected `5725` canonical rows from `952789` stored events, preserved `24207` historical version-3 rows, and applied local suppression to `4272` projected rows. Incident processing produced `17` deterministic instances, `311` evidence rows, `341` transitions, and `3` active instances. Normal rerun and cursor-reset replay changed no incident state. A second independent migration/projection/engine run from the protected pre-migration copy produced the exact same state SHA-256 `91e0ba1f8968dbf34480334126aeefc4ab5115861a37d4659e77c48b4cacdfa4`.

The working database retained zero version-4 rows and unchanged scheduling throughout rehearsal. The later guarded unscheduled migration installed exactly three empty incident tables and the exact engine artifact while retaining zero projection/incident cursors and zero scheduler references. One ordinary post-migration fetch/ingest cadence advanced source files from `10503` to `10504` and recent events from `953349` to `953430`, with historical version-3 rows unchanged at `24207` and zero service restarts. Item 26 subsequently completed the separately managed production invocation gate. See `docs/INCIDENT_ENGINE.md` and `docs/MANAGED_CORRELATION.md` for the durable contracts and evidence.

## Ollama and result-return boundary

Ollama is installed, active, enabled, and loopback-only on TCP/11434. Its binary is not owned by a Debian package. Six complete model manifests and all referenced blobs were verified; exact manifests and digests are recorded in item 12L.

Rediscovery found no application-specific network-observability caller of Ollama.

The collector provides a validated write-only AI-result return boundary, but rediscovery found no GX10 producer executable, wrapper, service, or retained transfer command.

The rebuild must reproduce installed infrastructure and proven application behavior without inventing production LLM orchestration or a result producer.

The public package now installs the exact captured Ollama executable from an operator-supplied file, creates the service/model-storage boundary, and verifies the complete captured model inventory. Model blobs are deliberately external to Git and must be populated before activation. Neither installation nor offline verification calls the Ollama API, pulls a model, or runs inference.

## Runtime identity and filesystem contract

Item 12N captures the private runtime-account properties, path-role hashes, ownership classes, and modes without publishing identity-bearing values.

Reconstruction requirements include:

- a dedicated non-login system account and group
- private SSH-material directory mode `0700`
- known-hosts and private-key file modes `0600`
- spool parent/incoming/processed/temporary directory modes `0750`
- application-state parent mode `0750`
- SQLite database mode `0640`
- runtime user/group ownership for private state and transport material

## Preserved rediscovery conclusions and later changes

Do not silently change these findings during reconstruction:

- automatic application behavior discovered during rediscovery was `timer -> fetch -> ingest`; item 26 later added a separate managed `projection -> incident` schedule without changing that original chain
- the captured enrichment had no historical scheduler; its canonical projector replacement remained unscheduled until the separately journaled item-26 activation
- Ollama/model infrastructure is present without an identified observability-pipeline caller
- the collector result-return boundary is present without an identified GX10 producer
- missing historical bootstrap/install provenance is reconstructed from effective contracts, not invented as recovered history

## Reconstruction order

Completed in bounded, journaled subsections:

1. `DONE` — define the public-safe operator input and filesystem/runtime identity contract
2. `DONE` — capture public-safe fetch, ingest, and deterministic-enrichment implementations
3. `DONE` — provide deterministic SQLite schema initialization from the recovered effective schema
4. `DONE` — provide service/timer templates preserving the proven automatic chain and hardening
5. `DONE` — provide Ollama installation/model verification without claiming application orchestration
6. `DONE` — add package, structural, public-safety, and runtime verifiers
7. `DONE` — write the clean-machine operator runbook
8. `WAIVED BY OPERATOR` — clean-machine GX10 validation remains empirically unverified; run it if a disposable target later becomes available

Every completed subsection is durably journaled. The component milestone is closed without laundering unavailable disposable-host validation into a pass.

Do not run clean-machine installers against the working GX10 reference system.
