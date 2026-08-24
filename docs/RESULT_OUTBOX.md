# GX10 Result Outbox

## Status

Execution-order item 30 repository and protected-copy gates pass. The version-1 producer is present at `components/gx10/sbin/build-result-outbox.py` and passed 149 GX10 tests locally and from an exact GX10-staged tree. It is not installed on the working system, has no service or timer, has no result-writer credential, and cannot transmit to the collector.

## Boundary

The producer opens the SQLite working database read-only and projects only `SUCCEEDED` reasoning runs that have their required append-only result row. Terminal failures and `STARTED` reservations never produce files. The producer does not call Ollama, change reasoning state, open a network socket, or make any incident/packet decision.

Every successful run maps to exactly one canonical JSON record and one newline-terminated JSONL file. The filename is versioned and derived from the SHA-256 of the run ID rather than exposing the run ID in the filesystem name. A filename collision fails closed.

The thin collector fields are:

- `timestamp`, `incident_id`, `run_id`, `model`, and `type`
- `status`, `severity`, `first_seen`, `last_seen`, and `occurrence_count`
- `title`, `body`, and `tags`

The complete canonical reasoning result is retained under `result`; it is not reduced to only the thin presentation fields. `provenance` retains the packet/result/request hashes, model version/reference/manifest/config, provider, prompt and output-schema hashes/versions, run attempt/timestamps, and canonical run diagnostics. The collector's existing Vector transform retains the complete input line as `raw_json`.

## Fail-closed checks

Before publication, the producer requires:

- a nonsymlink regular source database and protected nonsymlink outbox directory
- SQLite `quick_check`, foreign-key integrity, required tables, and the run/result invariant
- one read transaction so every projected row comes from one database snapshot
- exact canonical packet/result/diagnostic JSON and matching SHA-256 digests
- matching run/result/packet identity, output-schema version, timestamps, status, and immutable provenance rows
- a single-record file no larger than the collector's 256-KiB file limit
- no unknown, divergent, multiply linked, symlinked, wrongly owned, or wrongly moded outbox entry
- a single nonblocking mode-`0600` producer lock

All target files are mode `0640`. Publication uses a mode-`0600` unique temporary file, file `fsync`, mode normalization, atomic same-directory replacement, directory `fsync`, and exact post-publication validation. Only strictly named producer temporary files with safe ownership/link/mode metadata may be removed during crash recovery. Existing exact files are reused; divergent files stop all new publication during preflight.

Version 1 emits one record per file, so the collector's 100-record-per-file ceiling is satisfied by construction. The complete synthetic suite proves valid mapping, terminal-failure exclusion, exact reuse, divergent-target refusal before other publication, interruption after one file and idempotent resume, stale-partial recovery, unknown-entry refusal, lock contention, digest tamper refusal, and symlink refusal.

## Protected-copy evidence

The exact staged repository tree passed all 149 tests and the GX10 filesystem contract on the GX10 host. A root-only mode-`0600` SQLite online backup then contained 12 packets, 12 terminal runs, 11 successful results, and one preserved failure. The producer created exactly 11 private files. Every file contained one record, met the unchanged collector gate, and had the required metadata. A second run created zero files and exactly reused all 11. The copy byte/hash and reasoning aggregates remained unchanged, all live schedules remained healthy, and no collector transmission occurred.

## Next gate

Do not copy these protected files to the collector. The next item-30 sub-section is an inactive GX10 installation/managed-producer design that preserves this read-only projection and adds an independently verified local ready-directory boundary. Writer-key installation and any live collector transfer remain later explicit gates. Delivery acknowledgment/retry state must be designed before a scheduled sender can safely avoid replay after a successfully transferred local file leaves the ready directory.
