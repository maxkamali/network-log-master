# GX10 Result Outbox

## Status

Execution-order item 30 local producer activation passes after the service-ownership/resume correction. The version-1 boundary passes 159 tests locally and from exact GX10-staged trees. Production has 15 collector-valid ready files for 15 successful results, zero delivered, an active no-network timer, healthy preexisting schedules at zero lag, no result-writer credential, and no collector transmission.

## Boundary

The producer opens the SQLite working database read-only and projects only `SUCCEEDED` reasoning runs that have their required append-only result row. Terminal failures and `STARTED` reservations never produce files. The producer does not call Ollama, change reasoning state, open a network socket, or make any incident/packet decision.

Every successful run maps to exactly one canonical JSON record and one newline-terminated JSONL file. The filename is versioned and derived from the SHA-256 of the run ID rather than exposing the run ID in the filesystem name. A filename collision fails closed. `ready` and `delivered` are protected sibling directories under one outbox root and one shared lock. Each expected file may be present in at most one state. An exact delivered file suppresses ready-file recreation; duplicate or divergent state fails closed.

The thin collector fields are:

- `timestamp`, `incident_id`, `run_id`, `model`, and `type`
- `status`, `severity`, `first_seen`, `last_seen`, and `occurrence_count`
- `title`, `body`, and `tags`

The complete canonical reasoning result is retained under `result`; it is not reduced to only the thin presentation fields. `provenance` retains the packet/result/request hashes, model version/reference/manifest/config, provider, prompt and output-schema hashes/versions, run attempt/timestamps, and canonical run diagnostics. The collector's existing Vector transform retains the complete input line as `raw_json`.

## Fail-closed checks

Before publication, the producer requires:

- a nonsymlink regular source database and protected nonsymlink outbox-root, ready, and delivered directories with the required sibling layout
- SQLite `quick_check`, foreign-key integrity, required tables, and the run/result invariant
- one read transaction so every projected row comes from one database snapshot
- exact canonical packet/result/diagnostic JSON and matching SHA-256 digests
- matching run/result/packet identity, output-schema version, timestamps, status, and immutable provenance rows
- a single-record file no larger than the collector's 256-KiB file limit
- no unknown, divergent, multiply linked, symlinked, wrongly owned, or wrongly moded outbox entry
- a single nonblocking mode-`0600` producer lock

All target files are mode `0640`. Publication into ready uses a mode-`0600` unique temporary file, file `fsync`, mode normalization, atomic same-directory replacement, directory `fsync`, and exact post-publication validation. Only strictly named producer temporary files in ready with safe ownership/link/mode metadata may be removed during crash recovery. Existing exact ready or delivered files are reused; divergent, duplicated, or unexpected state stops all new publication during preflight.

Version 1 emits one record per file, so the collector's 100-record-per-file ceiling is satisfied by construction. The complete synthetic suite proves valid mapping, terminal-failure exclusion, exact ready/delivered reuse, delivered suppression of recreation, duplicate-state refusal, divergent-target refusal before other publication, interruption after one file and idempotent resume, stale-partial recovery, unknown-entry refusal, lock contention, digest tamper refusal, and symlink refusal.

## Protected-copy evidence

The initial exact staged repository tree passed 149 tests and created/reused 11-for-11 collector-valid files from a protected copy. The delivery-state revision passed all 151 tests locally and from a new exact GX10-staged tree. A fresh root-only mode-`0600` online backup then contained 12 packets, 13 terminal runs, 12 successful results, and one preserved failure. The producer created exactly 12 ready files. One was atomically moved to delivered to simulate a future durable acknowledgment. A second run created zero files, reused all 12, reported 11 ready plus one delivered, and did not recreate the delivered file. Every file still passed the unchanged collector gate and the combined content digest was state-location independent. The copy byte/hash and reasoning aggregates remained unchanged, all live schedules remained healthy, and no collector transmission occurred.

## Next gate

The managed package contains an exact-hash runner, an independently disableable oneshot/timer, a guarded inactive installer, and an independent verifier. Its service has `PrivateNetwork=yes`, Unix-socket-only address families, no capabilities, and write scope only to the outbox root. The installer derives the already-proven reasoning service identity and private database path from the installed managed-reasoning boundary, validates the read-only database/result invariant, places empty mode-`0700` ready/delivered directories beneath that validated database parent, leaves the timer disabled/service inactive, and installs no credential.

An exact GX10-staged private-copy rehearsal installed into an isolated root without touching systemd, generated all 12 copy results through the installed runner, reused 11 ready plus one delivered without recreation, preserved the database hash, and removed every managed artifact after a forced post-install verification failure.

The corrected working-system install derived the protected database/root without printing them, installed exact bytes, and independently verified 14 current successful results with zero ready/delivered files. The new timer is disabled, the service is inactive and never invoked, effective private networking/Unix-only/write scope passes, all three preexisting schedules remain healthy, and no credential or transmission exists.

The protected activator now passes 159 local and exact GX10-staged tests plus two full retained-copy rehearsals. It temporarily disables only managed reasoning, hashes all five reasoning tables, runs exactly one local outbox cycle while the outbox timer is disabled, requires an exact post-cycle table digest and one ready file per successful result, enables the outbox timer only after independent verification, and restores reasoning in both success/failure paths.

The first working-system activation safely created 15 ready files, then stopped because the root-run independent verifier incorrectly compared service-owned file UID to its own UID. Failure handling left the outbox timer disabled, restored reasoning active/enabled, retained all exact ready files, and transmitted nothing. The corrected verifier validates against the derived service UID/GID; the activator accepts exact populated-but-disabled state and safely fills only any results added before resume. A new focused ownership test and second protected-copy rehearsal pass.

The corrected working-system resume retained or idempotently filled one file per result, preserved the exact five-table reasoning digest, enabled the outbox timer, and restored reasoning. A bounded closure briefly paused pipeline/reasoning timers, ran deterministic correlation and an idempotent outbox catch-up, restored both timers, and proved all 15 files through the unchanged collector gate with deterministic aggregate digest `65a2b2399018840fe96a3d56291e60ea994e60d12fb8a7fc7ff011bafb2ece9c`.

Three consecutive natural outbox timer cadences passed at approximately 64–65-second intervals without manual service invocation. Each observed 15 results, created zero, exactly reused all 15 ready files, wrote zero bytes, and retained zero delivered/recovered/restarts.

Managed reasoning then naturally advanced from 15 to 16 results. The outbox timer started immediately afterward, created exactly one file, reused the prior 15, wrote only 2378 bytes, and retained zero delivered/recovered/restarts. The prior 15-file digest remained `65a2b2399018840fe96a3d56291e60ea994e60d12fb8a7fc7ff011bafb2ece9c`; all 16 files passed the collector gate and the new aggregate digest is `71955d542f80240fc18b27a481ae65b74f98fa04b7e005e2d9a3e5b646d641be`.

The local-producer milestone is complete. The collector-side durable acceptance ledger is active and closes the upload-success/local-acknowledgment crash window. The sender core/package passes 178 local and 178 exact GX10-staged tests and is installed in its independently verified inert state. No private sender config, writer credential, or transmission exists. Continue with the separately guarded configured-inactive boundary described in `docs/RESULT_TRANSPORT.md`.
