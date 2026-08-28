# Two-Server Rebuild Runbook

## Purpose

This runbook coordinates the collector and GX10 component runbooks at the system boundary. It does not duplicate their installation commands.

Use:

- `components/collector/README.md` for the clean collector
- `components/gx10/CLEAN_MACHINE_RUNBOOK.md` for the clean GX10

Both machines must use the same reviewed repository revision. Never mix artifacts from different commits.

## What the current rebuild reproduces

The current reconstructed automatic path is:

```text
devices
  -> collector Vector ingest
  -> collector ClickHouse raw storage
  -> collector compressed hourly backlog
  -> restricted read-only SFTP
  -> GX10 scheduled fetch
  -> GX10 replay-safe SQLite ingest
```

The collector also has a separate write-only AI-result transport, validation gate, ClickHouse sink, and Grafana presentation boundary.

The clean-machine base package intentionally reproduces the captured
fetch-to-ingest boundary first. Historical rediscovery found no predecessor
producer for the result-return boundary, no automatic canonical normalized-
field projection, and no application-specific Ollama caller. The active
production system now has separately gated extensions for those capabilities;
their activation is documented in `docs/CURRENT_STATE.md` and the relevant
component runbooks. Do not enable an extension by inference during a base
rebuild, and do not claim its end-to-end result path until its dedicated gate
has passed.

A rebuild of the **current functional target** therefore has two layers:

1. reconstruct and verify the captured base `fetch -> ingest` path
2. install and independently activate the documented normalization handoff,
   deterministic correlation, managed reasoning/hidden triage, selective
   outbox snapshot, lifecycle/result producers, and write-only sender gates

Completing only the first layer is a base-runtime rebuild, not a complete
reconstruction of the current application.

## Host prerequisites

Collector:

- clean Debian 13 amd64 host
- package/ACME network access and required inbound syslog, HTTPS, ACME, and restricted SSH/SFTP reachability
- the ten private/environment-specific inputs listed in the collector runbook

GX10:

- clean Ubuntu 24.04 arm64 GX10-class host
- captured kernel, NVIDIA driver, and CUDA compiler baseline
- exact pinned application packages
- exact captured Ollama binary
- exact offline six-model store
- outbound reachability to the collector's restricted read-only SFTP boundary
- the protected inputs listed in the GX10 runbook

Firewall/nftables policy is deliberately operator-owned and outside the public repository. Satisfy the functional connectivity requirements without publishing deployment allowlists.

## Transport-key relationship

Prepare independent least-privilege key material for the two collector transport roles:

1. backlog reader:
   - public authorized key is supplied to the collector rebuild
   - matching private key and pinned known-hosts file are supplied to the GX10 rebuild
   - role is read-only
2. AI-result writer:
   - public authorized key is supplied to the collector rebuild
   - matching private key and pinned collector metadata are supplied privately
     to the separately gated GX10 sender configuration
   - role is write-only and cannot read collector logs or ClickHouse

Do not reuse one keypair for both roles. Creating either identity alone is not
proof of a working end-to-end transport; require the dedicated sender,
acceptance-ledger, ClickHouse, replay, and conflict gates.

## Rebuild order

### 1. Select and verify one repository revision

Choose the reviewed milestone commit and use it for both hosts. Require a clean checkout before running either component audit.

### 2. Rebuild and verify the collector first

Follow `components/collector/README.md` through:

- package installation and `COLLECTOR_PACKAGE_VERIFY=PASS`
- runtime installation and `COLLECTOR_RUNTIME_INSTALL=PASS`
- safe nonstandard SSH-port activation
- independent `COLLECTOR_RUNTIME_VERIFY=PASS`

Do not proceed to GX10 until the collector backlog exists, its read-only transport is reachable, and the collector runtime verifier passes.

### 3. Prepare GX10 transport inputs from the verified collector

Outside both repositories:

- retain the backlog-reader private key
- generate a pinned known-hosts file for the verified collector endpoint
- record the collector endpoint, nonstandard port, and read-only username in the protected GX10 operator-input file

Never place these values or files in Git.

### 4. Rebuild GX10 without activation

Follow `components/gx10/CLEAN_MACHINE_RUNBOOK.md` through the preactivation phase:

- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- `GX10_PLATFORM_VERIFY=PASS`
- filesystem/configuration/database/application installation
- exact Ollama binary and offline model-store installation
- `GX10_RUNTIME_PREACTIVATION_VERIFY=PASS`
- offline `GX10_OLLAMA_VERIFY=PASS`

The GX10 spool and four application-state tables must still be empty at this point.

### 5. Activate GX10

Review the protected collector endpoint before supplying the second activation confirmation.

The activator enables Ollama first and the fetch/ingest timer second. It never enables canonical projection.

Require:

- `GX10_RUNTIME_ACTIVATION=PASS`
- `GX10_RUNTIME_ACTIVE_VERIFY=PASS`
- active `GX10_OLLAMA_VERIFY=PASS`

### 6. Verify the automatic cross-server path

After at least one timer interval:

- confirm the GX10 timer remains active
- inspect the fetch/ingest service result and recent logs
- confirm eligible collector backlog files are fetched through the read-only role
- confirm successfully ingested files move from GX10 incoming to processed state
- confirm replay does not duplicate `(source_file, record_number)` observations
- rerun both independent runtime verifiers

Do not invoke canonical projection ad hoc merely to make the end-to-end path look longer. Follow the component runbook's separate inactive install, initial backfill, zero-lag verification, and correlation-timer activation gate.

### 7. Activate and verify the post-base application gates

First complete Phase 9 and Phase 10 of the GX10 runbook for deterministic
correlation and managed local reasoning. Then follow the separately gated
contracts in:

- `docs/NORMALIZER_PRODUCTION_INTEGRATION.md`
- `docs/NORMALIZER_HANDOFF.md`
- `docs/AI_DETECTION_SIDE_CHANNEL.md`
- `docs/RESULT_OUTBOX.md`
- `docs/RESULT_TRANSPORT.md`
- `docs/NOC_WORKFLOW.md`

Require the collector normalizer's isolated activation and verified forward-
only GX10 handoff before retiring the raw view. Then require the selective
outbox snapshot, AI-result and incident-lifecycle
producers, disabled/inactive sender installation, dedicated collector writer
authorization, private sender configuration, explicit active verification, and
natural one-file delivery. Prove exact collector acceptance, one ClickHouse row
per accepted result, lifecycle-only routing to `incident_updates`, replay
isolation, divergent same-name conflict isolation, and dashboard queries.

The public artifacts and protected working-system gates exist, but this entire
sequence has not been executed on disposable clean hosts. Follow every current
installer/verifier and stop on disagreement; do not treat the historical
rediscovery absence as an instruction to omit reconstructed extensions.

## Required completion evidence

A disposable two-server rebuild is complete only when the operator records:

- exact repository revision used on both hosts
- collector package/runtime pass markers
- GX10 package/platform/preactivation/activation/runtime/Ollama pass markers
- restricted backlog transport success
- one successful automatic fetch/ingest cycle
- normalized forward-only handoff identity/hash parity with raw rollback
  retained
- successful managed-correlation inactive install, initial backfill, and at least three zero-lag scheduled cadences
- successful managed-reasoning and hidden-triage activation with bounded
  fail-closed model behavior
- successful selective snapshot, result/lifecycle outbox, configured sender,
  one-file delivery, collector acceptance, ClickHouse provenance, replay, and
  divergent-conflict gates
- replay/idempotency result
- rerun of both independent runtime verifiers
- confirmation that the correlation timer is separately disableable and the original fetch/ingest timer remains healthy
- confirmation that every reconstructed extension matches its versioned public
  contract and remains independently disableable

Record only public-safe outcomes and hashes. Never record private addresses, ports, usernames, credentials, keys, known-hosts contents, production log rows, or model blob contents.

## Deferred execution status

Repository reconstruction, synthetic tests, live read-only parity checks, and operator documentation are complete.

Disposable-host execution remains empirically unverified for both components because suitable clean validation systems are not available. The operator waived that gate for project sequencing with residual risk retained. Therefore the project must not claim that the full two-server clean rebuild passed.

## Failure rule

Stop at the first failed gate and follow the component runbook's recovery policy.

- Do not weaken clean-host refusals or service guards.
- Do not run either clean-machine installer against a reference system.
- Do not bypass collector database-existence refusal.
- Do not bypass GX10 empty-state, offline-model, or dual-confirmation activation gates.
- Do not add missing future architecture during reconstruction validation.
