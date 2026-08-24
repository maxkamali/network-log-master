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
- GX10 rebuild baseline at final repository acceptance: 49 tests passing
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
- live GX10 handoff cutover: `PASS` with immutable-floor identity continuity, exact collector/GX10 hash and record-count parity, zero duplicate event identities, and retained raw-view rollback
- transitional GX10 parser retirement: `PASS` with exact-hash replacement, zero scheduler references, canonical projection live-copy rehearsal, historical version-3 preservation, unchanged live database, and protected rollback
- deterministic GX10 incident engine: `PASS` with 63 current tests, guarded schema/artifact migration, private live-copy execution, cursor-reset idempotency, independent exact-state reproduction, unscheduled working-system installation, protected pre-migration backup, unchanged automatic chain, and successful ordinary post-migration fetch/ingest cadence
- managed GX10 correlation activation: `PASS` with 80 current GX10 tests, private-copy backfill/no-op/failure isolation, guarded inactive install, fail-closed production activation correction, full initial backfill, active zero-lag verification, three scheduled zero-lag cadences, zero correlation restarts, monotonic deterministic state, and continued original fetch/ingest timer advancement
- deterministic GX10 wake/packet boundary: `PASS` with 94 current GX10 tests, fixed event-time policy/priority, bounded canonical packets, recursive raw/source-key exclusion, append-only tamper detection, protected production-state-copy build/no-op/replay/independent reproduction/threshold/lifecycle/rollback evidence, and guarded empty unscheduled working-system installation under protected backup
- versioned GX10 local-reasoning boundary: `PASS` at item-28 closure with the then-current 115 GX10 tests, exact model/prompt/run/result provenance, strict structured output, calibrated synthetic OSPF/interface/BGP results, protected-copy success/invalid/unavailable/interrupted/no-op evidence, unchanged deterministic copy truth, and guarded empty unscheduled working-system installation with zero packet/model/prompt/run/result rows, zero scheduler references, and no production inference at that gate
- managed GX10 reasoning activation: `PASS` with 140 current GX10 tests, exact separately disableable schedule, protected-copy and guarded activation gates, bounded backlog control, one safely preserved terminal invalid output, immutable portable prompt revision `r3`, exact inactive compatibility upgrade, fresh-backup protected resume, and three natural fixed-packet drain cadences with one success/result each, zero new failures/`STARTED` rows/restarts, deterministic zero lag, and healthy independent schedules
- GX10 result-outbox repository/protected-copy candidate: `PASS` with 151 current GX10 tests locally and on an exact GX10-staged tree; one canonical collector-valid JSONL file per successful run; complete result and model/prompt/packet/request/run provenance; failure exclusion; shared-lock ready/delivered state with recreation suppression and duplicate-state refusal; divergence/lock/tamper/symlink refusal; atomic interruption/resume and strict partial recovery; 12-for-12 protected-copy creation followed by one simulated delivery and exact 11-ready/one-delivered reuse; unchanged copy and live production health; and zero installation, writer credential, or collector transmission
- GX10 inactive managed result-outbox package: `PASS` in repository/exact-stage/private-copy rehearsal with 157 total tests, exact-hash runner, isolated no-network service, disabled timer, bounded write scope, guarded empty install, independent verification, exact installed-runner production/replay, unchanged copy source, and forced post-install failure cleanup
- GX10 inactive managed result-outbox working-system install: `PASS` after safe public-default-path refusal/zero-target cleanup and exact private-runtime portability correction; 14 current results, zero ready/delivered files, disabled timer, never-invoked service, exact installed sources/configuration/ownership, effective private network/Unix-only/bounded-write scope, healthy zero-lag preexisting schedules, and zero credential/transport
- GX10 protected local result-outbox activator candidate: `PASS` after service-ownership/resume correction with 159 local/exact GX10-staged tests and two full retained-copy rehearsals proving exact five-table reasoning digest, 12-for-12 initial files, inactive/active cardinality verification, outbox timer enablement, reasoning timer restoration, unchanged copy, and zero credential/transmission; first working activation safely retained 15 files with timer disabled/reasoning restored before the verifier correction
- GX10 protected local result-outbox activation: `PASS` with exact reasoning digest preservation, 15 successful results/15 service-owned collector-gate-valid ready files, zero delivered, deterministic aggregate file digest, active no-network timer, zero restarts, zero projection/incident lag, restored healthy pipeline/reasoning schedules, and zero credential/transmission; natural timer cadence evidence remains pending
- GX10 natural local result-outbox no-op stability: `PASS` across three consecutive timer-only cadences at approximately 64–65-second intervals; each created zero, exactly reused all 15 ready files, wrote zero bytes, retained zero delivered/recovered/restarts, and used no credential/transport
- GX10 natural local result-outbox catch-up: `PASS`; reasoning naturally advanced 15→16 successful results and the immediately following outbox cadence created exactly one 2378-byte file, reused 15, preserved the prior 15-file digest, produced 16-for-16 collector-gate-valid files, retained zero delivered/restarts, and used no credential/transport
- GX10 configured-inactive sender candidate: `PASS` with 182 local and 182 exact GX10-staged tests, fixed-tool/key-role/pinned-host contracts, atomic config-last private-state installation, idempotent exact reuse, partial/divergent-state refusal, created-only failure cleanup, disabled/inactive enforcement, exact staged hash parity, and no SFTP invocation or live private input
- collector dedicated result-writer authorizer candidate: `PASS` with five local and five exact collector-staged tests covering single-line append, exact root-only predecessor backup, exact reuse, duplicate refusal, private-key-input refusal, and byte-for-byte rollback after injected SSH validation failure

The exact forward-identity contract, live evidence, retained rollback, and next stability/retirement gate are in `docs/NORMALIZER_HANDOFF.md` and `docs/CURRENT_STATE.md`.

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
