# GX10 Clean-Machine Runbook

## Purpose and boundary

This runbook reconstructs the currently proven GX10 state on a clean Ubuntu 24.04 arm64 host.

It reproduces:

- the dedicated runtime identity and protected filesystem
- read-only SFTP backlog fetch
- replay-safe local SQLite ingest
- canonical normalized-field projection and deterministic incident processing behind a separate managed offline schedule
- the inert deterministic wake-policy/compact-packet schema and builder without scheduling or inference
- the exact reconstructed SQLite base, deterministic incident extension, and two functional suppression patterns
- the original automatic `timer -> fetch -> ingest` chain
- the captured Ollama executable, service, loopback listener, and six-model store

It does not invent:

- an application-specific Ollama caller
- a GX10 producer for the collector result-return boundary
- historical kernel, NVIDIA, CUDA, Ollama, or SQLite bootstrap provenance that was not recovered

Never run these clean-machine installers against the working reference system.

## Required inputs

Prepare these outside the repository:

1. a clean Ubuntu 24.04 arm64 GX10-class host
2. the captured NVIDIA-capable kernel, driver, and CUDA compiler baseline recorded in `install/versions.env`
3. root access and working Ubuntu package repositories containing the exact pinned package versions
4. network reachability from GX10 to the collector's read-only SFTP boundary
5. the collector host, port, and read-only transport username
6. a dedicated SFTP private key and known-hosts file, each mode `0400` or `0600`
7. the exact captured Ollama binary:
   - size `35792104` bytes
   - SHA-256 `26f44ca89143f2326a3aad98b2cb5e8b5af9397aef7001cd8d022e90d6e0b55e`
8. an offline Ollama `models` directory containing the captured six manifests and all referenced blobs
9. a clean checkout of this public repository

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

At this point all application units must still be inactive, Ollama and the timer must be disabled, the spool must be empty, and the application database must contain no runtime rows.

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

## Failure and rerun rules

- Stop on the first failed marker. Never weaken a verifier to make installation continue.
- Filesystem, configuration, application, Ollama-binary, and model-store installation can reuse exact existing artifacts and refuse divergent ones.
- The database initializer intentionally cannot be rerun after successful creation.
- A partially copied model store may be resumed only when every existing artifact is exact. Divergent files require operator investigation; the importer never replaces them.
- Preactivation refuses a used database, spool content, SQLite sidecars, active units, enabled runtime units, unit drop-ins, or altered installed artifacts.
- Do not use this runbook to repair or modify the working reference GX10.
- Do not add an Ollama pipeline caller or a result-return producer as part of reconstruction. Those remain separate future implementation decisions.
- The installed reasoning-packet builder remains inert until its own production-state-copy and managed-invocation gates pass.
- The application installer places the item-26 correlation runner and unit files, but the base clean-runtime activator deliberately leaves the correlation timer disabled. Use Phase 9 and `docs/MANAGED_CORRELATION.md` only after the base runtime passes and operator authorization is explicit.

## Current validation status

Repository-only synthetic validation is complete. End-to-end execution of this runbook on a disposable Ubuntu 24.04 arm64 GX10-class host remains outstanding because no such validation target is currently available.

Do not report clean-machine validation complete until the full runbook has passed on that disposable target and the result has been journaled.
