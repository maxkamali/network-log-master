# Two-Server Rebuild Runbook

## Purpose and authority

This is the single authority for the ordered reconstruction of the current functional target
across an application-clean collector and an application-clean compatible
GX10. Component
runbooks own their host-specific commands; this document owns ordering,
cross-host inputs, inter-host acceptance, and rollback boundaries.

Use the same reviewed repository revision on both hosts. Never mix artifacts
from different commits. Do not run clean-machine installers on a working
reference system.

The rebuild has two layers:

1. the captured base `collector backlog -> GX10 fetch -> replay-safe ingest`
2. current reconstructed extensions: normalizer/handoff, deterministic
   correlation, managed reasoning and hidden triage, selective outbox snapshot,
   lifecycle/result producers, write-only sender, and NOC presentation

Completing only the first layer is a base-runtime rebuild, not a complete
reconstruction of the current application.

## Complete rebuild-input contract

“Application-clean” means no predecessor network-log application state or
services. It does not mean that this repository can turn an arbitrary bare
GX10 into the captured GPU platform. A complete rebuild requires all four input
classes below:

1. one clean Debian 13 amd64 collector and one clean Ubuntu 24.04 arm64
   GX10-class host compatible with the captured platform baseline;
2. the same reviewed public repository revision on both hosts;
3. the private deployment values and files inventoried below; and
4. an external GX10 prerequisite bundle: the captured kernel/NVIDIA
   driver/CUDA compiler baseline, repositories or mirrors containing the exact
   pinned packages, the exact hash-qualified Ollama executable, and the exact
   six-model offline store including every referenced blob.

The repository installs the application layer and verifies the bundle. It does
not acquire the exact Ollama binary or model blobs, provision the kernel,
driver, or CUDA layers, or guarantee that historical pinned packages remain on
public mirrors. If any bundle item is unavailable, stop before GX10 activation;
IPs, usernames, and credentials alone cannot complete the rebuild. Exact
versions, sizes, and hashes are owned by the GX10 runbook and its retained
manifests rather than duplicated here.

## Private deployment-input contract

Keep every populated input outside the checkout in root-owned, non-group/world
writable storage. A private file must be a regular single-link file with mode
`0400` or `0600` unless the consuming installer documents another mode. Never
echo a value, copy it into Git, or put it in a command transcript.

| Input | Consumer | Form and lifecycle | Purpose |
| --- | --- | --- | --- |
| Collector base inputs | collector runtime installer | Existing ten inputs in `components/collector/README.md`; retained through collector verification | ClickHouse/Grafana passwords, public host/certificate parameters, SSH port, and both authorized-key files |
| `PLATFORM_INVENTORY_FILE` | normalizer shadow installer | Root-owned private schema-v1 inventory; retained | Trusted device/platform mapping |
| `HANDOFF_PLAN_FILE` | normalizer handoff installer | Root-owned private schema-v1 plan; immutable floor selected after shadow catch-up | Forward-only normalized handoff boundary |
| Backlog-reader collector host, port, username, private key, and known-hosts | GX10 base | Distinct endpoint/identity plus private key and pin; retained | Read-only collector backlog access |
| Result-writer private key | GX10 sender configuration | Distinct private key staged briefly from protected storage; retained only in service-owned target | Write-only collector result access |
| Reasoning recovery target | GX10 reasoning activation | Protected absent backup path | Pre-activation recovery evidence |
| Grafana server-administrator login/password file, collector-side ClickHouse host, and existing read-only Grafana-reader password file | NOC reconstruction | Existing private collector inputs; retained | Organization, datasource, and Viewer setup |
| NOC Viewer username, display name, email, password file, and organization name | NOC reconstruction | Operator-selected private inputs; exact field constraints and use are in `docs/GRAFANA.md` | Isolated NOC access layer |
| Administrator evidence-transfer channel | first-live qualification | Existing non-root sudo-capable administrator usernames on both hosts plus their operator-host SSH aliases; values stay outside Git and transcripts | Transient byte-for-byte prepared/finalized evidence transfer without granting either application SFTP role new access |
| First-live prepared/finalized evidence | GX10 capture and collector verifier | Canonical root-owned mode-`0600` files transferred byte-for-byte only through the administrator channel; retained through reboot acceptance | Bind one exact sender transition to collector ledger/ready/ClickHouse provenance |
| Rollback locations | collector/GX10/NOC steps | Root-owned locations outside checkout | Exact predecessor or configuration recovery artifacts |

The two SSH roles are independent:

1. the **backlog reader** can only read the collector spool;
2. the **result writer** can only publish validated result files.

Do not reuse their keys. On a clean collector, the writer public key is already
installed by the base runtime installer; the later authorizer is for controlled
existing-host upgrades, not a mandatory second clean-rebuild mutation.

## Host prerequisites

Collector:

- clean Debian 13 amd64 host
- package, ACME, syslog, HTTPS, and restricted SSH/SFTP reachability
- the collector base inputs and extension inputs above

GX10:

- application-clean Ubuntu 24.04 arm64 GX10-class host compatible with the
  captured baseline
- captured kernel, NVIDIA driver, CUDA compiler baseline, pinned packages,
  exact Ollama binary, and exact offline model store
- reachability to both collector transport roles
- the GX10 base and extension inputs above

Firewall policy remains operator-owned. Meet functional connectivity without
publishing deployment addresses or allowlists.

## Ordered reconstruction

### 1. Freeze the revision and validate inputs

On both hosts, clone the same reviewed commit and require a clean checkout.
Run repository-only validators before making host changes. Verify private files
exist, have safe metadata, and satisfy each installer’s `--check`/preflight
without printing their contents.

### 2. Rebuild the collector base

Follow `components/collector/README.md` through package installation, runtime
installation, safe SSH-port activation, and independent verification. Require:

- `COLLECTOR_PACKAGE_VERIFY=PASS`
- `COLLECTOR_RUNTIME_INSTALL=PASS`
- `COLLECTOR_RUNTIME_VERIFY=PASS`

Do not continue until the raw backlog exists and the read-only backlog role is
reachable. The collector base also installs the write-only result role, result
gate, ClickHouse schema, main Grafana resources, and their verifiers.

### 3. Rebuild and activate the GX10 base

Follow `components/gx10/CLEAN_MACHINE_RUNBOOK.md` through base preactivation
and activation. Require:

- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- `GX10_PLATFORM_VERIFY=PASS`
- `GX10_RUNTIME_PREACTIVATION_VERIFY=PASS`
- `GX10_OLLAMA_VERIFY=PASS`
- `GX10_RUNTIME_ACTIVATION=PASS`
- `GX10_RUNTIME_ACTIVE_VERIFY=PASS`

At preactivation, all verifier-enumerated initialized application state,
cursors, spool files, and SQLite sidecars must be empty. Do not hard-code a
table count.

### 4. Prove one raw base cycle

Wait for at least one scheduled fetch/ingest cycle. Confirm a read-only spool
file was fetched, ingested, moved to processed state, and cannot duplicate
`(source_file, record_number)` on replay. The original fetch/ingest timer must
remain healthy throughout every later extension step.

### 5. Activate normalizer shadow before GX10 correlation

Install and verify the normalizer shadow package with the private inventory,
then enable only its shadow timer. Require staged and active verifier success,
shadow catch-up, and zero pending work before choosing the handoff floor.

Choose an immutable inclusive source path at least ten minutes in the future
and beyond the highest path already consumed by GX10. Stage the handoff
publisher and verify it before altering GX10’s read-only view.

### 6. Perform the bind-only normalized handoff

Use the clean-host command sequence in `docs/NORMALIZER_HANDOFF.md`. It names the
public clean-rebuild units, stages and runs the publisher while GX10 is paused,
stops the two collector timers for a stable prepared/cutover verification,
switches only the protected read-only bind, then resumes collector schedules and
one bounded GX10 cycle before its timer. Require exact file hash and record-count
parity. The rollback is a GX10 pause followed by exact restoration of the
protected raw-bind `/etc/fstab` predecessor and one replay-safe manual cycle;
raw and shadow files are never rewritten.

### 7. Activate deterministic correlation

Only after normalized handoff parity passes, perform the inactive install,
initial backfill, and active multi-cadence verification in Phase 9 of the GX10
runbook. Require zero projection and incident lag, a healthy original timer,
and a separately disableable correlation timer.

### 8. Activate managed reasoning and hidden triage

Follow Phase 10 of the GX10 runbook and `docs/AI_DETECTION_SIDE_CHANNEL.md`.
Managed reasoning owns both selected incident assessment and hidden uncovered
event triage. Require bounded one-run-per-cadence behavior, zero unreconciled
`STARTED` runs, no service restarts, and continued health of fetch/ingest and
correlation. Gemma failure leaves model work pending/no-result; it must not
block raw capture, fetch/ingest, or deterministic incident state.

The clean host must install the exact selected model manifest/configuration that
already passed the retained synthetic and protected-current-state-copy
qualification. The private historical database copy is model-version evidence,
not an input a clean host must recreate. Any model/prompt/schema/configuration
change reopens qualification and is outside rebuild scope.

### 9. Activate snapshot, outbox, and sender

Follow Phase 11 of the GX10 runbook exactly:

1. install and verify the local result/lifecycle outbox while inactive;
2. activate and verify the current selective-snapshot boundary without network
   transport;
3. install the sender inactive and verify staged state;
4. configure its distinct private writer identity while the timer is disabled,
   then remove and verify absence of the staged `/run` source;
5. run the retained synthetic sender/gate replay and divergent-conflict suites;
6. run the repository GX evidence prepare, transfer it only through the
   administrator channel, and require collector preflight before one manual
   sender oneshot;
7. finalize and transfer the GX evidence, then require the strict private
   collector ledger/ready/ClickHouse verifier in `docs/RESULT_TRANSPORT.md`;
8. enable the sender timer only after that proof passes;
9. prove natural cadence health.

The clean outbox installer already installs the current selective
rollback-journal snapshot. Never run the legacy
`upgrade-result-outbox-snapshot.py` after a clean install; its exact legacy
preconditions intentionally conflict with the current clean-installed state.

The retained synthetic suites replace deliberate live replay and divergent-
content re-upload probes during clean rebuild. They do not replace the
repository's executable first-live proof. Follow its prepare -> collector
preflight -> one manual send -> finalize -> collector final sequence exactly;
post-hoc collector selection is not a substitute.

Require one collector ledger identity and one matching ClickHouse row for an AI
file, or exactly `record_count` matching rows for a lifecycle batch. Lifecycle
records must route only to `incident_updates`; AI records must route only to
`ai_updates`.

### 10. Restore main Grafana resources and the NOC layer

The collector installer restores six main-organization resources and verifies
their queries. Then follow `docs/GRAFANA.md` to create the isolated NOC
organization, Viewer, two read-only datasources, two organization-local
dashboards, home/star settings, Explore compatibility, and one-minute playlist.
Use `build-noc-organization-captures.py` to create the exact private two-
dashboard stage, then use the retained restore/query verifiers with
`--expected-count 2`. The helper does not contact Grafana. Organization,
account, datasource, permission, preference, and playlist operations remain the
exact manual/API sequence; verify every requested isolation and denial boundary.

### 11. Full acceptance and staggered reboot

Use this matrix before reboot and again after each host returns. Commands are run
from the same reviewed checkout unless an installed absolute verifier is shown.

The base Phase-2 invocation uses the verifier's fail-closed default raw transport
view. After cutover, select the explicit current handoff view; every other
collector check remains unchanged:

    INPUT_DIR=/root/collector-rebuild-inputs
    export INPUT_DIR
    test -s "$INPUT_DIR/clickhouse-default-password"
    env CLICKHOUSE_DEFAULT_PASSWORD_FILE="$INPUT_DIR/clickhouse-default-password" \
        components/collector/install/verify-runtime.sh --transport-view handoff

Require both `reader_bind_source=handoff` and
`COLLECTOR_RUNTIME_VERIFY=PASS`. The handoff mode accepts only the exact
`/var/spool/network-log-normalizer-handoff` bind source, current owner/group,
read-only mount options, ACL, and exact `/etc/fstab` line. Omitting the option
continues to require the raw `/var/spool/vector-ai` base view.

Collector normalizer/handoff, with a bounded stable pause for the handoff
verifier (stopping a timer does not disable it):

    /usr/local/sbin/verify-network-log-normalizer-shadow --mode active
    systemctl stop network-log-normalizer-shadow.timer
    systemctl stop network-log-normalizer-shadow.service
    systemctl stop network-log-normalizer-handoff.timer
    systemctl stop network-log-normalizer-handoff.service
    systemctl is-enabled --quiet network-log-normalizer-shadow.timer
    systemctl is-enabled --quiet network-log-normalizer-handoff.timer
    systemctl start network-log-normalizer-handoff.service
    test "$(systemctl show network-log-normalizer-shadow.service --property=ActiveState --value)" = inactive
    test "$(systemctl show network-log-normalizer-handoff.service --property=ActiveState --value)" = inactive
    test "$(systemctl show network-log-normalizer-handoff.service --property=Result --value)" = success
    /usr/local/sbin/verify-network-log-normalizer-handoff --mode cutover
    systemctl start network-log-normalizer-shadow.timer
    systemctl start network-log-normalizer-handoff.timer
    systemctl is-enabled --quiet network-log-normalizer-shadow.timer
    systemctl is-enabled --quiet network-log-normalizer-handoff.timer
    systemctl is-active --quiet network-log-normalizer-shadow.timer
    systemctl is-active --quiet network-log-normalizer-handoff.timer

Run the cutover verifier only after the handoff oneshot reports inactive. Its
stable `cutover` mode deliberately expects the timer enabled but temporarily
inactive. Shadow is frozen before the final bounded handoff publication so a new
completed shadow row cannot race the complete handoff inventory; both timers are
restarted after verification.

GX10 current extended state:

    components/gx10/install/verify-platform.py
    components/gx10/install/verify-ollama.py
    systemctl is-enabled --quiet network-log-gx10.timer
    systemctl is-active --quiet network-log-gx10.timer
    components/gx10/install/verify-correlation.py --active --private-runtime
    components/gx10/install/verify-managed-reasoning.py --active --private-runtime
    components/gx10/install/verify-result-outbox.py --active
    components/gx10/install/verify-result-sender.py --configured --active \
        --runtime-config /etc/network-log-gx10/runtime.json

Do not rerun the base `verify-runtime.py --active` after the extension phases;
it correctly verifies the earlier base-only state and therefore requires the
correlation and reasoning timers to be disabled.

`INPUT_DIR` above is the retained private collector input directory used in
Phase 2; if the operator chose another absolute path, re-establish that exact
path instead. Repeat its assignment and protected-file check after each
collector reconnect.

Before either reboot, let every named oneshot report inactive, record the
redacted verifier/cardinality markers and restart counts, and confirm all
expected timers are enabled. Reboot the collector first. After reconnecting,
repeat the collector checks above and verify restricted read/write transport,
main dashboard queries, NOC isolation, and conserved accepted-ledger/ready
counts. Only then reboot GX10. After reconnecting, repeat the GX10 checks above
and require zero projection/incident/triage lag, zero `STARTED` reasoning runs,
unchanged delivered/ready counts except for explained in-flight movement, and no
unexpected restart growth.

The NOC private capture transformation plus dashboard restore/query verifiers
are retained. Its organization/account/datasource/permission/preference/
playlist operations still have no idempotent end-to-end bootstrap; execute and
record the exact manual/API acceptance matrix in `docs/GRAFANA.md`.


## Required completion evidence

Record only public-safe outcome markers, versions, and public artifact hashes:

- shared repository revision and clean checkouts
- collector package/runtime, transport, result-gate, ClickHouse, and Grafana
  verification markers
- GX10 package/platform/preactivation/activation/Ollama markers
- raw-cycle success and normalized handoff parity with raw rollback retained
- correlation, reasoning/triage, snapshot, outbox, and sender verifier markers
- first-live delivery, synthetic exact-replay/divergent-conflict qualification,
  and natural sender cadence evidence
- record-count-matched ClickHouse provenance and exclusive lifecycle routing
- main dashboard and isolated NOC inventory/query/permission verification
- collector-then-GX10 reboot recovery

Never record addresses, ports, usernames, credentials, keys, known-hosts
contents, production log rows, or model blobs.

## Failure and rollback rules

Stop at the first failed gate. Do not weaken installer refusals, verifier
checks, or service guards merely to continue.

- Base rebuild failures require correcting the input/environment and
  reprovisioning a clean host when the installer refuses a used state.
- Correlation, reasoning, outbox, and sender rollback is disable-only unless a
  dedicated guarded rollback exists; preserve databases, ledgers, ready files,
  quarantine, and backups.
- Normalizer rollback is the protected raw-bind restoration described above.
- Do not restore an old SQLite backup over newer ingest state.
- Do not add architecture beyond the versioned current target during a rebuild.

For an already activated exact GX10 installation, disable downstream-to-
upstream without deleting state:

    systemctl disable --now network-log-gx10-result-sender.timer
    systemctl stop network-log-gx10-result-sender.service
    systemctl disable --now network-log-gx10-result-outbox.timer
    systemctl stop network-log-gx10-result-outbox.service network-log-gx10-outbox-snapshot.service
    systemctl disable --now network-log-gx10-reasoning.timer
    systemctl stop network-log-gx10-reasoning.service
    systemctl disable --now network-log-gx10-correlation.timer
    systemctl stop network-log-gx10-correlation.service

Re-enable upstream-to-downstream only after the corresponding installed-state
checks pass, then require its active verifier. These direct timer controls are a
recovery path for a previously activated exact installation; first activation
must use the guarded activators in the GX10 runbook. Normalizer bind rollback is
the exact collector/GX10 sequence in `docs/NORMALIZER_HANDOFF.md`.

## Deferred execution status

Repository reconstruction, synthetic tests, and read-only-reference checks are
complete. Disposable clean-host execution remains `WAIVED BY OPERATOR` and
empirically unverified because suitable systems are unavailable. This runbook
is the procedure to execute when they become available; it must not be cited as
proof that a full two-server clean rebuild already passed.

Strict private first-live ledger/ready/ClickHouse provenance now has executable
GX capture and collector verification helpers plus cross-component synthetic
tests. It remains empirically unexecuted on disposable clean hosts, not a
missing-tool boundary. NOC organization/account/datasource reconstruction
remains a documented manual/API boundary, with retained dashboard
staging/restore/query verification but no end-to-end mutation helper.
