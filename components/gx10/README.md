# GX10 Component

GX10 is the replaceable reasoning host. It consumes prepared observations and maintains only the compact working state needed for incident correlation and local inference.

Responsibilities:

- securely fetch prepared/backlog data through a read-only path
- ingest replay-safe local records
- maintain deterministic incident identity and lifecycle
- track repeats, bursts, and supporting evidence
- build compact rolling context summaries
- decide when a local LLM should run
- invoke local models through Ollama
- emit thin AI result records through a write-only return path
- emit changed deterministic incident snapshots through the same bounded write-only path

GX10 is not:

- the authoritative raw-log archive
- the primary dashboard server
- a direct ClickHouse writer
- the owner of canonical deduplication or incident truth inside the LLM

Current state:

- secure backlog fetch and durable ingest are operational
- replay/idempotency protections exist in the ingest path
- normalized schema-version-1 projection is implemented as the deliberate replacement for transitional vendor/message reparsing
- the version-1 incident identity/schema contract is implemented, validated,
  and active; the later version-3 engine policy extends protocol monitoring to
  one-observation BGP/OSPF/OSPFv3 candidates
- a separate offline managed `projection -> incident` runner/service/timer passed initial production backfill and three zero-lag scheduled cadences with exact hashes, bounded cursor convergence, resource limits, telemetry, and state-preserving disable behavior
- the original automatic chain remains `timer -> fetch -> ingest`; the correlation chain is independently scheduled and disableable
- Ollama is active with six complete model manifests. No historical application-specific caller was discovered; the repository-managed bounded Gemma caller and hidden uncovered-event triage are now active additions.
- secure collector-side AI-result return transport is proven; no historical GX10 result producer was discovered
- production packet construction and bounded local-LLM inference are active behind the separately disableable item-29 gate; item 30's local result outbox and separately disableable recurring write-only sender are active after first-live, replay/conflict, exact-stage, and natural acceptance/ingestion gates
- the deterministic wake-policy/compact-packet schema and exact builder are active only through the managed reasoning boundary
- the versioned local-reasoning caller/schema/prompt boundary passes synthetic and protected-copy idempotency, strict-output, interruption, tamper, and unavailable-runtime gates; the original exact artifacts were installed empty under protected backup before item-29 activation
- item 29 is complete after backlog deferral, one safely diagnosed terminal invalid output, exact portable prompt revision `r3`, protected-copy replay, four-artifact upgrade, protected resume, and three natural fixed-packet drain cadences
- item 30 is complete after protected local-producer activation, durable collector acceptance-ledger deployment, configured-inactive writer installation, first-live ClickHouse provenance, exact replay and divergent conflict isolation, 186 local/exact-stage tests, active-state verification, timer-only activation, and natural collector acceptance/ingestion
- item 33 added a backward-compatible Device projection to new result files while preserving exact legacy ready/delivered bytes; its 192-test checkpoint passed and all production schedules retained zero restarts
- item 34 added an inference-independent incident lifecycle producer, strict shared transport validation, and the collector NOC projection; its then-current suite passed 200 tests and both outbox/sender timers remained enabled and healthy
- item 36 activated forward-only 24-hour monitoring for confirmed BGP/OSPF/OSPFv3 recovery, strict version-2 lifecycle recurrence projection with version-1 compatibility, and managed exact-hash upgrades
- a one-observation BGP/OSPF/OSPFv3 candidate reaches `RECOVERING` rather
  than resolving at its 15-minute deadline under the active version-3 policy
- the hidden AI detection side channel is active for uncovered important events; validated positives become ordinary deterministic incidents, failures remain pending, and guarded learned coverage is limited to severity 0–3
- current validation status is maintained in `docs/CURRENT_STATE.md`; exact
  milestone test totals remain in the append-only project journal

The normalized production handoff, multi-cadence stability window, and live-copy projection rehearsal now provide the retirement gate. Historical version-3 enrichment rows remain evidence and are not deleted.

Live-system rediscovery is complete. The authoritative reconstruction
checkpoint, captured contracts, preserved historical absences, and current
component state are in `REBUILD_STATUS.md`.

The complete installation and activation sequence is in
[`CLEAN_MACHINE_RUNBOOK.md`](CLEAN_MACHINE_RUNBOOK.md). Use that runbook only
on a clean intended rebuild target, never on the working reference system.

## Clean-machine reconstruction artifacts

The first reconstruction subsection defines the public-safe runtime identity and filesystem boundary:

- `config/operator-inputs.env.example` — synthetic operator-input template; populate only in a private file outside the repository
- `install/filesystem-contract.env` — neutral fixed runtime identity and path roles
- `install/install-filesystem.sh` — guarded clean-machine account, directory, and SSH-material bootstrap
- `tests/validate-filesystem-contract.sh` — non-mutating structural and public-safety validation

The filesystem installer requires operator-owned SFTP private-key and known-hosts files with mode `0400` or `0600`. It installs them with mode `0600`, creates the SSH parent with mode `0700`, creates spool/state directories with mode `0750`, locks the dedicated non-login system account, and refuses an existing application database.

Do not populate the example file in the repository. Do not run the clean-machine installer against the working GX10 reference system.

Run the safe repository validation with:

    components/gx10/tests/validate-filesystem-contract.sh

## Captured application implementations

The three rediscovered live custom applications and deliberate post-rediscovery implementation artifacts are under `sbin/` with deployment values removed:

- `fetch-spool.py`
- `ingest-spool.py`
- `enrich-events.py` — compatibility filename now containing the canonical normalized-field projector
- `incident-engine.py` — deterministic incident identity, evidence, lifecycle, repeat, and rolling-context engine
- `build-reasoning-packets.py` — deterministic wake selection and bounded append-only packet construction; no inference
- `run-local-reasoning.py` — exact model/prompt/run binding and strict loopback structured inference; not directly scheduled, but invoked by the active managed-reasoning owner
- `build-result-outbox.py` — installed read-only versioned successful-result projection to one canonical local JSONL file per run, including deterministic Device identity for new files and exact legacy-byte reuse
- `build-incident-outbox.py` — installed read-only changed-incident projection to content-addressed lifecycle batches of at most 100 records and 256 KiB
- `run-result-outbox.py` — installed exact-hash managed producer runner with no transport capability
- `run-incident-outbox.py` — installed exact-hash managed lifecycle runner with a protected local export cursor and no transport capability
- `send-result-outbox.py` — deterministic single-file write-only transport core; synthetic tests inject transport, while separately gated production uses a dedicated writer identity
- `run-result-sender.py` — installed exact-hash managed sender runner behind its independently disableable active timer
- `install/install-result-sender.py` and `verify-result-sender.py` — guarded inactive installation plus explicit configured inactive/active verification
- `run-managed-reasoning.py` — exact-hash packet/inference wrapper with one-inference-per-cycle locking, pending-backlog builder deferral, and aggregate health; exact portable revision `r3` is active after protected upgrade/resume and three natural cadences
- `triage-uncovered-events.py` — deterministic signature selection, bounded batching, strict Gemma decision validation, pending retries, incident bridging, and guarded learned coverage
- `run-managed-ai.py` — one-call coordinator that gives existing incident reasoning priority and otherwise runs uncovered-event triage

`sbin/runtime_config.py` loads the protected runtime configuration rendered by
`install/render-runtime-config.py`. See
[`sbin/PROVENANCE.md`](sbin/PROVENANCE.md) for live hashes and the
function-level parity proof.

Validate the synthetic application/configuration contract with:

    python3 -m unittest discover -s components/gx10/tests -p 'test_*.py' -v

Validate operator configuration inputs without writing files with:

    GX10_SFTP_HOST=collector.example.invalid GX10_SFTP_PORT=2222 GX10_SFTP_USER=spool-reader components/gx10/install/render-runtime-config.py --check

The original deterministic-enrichment source/hash remains recorded for provenance and rollback. The active repository file is now a canonical projector that performs no vendor/message classification, retains local suppression policy, and runs only through the separate managed correlation chain rather than the original `timer -> fetch -> ingest` service.

## SQLite initialization

`sql/initialize.sql` preserves the complete effective SQLite base contract recovered in item 12M:

- 5 application tables
- 13 explicit indexes
- 3 foreign keys
- the two enabled exact-match suppression patterns from item 12H

`sql/incident-v1.sql` adds the deliberate incident extension: three incident tables, five explicit indexes, and four append-only triggers. `sql/reasoning-v1.sql` adds the item-27 packet table, two indexes, and two append-only triggers. `sql/inference-v1.sql` adds the versioned item-28 model/prompt/run/result boundary with guarded terminal run transitions and append-only results. `sql/triage-v1.sql` adds append-only uncovered-event signature, batch, attempt, decision, override, summary, and learned-rule provenance. `install/initialize-database.py` creates the base plus all four extensions atomically, refuses any existing database, validates integrity/schema/corpus before publication, and installs mode `0640` for the dedicated runtime identity.

The historical suppression-rule names and reasons were not exposed during rediscovery and no initializer survived. The public rebuild therefore uses neutral names/reasons while preserving functional IDs, evaluation order, types, patterns, and enabled state.

Do not run the initializer against the working GX10 reference system.

## Service and timer reconstruction

`systemd/network-log-gx10.service` and `systemd/network-log-gx10.timer` preserve the complete captured live scheduling and hardening contract with neutral public identity/path values.

The original recovered chain remains exactly:

`timer -> fetch -> ingest`

The separately managed offline chain is:

`correlation timer -> canonical projection -> deterministic incident engine`

`install/install-applications.py` installs the application/configuration files and pipeline/correlation/reasoning units atomically without overwriting divergent files. It validates database/config ownership and modes, runs `systemd-analyze verify`, and reloads systemd without enabling or starting correlation or local reasoning. `install/retire-transitional-enrichment.py` separately performs an exact-old-hash, no-scheduler-reference live upgrade with a root-only rollback copy; it neither runs the projector nor writes the application database. `install/migrate-incident-engine.py`, `migrate-reasoning-packets.py`, `migrate-local-reasoning.py`, and `migrate-ai-triage.py` provide separately guarded existing-database extensions under protected backups. `install/install-correlation.py`, `activate-correlation.py`, and `verify-correlation.py` implement the deterministic managed-invocation gate documented in `docs/MANAGED_CORRELATION.md`. `install/install-managed-reasoning.py`, `activate-managed-reasoning.py`, and `verify-managed-reasoning.py` implement the bounded local-model schedule, one-call coordinator, hidden triage artifacts, and exact compatibility upgrades documented in `docs/MANAGED_REASONING.md` and `docs/AI_DETECTION_SIDE_CHANNEL.md`. `install/install-result-outbox.py`, `verify-result-outbox.py`, `activate-result-outbox.py`, and `upgrade-result-outbox-snapshot.py` implement the no-network local result-outbox/snapshot boundary documented in `docs/RESULT_OUTBOX.md`. The separately gated `install-result-sender.py`, `configure-result-sender.py`, and `verify-result-sender.py` implement the write-only transport documented in `docs/RESULT_TRANSPORT.md`; private transport inputs remain outside the repository.

See [`systemd/PROVENANCE.md`](systemd/PROVENANCE.md) for live/public hashes and
the exact sanitation boundary.

## Platform packages and Ollama

`install/versions.env` records the captured public platform/package checkpoints. `install/install-packages.sh` installs only the exact application-level Debian dependencies after an explicit clean-machine confirmation. Kernel, NVIDIA driver, and CUDA provisioning remain operator prerequisites because rediscovery did not recover a trustworthy historical installer for them.

`install/verify-platform.py` fails closed unless the clean host matches the captured Ubuntu/arm64, kernel, driver, CUDA compiler, Python/SQLite, SFTP, and Zstandard contract. CUDA is resolved at the captured public path `/usr/local/cuda/bin/nvcc`; it is not required to be present in a privileged command's reduced `PATH`.

`install/install-ollama.py` requires an operator-supplied binary with the exact captured size and SHA-256. It creates the locked service identity and model-root boundary, installs the binary and sanitized unit without replacing divergent artifacts, verifies the unit, and reloads systemd. It never enables or starts Ollama.

The large model blobs are intentionally not stored in Git. `install/install-model-store.py` imports an independently obtained exact offline model store with full source/target blob hashing, no overwrite, resumable exact-file reuse, and blobs-before-manifests publication. `install/verify-ollama.py --offline` verifies the exact six-manifest inventory, manifest references and hashes, config digests, declared bytes, and every referenced blob size without calling the Ollama API. The normal mode additionally requires the service active/enabled and exactly one loopback TCP listener.

The item-28 application-specific caller and supporting schema/configuration/prompt artifacts were installed empty and unscheduled under protected backup. Item 29 later invoked the boundary through its separately managed schedule; deterministic schedules remain independent of Ollama.

The item-29 service/timer/private binding and exact `r3` bytes are installed and active after natural-cadence gates; preserved terminal failures remain immutable evidence. Item 30's local outbox and write-only sender are active after protected-copy/package/install/failure-resume gates, exact reasoning-digest preservation, dedicated private writer configuration, 186 local/exact GX10-staged tests, first-live/raw-provenance proof, exact replay and divergent conflict isolation, and timer-only activation with natural durable acceptance/ClickHouse ingestion. The sender remains independently disableable and sends at most one file per oneshot. See `docs/MANAGED_REASONING.md`, `docs/RESULT_OUTBOX.md`, and `docs/RESULT_TRANSPORT.md`.

## Guarded activation and runtime verification

`install/verify-runtime.py --preactivation` validates the complete public filesystem, identity, configuration, exact installed-source, SQLite, systemd fragment/drop-in, effective-limit, inactive-unit, empty-spool, and empty-application-state boundary. It fails if the host resembles an already-used or reference deployment.

`install/activate-runtime.py` requires both clean-install and activation-specific confirmation phrases. It runs the platform, preactivation runtime, exact Ollama binary/unit/model, and full model-blob hash gates before enabling anything. Activation order is Ollama first and the pipeline timer second. If activation or final verification fails, it stops any triggered pipeline service and disables/stops the units it changed.

The model-blob hashing pass reads every unique blob and may take substantial time. It makes no API call and runs no inference.

Base clean-machine activation enables exactly:

- `ollama.service`
- `network-log-gx10.timer`

The pipeline service remains static. Starting the base timer authorizes only the proven automatic `fetch -> ingest` behavior. The clean-machine runbook uses the separate inactive install/backfill/activation gate before enabling correlation, so run each phase only after reviewing its exact boundary.

Do not run the activation script against the working reference system.

Run the final non-mutating repository package audit with:

    components/gx10/tests/validate-rebuild-package.py

Expected marker:

`GX10_REBUILD_PACKAGE_VALIDATION=PASS`
