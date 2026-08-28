# Collector Normalizer Shadow Package

## Status

Repository implementation and synthetic validation: complete.

Live collector deployment: shadow worker active as of 2026-08-23; forward-only handoff publisher and GX10 bind cutover active as of 2026-08-24.

Bounded live verification: complete for historical catch-up plus five normal-cadence steady-state cycles. The active verifier tolerates legitimate append-only worker progress by resnapshotting newly completed rows, while still failing on missing, orphaned, mutated, incomplete, or disappearing evidence.

This package stages the deterministic Python normalizer as a separate collector-local shadow worker plus an independently packaged forward handoff publisher. The guarded production activation changed only the GX10 read-only SFTP bind view; Vector, ClickHouse, `/var/spool/vector-ai`, shadow history, and existing GX10 identities remain unchanged.

The architecture and promotion/rollback gates are in
[`docs/NORMALIZER_PRODUCTION_INTEGRATION.md`](../../../docs/NORMALIZER_PRODUCTION_INTEGRATION.md).

The forward-only handoff design, synthetic rehearsal, and live activation are
complete in [`docs/NORMALIZER_HANDOFF.md`](../../../docs/NORMALIZER_HANDOFF.md).
Its launcher and hardened units remain excluded from the shadow manifest and
are instead installed through the separate exact-hash handoff manifest.

## Artifacts

- `install-shadow.py` — guarded, non-activating staging installer
- `verify-shadow.py` — independent staged/active runtime verifier
- `network-log-normalizer-shadow` — fixed-path runtime launcher
- `systemd/network-log-normalizer-shadow.service` — hardened oneshot worker
- `systemd/network-log-normalizer-shadow.timer` — one-minute catch-up schedule
- `package-manifest.json` — exact installed artifact inventory and SHA-256 values
- `versions.env` — Python and Zstandard versions observed on the collector reference host
- `platform-inventory.example.json` — public schema example using documentation-only identities
- `install-handoff.py` — separately guarded, non-activating handoff staging installer
- `verify-handoff.py` — independent installed-artifact, ACL, state, content, and bind verifier
- `handoff-package-manifest.json` — exact hashes for handoff-only installed artifacts
- `handoff-plan.example.json` — public schema/path example for the private immutable floor
- `network-log-normalizer-handoff` — forward publisher launcher
- `systemd/network-log-normalizer-handoff.service` — no-network hardened publisher
- `systemd/network-log-normalizer-handoff.timer` — one-minute publisher schedule

The worker implementation is `components/normalizer/src/network_log_normalizer/shadow.py`.

## Safety model

The dedicated locked `network-log-normalizer` account has the `vector` supplementary group only so it can read the existing `0750 vector:vector` source root. The systemd service still mounts `/var/spool/vector-ai` read-only in its private filesystem view.

The service has:

- no network namespace or usable IP address family
- no capabilities or privilege escalation
- no ClickHouse, SSH, Ollama, or AI-result credentials
- read access only to the source backlog and private inventory
- write access only to its shadow-output and ledger paths
- no `Wants=` coupling that could start Vector

The staging installer refuses an active or enabled shadow timer and does not enable or start it.

## Private platform inventory

Create the real inventory outside the repository. It must:

- use schema version 1 from `platform-inventory.example.json`
- contain canonical source IP identities and supported canonical vendor/OS pairs
- be a regular, nonempty, single-link file
- have input mode `0400` or `0600`

The installer copies it to `/etc/network-log-normalizer/platform-inventory.json` as `0640 root:network-log-normalizer`. Neither verifier prints inventory identities or contents.

## Repository validation

From repository root, using Python 3.13:

```text
PYTHONDONTWRITEBYTECODE=1 python3.13 -m pytest -q -c components/normalizer/pyproject.toml components/normalizer/tests
PYTHONDONTWRITEBYTECODE=1 python3.13 components/collector/tests/validate-normalizer-shadow-package.py
scripts/validate-public-repository.py
```

## Staging procedure

Do not run this procedure on the live collector without explicit deployment authorization.

On a reviewed collector target with the existing Vector backlog present and the shadow timer absent/inactive:

```text
sudo env \
  NORMALIZER_SHADOW_INSTALL_CONFIRM=YES-INSTALL-NORMALIZER-SHADOW \
  PLATFORM_INVENTORY_FILE=/operator/private/platform-inventory.json \
  components/collector/normalizer/install-shadow.py
```

The installer:

1. verifies exact Python/Zstandard package versions
2. verifies the package manifest against repository artifacts
3. creates or verifies the locked runtime identity
4. creates empty state/output roots
5. installs the protected inventory, code, launcher, verifier, and units without overwriting divergence
6. validates units with `systemd-analyze verify`
7. reloads unit definitions without enabling or starting the timer
8. runs the independent verifier in `staged` mode

Expected markers:

```text
NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS
NORMALIZER_SHADOW_INSTALL=STAGED
normalizer_shadow_timer=disabled,inactive
```

## Clean-rebuild shadow activation

After the staged installer passes and the collector base is healthy, enable
only the shadow timer and require active verification before staging the
handoff:

```text
sudo systemctl enable --now network-log-normalizer-shadow.timer
sudo components/collector/normalizer/verify-shadow.py --mode active
```

Expected marker:

```text
NORMALIZER_SHADOW_RUNTIME_VERIFY=PASS
```

Require historical catch-up and zero pending/incomplete/missing/orphaned or
mutated evidence before selecting a future handoff floor. The full cross-host
order, including GX10 pause and bind-only cutover, is authoritative in
`docs/TWO_SERVER_REBUILD.md`.

## Historical item-19 activation boundary

Item 19 did not provide an automatic activation command. Its separately
authorized shadow-deployment step had to:

1. revalidate live source metadata and current Vector health
2. verify the platform inventory privately
3. run the staged verifier
4. record a bounded evidence threshold based on observed production rate/coverage
5. enable/start only `network-log-normalizer-shadow.timer`
6. run the independent verifier with `--mode active`
7. confirm Vector, ClickHouse, and the current GX10 backlog remain unchanged

The later GX10 normalized-output promotion and handoff gates are complete.
Current state and retained rollback boundaries are recorded in
[`docs/CURRENT_STATE.md`](../../../docs/CURRENT_STATE.md) and
[`docs/NORMALIZER_HANDOFF.md`](../../../docs/NORMALIZER_HANDOFF.md).

## Handoff staging procedure

Production staging requires the separately recorded cutover authorization and a private plan whose floor is at least ten minutes in the future. The input plan must be a regular single-link `0400` or `0600` file matching `handoff-plan.example.json`.

```text
sudo env \
  NORMALIZER_HANDOFF_INSTALL_CONFIRM=YES-STAGE-NORMALIZER-HANDOFF \
  HANDOFF_PLAN_FILE=/operator/private/handoff-plan.json \
  components/collector/normalizer/install-handoff.py
```

The installer revalidates the complete active shadow runtime, exact repository hashes, future floor, existing identities/paths, empty ACL-protected handoff root, protected installed plan, hardened units, empty initialized handoff ledger, and independent staged mode. It does not enable or start the handoff timer and does not change the GX10 bind mount.

To stop shadow execution without deleting evidence:

```text
sudo systemctl disable --now network-log-normalizer-shadow.timer
```

Stopping the timer does not alter Vector, ClickHouse, the raw backlog, the GX10 bind mount, normalized output, or the ledger.

## Failure and retry

The worker records a `processing` ledger row before publishing output. An interrupted retry regenerates the output and may adopt only an exact already-published match. Completed source paths are immutable: source, output, ledger, inventory-context, or version inconsistencies fail closed.

Original source files are never renamed, locked, truncated, deleted, or modified.
