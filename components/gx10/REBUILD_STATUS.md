# GX10 Rebuild Status

## Status

Live-system rediscovery is `DONE`.

Public clean-machine reconstruction and operator documentation are `DONE` under execution-order item 12.

Clean-machine GX10 validation is `WAIVED BY OPERATOR` because no disposable Ubuntu 24.04 arm64 GX10-class target is available. It remains empirically unverified.

The later collector-normalizer production integration completed its forward-only GX10 handoff cutover on 2026-08-24. The unchanged fetch/ingest pipeline reached exact collector-ledger parity across the reviewed multi-cadence window. The repository now contains the validated item-24 replacement for transitional vendor/message reparsing: an unscheduled canonical schema-version-1 projector with local suppression-policy overlay and guarded exact-hash live replacement/rollback. Live replacement remains the next step at this checkpoint.

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
- canonical projection remains intentionally unscheduled
- exact pinned application-package installer and fail-closed platform verifier
- exact operator-supplied Ollama binary installer with no automatic activation
- guarded offline model-store importer with source/target content hashing, no overwrite, and resumable exact reuse
- sanitized Ollama unit preserving the captured service contract
- offline six-manifest/model-blob verifier and active loopback runtime verifier
- live read-only `GX10_PLATFORM_VERIFY=PASS` and `GX10_OLLAMA_VERIFY=PASS`
- complete preactivation verifier with reference-like/nonempty-state refusal
- exact installed-source, configuration, SQLite, filesystem, systemd, and effective-limit verification
- dual-confirmation activator with full offline blob hashing, ordered enablement, and failure rollback
- only Ollama and the fetch/ingest timer are activated; canonical projection remains unscheduled
- complete clean-machine operator runbook
- final structural, syntax, generated/private-artifact, IPv4/public-safety, unit-test, and filesystem-contract audit
- 49 synthetic tests passing
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`

The bootstrap refuses an existing application database and is not executed against the working reference system.

The activation flow also refuses nonempty spool directories, any application-state rows, SQLite sidecar state, altered schema or suppression state, active/enabled runtime units, unexpected unit drop-ins, and installed artifacts that differ from the repository. Clean-machine activation has not been executed because no disposable GX10-class validation target is available.

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

The currently proven automatic chain is:

`timer -> fetch -> ingest`

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

## Historical deterministic enrichment and canonical projection

The captured deterministic classifier is version 3. Its source behavior, schema writes, vendor/event classification, repeat handling, and complete two-rule active suppression corpus are captured in items 12G and 12H.

The executable exists, but rediscovery found:

- no reference from the fetch/ingest service
- no other systemd reference
- no cron reference
- no retained direct invocation evidence in bounded shell history

The normalized production handoff made reparsing those same vendor messages a duplicate and potentially divergent authority. The item-24 replacement therefore projects exact normalized event fields as classification version 4, retains the two local enabled suppression rules, preserves all version-3 history, and advances through an atomic cursor. It remains unscheduled; automatically adding it to the pipeline would be a separate implementation change.

An on-server copy rehearsal scanned `949845` stored events, projected `2781` exact canonical rows, preserved `24207` historical version-3 rows, applied local suppression to `1984` rows, and projected zero rows on the second run. The live database was unchanged.

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

## Preserved rediscovery conclusions

Do not silently change these findings during reconstruction:

- automatic application behavior is `timer -> fetch -> ingest`
- the captured enrichment was unscheduled; its canonical projector replacement also remains unscheduled
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
