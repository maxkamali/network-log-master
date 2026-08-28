# Two-Server Rebuild Runbook

## Purpose and authority

This is the single authority for the ordered reconstruction of the current functional target
across a clean collector and a clean GX10. Component
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

## Private-input contract

Keep every populated input outside the checkout in root-owned, non-group/world
writable storage. A private file must be a regular single-link file with mode
`0400` or `0600` unless the consuming installer documents another mode. Never
echo a value, copy it into Git, or put it in a command transcript.

| Input | Consumer | Form and lifecycle | Purpose |
| --- | --- | --- | --- |
| Collector base inputs | collector runtime installer | Existing ten inputs in `components/collector/README.md`; retained through collector verification | ClickHouse/Grafana passwords, public host/certificate parameters, SSH port, and both authorized-key files |
| `PLATFORM_INVENTORY_FILE` | normalizer shadow installer | Root-owned private schema-v1 inventory; retained | Trusted device/platform mapping |
| `HANDOFF_PLAN_FILE` | normalizer handoff installer | Root-owned private schema-v1 plan; immutable floor selected after shadow catch-up | Forward-only normalized handoff boundary |
| Backlog-reader key and known-hosts | GX10 base | Distinct private key plus pin; retained | Read-only collector backlog access |
| Result-writer private key | GX10 sender configuration | Distinct private key staged briefly from protected storage; retained only in service-owned target | Write-only collector result access |
| Reasoning recovery target | GX10 reasoning activation | Protected absent backup path | Pre-activation recovery evidence |
| Snapshot recovery directory | GX10 snapshot upgrade | Protected absent child directory | Snapshot upgrader backup |
| Grafana administrator and reader credentials | NOC reconstruction | Existing private collector inputs; retained | Organization, datasource, and Viewer setup |
| NOC Viewer username, password file, and organization name | NOC reconstruction | Operator-selected private inputs | Isolated NOC access layer |
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

- clean Ubuntu 24.04 arm64 GX10-class host
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

Stop or pause GX10 only long enough to stabilize the handoff view. Preserve the
raw bind configuration, switch GX10 to the verified normalized read-only bind,
and run the prepared/cutover verifier. Resume schedules, process one normalized
cycle, and require exact file hash and record-count parity. The rollback is a
GX10 pause followed by restoration of the raw read-only bind and replay check;
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

### 9. Activate snapshot, outbox, and sender

Follow Phase 11 of the GX10 runbook exactly:

1. install and verify the local result/lifecycle outbox while inactive;
2. activate and verify it without network transport;
3. preflight and apply the selective rollback-journal snapshot upgrade;
4. install the sender inactive and verify staged state;
5. configure its distinct private writer identity while the timer is disabled;
6. prove one bounded first-live file and collector acceptance;
7. prove exact replay and divergent same-name conflict isolation;
8. enable the sender timer and prove natural cadence health.

Require one collector ledger identity and exactly one matching ClickHouse row
for a first-live file. Lifecycle records must route only to
`incident_updates`; AI records must route only to `ai_updates`.

### 10. Restore main Grafana resources and the NOC layer

The collector installer restores six main-organization resources and verifies
their queries. Then follow `docs/GRAFANA.md` to create the isolated NOC
organization, Viewer, two read-only datasources, two organization-local
dashboards, home/star settings, Explore compatibility, and one-minute playlist.
NOC provisioning is currently a documented manual/API procedure, not a
permanent automated helper; verify every requested permission boundary.

### 11. Full acceptance and staggered reboot

Run every host/component verifier plus the normalizer, handoff, sender, gate,
dashboard, NOC, and data-flow checks listed below. Let oneshot services settle,
reboot the collector first, verify it, then reboot GX10 and verify it. A reboot
pass requires all expected services/timers enabled, no unexpected restart
growth, zero deterministic lag, and conserved outbox/ready/delivered/ledger
state.

## Required completion evidence

Record only public-safe outcome markers, versions, and public artifact hashes:

- shared repository revision and clean checkouts
- collector package/runtime, transport, result-gate, ClickHouse, and Grafana
  verification markers
- GX10 package/platform/preactivation/activation/Ollama markers
- raw-cycle success and normalized handoff parity with raw rollback retained
- correlation, reasoning/triage, snapshot, outbox, and sender verifier markers
- first-live delivery, exact replay, divergent-conflict, and natural sender
  cadence evidence
- one-row-per-accepted-result ClickHouse provenance and lifecycle routing
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

## Deferred execution status

Repository reconstruction, synthetic tests, and read-only-reference checks are
complete. Disposable clean-host execution remains `WAIVED BY OPERATOR` and
empirically unverified because suitable systems are unavailable. This runbook
is the procedure to execute when they become available; it must not be cited as
proof that a full two-server clean rebuild already passed.
