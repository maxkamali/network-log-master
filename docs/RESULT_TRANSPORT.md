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

The active gate maintains `.accepted-v1.sqlite3` inside the protected ready directory. Vector reads only `*.jsonl`, so the ledger and any short-lived SQLite journal are outside its source glob.

Each immutable ledger row stores:

- basename-only JSONL filename
- lowercase SHA-256 of exact file bytes
- byte size and validated record count
- timezone-aware acceptance timestamp

The gate verifies ledger ownership, mode `0640`, single-link metadata, schema version, exact columns, exact immutable triggers, SQLite quick check, and every row before processing incoming files. Rows cannot be updated or deleted through SQLite.

At startup the gate validates every existing ready JSONL file. Missing rows are inserted before incoming enumeration; an existing row with different file evidence fails the entire service. This bootstraps historical ready files and recovers a crash after ready publication but before ledger commit.

Ready payloads are currently preserved rather than archived or deleted. Vector
keeps one descriptor for every discovered ready file, so its service has an
explicit `LimitNOFILE=65536` override. This restores ingestion headroom without
claiming that gate acceptance proves ClickHouse delivery. Any future archive or
removal mechanism must prove exact per-file ClickHouse delivery first and be
separately reversible.

First acceptance uses this durable order:

1. validate stable incoming metadata and exact bytes
2. copy the bytes into a gate-owned temporary file in the ready directory and
   `fsync` it
3. revalidate both the source and copied bytes against the original evidence
4. create a same-owner, no-overwrite publication marker from the gate-owned
   temporary file to the ready name and persist the directory
5. remove the incoming name, persist the incoming directory, remove the marker,
   and persist ready again
6. insert and synchronously commit the immutable acceptance row

The writer-owned incoming inode is never linked directly into the ready
directory. A crash can leave a recognizable same-owner ready/marker relation;
recovery accepts only that relation plus exact matching incoming bytes before
cleanup and ledger reconciliation. Unexplained links or divergent evidence fail
closed.

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

The repository core independently validates the outbox root/ready/delivered layout, shared lock, every ready and delivered file, exact service ownership/group/modes/links, 256-KiB bounds, canonical JSON, exact top-level contracts, producer identity, deterministic filenames, and timezone-aware timestamps before selecting work. It accepts exact legacy/current single-record AI result files and strict multi-record `incident_lifecycle` batches. Lifecycle producer versions 1 and 2 remain independently strict; version 2 adds `recurrence_count` and uses `incident-state-v2-*` filenames while immutable version-1 files remain accepted unchanged. New AI files and every lifecycle row require nonempty bounded Device identity. It sends at most one file per invocation, oldest embedded timestamp first with filename as a stable tie-breaker.

Its SFTP subprocess uses a fixed executable and argument vector without a shell. Batch mode, identities-only behavior, password and keyboard-interactive refusal, strict supplied known-host checking, disabled global known hosts, one connection attempt, bounded connection/keepalive behavior, and a total process timeout are mandatory. The upload batch preserves the exact local absolute path bytes and unchanged remote basename. Process output is captured and never included in sender error messages.

Transport failure leaves ready unchanged. After transport success, the sender revalidates the source and atomically renames it into delivered under the shared producer/sender lock, then synchronizes both directories and postvalidates the exact bytes. An injected interruption after transport success left ready unchanged; the next cycle issued the exact same upload batch and then completed the local transition.

Eleven local and eleven exact GX10-staged tests cover strict command construction, exact-byte/name movement, one-file bound, oldest-first ordering, no-op, transport failure isolation, post-transport interruption/retry, duplicate state, divergent content, private-file metadata, shared-lock contention, and delivered-state validation. In those synthetic tests, transports are injected doubles and the core does not contact the collector.

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

## Clean-host transport qualification

The clean collector base already installs the result-writer public key. The
existing-host authorizer above is not a second clean-rebuild step.

Before any live transport, run the retained no-network suites from the reviewed
repository revision:

```text
python3 -B components/collector/tests/validate-result-gate-package.py
python3 -B components/gx10/tests/test_result_sender.py
python3 -B components/gx10/tests/test_result_sender_management.py
python3 -B components/gx10/tests/test_first_live_evidence.py
```

The collector suite explicitly proves exact replay after ready-file removal,
same-name divergent replay, immutable acceptance rows, and ready/ledger
divergence refusal. The GX10 suites prove at-most-one transport selection,
unchanged deterministic name/content, post-success ready-to-delivered movement,
interrupted/failing transport retention, duplicate/divergent-state refusal, and
configured inactive/active systemd boundaries. These synthetic tests are the
safe clean-rebuild substitute for deliberate exact and divergent production
re-uploads. Do not create a modified production result solely to retest a
historical quarantine outcome.

The first-live suites additionally prove GX/collector evidence-schema
compatibility, concurrent new-ready accounting, privilege restoration,
ready/delivered overlap refusal, preaccepted identity refusal, ledger and ready
identity mismatch, zero/duplicate/wrong-route/divergent ClickHouse results,
thin-projection mismatch, private credential metadata, temporary credential-
configuration cleanup, and no private-path echo on unexpected failures.

After the sender is configured and its staged `/run` key source has been
removed, keep its timer disabled through the first-live proof:

```text
components/gx10/install/verify-result-outbox.py --active
components/gx10/install/verify-result-sender.py --configured \
    --runtime-config /etc/network-log-gx10/runtime.json
```

The sender verifier must still report `timer_enabled=no` and service inactive.
Do not start the sender service until the retained qualification package below
has first captured a protected GX10 pre-send inventory. The sender selects the
oldest entry across AI results and incident-lifecycle batches, while the outbox
verifier prints only AI `ready`/`delivered` counts; those counts cannot identify
the selected cross-host byte sequence.

Allow the normal collector settling window, result-gate timer, and Vector
cadence to run. On the collector, require the gate timer and core current-view
runtime to remain healthy:

```text
systemctl is-enabled --quiet ai-results-gate.timer
systemctl is-active --quiet ai-results-gate.timer
COLLECTOR_CLICKHOUSE_PASSWORD_FILE=/root/collector-rebuild-inputs/clickhouse-default-password
test -s "$COLLECTOR_CLICKHOUSE_PASSWORD_FILE"
env CLICKHOUSE_DEFAULT_PASSWORD_FILE="$COLLECTOR_CLICKHOUSE_PASSWORD_FILE" \
    components/collector/install/verify-runtime.sh --transport-view handoff
```

This proves the current collector/runtime contract. The one manual sender cycle
below is the only live action allowed before recurring activation.

### Executable first-live provenance proof

The retained package is public code but its two evidence files are private.
`capture-first-live-evidence.py` acquires the sender lock, inventories the
outbox as the service account, binds the deterministic next file, and emits only
aggregate markers. `verify-first-live-provenance.py` reads the existing
root-protected `grafana_reader` password file through a temporary mode-`0600`
client configuration, performs read-only queries, and emits no filename,
digest, content, credential, or connection value. Evidence is canonical,
root-owned, single-link mode `0600`, bounded to 4 MiB, and kept outside Git.

Run the following from the reviewed checkout as root on GX10 while the sender
timer is disabled:

```text
GX_FIRST_LIVE_DIR=/root/network-log-first-live-evidence
GX_FIRST_LIVE_PREPARED="$GX_FIRST_LIVE_DIR/prepared-v1.json"
GX_FIRST_LIVE_FINALIZED="$GX_FIRST_LIVE_DIR/finalized-v1.json"
: "${GX_ADMIN_USER:?set GX_ADMIN_USER to the existing non-root GX administrator}"
GX_ADMIN_GROUP="$(id -gn "$GX_ADMIN_USER")"
GX_FIRST_LIVE_TRANSFER_DIR=/run/network-log-first-live-admin
export GX_FIRST_LIVE_DIR GX_FIRST_LIVE_PREPARED GX_FIRST_LIVE_FINALIZED
export GX_ADMIN_USER GX_ADMIN_GROUP GX_FIRST_LIVE_TRANSFER_DIR
test "$(id -u "$GX_ADMIN_USER")" -ne 0
install -d -o root -g root -m 0700 "$GX_FIRST_LIVE_DIR"
test ! -L "$GX_FIRST_LIVE_DIR"
test "$(stat -c '%U:%G:%a' "$GX_FIRST_LIVE_DIR")" = root:root:700
test ! -e "$GX_FIRST_LIVE_PREPARED"
test ! -e "$GX_FIRST_LIVE_FINALIZED"
test ! -e "$GX_FIRST_LIVE_TRANSFER_DIR"
install -d -o "$GX_ADMIN_USER" -g "$GX_ADMIN_GROUP" -m 0700 \
    "$GX_FIRST_LIVE_TRANSFER_DIR"
components/gx10/install/capture-first-live-evidence.py prepare \
    --output "$GX_FIRST_LIVE_PREPARED"
install -o "$GX_ADMIN_USER" -g "$GX_ADMIN_GROUP" -m 0600 -- \
    "$GX_FIRST_LIVE_PREPARED" \
    "$GX_FIRST_LIVE_TRANSFER_DIR/prepared-v1.json"
cmp -s -- "$GX_FIRST_LIVE_PREPARED" \
    "$GX_FIRST_LIVE_TRANSFER_DIR/prepared-v1.json"
```

Require `GX10_FIRST_LIVE_EVIDENCE_PREPARE=PASS`. On the operator management
host, transfer the transient admin-owned copy byte-for-byte through the existing
administrator SSH aliases—not the backlog-reader or result-writer SFTP role—to
the collector administrator's home, then remove the GX transient source:

```text
: "${GX_ADMIN_SSH_ALIAS:?set the existing GX administrator SSH alias}"
: "${COLLECTOR_ADMIN_SSH_ALIAS:?set the existing collector administrator SSH alias}"
: "${GX_ADMIN_USER:?set the existing non-root GX administrator}"
: "${COLLECTOR_ADMIN_USER:?set the existing non-root collector administrator}"
export GX_ADMIN_SSH_ALIAS COLLECTOR_ADMIN_SSH_ALIAS
export GX_ADMIN_USER COLLECTOR_ADMIN_USER
test "$(ssh "$GX_ADMIN_SSH_ALIAS" 'id -un')" = "$GX_ADMIN_USER"
test "$(ssh "$COLLECTOR_ADMIN_SSH_ALIAS" 'id -un')" = "$COLLECTOR_ADMIN_USER"
ssh "$COLLECTOR_ADMIN_SSH_ALIAS" \
    'test ! -e .network-log-first-live-prepared.json'
scp -3 -p \
    "$GX_ADMIN_SSH_ALIAS:/run/network-log-first-live-admin/prepared-v1.json" \
    "$COLLECTOR_ADMIN_SSH_ALIAS:.network-log-first-live-prepared.json"
ssh "$GX_ADMIN_SSH_ALIAS" \
    'rm -f -- /run/network-log-first-live-admin/prepared-v1.json'
ssh "$GX_ADMIN_SSH_ALIAS" \
    'test ! -e /run/network-log-first-live-admin/prepared-v1.json'
```

The alias values and their endpoint/user configuration remain operator-private.
On the collector, adopt and preflight the admin-owned home file as root:

```text
: "${COLLECTOR_ADMIN_USER:?set COLLECTOR_ADMIN_USER to the existing non-root collector administrator}"
COLLECTOR_ADMIN_HOME="$(getent passwd "$COLLECTOR_ADMIN_USER" | cut -d: -f6)"
test "$(getent passwd "$COLLECTOR_ADMIN_USER" | wc -l)" -eq 1
test "$(id -u "$COLLECTOR_ADMIN_USER")" -ne 0
test -n "$COLLECTOR_ADMIN_HOME"
test "${COLLECTOR_ADMIN_HOME#/}" != "$COLLECTOR_ADMIN_HOME"
test -d "$COLLECTOR_ADMIN_HOME"
test ! -L "$COLLECTOR_ADMIN_HOME"
test "$(stat -c '%U' "$COLLECTOR_ADMIN_HOME")" = "$COLLECTOR_ADMIN_USER"
COLLECTOR_ADMIN_HOME_MODE="$(stat -c '%a' "$COLLECTOR_ADMIN_HOME")"
test "$((0$COLLECTOR_ADMIN_HOME_MODE & 0022))" -eq 0
COLLECTOR_FIRST_LIVE_PREPARED_INPUT="$COLLECTOR_ADMIN_HOME/.network-log-first-live-prepared.json"
COLLECTOR_FIRST_LIVE_FINALIZED_INPUT="$COLLECTOR_ADMIN_HOME/.network-log-first-live-finalized.json"
COLLECTOR_FIRST_LIVE_DIR=/root/network-log-first-live-evidence
COLLECTOR_FIRST_LIVE_PREPARED="$COLLECTOR_FIRST_LIVE_DIR/prepared-v1.json"
COLLECTOR_FIRST_LIVE_FINALIZED="$COLLECTOR_FIRST_LIVE_DIR/finalized-v1.json"
COLLECTOR_GRAFANA_READER_PASSWORD_FILE=/root/collector-rebuild-inputs/grafana-reader-password
export COLLECTOR_ADMIN_USER COLLECTOR_ADMIN_HOME
export COLLECTOR_FIRST_LIVE_PREPARED_INPUT COLLECTOR_FIRST_LIVE_FINALIZED_INPUT
export COLLECTOR_FIRST_LIVE_DIR COLLECTOR_FIRST_LIVE_PREPARED
export COLLECTOR_FIRST_LIVE_FINALIZED COLLECTOR_GRAFANA_READER_PASSWORD_FILE
install -d -o root -g root -m 0700 "$COLLECTOR_FIRST_LIVE_DIR"
test ! -L "$COLLECTOR_FIRST_LIVE_DIR"
test "$(stat -c '%U:%G:%a' "$COLLECTOR_FIRST_LIVE_DIR")" = root:root:700
test ! -e "$COLLECTOR_FIRST_LIVE_PREPARED"
test ! -e "$COLLECTOR_FIRST_LIVE_FINALIZED"
test -f "$COLLECTOR_FIRST_LIVE_PREPARED_INPUT"
test ! -L "$COLLECTOR_FIRST_LIVE_PREPARED_INPUT"
test "$(stat -c '%U:%a:%h' "$COLLECTOR_FIRST_LIVE_PREPARED_INPUT")" = "$COLLECTOR_ADMIN_USER:600:1"
install -o root -g root -m 0600 -- \
    "$COLLECTOR_FIRST_LIVE_PREPARED_INPUT" \
    "$COLLECTOR_FIRST_LIVE_PREPARED"
cmp -s -- "$COLLECTOR_FIRST_LIVE_PREPARED_INPUT" \
    "$COLLECTOR_FIRST_LIVE_PREPARED"
rm -f -- "$COLLECTOR_FIRST_LIVE_PREPARED_INPUT"
test ! -e "$COLLECTOR_FIRST_LIVE_PREPARED_INPUT"
components/collector/sbin/verify-first-live-provenance.py \
    --password-file "$COLLECTOR_GRAFANA_READER_PASSWORD_FILE" \
    preflight --prepared "$COLLECTOR_FIRST_LIVE_PREPARED"
```

Require `COLLECTOR_FIRST_LIVE_PREFLIGHT=PASS`. It proves the selected identity
is absent from the immutable acceptance ledger, incoming/ready spools, and both
ClickHouse routes before any send. Back on GX10, invoke exactly one oneshot and
seal the transition while the timer remains disabled:

```text
systemctl start network-log-gx10-result-sender.service
test "$(systemctl show network-log-gx10-result-sender.service --property=ActiveState --value)" = inactive
test "$(systemctl show network-log-gx10-result-sender.service --property=Result --value)" = success
components/gx10/install/capture-first-live-evidence.py finalize \
    --prepared "$GX_FIRST_LIVE_PREPARED" \
    --output "$GX_FIRST_LIVE_FINALIZED"
components/gx10/install/verify-result-sender.py --configured \
    --runtime-config /etc/network-log-gx10/runtime.json
```

Require `GX10_FIRST_LIVE_EVIDENCE_FINALIZE=PASS`, `timer_enabled=no`, and an
inactive service. Finalize requires the selected bytes/name to have moved to
delivered, every baseline ready/delivered identity to remain unchanged, no
ready/delivered overlap, and exactly one delivered transition. New ready work
created concurrently is counted and bound without being mistaken for a second
send.

Back on GX10 as root, create only the transient admin-readable finalized copy:

```text
: "${GX_ADMIN_USER:?set GX_ADMIN_USER to the existing non-root GX administrator}"
GX_ADMIN_GROUP="$(id -gn "$GX_ADMIN_USER")"
GX_FIRST_LIVE_DIR=/root/network-log-first-live-evidence
GX_FIRST_LIVE_FINALIZED="$GX_FIRST_LIVE_DIR/finalized-v1.json"
GX_FIRST_LIVE_TRANSFER_DIR=/run/network-log-first-live-admin
test -d "$GX_FIRST_LIVE_TRANSFER_DIR"
test ! -L "$GX_FIRST_LIVE_TRANSFER_DIR"
test "$(stat -c '%U:%G:%a' "$GX_FIRST_LIVE_TRANSFER_DIR")" = "$GX_ADMIN_USER:$GX_ADMIN_GROUP:700"
test ! -e "$GX_FIRST_LIVE_TRANSFER_DIR/finalized-v1.json"
install -o "$GX_ADMIN_USER" -g "$GX_ADMIN_GROUP" -m 0600 -- \
    "$GX_FIRST_LIVE_FINALIZED" \
    "$GX_FIRST_LIVE_TRANSFER_DIR/finalized-v1.json"
cmp -s -- "$GX_FIRST_LIVE_FINALIZED" \
    "$GX_FIRST_LIVE_TRANSFER_DIR/finalized-v1.json"
```

On the operator management host, transfer it through the same aliases and
remove the GX transient source:

```text
: "${GX_ADMIN_SSH_ALIAS:?set the existing GX administrator SSH alias}"
: "${COLLECTOR_ADMIN_SSH_ALIAS:?set the existing collector administrator SSH alias}"
: "${GX_ADMIN_USER:?set the existing non-root GX administrator}"
: "${COLLECTOR_ADMIN_USER:?set the existing non-root collector administrator}"
test "$(ssh "$GX_ADMIN_SSH_ALIAS" 'id -un')" = "$GX_ADMIN_USER"
test "$(ssh "$COLLECTOR_ADMIN_SSH_ALIAS" 'id -un')" = "$COLLECTOR_ADMIN_USER"
ssh "$COLLECTOR_ADMIN_SSH_ALIAS" \
    'test ! -e .network-log-first-live-finalized.json'
scp -3 -p \
    "$GX_ADMIN_SSH_ALIAS:/run/network-log-first-live-admin/finalized-v1.json" \
    "$COLLECTOR_ADMIN_SSH_ALIAS:.network-log-first-live-finalized.json"
ssh "$GX_ADMIN_SSH_ALIAS" \
    'rm -f -- /run/network-log-first-live-admin/finalized-v1.json'
ssh "$GX_ADMIN_SSH_ALIAS" \
    'test ! -e /run/network-log-first-live-admin/finalized-v1.json'
```

On the collector as root, adopt and verify the finalized evidence:

```text
: "${COLLECTOR_ADMIN_USER:?set COLLECTOR_ADMIN_USER to the existing non-root collector administrator}"
COLLECTOR_ADMIN_HOME="$(getent passwd "$COLLECTOR_ADMIN_USER" | cut -d: -f6)"
test "$(getent passwd "$COLLECTOR_ADMIN_USER" | wc -l)" -eq 1
test "$(id -u "$COLLECTOR_ADMIN_USER")" -ne 0
test -n "$COLLECTOR_ADMIN_HOME"
test "${COLLECTOR_ADMIN_HOME#/}" != "$COLLECTOR_ADMIN_HOME"
test -d "$COLLECTOR_ADMIN_HOME"
test ! -L "$COLLECTOR_ADMIN_HOME"
test "$(stat -c '%U' "$COLLECTOR_ADMIN_HOME")" = "$COLLECTOR_ADMIN_USER"
COLLECTOR_ADMIN_HOME_MODE="$(stat -c '%a' "$COLLECTOR_ADMIN_HOME")"
test "$((0$COLLECTOR_ADMIN_HOME_MODE & 0022))" -eq 0
COLLECTOR_FIRST_LIVE_FINALIZED_INPUT="$COLLECTOR_ADMIN_HOME/.network-log-first-live-finalized.json"
COLLECTOR_FIRST_LIVE_DIR=/root/network-log-first-live-evidence
COLLECTOR_FIRST_LIVE_PREPARED="$COLLECTOR_FIRST_LIVE_DIR/prepared-v1.json"
COLLECTOR_FIRST_LIVE_FINALIZED="$COLLECTOR_FIRST_LIVE_DIR/finalized-v1.json"
COLLECTOR_GRAFANA_READER_PASSWORD_FILE=/root/collector-rebuild-inputs/grafana-reader-password
test -f "$COLLECTOR_FIRST_LIVE_FINALIZED_INPUT"
test ! -L "$COLLECTOR_FIRST_LIVE_FINALIZED_INPUT"
test "$(stat -c '%U:%a:%h' "$COLLECTOR_FIRST_LIVE_FINALIZED_INPUT")" = "$COLLECTOR_ADMIN_USER:600:1"
install -o root -g root -m 0600 -- \
    "$COLLECTOR_FIRST_LIVE_FINALIZED_INPUT" \
    "$COLLECTOR_FIRST_LIVE_FINALIZED"
cmp -s -- "$COLLECTOR_FIRST_LIVE_FINALIZED_INPUT" \
    "$COLLECTOR_FIRST_LIVE_FINALIZED"
rm -f -- "$COLLECTOR_FIRST_LIVE_FINALIZED_INPUT"
test ! -e "$COLLECTOR_FIRST_LIVE_FINALIZED_INPUT"
components/collector/sbin/verify-first-live-provenance.py \
    --password-file "$COLLECTOR_GRAFANA_READER_PASSWORD_FILE" \
    final --prepared "$COLLECTOR_FIRST_LIVE_PREPARED" \
    --finalized "$COLLECTOR_FIRST_LIVE_FINALIZED" --wait-seconds 300
```

Require `COLLECTOR_FIRST_LIVE_PROVENANCE=PASS`. The verifier binds the finalized
GX evidence to its exact prepared bytes, one immutable ledger row and accepted
ready file, absence from incoming, the selected ClickHouse route, zero rows in
the wrong route, exact `raw_json` byte multisets, and every stored thin
projection. An AI file requires one row; a lifecycle batch requires exactly its
`record_count` rows. Only transient absence is retried; metadata, schema,
ledger, route, duplicate, content, or projection divergence fails immediately.

Retain both root-only evidence files through full acceptance and reboot
verification, then archive or remove them according to operator evidence policy.
Never place them in Git or routine command output. Failed writes remove only
their attempt-created output; an existing evidence path is always refused. Once
both transfers are adopted, return to GX10, remove the now-empty admin staging
directory as root and require it absent:

```text
GX_FIRST_LIVE_TRANSFER_DIR=/run/network-log-first-live-admin
test -d "$GX_FIRST_LIVE_TRANSFER_DIR"
rmdir -- "$GX_FIRST_LIVE_TRANSFER_DIR"
test ! -e "$GX_FIRST_LIVE_TRANSFER_DIR"
```

If a transfer fails, preserve the root-owned evidence, remove only the
admin-owned GX source and collector-home destination for that phase, and retry
the administrator transfer from the unchanged root evidence. The bounded
cleanup is:

```text
: "GX10 root-shell transient cleanup"
GX_FIRST_LIVE_TRANSFER_DIR=/run/network-log-first-live-admin
rm -f -- "$GX_FIRST_LIVE_TRANSFER_DIR/prepared-v1.json"
rm -f -- "$GX_FIRST_LIVE_TRANSFER_DIR/finalized-v1.json"
rmdir -- "$GX_FIRST_LIVE_TRANSFER_DIR"

: "collector root-shell transient cleanup after validated administrator-home lookup"
rm -f -- "$COLLECTOR_ADMIN_HOME/.network-log-first-live-prepared.json"
rm -f -- "$COLLECTOR_ADMIN_HOME/.network-log-first-live-finalized.json"
```

Never reuse or overwrite a root evidence output path. If the one manual sender
cycle already ran, do not rerun it; repair only the evidence-transfer/final
verification step from the unchanged root evidence.

## Configured-inactive production checkpoint

At this checkpoint, the dedicated authorization and all GX10 private inputs were installed and independently verified. Exact idempotent configuration reuse passed. Temporary key inputs were removed after the installed GX10 identity matched the collector authorization. The sender timer remained disabled; exactly one bounded manual service cycle invoked SFTP and moved one ready file to delivered. The active outbox and all prior deterministic schedules remained healthy; the collector result gate, Vector, ClickHouse, SSH configuration, authorization metadata, and exact predecessor-backup relation passed.

## Historical bounded first-live and replay plan

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

Item 33 later added the backward-compatible Device projection. Exact
predecessor copies were retained, existing ready/delivered bytes were reused
without rewrite, the producer/sender wrappers were updated to exact new hashes,
and the item-33 192-test gate passed. Replay identity, filenames, provenance,
deterministic incident state, and the write-only transport boundary remain
unchanged.

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

## Completed activation gates

1. `DONE` — publish and independently verify the configured-inactive production checkpoint and bounded plan.
2. `DONE` — transmit exactly one file and prove collector acceptance, Vector/ClickHouse ingestion, complete `raw_json` provenance, local delivered transition, and all preexisting schedule health.
3. `DONE` — prove an exact replay creates no second acceptance or ClickHouse row and is quarantined distinctly.
4. `DONE` — prove a controlled same-name divergent file remains isolated with a distinct conflict reason and no new acceptance or ClickHouse row.
5. `DONE` — explicit active-schedule verification passes 186 local and exact GX10-staged tests; only the recurring timer was enabled; three natural deliveries, first natural collector acceptance/ClickHouse ingestion, zero sender restarts, unchanged replay evidence, and healthy preexisting schedules passed.

The separate item-31 production/repository closure audit also passes: active delivered/accepted/in-flight cardinality conserved exactly, every accepted result had one complete ClickHouse row, both hosts and all repository suites/sanitation passed, and rollback/quarantine evidence remained preserved.
