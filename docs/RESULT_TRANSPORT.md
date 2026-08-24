# GX10 Result Return Transport

## Status

Execution-order item 30 remains in progress. The collector-side durable acceptance ledger is active with exact predecessor rollback retained. The sender core/package passes 178 local and 178 exact GX10-staged tests. The exact package is installed on GX10 in its independently verified inert state: timer disabled, service inactive, configuration/identity/writer-known-hosts absent, and no transmission. Every sender transport test remains injected.

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

The guarded working-system inactive install passed from the exact published/staged package. Independent verification rederived the historical private outbox/runtime identity without printing it, matched every installed public byte and dynamic drop-in, and required absent config/key/writer-known-hosts plus disabled/inactive sender state. The active outbox independently passed at 20 results, 20 ready, zero delivered. Correct private-runtime verification passed correlation and reasoning at zero lag, and a separate identity-withholding check proved the original pipeline timer remained enabled/active with zero service restarts.

## Configured-inactive candidate

The separate configurator derives endpoint and outbox values only from already validated private runtime state. It accepts a root-owned mode-`0400`/`0600` Ed25519 input from `/run`, refuses reuse of the existing read-only spool identity, copies the already pinned host entry into a separate writer known-hosts file, and installs the canonical sender configuration last. The writer identity and writer known-hosts are service-owned mode `0600`; the configuration is root-owned, service-group-readable mode `0640`.

Every target must be either wholly absent or wholly present and independently valid. Partial state is refused. New installation uses no-overwrite publication and directory synchronization; a later validation failure removes only files created by that attempt. Existing exact state is idempotently reusable, while divergent state is refused. Both the configurator and verifier use a fixed `/usr/bin/ssh-keygen`; neither invokes SFTP. The verifier rederives the installed paths, role, endpoint, pinned-host lookup, canonical bytes, metadata, exact installed public package, active outbox, and disabled/inactive zero-restart sender state.

Four new management tests cover config-last installation, failure cleanup, partial-state refusal, and absence of an SFTP execution path. The resulting 182-test GX10 suite and filesystem/package contracts pass locally. The same exact changed bytes pass all 182 tests and the filesystem contract from the retained temporary GX10 candidate tree with exact SHA-256 parity. No live private input has been installed by this gate.

The matching collector authorizer is independently guarded. It accepts exactly one root-owned public Ed25519 input, refuses key duplication, preserves the complete predecessor `authorized_keys` bytes in a root-only mode-`0600` backup, atomically appends only the new line, and runs `sshd -t` without reloading or restarting SSH. Any failure after publication restores the exact predecessor and removes attempt-created backup state. An exact already-authorized key is idempotently reusable and, when the protected backup exists, must equal the exact backup plus that single line. Five synthetic append/reuse/duplicate/private-input/rollback tests pass locally and from exact bytes staged on the collector runtime.

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

1. Publish and independently verify the configured-inactive candidate.
2. Publish the exact-backup collector authorizer, then generate/install a dedicated writer identity, install only its matching collector authorization, bind the separate pinned known-host file, retain exact rollback evidence, and pass configured-inactive production verification with no SFTP invocation.
3. Publish the bounded first-live/replay plan, then transmit one file and prove collector acceptance, Vector/ClickHouse ingestion, complete `raw_json` provenance, local delivered transition, and all preexisting schedule health.
4. Prove an exact replay creates no second ClickHouse row and a controlled malformed/divergent file remains isolated.
