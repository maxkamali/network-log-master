# GX10 Result Return Transport

## Status

Execution-order item 30 is complete. The collector-side durable acceptance ledger and cross-owner publication correction are active with exact predecessor rollback retained. GX10 has its dedicated writer identity, pin, canonical configuration, and enabled/active recurring timer. First transport/acceptance/ClickHouse provenance, exact replay isolation, same-name divergent-content isolation, 186-test exact GX10 staging, explicit active-state verification, and natural delivery/acceptance/ingestion all pass. The collector retains one distinct quarantine pair for each replay class; new accepted identities remain append-only and each proven accepted raw record has exactly one complete ClickHouse row.

## Replay problem

Each GX10 outbox producer derives deterministic filenames and canonical JSONL payloads. The active sender can therefore retry exactly. The unsafe window is:

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

The active sender uploads the already-validated local ready file under its unchanged deterministic basename. It never generates a second transport identity or rewrites content during retry. Only after the transport client reports successful completion may it atomically move the local file from `ready` to `delivered` under the existing shared outbox lock.

`delivered` means transport completion, not proven collector ingestion. Collector gate failures, rejected files, Vector ingestion, and ClickHouse row/provenance evidence remain independent end-to-end gates. The sender must retain bounded logs/metrics that expose retries and failures without result content.

## Sender core

The repository core independently validates the outbox root/ready/delivered layout, shared lock, every ready and delivered file, exact service ownership/group/modes/links, 256-KiB bounds, canonical JSON, exact top-level contracts, producer identity, deterministic filenames, and timezone-aware timestamps before selecting work. It accepts exact legacy/current single-record AI result files and strict multi-record `incident_lifecycle` batches. New AI files and every lifecycle row require nonempty bounded Device identity. It sends at most one file per invocation, oldest embedded timestamp first with filename as a stable tie-breaker.

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

Eight management tests cover config-last installation, failure cleanup, partial-state refusal, absence of an SFTP execution path, optional public-key comment normalization, exact captured-legacy-runtime derivation, real canonical configuration rendering, and strict inactive-versus-active timer-state verification. The resulting 186-test GX10 suite passes locally; the prior 185-test configured-inactive tree also passed from exact GX10-staged bytes. The production attempts safely exposed and corrected the optional-comment, historical-runtime, and missing-import assumptions without leaving configured targets. The verifier supports either the clean-rebuild JSON or only the captured fetcher with its published SHA-256, strict root/mode/link metadata, AST-literal endpoint/key extraction, service-owned input metadata, private-home containment, and an explicit active mode that still requires the oneshot service idle with zero restarts.

The matching collector authorizer is independently guarded. It accepts exactly one root-owned public Ed25519 input, refuses key duplication, preserves the complete predecessor `authorized_keys` bytes in a root-only mode-`0600` backup, atomically appends only the new line, and runs `sshd -t` without reloading or restarting SSH. Any failure after publication restores the exact predecessor and removes attempt-created backup state. An exact already-authorized key is idempotently reusable and, when the protected backup exists, must equal the exact backup plus that single line. Five synthetic append/reuse/duplicate/private-input/rollback tests pass locally and from exact bytes staged on the collector runtime.

## Configured-inactive production checkpoint

At this checkpoint, the dedicated authorization and all GX10 private inputs were installed and independently verified. Exact idempotent configuration reuse passed. Temporary key inputs were removed after the installed GX10 identity matched the collector authorization. The sender timer remained disabled; exactly one bounded manual service cycle invoked SFTP and moved one ready file to delivered. The active outbox and all prior deterministic schedules remained healthy; the collector result gate, Vector, ClickHouse, SSH configuration, authorization metadata, and exact predecessor-backup relation passed.

## Bounded first-live and replay plan

This plan was executed successfully before recurring activation:

1. Keep the sender timer disabled. Capture the oldest ready filename, exact digest, and relevant ClickHouse/collector-ledger baseline privately without printing content or identifiers.
2. Start exactly one sender service cycle manually. Require success, zero restarts, exactly one ready-to-delivered transition, unchanged bytes/name, and no second send.
3. Wait only for the existing collector gate and Vector cadences. Require one new immutable acceptance-ledger row bound to the exact name/digest, no rejection, and exactly one ClickHouse row whose stored `raw_json` is byte-equivalent to the canonical sent line and preserves the complete versioned provenance contract.
4. Reverify sender disabled/inactive, outbox cardinality, correlation/reasoning zero lag, original pipeline health, collector gate, Vector, and ClickHouse. Publish the first-live checkpoint before replay.
5. Upload the exact delivered bytes/name once more through the same fixed writer credential without altering local delivered state. Require collector classification as exact already-accepted replay, no new acceptance-ledger row, and no second ClickHouse row.
6. Upload one bounded same-name divergent derivative created only in protected temporary storage. Require conflict quarantine, no acceptance-ledger mutation, no ClickHouse row, and immediate deletion of the temporary derivative. Reverify all schedules and publish closure before considering recurring sender activation.

The first manual sender cycle completed transport and local delivery exactly as planned. Collector acceptance then exposed one Linux ownership boundary absent from the same-user synthetic tests: `fs.protected_hardlinks` prevents the unprivileged gate account from hard-linking the writer-owned incoming inode. The file remained incoming and the ledger/ready/rejected states remained empty. The timer was stopped to isolate retries.

The corrected gate copies validated bytes into a gate-owned, fsynced ready-directory partial, revalidates both source and copy against the original evidence, uses a same-owner no-overwrite hard link only as the atomic publication step, persists ready, removes incoming, then removes the marker. A crash leaves a recognizable two-link ready/marker state; recovery accepts only that exact inode relation and exact incoming bytes before completing cleanup. Eleven local and eleven collector-runtime tests pass, including first acceptance with a deliberately different ready inode and interruption recovery.

The exact correction was installed under a new root-only predecessor backup while the gate timer was stopped and the settled incoming file remained unchanged. One explicit gate cycle accepted it, created exactly one immutable ledger row and one ready file, and restored the enabled/active timer. Private comparison proves GX10 delivered, ledger, and collector ready names/digests are identical. Sender/outbox/correlation/reasoning/original-pipeline and collector gate/Vector/ClickHouse service health all pass.

After explicit authorization, the existing read-only ClickHouse account was supplied through a no-echo terminal directly to a collector-local verifier and retained only in process memory. The query returned exactly one row whose server-computed digest over `raw_json` plus its newline matched the accepted ready bytes. That same row matched the exact byte length and every thin projected scalar/array column checked against its own raw JSON. Local canonical validation required the complete version-1 top-level result contract and exact complete provenance-key shape. No credential, private identifier, hash, result content, or provenance value was printed or stored by the verifier.

After the first-live closure was published, a bounded helper imported and hash-validated the exact installed sender core/configuration, derived and dropped to the installed private service identity, locked the shared outbox, and uploaded the sole delivered file once under its unchanged basename. It did not rename, rewrite, or recreate local state. The normal collector cadence first left the young file waiting, then quarantined the settled file with the exact already-accepted reason. Incoming returned to zero; ready and the immutable ledger remained one; one replay payload/reason pair was isolated; and the matching ClickHouse row count remained exactly one. Both hosts' complete configured-inactive postchecks passed afterward.

After exact-replay closure was published, the same installed-identity/core/configuration validation and shared lock protected a one-time divergent probe. Initial lock contention with the normal producer failed before derivative creation or transport. The retry created a protected temporary same-name record, changed only one bounded collector-valid display field, validated the resulting canonical bytes, uploaded once, revalidated the unchanged original delivered file, and synchronously removed all temporary storage. The natural collector cadence quarantined it specifically as a durable-acceptance conflict. Incoming returned to zero; rejected evidence now contains exactly one exact-replay pair and one conflict pair; ledger/ready remain one; and ClickHouse still contains exactly one matching row. Complete postchecks passed on both hosts with the sender timer disabled.

The public verifier then gained an explicit active configured-state mode and passed 186 tests locally. An initial GX10 stage omitted the repository-relative collector sibling and failed only the 11 cross-boundary imports; no production state was touched. The corrected exact published repository layout passed all 186 tests on GX10. Exact inactive full preflight passed before `systemctl enable --now` changed only the sender timer. Immediate active verification passed and the first natural cycle moved one file. Two more natural cycles followed, for delivered `1 -> 4` with the active producer/outbox remaining internally consistent. The first natural result then settled, created the second immutable ledger/ready identity, and was proven as the second exact complete ClickHouse row; the next two natural files remained normally in flight at the activation checkpoint. Sender restarts remained zero and every preexisting schedule/service passed.

Item 33 later added the backward-compatible Device projection. Exact predecessor copies were retained, existing ready/delivered bytes were reused without rewrite, the producer/sender wrappers were updated to exact new hashes, and the current 192-test GX10 suite passes. Replay identity, filenames, provenance, deterministic incident state, and the write-only transport boundary remain unchanged.

Item 34 added the independent changed-incident producer, strict lifecycle batch validation, collector-exclusive lifecycle routing, and deterministic NOC presentation. The first production pass exported 804 incidents in nine bounded files; all were delivered through the existing sender and ingested without any lifecycle row entering `ai_updates`. Natural scheduled changes continued through the same path. The active installed outbox and sender verifiers pass, both timers remain enabled/active, and existing AI-result bytes and identities were not rewritten.

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

1. `DONE` — publish and independently verify the configured-inactive production checkpoint and bounded plan.
2. `DONE` — transmit exactly one file and prove collector acceptance, Vector/ClickHouse ingestion, complete `raw_json` provenance, local delivered transition, and all preexisting schedule health.
3. `DONE` — prove an exact replay creates no second acceptance or ClickHouse row and is quarantined distinctly.
4. `DONE` — prove a controlled same-name divergent file remains isolated with a distinct conflict reason and no new acceptance or ClickHouse row.
5. `DONE` — explicit active-schedule verification passes 186 local and exact GX10-staged tests; only the recurring timer was enabled; three natural deliveries, first natural collector acceptance/ClickHouse ingestion, zero sender restarts, unchanged replay evidence, and healthy preexisting schedules passed.

The separate item-31 production/repository closure audit also passes: active delivered/accepted/in-flight cardinality conserved exactly, every accepted result had one complete ClickHouse row, both hosts and all repository suites/sanitation passed, and rollback/quarantine evidence remained preserved.
