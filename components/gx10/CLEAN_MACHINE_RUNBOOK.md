# GX10 Clean-Machine Runbook

## Purpose and boundary

This runbook reconstructs the currently proven GX10 state on a clean Ubuntu 24.04 arm64 host.

It reconstructs two deliberate layers:

1. the recovered base runtime; and
2. the current reconstructed correlation, managed AI/triage, result/lifecycle
   outbox, selective snapshot, and write-only sender extensions.

It reproduces:

- the dedicated runtime identity and protected filesystem
- read-only SFTP backlog fetch
- replay-safe local SQLite ingest
- canonical normalized-field projection and deterministic incident processing behind a separate managed offline schedule
- deterministic wake-policy/compact-packet schema and builder through the
  separately managed reasoning owner
- the exact reconstructed SQLite base, deterministic incident extension, and two functional suppression patterns
- the original automatic `timer -> fetch -> ingest` chain
- the captured Ollama executable, service, loopback listener, and six-model store
- hidden uncovered-event triage, selective snapshot, result/lifecycle outbox,
  and independently disableable write-only sender through their guarded phases

It does not claim to rediscover historical provenance that was not recovered:

- historical kernel, NVIDIA, CUDA, Ollama, or SQLite bootstrap provenance that was not recovered

Historical rediscovery found no predecessor application-specific Ollama caller
or GX10 result producer. The repository-managed caller, triage, producer, and
sender below are active reconstructed extensions and must be installed only
through their own gates.

Never run these clean-machine installers against the working reference system.

## Required inputs

Prepare these outside the repository:

1. a clean Ubuntu 24.04 arm64 GX10-class host
2. the captured NVIDIA-capable kernel, driver, and CUDA compiler baseline recorded in `install/versions.env`
3. root access and working Ubuntu package repositories containing the exact pinned package versions
4. network reachability from GX10 to both collector transport roles
5. the collector host, port, and read-only transport username
6. a dedicated backlog-reader private key and known-hosts file, each mode `0400` or `0600`
7. the exact captured Ollama binary:
   - size `35792104` bytes
   - SHA-256 `26f44ca89143f2326a3aad98b2cb5e8b5af9397aef7001cd8d022e90d6e0b55e`
8. an offline Ollama `models` directory containing the captured six manifests and all referenced blobs
9. a clean checkout of this public repository
10. a distinct root-owned result-writer Ed25519 private key for the later
    sender configuration; its public half must already be present in the
    collector base authorized-keys input
11. a protected absent location for the reasoning pre-activation backup
12. existing non-root sudo-capable administrator accounts on GX10 and the
    collector, plus their operator-host SSH aliases, for the transient private
    first-live evidence transfer in Phase 11C; keep those values outside Git

Firewall reconstruction is out of scope. The operator is responsible for allowing only the required outbound collector transport and for retaining the Ollama listener on loopback.

## Protect operator inputs

Copy `config/operator-inputs.env.example` to a root-readable file outside the repository. Replace every example value and set mode `0600`.

The populated file must define:

- `GX10_SFTP_HOST`
- `GX10_SFTP_PORT`
- `GX10_SFTP_USER`
- `GX10_SFTP_PRIVATE_KEY_FILE`
- `GX10_SFTP_KNOWN_HOSTS_FILE`
- `OLLAMA_BINARY_FILE`
- `OLLAMA_MODEL_STORE_DIR`

The later sender configuration also needs a separately protected result-writer
identity. Do not put that key in this base input file or repository. Stage it
only from protected temporary storage when Phase 11B requests it. The
configurator installs the service-owned copy and removes only target files that
its own failed attempt created. It does **not** remove the operator-supplied
source. Phase 11B explicitly removes and verifies absence of the `/run` source
after configured-state verification.

Phase 11C additionally uses `GX_ADMIN_USER` in the GX root shell and the
operator-private administrator usernames/SSH aliases named in
`docs/TWO_SERVER_REBUILD.md`. They are transport-channel inputs, not application
runtime configuration, and must not be added to this file or committed.

In the same root shell, set only the path to that separately protected source;
the variable is not rendered into the GX10 base configuration:

    GX10_RESULT_WRITER_PRIVATE_KEY_FILE=/root/network-log-gx10-inputs/result-writer-ed25519
    export GX10_RESULT_WRITER_PRIVATE_KEY_FILE

The source must be a non-symlinked, nonempty, root-owned regular file with mode
`0400` or `0600`. Do not read it into a shell variable.

Do not place the populated file, private key, known-hosts file, Ollama binary, or model store inside the Git checkout.

In a root shell, set the repository and input-file locations, then load the protected input file:

    GX10_REPOSITORY_DIR=/opt/network-log-master
    GX10_OPERATOR_INPUTS_FILE=/root/network-log-gx10-inputs/operator-inputs.env
    export GX10_REPOSITORY_DIR GX10_OPERATOR_INPUTS_FILE
    set -a
    . "$GX10_OPERATOR_INPUTS_FILE"
    set +a
    cd "$GX10_REPOSITORY_DIR"

## Phase 1: repository-only validation

Before changing the host, require a clean checkout and run the complete non-mutating package audit:

    test -z "$(git status --porcelain)"
    git log -1 --oneline
    components/gx10/tests/validate-rebuild-package.py

Expected final marker:

`GX10_REBUILD_PACKAGE_VALIDATION=PASS`

Validate the private runtime configuration values without writing them:

    components/gx10/install/render-runtime-config.py --check

Expected marker:

`GX10_RUNTIME_CONFIG_INPUT=PASS`

## Phase 2: platform packages

Confirm that the host is a clean intended rebuild target. Then install only the pinned application-level packages:

    CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10 \
        components/gx10/install/install-packages.sh

Expected marker:

`GX10_PACKAGE_INSTALL=PASS`

Verify the complete platform baseline:

    components/gx10/install/verify-platform.py

Expected marker:

`GX10_PLATFORM_VERIFY=PASS`

If this fails on the kernel, driver, or CUDA checks, stop. Provisioning those platform layers is deliberately not automated because trustworthy historical installation provenance was not recovered.

## Phase 3: protected filesystem and configuration

Create the dedicated locked runtime identity, public path layout, and protected SFTP material:

    CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10 \
    GX10_SFTP_PRIVATE_KEY_FILE="$GX10_SFTP_PRIVATE_KEY_FILE" \
    GX10_SFTP_KNOWN_HOSTS_FILE="$GX10_SFTP_KNOWN_HOSTS_FILE" \
        components/gx10/install/install-filesystem.sh

Expected marker:

`GX10_FILESYSTEM_BOOTSTRAP=PASS`

Render the protected runtime configuration:

    GX10_SFTP_HOST="$GX10_SFTP_HOST" \
    GX10_SFTP_PORT="$GX10_SFTP_PORT" \
    GX10_SFTP_USER="$GX10_SFTP_USER" \
        components/gx10/install/render-runtime-config.py

Expected marker:

`GX10_RUNTIME_CONFIG_RENDER=PASS`

## Phase 4: database and application units

Create the exact empty reconstructed SQLite state. This intentionally refuses any existing database:

    CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10 \
        components/gx10/install/initialize-database.py

Expected marker:

`GX10_DATABASE_INITIALIZE=PASS`

Install the captured applications and pipeline service/timer without activating them:

    CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10 \
        components/gx10/install/install-applications.py

Expected marker:

`GX10_APPLICATION_INSTALL=PASS`

## Phase 5: Ollama and offline models

Install the exact operator-supplied Ollama binary and sanitized service unit without activating the service:

    CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10 \
    OLLAMA_BINARY_FILE="$OLLAMA_BINARY_FILE" \
        components/gx10/install/install-ollama.py

Expected marker:

`GX10_OLLAMA_INSTALL=PASS`

Import the offline model store:

    CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10 \
    OLLAMA_MODEL_STORE_DIR="$OLLAMA_MODEL_STORE_DIR" \
        components/gx10/install/install-model-store.py

Expected marker:

`GX10_OLLAMA_MODEL_INSTALL=PASS`

The importer:

- calls no API and pulls no model
- hashes every unique source blob before writing
- copies only blobs referenced by the six exact manifests
- publishes blobs before manifests
- never overwrites an existing file
- can reuse already-copied exact files after an interrupted run
- rejects unexpected or divergent target content
- hashes the complete installed store again before returning success

The source and installed model stores must be different directories. Large stores require enough free target space and may take substantial time to hash and copy.

## Phase 6: preactivation review

Run the complete reference-like-state refusal gate:

    components/gx10/install/verify-runtime.py --preactivation

Expected marker:

`GX10_RUNTIME_PREACTIVATION_VERIFY=PASS`

Run the fast offline Ollama structure/size check:

    components/gx10/install/verify-ollama.py --offline

Expected marker:

`GX10_OLLAMA_VERIFY=PASS`

At this point all application units must still be inactive, Ollama and the
timer must be disabled, and every verifier-enumerated application table,
cursor, spool file, and SQLite sidecar must be empty.

Before continuing, review the protected collector host, port, and username in the external input file. Activation starts the timer and authorizes automatic read-only fetch followed by local ingest.

## Phase 7: activation

Activate only after every prior phase passes:

    CLEAN_INSTALL_CONFIRM=YES-CLEAN-GX10 \
    GX10_ACTIVATE_CONFIRM=ENABLE-VERIFIED-GX10 \
        components/gx10/install/activate-runtime.py

Expected final marker:

`GX10_RUNTIME_ACTIVATION=PASS`

The activator repeats the platform and preactivation checks, hashes the complete installed model store, enables Ollama, verifies its loopback-only listener, then enables the fetch/ingest timer. If a post-preflight step fails, it stops a potentially triggered pipeline service and disables/stops the units it changed.

It leaves the separately gated correlation timer disabled until Phase 9.

## Phase 8: post-activation verification

Verify installed runtime state:

    components/gx10/install/verify-runtime.py --active
    components/gx10/install/verify-ollama.py

Expected markers:

- `GX10_RUNTIME_ACTIVE_VERIFY=PASS`
- `GX10_OLLAMA_VERIFY=PASS`

After at least one timer interval, inspect service state and recent service logs without invoking an application manually:

    systemctl status --no-pager network-log-gx10.timer
    systemctl status --no-pager network-log-gx10.service
    journalctl --no-pager -u network-log-gx10.service -n 100

Do not paste private transport values or production log content into the public repository or project journal.

## Phase 9: managed correlation activation

After the base runtime passes and at least one fetch/ingest cycle has completed, install the private correlation binding while leaving its timer disabled:

    GX10_CORRELATION_INSTALL_CONFIRM=INSTALL-UNSCHEDULED-CORRELATION \
        components/gx10/install/install-correlation.py \
        --database /var/lib/network-log-gx10/state/events.sqlite3 \
        --runtime-user network-log-agent \
        --runtime-group network-log-agent \
        --pipeline-unit network-log-gx10.service \
        --apply

Verify the exact inactive boundary:

    components/gx10/install/verify-correlation.py \
        --installed \
        --private-runtime

Expected markers:

- `GX10_MANAGED_CORRELATION_INSTALL=PASS`
- `GX10_MANAGED_CORRELATION_INSTALLED_VERIFY=PASS`

Run the initial backfill and enable only the correlation timer after zero-lag verification:

    GX10_CORRELATION_ACTIVATE_CONFIRM=ENABLE-VERIFIED-CORRELATION \
        components/gx10/install/activate-correlation.py \
        --database /var/lib/network-log-gx10/state/events.sqlite3

Expected marker:

`GX10_MANAGED_CORRELATION_ACTIVATION=PASS`

Verify active state after at least three independent correlation timer cadences:

    components/gx10/install/verify-correlation.py \
        --active \
        --private-runtime

Require zero projection lag, zero incident lag, successful service result, zero restarts, monotonic incident aggregates, and continued advancement of the original fetch/ingest timer. Do not invoke the packet builder or enable any Ollama application caller in this phase.

## Phase 10: managed AI and hidden-triage activation

Proceed only after managed correlation has passed its multi-cadence gate and
the installed selected-model manifest/configuration exactly matches the version
qualified by the retained synthetic and protected-current-state-copy evidence
in `docs/MANAGED_REASONING.md`. The protected current-state-copy exercise was a
one-time model-version qualification gate; a clean host has no predecessor
production database and is not expected to recreate that private copy. A model,
manifest, configuration, prompt, or output-schema change is a new qualification
event and must not be treated as part of this rebuild.

This phase activates the selected incident-assessment path and the hidden
uncovered-event triage path under the same managed owner. Deterministic
incidents retain priority; unavailable or invalid model work remains pending or
records a no-result without blocking raw capture, ingest, or correlation.

Create a protected recovery directory, then install the managed reasoning binding while leaving its timer disabled:

    install -d -m 0700 /root/network-log-gx10-reasoning-recovery
    GX10_REASONING_INSTALL_CONFIRM=INSTALL-UNSCHEDULED-MANAGED-REASONING \
        components/gx10/install/install-managed-reasoning.py \
        --database /var/lib/network-log-gx10/state/events.sqlite3 \
        --runtime-user network-log-agent \
        --runtime-group network-log-agent \
        --correlation-unit network-log-gx10-correlation.service \
        --apply

Verify the exact inactive boundary:

    components/gx10/install/verify-managed-reasoning.py \
        --installed \
        --private-runtime

Expected markers:

- `GX10_MANAGED_REASONING_INSTALL=PASS`
- `GX10_MANAGED_REASONING_INSTALLED_VERIFY=PASS`

Create the protected pre-activation backup, run exactly one bounded initial cycle, and enable only the reasoning timer after post-cycle verification:

    GX10_REASONING_ACTIVATE_CONFIRM=ENABLE-VERIFIED-MANAGED-REASONING \
        components/gx10/install/activate-managed-reasoning.py \
        --database /var/lib/network-log-gx10/state/events.sqlite3 \
        --backup /root/network-log-gx10-reasoning-recovery/pre-activation.sqlite3

Expected marker:

`GX10_MANAGED_REASONING_ACTIVATION=PASS`

Verify active state after multiple independent reasoning timer cadences:

    components/gx10/install/verify-managed-reasoning.py \
        --active \
        --private-runtime

Require zero deterministic lag, zero unreconciled `STARTED` runs, zero service restarts, consistent success/result counts, bounded one-run-per-cadence advancement, and continued health of the original fetch/ingest and correlation timers. Keep collector result return disabled until the separately guarded Phase 11 gates.

## Phase 11: current result/lifecycle extensions

Phase 10 is not the complete current application. This phase installs the
active no-network result/lifecycle projection, the selective snapshot used by
that projection, and the independently disableable write-only sender. It also
depends on the hidden triage contract already installed by managed reasoning.

### 11A. Install and activate the current snapshot-aware local outbox

The current clean installer directly installs the selective rollback-journal
snapshot boundary together with both local producers. It creates the protected
snapshot root and configuration, installs
`network-log-gx10-outbox-snapshot.service`, and binds the result/lifecycle
producers to that snapshot. It does **not** install the historical direct-
working-database predecessor.

Install the current outbox while its managed timer remains inactive:

    components/gx10/install/install-result-outbox.py \
        --confirm-install-inactive-result-outbox

Expected marker:

`GX10_RESULT_OUTBOX_INACTIVE_INSTALL=PASS`

Verify the inactive installation:

    components/gx10/install/verify-result-outbox.py --installed

Expected marker:

`GX10_MANAGED_RESULT_OUTBOX_VERIFY=PASS`

Activate the protected local producer. It has no network capability:

    components/gx10/install/activate-result-outbox.py \
        --confirm-activate-local-result-outbox
    components/gx10/install/verify-result-outbox.py --active

Expected activation marker:

`GX10_RESULT_OUTBOX_LOCAL_ACTIVATION=PASS`

The producer now reads the selective rollback-journal snapshot, not the mutable
working database. Do not retain the rejected recurring full-database-copy
design.

`upgrade-result-outbox-snapshot.py` is **not** a clean-install phase. It is a
guarded migration for an exact, already-active legacy outbox whose snapshot
unit, configuration, and root are absent. Running it after the clean installer
must fail because the current snapshot targets already exist. Retain that tool
only for a separately authorized existing-host migration.

### 11B. Install and configure the sender while disabled

The clean collector base already installed the matching result-writer public
key. Do not append it again unless repairing an existing collector through the
separate guarded authorizer.

Install and verify the sender while it remains staged and inactive:

    components/gx10/install/install-result-sender.py \
        --confirm-install-inactive-result-sender
    components/gx10/install/verify-result-sender.py --staged

Expected install marker:

`GX10_RESULT_SENDER_INACTIVE_INSTALL=PASS`

Stage the distinct protected writer key temporarily at the documented
root-readable path, then configure the disabled sender using the rendered
runtime configuration:

    test -n "${GX10_RESULT_WRITER_PRIVATE_KEY_FILE:-}"
    test -f "$GX10_RESULT_WRITER_PRIVATE_KEY_FILE"
    test -s "$GX10_RESULT_WRITER_PRIVATE_KEY_FILE"
    test ! -L "$GX10_RESULT_WRITER_PRIVATE_KEY_FILE"
    test "$(stat -c '%U' "$GX10_RESULT_WRITER_PRIVATE_KEY_FILE")" = root
    test "$(stat -c '%h' "$GX10_RESULT_WRITER_PRIVATE_KEY_FILE")" -eq 1
    case "$(stat -c '%a' "$GX10_RESULT_WRITER_PRIVATE_KEY_FILE")" in 400|600) ;; *) false ;; esac
    test ! -e /run/network-log-result-writer.key
    cleanup_result_writer_input() { rm -f -- /run/network-log-result-writer.key; }
    trap cleanup_result_writer_input EXIT
    trap 'exit 1' HUP INT TERM
    install -o root -g root -m 0600 -- \
        "$GX10_RESULT_WRITER_PRIVATE_KEY_FILE" \
        /run/network-log-result-writer.key
    components/gx10/install/configure-result-sender.py \
        --identity-input /run/network-log-result-writer.key \
        --runtime-config /etc/network-log-gx10/runtime.json \
        --confirm-configure-disabled-result-sender
    cleanup_result_writer_input
    trap - EXIT HUP INT TERM
    test ! -e /run/network-log-result-writer.key
    components/gx10/install/verify-result-sender.py --configured \
        --runtime-config /etc/network-log-gx10/runtime.json

Expected configuration marker:

`GX10_RESULT_SENDER_CONFIGURED_INACTIVE=PASS`

The configured sender must still be disabled/inactive and must not invoke SFTP
during configuration. The verifier proves the separately installed service
identity, known-hosts pin, canonical configuration, and zero-transport state.

The exit/signal trap removes only the staged source on configurator failure or
interruption. On success, remove it immediately before configured-state
verification and clear the traps only after proving absence. Thus a later
verifier failure cannot leave the operator-supplied key staged in `/run`. The
installed service-owned identity remains in its verifier-derived private
location. Never print either the source or installed key.

### 11C. Qualify transport before recurring delivery

First run the retained public-safe replay and conflict suites. These tests use
only synthetic temporary state and make no network connection:

    python3 -B components/collector/tests/validate-result-gate-package.py
    python3 -B components/gx10/tests/test_result_sender.py
    python3 -B components/gx10/tests/test_result_sender_management.py

Require `AI_RESULTS_GATE_PACKAGE_VALIDATION=PASS` and successful GX10 test
completion. These suites prove sender interruption behavior and the collector's
exact-replay/divergent-conflict classification. They deliberately replace live
re-upload probes during a clean rebuild; do not fabricate a divergent
production payload merely to repeat historical evidence.

Keep the sender at the independently verified zero-transport boundary:

    components/gx10/install/verify-result-outbox.py --active
    components/gx10/install/verify-result-sender.py --configured \
        --runtime-config /etc/network-log-gx10/runtime.json

Require `timer_enabled=no` and service inactive. Do not manually start the
sender merely because a ready file exists. Create the protected first-live
evidence files as root; an existing output path is a stop condition:

    GX_FIRST_LIVE_DIR=/root/network-log-first-live-evidence
    GX_FIRST_LIVE_PREPARED="$GX_FIRST_LIVE_DIR/prepared-v1.json"
    GX_FIRST_LIVE_FINALIZED="$GX_FIRST_LIVE_DIR/finalized-v1.json"
    export GX_FIRST_LIVE_DIR GX_FIRST_LIVE_PREPARED GX_FIRST_LIVE_FINALIZED
    install -d -o root -g root -m 0700 "$GX_FIRST_LIVE_DIR"
    test ! -L "$GX_FIRST_LIVE_DIR"
    test "$(stat -c '%U:%G:%a' "$GX_FIRST_LIVE_DIR")" = root:root:700
    test ! -e "$GX_FIRST_LIVE_PREPARED"
    test ! -e "$GX_FIRST_LIVE_FINALIZED"
    components/gx10/install/capture-first-live-evidence.py prepare \
        --output "$GX_FIRST_LIVE_PREPARED"

Require `GX10_FIRST_LIVE_EVIDENCE_PREPARE=PASS`. Transfer the prepared file
unchanged through the existing authenticated administrator channel, never an
application SFTP role. On the collector, follow the exact root-owned adoption
and `COLLECTOR_FIRST_LIVE_PREFLIGHT=PASS` sequence in the **Executable first-live
provenance proof** section of `docs/RESULT_TRANSPORT.md`. Only after that
preflight passes, invoke exactly one sender oneshot while its timer is disabled:

    systemctl start network-log-gx10-result-sender.service
    test "$(systemctl show network-log-gx10-result-sender.service --property=ActiveState --value)" = inactive
    test "$(systemctl show network-log-gx10-result-sender.service --property=Result --value)" = success
    components/gx10/install/capture-first-live-evidence.py finalize \
        --prepared "$GX_FIRST_LIVE_PREPARED" \
        --output "$GX_FIRST_LIVE_FINALIZED"
    components/gx10/install/verify-result-sender.py --configured \
        --runtime-config /etc/network-log-gx10/runtime.json

Require `GX10_FIRST_LIVE_EVIDENCE_FINALIZE=PASS`, `timer_enabled=no`, and
service inactive. Transfer the finalized file unchanged through the same
administrator channel and run the exact collector final verifier in
`docs/RESULT_TRANSPORT.md`. It must report
`COLLECTOR_FIRST_LIVE_PROVENANCE=PASS`, with one AI row or exactly
`record_count` lifecycle rows in the selected route and zero in the other.
Retain the root-only evidence through Phase 12.

Only after that two-host first-live qualification passes may the recurring
timer be enabled:

    systemctl enable --now network-log-gx10-result-sender.timer
    components/gx10/install/verify-result-sender.py --configured --active \
        --runtime-config /etc/network-log-gx10/runtime.json

Require natural timer cadences with zero sender restarts. Lifecycle batches
must route only to `incident_updates`; AI records must route only to
`ai_updates`. Verify all current NOC queries through `docs/NOC_WORKFLOW.md`.

## Phase 12: full-system acceptance and reboot recovery

Before declaring a clean rebuild complete, run the exact cross-host acceptance
matrix in `docs/TWO_SERVER_REBUILD.md`. For the final extended GX10 state, use:

    components/gx10/install/verify-platform.py
    components/gx10/install/verify-ollama.py
    systemctl is-enabled --quiet network-log-gx10.timer
    systemctl is-active --quiet network-log-gx10.timer
    components/gx10/install/verify-correlation.py --active --private-runtime
    components/gx10/install/verify-managed-reasoning.py --active --private-runtime
    components/gx10/install/verify-result-outbox.py --active
    components/gx10/install/verify-result-sender.py --configured --active \
        --runtime-config /etc/network-log-gx10/runtime.json

Do not rerun `verify-runtime.py --active` after Phase 9. That verifier
deliberately describes the earlier base-only boundary and requires correlation
and reasoning to remain disabled; Phase 8 is its correct execution point.

Let all oneshots settle, capture the redacted verifier counts, reboot the
collector first and verify it, then reboot GX10 and repeat the matrix above.
Require enabled expected timers, zero deterministic/triage lag, zero
unreconciled `STARTED` runs, no unexpected restart growth, and conserved
outbox/ready/delivered/collector-ledger state.

No disposable GX10 host has executed this complete extension sequence. This is
retained empirical risk: stop on any mismatch rather than translating
historical production commands by memory.

## Failure and rerun rules

- Stop on the first failed marker. Never weaken a verifier to make installation continue.
- Filesystem, configuration, application, Ollama-binary, and model-store installation can reuse exact existing artifacts and refuse divergent ones.
- The database initializer intentionally cannot be rerun after successful creation.
- A partially copied model store may be resumed only when every existing artifact is exact. Divergent files require operator investigation; the importer never replaces them.
- Preactivation refuses a used database, spool content, SQLite sidecars, active units, enabled runtime units, unit drop-ins, or altered installed artifacts.
- Do not use this runbook to repair or modify the working reference GX10.
- Do not enable result return as part of base activation. It is a separately
  implemented current extension and must pass Phase 11's independent gates.
- Do not run the legacy snapshot upgrader on a clean installation; the clean
  outbox installer already installs the current snapshot-aware boundary.
- The application installer places the item-26 correlation and item-29 reasoning runner/unit files, but the base clean-runtime activator deliberately leaves both timers disabled.
- Use Phase 9 and `docs/MANAGED_CORRELATION.md` before Phase 10. Use Phase 10 and `docs/MANAGED_REASONING.md` only after deterministic correlation and local-model copy gates pass and operator authorization is explicit.

For a temporary disable after successful first activation, preserve all durable
state and stop only the owning timer/oneshot:

    systemctl disable --now network-log-gx10-result-sender.timer
    systemctl stop network-log-gx10-result-sender.service
    systemctl disable --now network-log-gx10-result-outbox.timer
    systemctl stop network-log-gx10-result-outbox.service network-log-gx10-outbox-snapshot.service
    systemctl disable --now network-log-gx10-reasoning.timer
    systemctl stop network-log-gx10-reasoning.service
    systemctl disable --now network-log-gx10-correlation.timer
    systemctl stop network-log-gx10-correlation.service

Disable downstream-to-upstream in that order. Re-enable upstream-to-downstream
only after each installed-state verifier passes, then run its active verifier.
This recovery path applies only to an already activated exact installation; it
does not replace the guarded first-activation scripts. Never remove or restore
the database, snapshot, outbox, delivered files, key, ledger, quarantine, or
activation backup merely to make a verifier pass.

## Current validation status

Repository-only synthetic validation is complete. End-to-end execution of this
runbook—including Phase 11—on a disposable Ubuntu 24.04 arm64 GX10-class host
remains outstanding because no such validation target is currently available.

Do not report clean-machine validation complete until the full runbook has passed on that disposable target and the result has been journaled.
