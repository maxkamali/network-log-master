# Collector rebuild checkpoint

Status: public collector rebuild package, sanitation, and operator documentation complete. Clean-machine end-to-end validation was unavailable and waived by the operator; it remains empirically unverified.

## Execution authority

This file records detailed collector-specific rebuild evidence and remaining technical work. `docs/CURRENT_STATE.md` at the repository root is the authority for project execution order and the single `NEXT` item.

The later production-normalizer extension is implemented separately under `components/collector/normalizer/`. It is not part of the clean-machine reconstruction path and is not invoked by that installer. Shadow mode was separately authorized and activated on 2026-08-23. Its catch-up/steady-state evidence and the forward-only handoff design/rehearsal passed. On 2026-08-24 the separate handoff package completed its guarded immutable-floor production activation with exact collector/GX10 hash and cardinality parity; the raw backlog and exact mount-only rollback remain preserved. See `docs/NORMALIZER_PRODUCTION_INTEGRATION.md` and `docs/NORMALIZER_HANDOFF.md`.

After each completed validated collector sub-section, append and push a `docs/PROJECT_JOURNAL.md` entry before materially proceeding into the next sub-section.

## Rebuild objective

Two clean servers, this public repository, and operator-supplied environment values must be sufficient to reconstruct the functional deployment without undocumented implementation knowledge.

Deployment-specific secrets, credentials, addresses, SSH keys, certificate private keys, and private identity values are intentionally not stored in this repository.

## Previous completed milestone

The normalizer replay/parity milestone was completed before this collector checkpoint.

Reference public commit:

`4220f50474d608fd8745b4465398af521d7625bd`

The normalizer test suite had 73 passing tests. Live replay parity used 24 samples with 21 strict matches, 3 intentional differences, and 0 unexpected differences.

## Collector package layer

Captured versions include:

- Vector 0.57.0-1
- ClickHouse server/client 26.3.17.110
- Grafana OSS 13.1.1
- Grafana ClickHouse plugin 4.20.0
- Certbot 5.7.0

The package verifier passed against the reference collector:

`COLLECTOR_PACKAGE_VERIFY=PASS`

The rebuild package installer installs explicit captured versions. It does not invent an apt hold policy that is absent from production.

Package-install no-autostart protection is complete. Before apt transactions, the installer installs a temporary `policy-rc.d` deny guard plus persistent systemd condition guards for Vector, ClickHouse, and Grafana. Existing active SSH management access is preserved; otherwise SSH is held until transport configuration is validated.

Runtime installation uses short-lived authorization for required pre-final starts while retaining persistent guards, and permanently releases the collector guards only at final configured-service activation.

Validation includes:

- `PACKAGE_NO_AUTOSTART_FAILURE_PATH_VALIDATION=PASS`
- `SYSTEMD_GUARD_BLOCK=PASS`
- `SYSTEMD_TEMPORARY_AUTHORIZATION=PASS`
- `SYSTEMD_GUARD_REASSERTION=PASS`
- `SYSTEMD_FINAL_RELEASE=PASS`
- `collector_service_state_unchanged=PASS`
- `PACKAGE_NO_AUTOSTART_SYNTHETIC_PROOF=PASS`

## Configuration renderer

`install/render-configs.py` renders environment-specific configuration using operator-supplied values.

It renders:

- Vector configuration
- ClickHouse access SQL
- Grafana ClickHouse datasource provisioning
- Grafana HTTPS systemd override
- Grafana certificate renewal deploy hook

Service-account passwords are supplied using operator-owned password files rather than being committed to the repository.

## Vector

The current Vector implementation is captured.

Important behavior preserved:

- UDP syslog ingestion
- TCP syslog ingestion
- current normalization/transforms
- ClickHouse syslog sink
- ClickHouse AI-update sink
- AI result ingestion
- durable compressed GX10 spool output
- existing disabled ClickHouse sink health checks
- existing Vector validation behavior

GX10 spool output remains under `/var/spool/vector-ai` using UTC time partitioning, JSON Lines, and zstd compression.

The live runtime verifier passed:

`VECTOR_CRITICAL_CONFIG_PARITY=PASS`

`VECTOR_SYSLOG_LISTENERS=PASS`

## ClickHouse

Captured database objects:

- `observability.syslog`
- `observability.ai_updates`
- `observability.grafana_logs`

Captured access policy includes:

- `grafana_reader`
- `vector_ingest`
- Grafana read-only settings profile
- required SELECT grants
- required INSERT grants

ClickHouse application listeners remain loopback-only.

The independent live verifier passed:

`CLICKHOUSE_OBJECT_CONTRACT=PASS`

`CLICKHOUSE_COLUMN_CONTRACT=PASS`

`CLICKHOUSE_USER_POLICY=PASS`

`CLICKHOUSE_GRANT_CONTRACT=PASS`

`CLICKHOUSE_LOOPBACK_LISTENERS=PASS`

## Grafana datasources

Both required ClickHouse datasources are captured with their stable UIDs and current behavior.

Datasource UIDs:

- `efvaztlrk8ow0a`
- `bfvik20ilwoaof`

The live verifier passed:

`GRAFANA_DATASOURCE_CONTRACT=PASS`

## Grafana HTTPS and certificates

Captured:

- HTTPS systemd override
- TCP/443 configuration
- TLS ownership/mode contract
- Certbot renewal service
- Certbot renewal timer
- Grafana certificate deploy hook

The live verifier passed:

`GRAFANA_HTTPS_OVERRIDE=PASS`

`GRAFANA_HTTPS_HEALTH=PASS`

`CERTBOT_RUNTIME_CONTRACT=PASS`

Firewall/nftables reconstruction is intentionally outside this capture milestone. Rebuild documentation should state required network prerequisites without reproducing deployment-specific firewall rules.

## Grafana dashboards

Four dashboards are captured as native Grafana 13 unified-resource documents using:

`dashboard.grafana.app/v2`

Captured files:

- `device-logs.json`
- `logs-dash.json`
- `noc-view.json`
- `noc-view-copy-backup.json`

Production API testing proved:

- every captured dashboard round-trips through the v2 resource API
- every captured `spec` exactly matches production
- POST is the supported create operation
- PUT is the supported full replacement operation
- `dryRun=All` performs non-persistent validation
- dry-run create does not persist
- dry-run replacement does not alter production resource versions

Permanent scripts are captured:

- `grafana/scripts/dashboard_api.py`
- `grafana/scripts/restore-dashboards.py`
- `grafana/scripts/verify-dashboards.py`

Validation completed:

`GRAFANA_UNIFIED_RESOURCE_ROUND_TRIP=PASS`

`GRAFANA_DRYRUN_RESTORE_PROOF=PASS`

`GRAFANA_DASHBOARD_VERIFY=PASS`

`GRAFANA_DASHBOARD_RESTORE_DRYRUN=PASS`

`GRAFANA_DASHBOARD_LIVE_NONDESTRUCTIVE_TEST=PASS`

`GRAFANA_DASHBOARD_WIRING_FINAL_VALIDATION=PASS`

The clean-machine runtime installer now requires the dashboard API scripts and all four captured dashboard resources, restores dashboards only after normal HTTPS Grafana health and datasource provisioning are verified, then runs the independent dashboard verifier. The runtime calls use Python `-B` so installer execution does not create bytecode cache artifacts inside the repository.

Automatic dashboard replacement is not enabled in the installer. A missing dashboard is created, an exact match is left unchanged, and an unexpected divergent existing resource causes the rebuild to fail rather than overwrite it.

Grafana 13.1.1 was verified to support:

`grafana cli admin reset-admin-password --password-from-stdin`

Secure administrator bootstrap wiring is now complete in the clean-machine runtime installer.

The installer requires a mode-private `GRAFANA_ADMIN_PASSWORD_FILE`, performs the initial Grafana start on `127.0.0.1:3000`, validates health and loopback-only listener state, stops Grafana, and resets administrator user ID 1 through stdin while explicitly targeting the packaged Grafana configuration and `/var/lib/grafana` data path.

Failure cleanup removes the bootstrap-only systemd drop-in. Successful bootstrap also removes that temporary override before the normal HTTPS startup path.

A temporary-database behavioral proof confirmed the CLI reset changed only the explicitly selected temporary database while the live administrator password hash remained unchanged.

Validation includes:

- `GRAFANA_ADMIN_BOOTSTRAP_PATCH_VALIDATION=PASS`
- `GRAFANA_BOOTSTRAP_FAILURE_FLOW_VALIDATION=PASS`
- `GRAFANA_CLI_WORKDIR_FIX_VALIDATION=PASS`
- `GRAFANA_CLI_TEMP_DATABASE_TARGETING=PASS`

## Collector transport boundary

Captured:

- restricted SFTP service accounts
- chroot configuration
- SSH Match policies
- authorized-key file placement contract
- service-account filesystem ownership/modes
- ACLs
- read-only GX10 spool bind mount
- write-only result-return boundary
- result incoming/ready/rejected directory behavior

Actual authorized keys are not stored in this repository.

The independent live verifier passed:

`TRANSPORT_VERIFY=PASS`

## AI result gate

Captured:

- result validation implementation
- versioned immutable accepted filename/content ledger and startup reconciliation
- systemd service
- systemd timer
- service filesystem-access drop-in
- incoming/ready/rejected workflow

The original live implementation and public capture were validated for exact implementation parity where naming is not environment-specific. The item-30 durable-ledger revision passes 11 local and 11 exact collector-staged tests plus guarded production installation, independent empty-ledger verification, and one natural no-op cadence. Exact predecessor bytes remain protected for rollback.

## GX10 spool retention

The public rebuild uses neutral retention naming.

The reference collector still uses an older deployment-specific unit name, so runtime verification intentionally verifies behavior rather than requiring identical unit names.

Verified behavior:

- daily execution
- persistent timer
- 30-minute randomized delay
- 90-day retention
- expired-file deletion
- empty-directory cleanup

Validation completed:

`RETENTION_SCRIPT_CONTRACT=PASS`

`RETENTION_RUNTIME_CONTRACT=PASS`

## Independent collector runtime verification

The complete independent verifier was run against the working collector.

It validated:

- package versions
- service state
- result-gate implementation
- retention behavior
- transport
- ClickHouse schema
- ClickHouse columns
- ClickHouse users and grants
- ClickHouse listener boundary
- Vector configuration
- Vector listeners
- Grafana TLS
- Grafana health
- Grafana datasources
- Certbot behavior

Final result:

`COLLECTOR_RUNTIME_VERIFY=PASS`

## Current clean-machine installer state

`install/install-runtime.sh` contains the current clean-machine reconstruction flow and includes a guard refusing use against an existing `observability` database.

Do not execute it against the working reference collector.

Secure Grafana administrator bootstrap is integrated:

1. `GRAFANA_ADMIN_PASSWORD_FILE` is required as a private operator-supplied input.
2. The first Grafana start uses a temporary loopback-only HTTP systemd override.
3. Grafana health and database initialization are verified.
4. The bootstrap listener is required to be exactly `127.0.0.1:3000`.
5. Grafana is stopped before administrator reset.
6. The CLI runs as the `grafana` account from `/usr/share/grafana`.
7. The CLI explicitly selects `/etc/grafana/grafana.ini` and `/var/lib/grafana`.
8. Administrator user ID 1 is reset through `--password-from-stdin`.
9. SQLite quick-check and database ownership are verified.
10. Failure cleanup removes the temporary bootstrap drop-in.
11. Successful completion removes the temporary drop-in before later HTTPS startup.

Grafana dashboard restore/verification is also integrated:

1. Required dashboard API scripts and all four capture files are checked before installation proceeds.
2. Restore runs after normal HTTPS Grafana health and datasource provisioning are verified.
3. The API connection is loopback HTTPS at `https://127.0.0.1:443`.
4. The operator-supplied private Grafana administrator password file is reused for API authentication.
5. Missing dashboards are created and exact matches are unchanged.
6. Automatic replacement of divergent dashboards is deliberately disabled.
7. `verify-dashboards.py` independently verifies all four captured resources after restore.
8. Python `-B` prevents runtime bytecode cache files from being written into the repository.

Package no-autostart protection is integrated across package and runtime installation:

1. A temporary `policy-rc.d` prevents policy-aware package maintainer scripts from starting/restarting services during package transactions.
2. Persistent systemd condition guards are installed before package transactions for Vector, ClickHouse, and Grafana.
3. An already-active SSH management plane is preserved rather than deliberately interrupted.
4. If SSH is initially inactive, service/socket guards hold it until transport configuration and `sshd -t` succeed.
5. ClickHouse bootstrap uses a short-lived authorization token without permanently removing its guard.
6. Grafana loopback administrator bootstrap uses the same temporary-authorization mechanism while retaining its persistent guard.
7. The authorization token is removed after each intentional start and through runtime-installer failure cleanup.
8. Vector, ClickHouse, and Grafana guards are permanently released only at the final configured-service activation boundary.
9. A synthetic systemd proof validated block, temporary authorization, reassertion, and final release semantics without changing real collector unit states.

Earlier patch attempts failed safely because of ambiguous anchors and heredoc collisions. Later validation also exposed two useful corrections before publication: Grafana CLI configuration overrides must use `--configOverrides`, and the CLI must run from a working directory traversable by the `grafana` account.

## Item 8 structural/public-safety validation

Collector installer structural, credential-exposure, dependency, operator-input preflight, failure-cleanup, destination-mode, and public-safety validation is complete.

Final validation established:

- credential/process-argument exposure is closed
- required `iproute2` and `sqlite3` dependencies are explicit
- package verification requires its actual root execution context
- authorized-keys inputs are validated before ClickHouse mutation
- private-key PEM detection uses an explicit grep option terminator
- runtime repository artifact references are complete
- renderer environment and output contracts are complete
- Grafana bootstrap override cleanup is failure-safe
- service authorization-token cleanup is failure-safe
- private temporary-file creation occurs under `umask 077`
- sensitive Vector and Grafana destination modes are explicit and validated
- TLS private-key mode remains `0400 grafana:grafana`
- shell evaluation scanning found no `eval` or xtrace
- public identity/material scanning closed with no deployment identity finding
- live Grafana datasource database state matches the captured functional contract
- absence of the clean-rebuild datasource provisioning file on the reference collector is an expected representation difference
- the public repository gate passes

No clean-machine installer was executed against the working reference collector.

## Item 9 operator documentation

The collector README is now the validated operator-facing clean-machine rebuild runbook.

It documents:

- clean Debian 13 amd64 baseline
- explicit clean-install confirmation
- required external connectivity without deployment-specific firewall reconstruction
- all ten runtime operator inputs
- private password-file preparation
- public authorized-key input preparation
- package installation and independent package verification
- runtime installation
- deferred SSH reload safety
- independent runtime verification
- installer success markers
- fail-closed retry/reprovision guidance

The documentation is based on the actual published installer/verifier contracts and does not introduce a parallel manual reconstruction procedure.

Validation completed with:

- `ITEM9B_README_OPERATOR_RUNBOOK_CONTRACT=PASS`
- `ITEM9_FINAL_DOCUMENTATION_CONSISTENCY=PASS`
- public repository gate passing

No package installer, runtime installer, or runtime verifier was executed as part of the documentation milestone.

## Item 10 public sanitation and milestone closure

Final public sanitation completed against the current tracked repository and the complete Git history reachable from public `main`.

Validated public-ref topology:

- one public branch: `main`
- zero public tags

Current tracked-state validation confirmed:

- no tracked local forbidden-term policy file
- no sensitive-key/database/temporary artifact paths
- no tracked backup or Python-bytecode artifacts
- collector shell syntax passes
- collector Python syntax passes
- captured Grafana JSON parses successfully
- public repository gate passes with five local forbidden terms

Public `main` history validation covered 205 unique historical blobs, including 151 collector/documentation history blobs.

Historical finding counts were all zero for:

- local forbidden terms in paths
- sensitive artifact paths
- local forbidden terms in blob content
- local forbidden terms in commit messages
- private-key material
- certificate material
- SSH authorized-key material
- recognized credential tokens
- URL-embedded credentials
- unapproved IPv4 addresses in collector/documentation history
- unapproved IPv6 addresses in collector/documentation history
- unapproved email addresses in collector/documentation history
- hardcoded user-specific home-directory identity paths

Two sanitation-tool defects failed safely and did not modify repository content:

1. the first public-tag counter used `grep -v` under `set -o pipefail`; a repository with zero tags therefore terminated the audit before the count was printed
2. the first local-policy assertion looked for `.public-gate-local.txt` at repository root, while the actual untracked policy file used by the gate is `components/normalizer/.public-gate-local.txt`

Both validator defects were diagnosed and corrected before the final sanitation pass.

Final validation marker:

- `ITEM10A_FINAL_SANITATION_AUDIT=PASS`

The public collector rebuild-package/documentation milestone is therefore closed.

Clean-machine end-to-end collector rebuild execution remains a separate validation gate.

## Detailed remaining collector work

Use `docs/CURRENT_STATE.md` for the authoritative ordering/status. The remaining collector work currently consists of:

- waived by operator: clean-machine end-to-end collector rebuild validation remains empirically unverified; execute it if a disposable Debian 13 amd64 system later becomes available

## GX10 remaining milestone

GX10 still needs the same complete capture/rebuild treatment.

Known areas that still require durable public artifacts and validation include:

- Ubuntu/runtime package reconstruction
- NVIDIA/GB10 environment dependencies
- Ollama configuration
- model configuration
- spool fetcher
- SFTP transport
- local SQLite state schema
- deterministic ingest/idempotency
- deterministic enrichment/classification
- systemd service/timer configuration
- local inference integration
- result-return path
- verification scripts
- operator rebuild documentation

The final project is complete only when both the collector and GX10 can be reconstructed from this public repository plus operator-supplied environment values.
