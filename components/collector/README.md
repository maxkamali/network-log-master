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

## Clean-machine operator runbook

This is the supported reconstruction path for the collector. Use the published installers rather than manually recreating package, service, database, transport, or Grafana state.

### Supported baseline

The package bootstrap is deliberately narrow and fail-closed:

- clean Debian 13
- amd64 architecture
- root or sudo access
- this public repository
- operator-supplied environment values and credential files
- no existing `observability` ClickHouse database

Both clean-machine installers require the explicit confirmation value:

`CLEAN_INSTALL_CONFIRM=YES-CLEAN-COLLECTOR`

The confirmation is a guard against accidental execution. It is not permission to run the installer on an existing collector.

Do not execute `install/install-runtime.sh` against the working reference collector or another server containing state that must be preserved.

### External connectivity prerequisites

Firewall and nftables reconstruction is intentionally out of scope. The operator is responsible for establishing the required connectivity according to the local security policy.

The clean collector needs outbound DNS/HTTPS access sufficient to reach:

- Debian package repositories
- Vector package-repository endpoints
- ClickHouse package-repository endpoints
- Grafana package-repository endpoints
- Python package indexes used to install the captured Certbot version
- the ACME service used for certificate issuance and renewal

Required inbound application connectivity is:

- UDP/514 from network devices that send syslog
- TCP/514 from network devices that send syslog
- TCP/443 from authorized Grafana clients
- TCP/80 while ACME standalone validation is required for certificate issuance or renewal
- the operator-selected nonstandard `SSH_PORT` from authorized management and GX10 transport sources

ClickHouse application endpoints remain loopback-only. Do not expose the ClickHouse HTTP/native listeners as external prerequisites.

### Operator-supplied runtime inputs

`install/install-runtime.sh` requires exactly these ten operator-supplied values:

| Variable | Purpose and constraint |
| --- | --- |
| `CLICKHOUSE_DEFAULT_PASSWORD_FILE` | Private file containing the fresh ClickHouse `default` administrative password selected during package installation. |
| `GRAFANA_READER_PASSWORD_FILE` | Private file containing the password to create the read-only `grafana_reader` ClickHouse account and Grafana datasource credentials. |
| `GRAFANA_ADMIN_PASSWORD_FILE` | Private file containing the Grafana administrator password. It must contain one non-empty line. |
| `VECTOR_INGEST_PASSWORD_FILE` | Private file containing the password for the `vector_ingest` ClickHouse account. |
| `GRAFANA_PUBLIC_HOST` | Public IPv4 address used for Grafana HTTPS. |
| `CERT_NAME` | Current certificate contract requires this to equal `GRAFANA_PUBLIC_HOST`. |
| `CERTBOT_EMAIL` | Operator-supplied ACME contact email address. |
| `SSH_PORT` | Numeric TCP port from 1 through 65535. Port 22 is intentionally rejected by the captured deployment contract. |
| `AI_SPOOL_READER_AUTHORIZED_KEYS_FILE` | Non-empty file containing only the OpenSSH public authorized key material allowed to read the GX10 spool boundary. |
| `AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE` | Non-empty file containing only the OpenSSH public authorized key material allowed to return GX10 results. |

The four password inputs are file-backed so the secret values do not have to appear in installer command arguments.

Password files must be regular, non-empty files with no group or world permission bits. Mode `0600` owned by root is the recommended operator preparation.

The authorized-key source files are also validated before persistent runtime mutation. They must be regular and non-empty. Private-key PEM material is rejected. Supplying a private SSH key where an authorized-keys public-key file is expected is an installation error.

Optional runtime control:

- `RELOAD_SSH=yes` requests an SSH reload at the end of runtime installation.
- if `RELOAD_SSH` is unset or anything other than `yes`, SSH reload is deferred
- deferring the first reload is recommended until access to the selected nonstandard port has been independently checked

Optional configuration values have these captured defaults:

| Variable | Default |
| --- | --- |
| `SYSLOG_UDP_ADDRESS` | `0.0.0.0:514` |
| `SYSLOG_TCP_ADDRESS` | `0.0.0.0:514` |
| `CLICKHOUSE_ENDPOINT` | `http://127.0.0.1:8123` |
| `CLICKHOUSE_HOST` | `127.0.0.1` |
| `CLICKHOUSE_USER` | `vector_ingest` |

### Clone the repository

On the clean Debian 13 amd64 collector:

    git clone https://github.com/maxkamali/network-log-master.git
    cd network-log-master

Use the project milestone commit or release selected for the rebuild. Do not mix installer files from different repository revisions.

### Prepare operator input files

Create a root-owned input directory outside the repository:

    INPUT_DIR=/root/collector-rebuild-inputs
    sudo install -d -o root -g root -m 0700 "$INPUT_DIR"

Create private empty files with safe initial metadata:

    for name in clickhouse-default-password grafana-reader-password grafana-admin-password vector-ingest-password ai-spool-reader.authorized_keys ai-results-writer.authorized_keys; do sudo install -o root -g root -m 0600 /dev/null "$INPUT_DIR/$name"; done

Populate those files using a secure local editor or secret-management workflow.

Do not place password values, SSH private keys, or other secrets in shell command arguments, repository files, Git history, screenshots, or support transcripts.

For the password files, use one non-empty password line. In particular, `clickhouse-default-password` must contain the same fresh ClickHouse `default` password entered locally if the ClickHouse package installation prompts for one.

The two `*.authorized_keys` source files contain OpenSSH public authorized-key lines only. Do not copy private SSH key material into these files.

### Install the captured packages

Run the package installer as root with the explicit clean-machine confirmation:

    sudo env CLEAN_INSTALL_CONFIRM=YES-CLEAN-COLLECTOR components/collector/install/install-packages.sh

The package installer:

- verifies Debian 13 amd64
- installs the captured package versions and required runtime dependencies
- configures the Vector, ClickHouse, and Grafana package repositories
- installs the captured Grafana ClickHouse plugin
- installs the captured Certbot version in `/opt/certbot`
- protects Vector, ClickHouse, and Grafana from premature package-triggered startup
- preserves an already-active SSH management plane, or holds an initially inactive SSH service until transport configuration is ready

Expected package-install completion markers include:

- `PACKAGE_NO_AUTOSTART_HOLD=PASS`
- `COLLECTOR_PACKAGE_INSTALL=PASS`

At this point the collector application services intentionally remain held for runtime configuration.

### Verify the package layer

Run the independent package verifier as root:

    sudo components/collector/install/verify-packages.sh

The required successful terminal marker is:

`COLLECTOR_PACKAGE_VERIFY=PASS`

Resolve package/version/plugin failures before proceeding to runtime installation.

### Set the non-secret deployment values

Set the deployment-specific non-secret values in the current operator shell. Replace every `REPLACE_WITH_...` value before running the runtime installer:

    export GRAFANA_PUBLIC_HOST='REPLACE_WITH_PUBLIC_IPV4'
    export CERT_NAME="$GRAFANA_PUBLIC_HOST"
    export CERTBOT_EMAIL='REPLACE_WITH_ACME_CONTACT_EMAIL'
    export SSH_PORT='REPLACE_WITH_NONSTANDARD_SSH_PORT'

The current certificate contract requires `GRAFANA_PUBLIC_HOST` and `CERT_NAME` to be the same IPv4 address.

### Install the collector runtime

The first runtime installation should normally leave `RELOAD_SSH` unset so management access can be confirmed before SSH is reloaded.

Run:

    sudo env CLEAN_INSTALL_CONFIRM=YES-CLEAN-COLLECTOR CLICKHOUSE_DEFAULT_PASSWORD_FILE="$INPUT_DIR/clickhouse-default-password" GRAFANA_READER_PASSWORD_FILE="$INPUT_DIR/grafana-reader-password" GRAFANA_ADMIN_PASSWORD_FILE="$INPUT_DIR/grafana-admin-password" VECTOR_INGEST_PASSWORD_FILE="$INPUT_DIR/vector-ingest-password" GRAFANA_PUBLIC_HOST="$GRAFANA_PUBLIC_HOST" CERT_NAME="$CERT_NAME" CERTBOT_EMAIL="$CERTBOT_EMAIL" SSH_PORT="$SSH_PORT" AI_SPOOL_READER_AUTHORIZED_KEYS_FILE="$INPUT_DIR/ai-spool-reader.authorized_keys" AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE="$INPUT_DIR/ai-results-writer.authorized_keys" components/collector/install/install-runtime.sh

The runtime installer reconstructs the captured functional collector state, including:

- ClickHouse database objects, access users, grants, and settings
- restricted SSH/SFTP transport files, accounts, chroots, ACLs, and bind mounts
- Vector configuration and its private ClickHouse credential file
- GX10 compressed spool output
- AI-result validation service/timer
- GX10 spool-retention service/timer
- Grafana datasource provisioning
- loopback-only first-run Grafana administrator bootstrap
- Grafana HTTPS configuration
- certificate issuance/reuse and renewal integration
- the four captured Grafana dashboards
- final guarded service activation

The runtime installer intentionally refuses a machine where the `observability` ClickHouse database already exists.

The required final runtime-install marker is:

`COLLECTOR_RUNTIME_INSTALL=PASS`

### Activate the selected SSH port safely

If runtime installation reported `ssh_reload=deferred`, do not close the current management session yet.

Validate the generated SSH configuration:

    sudo sshd -t

Confirm that network policy permits the selected nonstandard TCP `SSH_PORT`.

Then reload SSH:

    sudo systemctl reload ssh.service

Open and validate a second management connection on the selected port before closing the original session. Also validate the GX10 SFTP access appropriate to the spool-reader and results-writer roles.

`RELOAD_SSH=yes` may instead be supplied to `install-runtime.sh` only when the operator has already confirmed that reloading SSH during the installer is safe.

### Verify the reconstructed runtime

Run the independent runtime verifier as root. It requires only the private ClickHouse default-password file from the operator input set:

    sudo env CLICKHOUSE_DEFAULT_PASSWORD_FILE="$INPUT_DIR/clickhouse-default-password" components/collector/install/verify-runtime.sh

The required final marker is:

`COLLECTOR_RUNTIME_VERIFY=PASS`

The verifier checks package state, services, retention, transport, ClickHouse schema/access/listeners, Vector configuration/listeners, Grafana TLS/health/datasources, and Certbot behavior.

If SSH was deliberately reloaded after the first verifier run, run the verifier again after confirming the new management/transport access.

### Failure and retry policy

The installers are fail-closed rebuild tools, not general idempotent configuration-management convergence tools.

If `install-packages.sh` fails, inspect the reported error before changing any package no-autostart guard. Do not manually remove a guard merely to force installation forward.

If `install-runtime.sh` fails after persistent state has been created, do not blindly rerun it. The clean-machine contract intentionally refuses an existing `observability` database. For deterministic rebuild validation, restore the clean-server snapshot or reprovision the clean collector, correct the identified input/environment problem, and run the documented sequence again.

Do not bypass the clean-install confirmation, database-existence refusal, package no-autostart guards, private-file validation, or transport-key validation to make a failed rebuild continue.

Keep all operator credential files outside the repository and preserve their private metadata until the rebuild has been verified and the operator has applied the local credential-retention policy.

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

## Collector execution status

`docs/CURRENT_STATE.md` is the authority for project execution order.

Collector installer structural, credential-exposure, dependency, failure-cleanup, and public-safety validation is complete.

The operator-facing clean-machine rebuild runbook is complete and validated.

Execution-order item 9 is complete. The next collector phase is final public-repository sanitation and collector milestone closure, followed by clean-machine end-to-end rebuild validation when practical.

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