# Collector Component

The collector/log-server component is the durable observability control point and the current active rebuild-capture milestone.

For the exact verified checkpoint and resume order, read [`REBUILD_STATUS.md`](REBUILD_STATUS.md) and then `docs/CURRENT_STATE.md` at the repository root.

## Responsibilities

The collector owns:

- network syslog ingress
- durable raw observation storage
- deterministic normalization
- ClickHouse storage and access policy
- Grafana presentation
- compressed backlog creation for GX10
- restricted backlog transport boundary
- AI-result validation before durable ingestion
- validated AI-result storage
- long-lived data retention
- unknown-event inventory and replay material

## Rebuild objective

A clean collector server plus this repository and operator-supplied environment values must be sufficient to reproduce the currently functional collector without undocumented implementation memory.

Environment-specific credentials, addresses, usernames, SSH public keys, certificate material, and similar private values are supplied by the operator and are intentionally absent from the public repository.

## Published rebuild artifacts

### Package/install layer

`install/` contains:

- `versions.env` — captured package/component versions
- `install-packages.sh` — clean-machine package installation flow
- `verify-packages.sh` — independent package/version verifier
- `render-configs.py` — environment-specific configuration renderer
- `install-runtime.sh` — clean-machine runtime/configuration installer with guarded service release, secure Grafana bootstrap, and dashboard reconstruction
- `verify-runtime.sh` — independent live runtime verifier

The package verifier passed against the working reference collector with `COLLECTOR_PACKAGE_VERIFY=PASS`.

Package installation now establishes a no-autostart boundary before apt transactions using a temporary Debian `policy-rc.d` guard and persistent systemd condition guards. Runtime configuration releases those guards only at validated start boundaries. Synthetic systemd testing passed with `PACKAGE_NO_AUTOSTART_SYNTHETIC_PROOF=PASS`.

Do not execute `install-runtime.sh` against the working reference collector. It contains a clean-install guard and is intended for reconstruction on a clean machine.

### Vector

`vector/vector.yaml` captures the current Vector behavior with environment-specific values abstracted.

Preserved behavior includes:

- UDP and TCP syslog ingestion
- current transforms
- ClickHouse syslog and AI-update sinks
- AI-result ready-file ingestion
- durable compressed GX10 spool output
- current disabled ClickHouse sink health-check behavior

The independent runtime verifier passed Vector configuration/listener parity.

### ClickHouse

`clickhouse/` contains:

- database creation
- raw syslog table
- AI-update table
- Grafana semantic view
- rendered service-account/access SQL template

The captured contract includes the required service accounts, grants, Grafana read-only settings profile, 12-month retention behavior, and loopback-only ClickHouse application listeners.

### Grafana

`grafana/` contains:

- ClickHouse datasource provisioning template
- HTTPS systemd override template
- ClickHouse plugin manifest
- four captured Grafana 13 dashboards
- API-based dashboard restore/verification tooling

Dashboard resources are native `dashboard.grafana.app/v2` documents.

The following scripts are published and were tested non-destructively against Grafana 13.1.1:

- `grafana/scripts/dashboard_api.py`
- `grafana/scripts/restore-dashboards.py`
- `grafana/scripts/verify-dashboards.py`

Proven behavior includes exact captured-`spec` round trip, POST create, PUT replace, and `dryRun=All` validation without persistence.

Grafana 13.1.1 also supports secure administrator reset through `/usr/share/grafana/bin/grafana cli admin reset-admin-password --password-from-stdin`.

Secure administrator bootstrap is now wired into `install-runtime.sh` with a private operator password file, loopback-only first startup, explicit packaged CLI/data targeting, integrity checks, and cleanup of the temporary bootstrap override.

Dashboard restore and independent verification are now wired into `install-runtime.sh` after HTTPS health and datasource checks. The installer creates missing dashboards, accepts exact matches, refuses unexpected divergent resources rather than replacing them automatically, and uses Python no-bytecode mode for the runtime scripts.

### Certificates

`certbot/` contains:

- renewal service
- renewal timer
- Grafana certificate deploy-hook template

Private key/certificate material is never stored in the repository.

### Transport/filesystem boundary

`filesystem/` and `ssh/` contain the rebuild contract for:

- restricted SFTP service accounts
- chroot roots
- service-account SSH Match policies
- authorized-key placement contract
- spool/result ACLs
- read-only GX10 spool bind mount
- write-only result-return bind mount
- filesystem verification

Actual authorized keys are operator-supplied and are not committed.

The live transport verifier passed with `TRANSPORT_VERIFY=PASS`.

### AI result gate and retention

`sbin/` and `systemd/` contain:

- AI-result validation gate
- result-gate service/timer
- result-gate filesystem access override
- GX10 spool-retention implementation
- retention service/timer

The public rebuild uses neutral service naming where historical live names contain private identity. Runtime verification checks behavior rather than requiring identity-bearing historical names.

## Verified collector checkpoint

The independent collector runtime verifier reached:

`COLLECTOR_RUNTIME_VERIFY=PASS`

The published durable collector capture checkpoint is:

`e8df224` — `Checkpoint collector rebuild capture`

For the detailed list of completed validations, known incomplete work, and clean-machine resume sequence, read [`REBUILD_STATUS.md`](REBUILD_STATUS.md).

## Remaining collector execution order

`docs/CURRENT_STATE.md` is authoritative. At the current checkpoint the collector sequence is:

1. installer/public-safety validation
2. final collector operator/rebuild documentation
3. final collector sanitation/milestone closure
4. clean-machine collector rebuild validation when practical

Do not skip ahead without updating `docs/CURRENT_STATE.md` first.

## Implementation contracts

- Capture first; parser failure must not drop an observation.
- Preserve verified working behavior even when a setting looks unusual.
- Raw log storage remains independent of AI decisions.
- Grafana presentation uses semantic views rather than mutating raw storage solely for display concerns.
- GX10 never receives direct authority to write ClickHouse records.
- Private/environment-specific identity stays outside the public repository.
- Firewall/nftables reconstruction is intentionally out of scope; operator documentation should state required connectivity prerequisites instead.
- After each completed validated sub-section, append and push a project-journal entry before materially entering the next sub-section.
- During long or risk-heavy sub-sections, publish validated intermediate recovery checkpoints when they reduce reconstruction risk without prematurely advancing `CURRENT_STATE.md`.