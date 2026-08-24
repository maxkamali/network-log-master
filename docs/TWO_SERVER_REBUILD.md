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

The current GX10 package does not contain a producer for that result-return boundary. It also does not automatically run canonical normalized-field projection and does not contain an application-specific Ollama caller. A successful rebuild must preserve those absences.

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
   - role is write-only
   - the current reconstructed GX10 does not install or use the matching private key because no GX10 result producer was discovered

Do not reuse one keypair for both roles. Do not interpret creation of the result-writer boundary as proof of a working GX10 result producer.

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

### 7. Verify the independent collector result boundary

The collector runtime verifier covers the write-only transport, validation gate, ClickHouse AI-update storage, and Grafana presentation prerequisites.

Do not claim an end-to-end GX10 AI-result round trip. The current GX10 rebuild has no discovered result producer or observability-pipeline Ollama caller.

## Required completion evidence

A disposable two-server rebuild is complete only when the operator records:

- exact repository revision used on both hosts
- collector package/runtime pass markers
- GX10 package/platform/preactivation/activation/runtime/Ollama pass markers
- restricted backlog transport success
- one successful automatic fetch/ingest cycle
- successful managed-correlation inactive install, initial backfill, and at least three zero-lag scheduled cadences
- replay/idempotency result
- rerun of both independent runtime verifiers
- confirmation that the correlation timer is separately disableable and the original fetch/ingest timer remains healthy
- confirmation that no GX10 result producer or application-specific Ollama caller was invented

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
