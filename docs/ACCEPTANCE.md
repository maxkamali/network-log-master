# Rebuild Acceptance Status

## Status

Repository-only two-server rebuild acceptance: `PASS`.

Read-only reference-system revalidation: `PASS`.

Disposable clean two-server execution: `WAIVED BY OPERATOR`, empirically unverified.

The public collector and GX10 rebuild packages, component runbooks, cross-system runbook, current/target architecture split, and final sanitation gate are complete. Suitable disposable Debian 13 amd64 and Ubuntu 24.04 arm64 GX10-class targets are not available. On 2026-08-23, the operator explicitly accepted that residual risk and authorized advancement; the project still does not claim that clean-host execution passed.

## Durable public-repository gate

Run:

    scripts/validate-public-repository.py

The gate validates:

- tracked plus nonignored-untracked current-tree artifacts
- UTF-8/text-only repository content and nonsymlinked files
- generated/private artifact paths
- private-key and common access-token patterns
- workstation-private paths
- IPv4 literals limited to loopback/unspecified, documentation networks, and reviewed non-address version literals
- local Markdown link targets
- exactly one numbered `NEXT` in `docs/CURRENT_STATE.md`
- sensitive paths and secret/private-address patterns across every commit reachable from all refs
- one local branch (`main`) and zero tags

Required markers:

- `PUBLIC_REPOSITORY_CURRENT_TREE=PASS`
- `PUBLIC_REPOSITORY_HISTORY=PASS`
- `PUBLIC_REPOSITORY_LINKS=PASS`
- `PUBLIC_REPOSITORY_REF_TOPOLOGY=PASS`
- `PUBLIC_REPOSITORY_VALIDATION=PASS`

Five synthetic negative/positive tests prove rejection of private addresses, token patterns, private-key markers, and sensitive artifact paths while accepting documentation addresses and the captured ClickHouse version literal.

## Final repository-only validation

Completed results:

- normalizer: 73 tests passing under the required Python 3.13 runtime
- normalizer public gate: `PASS`
- GX10: 42 tests passing
- `GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS`
- `GX10_REBUILD_PACKAGE_VALIDATION=PASS`
- root sanitation gate: 5 tests passing
- collector configuration renderer: `COLLECTOR_CONFIG_RENDER=PASS`
- collector source/rendered YAML parsing: `PASS`
- four collector Grafana dashboard JSON resources parsed
- collector shell/Python static validation: `PASS`
- collector AI-result gate synthetic valid/invalid behavior: `PASS`
- Grafana dashboard capture/base-URL/payload static contract: `PASS`
- `git diff --check`: `PASS`
- `git fsck --full --strict`: `PASS`
- aggregate marker: `FINAL_REPOSITORY_ONLY_ACCEPTANCE=PASS`

## Post-acceptance normalizer integration validation

The later production-normalizer work advanced after the rebuild-acceptance checkpoint without changing its historical evidence:

- live isolated shadow catch-up and steady-state evidence: `PASS`
- normalizer/parser/replay/shadow/handoff suite: `94 passed`
- collector shadow/handoff package tests: `14 passed`
- forward-only GX10 handoff and rollback synthetic rehearsal: `PASS`
- live GX10 handoff cutover: explicitly authorized, not yet performed

The exact forward-identity contract and the remaining production gate are in `docs/NORMALIZER_HANDOFF.md` and `docs/CURRENT_STATE.md`.

## Public history and remote topology

The final gate scanned all 118 commits reachable during the acceptance run.

An additional private local-policy audit derived three environment identifiers from the operator VM's existing SSH configuration without printing them. None appeared in the current tree or reachable history.

GitHub verification during the acceptance run established:

- exactly one public branch: `main`
- zero public tags
- remote default branch: `main`
- public `main` matched the locally validated published checkpoint before the final acceptance changes

The item-15 acceptance checkpoint was published and independently matched at:

`27ca641c261552428dab88fc57b98851f7cedecf`

The final milestone publication repeats the remote-HEAD equality check after push; that result is recorded in the final journal verification entry.

## Read-only reference revalidation

Without writing either reference system or changing service state:

- collector authenticated SSH succeeded through the configured alias
- collector SSH, Vector, ClickHouse, and Grafana core services were active
- GX10 authenticated SSH succeeded through the configured alias
- `GX10_PLATFORM_VERIFY=PASS`
- `GX10_OLLAMA_VERIFY=PASS`

The GX10 check validated package/platform state, Ollama executable/unit/model metadata and referenced-blob sizes, active/enabled state, and loopback-only listener without calling the API or reading model blob contents.

Previously journaled component-specific live runtime gates remain authoritative, including `COLLECTOR_RUNTIME_VERIFY=PASS`, `TRANSPORT_VERIFY=PASS`, application/unit hash closure, and unchanged live GX10 application hashes.

## Waived external execution and residual risk

The following remain empirically unverified:

- clean collector execution on disposable Debian 13 amd64
- clean GX10 execution on disposable Ubuntu 24.04 arm64 GX10-class hardware
- full disposable two-server execution of `docs/TWO_SERVER_REBUILD.md`

These checks no longer block subsequent milestones because the operator explicitly waived the execution gate. When suitable systems become available, execute the component and cross-system runbooks exactly and append public-safe results here and in `docs/PROJECT_JOURNAL.md`.

## Acceptance interpretation

The repository contains the implementation, guarded installers, offline dependencies contract, verifiers, current/target architecture, and operator instructions necessary to attempt a deterministic rebuild without undocumented conversational memory.

Repository and reference-read-only evidence pass. Environmental execution evidence is waived for project sequencing, not assumed or represented as a pass. The rebuild/documentation milestone is therefore accepted with residual risk.
