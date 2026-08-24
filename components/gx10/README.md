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

GX10 is not:

- the authoritative raw-log archive
- the primary dashboard server
- a direct ClickHouse writer
- the owner of canonical deduplication or incident truth inside the LLM

Current state:

- secure backlog fetch and durable ingest are operational
- replay/idempotency protections exist in the ingest path
- normalized schema-version-1 projection is implemented as the deliberate replacement for transitional vendor/message reparsing
- a deterministic version-1 incident engine and append-only schema are implemented, validated, and installed unscheduled on the working system under protected backup
- a separate offline managed `projection -> incident` runner/service/timer is implemented as an inactive repository candidate with exact hashes, bounded cursor convergence, resource limits, telemetry, and state-preserving disable behavior
- the proven automatic chain is `timer -> fetch -> ingest`
- canonical projection and incident processing remain deliberately absent from the automatic invocation chain
- Ollama is active with six complete model manifests, but no application-specific observability-pipeline caller was discovered
- secure collector-side AI-result return transport is proven, but no GX10 result producer was discovered
- managed projection/incident invocation and local-LLM orchestration remain future gated phases

The normalized production handoff, multi-cadence stability window, and live-copy projection rehearsal now provide the retirement gate. Historical version-3 enrichment rows remain evidence and are not deleted.

Live-system rediscovery is complete. The authoritative reconstruction checkpoint, captured contracts, preserved absences, and next implementation order are in `REBUILD_STATUS.md`.

The complete installation and activation sequence is in `CLEAN_MACHINE_RUNBOOK.md`. Use that runbook only on a clean intended rebuild target, never on the working reference system.

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

The three rediscovered live custom applications and the new incident candidate are under `sbin/` with deployment values removed:

- `fetch-spool.py`
- `ingest-spool.py`
- `enrich-events.py` — compatibility filename now containing the canonical normalized-field projector
- `incident-engine.py` — deterministic incident identity, evidence, lifecycle, repeat, and rolling-context engine

`sbin/runtime_config.py` loads the protected runtime configuration rendered by `install/render-runtime-config.py`. See `sbin/PROVENANCE.md` for live hashes and the function-level parity proof.

Validate the synthetic application/configuration contract with:

    python3 -m unittest discover -s components/gx10/tests -p 'test_*.py' -v

Validate operator configuration inputs without writing files with:

    GX10_SFTP_HOST=collector.example.invalid GX10_SFTP_PORT=2222 GX10_SFTP_USER=spool-reader components/gx10/install/render-runtime-config.py --check

The original deterministic-enrichment source/hash remains recorded for provenance and rollback. The active repository file is now a canonical projector that performs no vendor/message classification, retains local suppression policy, and remains intentionally absent from the proven automatic `timer -> fetch -> ingest` chain.

## SQLite initialization

`sql/initialize.sql` preserves the complete effective SQLite base contract recovered in item 12M:

- 5 application tables
- 13 explicit indexes
- 3 foreign keys
- the two enabled exact-match suppression patterns from item 12H

`sql/incident-v1.sql` adds the deliberate target-state extension: three incident tables, five explicit indexes, and four append-only triggers. `install/initialize-database.py` creates the base plus this extension atomically, refuses any existing database, validates integrity/schema/corpus before publication, and installs mode `0640` for the dedicated runtime identity.

The historical suppression-rule names and reasons were not exposed during rediscovery and no initializer survived. The public rebuild therefore uses neutral names/reasons while preserving functional IDs, evaluation order, types, patterns, and enabled state.

Do not run the initializer against the working GX10 reference system.

## Service and timer reconstruction

`systemd/network-log-gx10.service` and `systemd/network-log-gx10.timer` preserve the complete captured live scheduling and hardening contract with neutral public identity/path values.

The automatic chain remains exactly:

`timer -> fetch -> ingest`

`install/install-applications.py` installs the six application files and four pipeline/correlation units atomically without overwriting divergent files. It validates database/config ownership and modes, runs `systemd-analyze verify`, and reloads systemd without enabling or starting the correlation timer. `install/retire-transitional-enrichment.py` separately performs an exact-old-hash, no-scheduler-reference live upgrade with a root-only rollback copy; it neither runs the projector nor writes the application database. `install/migrate-incident-engine.py` provides the guarded existing-database extension and unscheduled engine installation with exact hashes, a protected SQLite backup, and empty-state-only rollback. `install/install-correlation.py`, `activate-correlation.py`, and `verify-correlation.py` implement the separate managed-invocation gate documented in `docs/MANAGED_CORRELATION.md`.

See `systemd/PROVENANCE.md` for live/public hashes and the exact sanitation boundary.

## Platform packages and Ollama

`install/versions.env` records the captured public platform/package checkpoints. `install/install-packages.sh` installs only the exact application-level Debian dependencies after an explicit clean-machine confirmation. Kernel, NVIDIA driver, and CUDA provisioning remain operator prerequisites because rediscovery did not recover a trustworthy historical installer for them.

`install/verify-platform.py` fails closed unless the clean host matches the captured Ubuntu/arm64, kernel, driver, CUDA compiler, Python/SQLite, SFTP, and Zstandard contract. CUDA is resolved at the captured public path `/usr/local/cuda/bin/nvcc`; it is not required to be present in a privileged command's reduced `PATH`.

`install/install-ollama.py` requires an operator-supplied binary with the exact captured size and SHA-256. It creates the locked service identity and model-root boundary, installs the binary and sanitized unit without replacing divergent artifacts, verifies the unit, and reloads systemd. It never enables or starts Ollama.

The large model blobs are intentionally not stored in Git. `install/install-model-store.py` imports an independently obtained exact offline model store with full source/target blob hashing, no overwrite, resumable exact-file reuse, and blobs-before-manifests publication. `install/verify-ollama.py --offline` verifies the exact six-manifest inventory, manifest references and hashes, config digests, declared bytes, and every referenced blob size without calling the Ollama API. The normal mode additionally requires the service active/enabled and exactly one loopback TCP listener.

No reconstruction artifact creates an application-specific Ollama caller. The proven automatic application chain remains `timer -> fetch -> ingest`.

## Guarded activation and runtime verification

`install/verify-runtime.py --preactivation` validates the complete public filesystem, identity, configuration, exact installed-source, SQLite, systemd fragment/drop-in, effective-limit, inactive-unit, empty-spool, and empty-application-state boundary. It fails if the host resembles an already-used or reference deployment.

`install/activate-runtime.py` requires both clean-install and activation-specific confirmation phrases. It runs the platform, preactivation runtime, exact Ollama binary/unit/model, and full model-blob hash gates before enabling anything. Activation order is Ollama first and the pipeline timer second. If activation or final verification fails, it stops any triggered pipeline service and disables/stops the units it changed.

The model-blob hashing pass reads every unique blob and may take substantial time. It makes no API call and runs no inference.

Successful activation enables exactly:

- `ollama.service`
- `network-log-gx10.timer`

The pipeline service remains static; canonical projection and incident processing remain unscheduled. Starting the timer authorizes only the proven automatic `fetch -> ingest` behavior, so run activation only after the operator has reviewed the final clean-machine runbook and confirmed the transport endpoint.

Do not run the activation script against the working reference system.

Run the final non-mutating repository package audit with:

    components/gx10/tests/validate-rebuild-package.py

Expected marker:

`GX10_REBUILD_PACKAGE_VALIDATION=PASS`
