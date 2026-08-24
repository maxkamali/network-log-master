# GX10 Result Outbox

## Status

Execution-order item 30 repository, protected-copy, inactive-package rehearsal, and corrected working-system inactive-install gates pass. The version-1 producer and managed package passed 157 GX10 tests locally and from exact GX10-staged trees. Exact artifacts/configuration and empty ready/delivered directories are installed; the service has never run, the timer is disabled/inactive, no result-writer credential exists, and the boundary cannot transmit to the collector.

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

The protected activator now passes 158 local and exact GX10-staged tests plus a full retained-copy rehearsal. It temporarily disables only managed reasoning, hashes all five reasoning tables, runs exactly one local outbox cycle while the outbox timer is disabled, requires an exact post-cycle table digest and one ready file per successful result, enables the outbox timer only after independent verification, and restores reasoning in both success/failure paths. The rehearsal produced 12-for-12 files with unchanged copy state and simulated systemd only.

Next publish the activator checkpoint and run the exact protected working-system activation. Require one ready file per then-current successful result, zero delivered, unchanged reasoning-table digest, active outbox/reasoning timers, collector-valid files, healthy deterministic schedules, and zero credential/transmission. Writer-key installation and live transfer remain later explicit gates. The later sender and collector gate must still close the upload-success/local-acknowledgment crash window before live replay safety can pass.
