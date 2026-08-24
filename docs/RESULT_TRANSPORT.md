# GX10 Result Return Transport

## Status

Execution-order item 30 remains in progress. The collector-side durable acceptance ledger is active with exact predecessor rollback retained. The sender core and inactive managed package pass 178 local tests plus the filesystem contract and the same 178 tests from exact GX10-staged bytes. The package is not installed; every sender transport test was injected, and no private config, writer credential, or result transmission exists.

## Replay problem

The GX10 result producer derives one deterministic filename and canonical JSONL payload per successful reasoning run. A future sender can therefore retry exactly. The unsafe window is:

1. the remote upload completes
2. the sender is interrupted before moving the local file from `ready` to `delivered`
3. the next sender cycle uploads the same name again

The prior collector gate rejected a duplicate only while a same-name file remained in its ready directory. If that ready file was later removed, the same filename could be accepted again and Vector could insert it into ClickHouse again. The current ClickHouse result table is not itself a file-identity deduplication boundary.

## Durable collector acceptance

The candidate gate creates `.accepted-v1.sqlite3` inside the protected ready directory. Vector reads only `*.jsonl`, so the ledger and any short-lived SQLite journal are outside its source glob.

Each immutable ledger row stores:

- basename-only JSONL filename
- lowercase SHA-256 of exact file bytes
- byte size and validated record count
- timezone-aware acceptance timestamp

The gate verifies ledger ownership, mode `0640`, single-link metadata, schema version, exact columns, exact immutable triggers, SQLite quick check, and every row before processing incoming files. Rows cannot be updated or deleted through SQLite.

At startup the gate validates every existing ready JSONL file. Missing rows are inserted before incoming enumeration; an existing row with different file evidence fails the entire service. This bootstraps historical ready files and recovers a crash after ready publication but before ledger commit.

First acceptance uses this durable order:

1. validate stable incoming metadata and exact bytes
2. create the same-inode ready name without overwriting an existing destination
3. persist the ready directory
4. remove the incoming name and persist the incoming directory
5. insert and synchronously commit the immutable acceptance row
6. persist the ready directory again

If interruption occurs between creating the ready name and removing the incoming name, the next cycle accepts only the explained two-link same-inode state, removes the incoming link, and resumes reconciliation. Unexplained hard links fail closed.

## Duplicate outcomes

- Same filename and exact accepted digest/size/count: quarantine as an exact already-accepted replay.
- Same filename with different evidence: quarantine as a conflict with durable acceptance.
- Existing ready file with evidence different from its ledger row: fail the gate service before processing incoming files.
- Invalid input: quarantine without creating an acceptance row.

Exact replay is operationally safe and expected after sender interruption. It is still quarantined so collector operators can distinguish transport retries from first acceptance. A divergent replay is a stronger integrity finding.

## Sender acknowledgment contract

The future sender must upload the already-validated local ready file under its unchanged deterministic basename. It must never generate a second transport identity or rewrite content during retry. Only after the transport client reports successful completion may it atomically move the local file from `ready` to `delivered` under the existing shared outbox lock.

`delivered` means transport completion, not proven collector ingestion. Collector gate failures, rejected files, Vector ingestion, and ClickHouse row/provenance evidence remain independent end-to-end gates. The sender must retain bounded logs/metrics that expose retries and failures without result content.

## Sender core

The repository core independently validates the outbox root/ready/delivered layout, shared lock, every ready and delivered file, exact service ownership/group/modes/links, 256-KiB/one-line bounds, canonical JSON, exact top-level contract, versioned producer identity, run-derived filename, and timezone-aware timestamps before selecting work. It sends at most one file: the oldest embedded result timestamp, with filename as a stable tie-breaker.

Its SFTP subprocess uses a fixed executable and argument vector without a shell. Batch mode, identities-only behavior, password and keyboard-interactive refusal, strict supplied known-host checking, disabled global known hosts, one connection attempt, bounded connection/keepalive behavior, and a total process timeout are mandatory. The upload batch preserves the exact local absolute path bytes and unchanged remote basename. Process output is captured and never included in sender error messages.

Transport failure leaves ready unchanged. After transport success, the sender revalidates the source and atomically renames it into delivered under the shared producer/sender lock, then synchronizes both directories and postvalidates the exact bytes. An injected interruption after transport success left ready unchanged; the next cycle issued the exact same upload batch and then completed the local transition.

Eleven local and eleven exact GX10-staged tests cover strict command construction, exact-byte/name movement, one-file bound, oldest-first ordering, no-op, transport failure isolation, post-transport interruption/retry, duplicate state, divergent content, private-file metadata, shared-lock contention, and delivered-state validation. All transports are injected test doubles; the core has never contacted the collector.

## Inactive managed package

The managed package adds:

- an exact-hash runner that accepts only one strict root-owned/group-readable JSON configuration and passes only parsed values to the sender core
- a `ConditionPathExists` oneshot with network availability, 45-second total service bound, no capabilities, no privilege gain, protected system, home, kernel, and control state, restricted process view/namespaces/SUID, and only Unix/IPv4/IPv6 address families
- a dynamic systemd drop-in derived from the already-installed outbox service/config that grants write access only to the actual outbox, read-only access only to future sender config/private inputs, and makes the reasoning database inaccessible
- a nonpersistent one-minute timer that the installer explicitly leaves disabled/inactive
- a nonactivating installer that requires the active outbox boundary, exact empty sender target state, separate absent result-writer identity/known-hosts/config, and exact sources before installing only public code/units/drop-in
- an independent staged verifier that rederives identity/paths and requires exact installed bytes, drop-in, unit states, active outbox, absent private inputs, zero sender restarts, and fixed SFTP executable metadata
- complete created-artifact cleanup and systemd reload after any postinstall verification failure

The public example contains only documentation-domain values and reserved writer filenames. It is never installed. The result-writer key is structurally required to be separate from the existing spool-reader key.

## Passed repository/copy gates

The 11 focused tests prove:

- first acceptance and durable identity creation
- preexisting ready-file bootstrap
- exact replay while ready exists
- exact replay after ready removal
- divergent replay after ready removal
- malformed rejection without acceptance
- immutable ledger update/delete refusal
- ledger mode tamper refusal
- ready/ledger divergence refusal
- crash after ready publication before ledger commit
- crash between no-overwrite link and incoming unlink

The exact candidate passed the same suite on the collector's Linux/Python runtime from temporary storage. A metadata-only preflight proved the live gate still matched the published predecessor, its timer was enabled/active with zero restarts, the service was idle, all three result spool directories contained zero files, and no acceptance ledger existed.

After GitHub independently matched the published candidate, the guarded upgrader stopped only the gate timer, repeated the exact predecessor/candidate and empty-spool checks, retained mode-private exact rollback bytes, atomically installed the candidate, and ran one empty bootstrap cycle. Independent verification proved the exact installed/backup hashes, service-owned/vector-group mode-`0640` single-link ledger, version/schema/quick-check/immutable triggers, zero rows/files, healthy Vector/ClickHouse, enabled active timer, successful service, and zero restarts. A later natural cadence repeated the exact empty no-op state.

## Remaining gates

1. Publish and independently verify the inactive managed-package checkpoint.
2. Guardedly install only public sender code/units/drop-in on GX10 and independently require timer disabled, service inactive, config/key/known-hosts absent, active no-network outbox, and healthy preexisting schedules.
3. Build private writer inputs from the operator-authorized existing access boundary, install them separately while the sender remains disabled, and verify strict host/key/config state without transmitting.
4. Transmit a bounded first file and prove collector acceptance, Vector/ClickHouse ingestion, complete `raw_json` provenance, local delivered transition, and all preexisting schedule health.
5. Prove an exact replay creates no second ClickHouse row and a controlled malformed/divergent file remains isolated.
