# Direct-access VM handoff

Status: `PAUSED FOR EXECUTION-ENVIRONMENT MIGRATION`

Date: 2026-08-23 PDT

This file is a durable recovery checkpoint for moving the remaining project work from a human copy/paste relay workflow to an operator-controlled VM where the executing AI can use direct authenticated access to the reference systems and GitHub.

It does not advance execution-order item 12 and does not mark GX10 rediscovery complete.

## Durable repository baseline

Before this handoff, public `main` was independently verified at:

`1f008269c6613a0759a8a3d00ccc346ae1b4496d` — `Journal GX10 SQLite bootstrap provenance`

That commit closes GX10 rediscovery through item 12M.

Execution-order item 12 remains the single `NEXT` item.

## Rediscovery completed before the handoff

Durably journaled GX10 rediscovery includes:

- platform/runtime inventory
- timer and oneshot service contract
- remote-spool fetcher structure and semantics
- local spool-ingest implementation and schema behavior
- deterministic enrichment implementation
- active suppression corpus
- runtime orchestration boundary
- enrichment invocation closeout
- result-return and Ollama-caller boundary
- Ollama service/model runtime state
- complete effective SQLite schema and bootstrap-provenance closeout

The currently proven automatic application chain is:

`timer -> fetch -> ingest`

The deterministic enrichment executable exists and has been characterized, but no current automatic invocation mechanism has been discovered.

The collector-side write-only result-return boundary exists, but no GX10 application producer has been discovered.

Ollama is installed, active, enabled, loopback-only on TCP/11434, and has six complete local model manifests, but no application-specific observability-pipeline caller has been discovered.

## Item 12N partial runtime-contract capture

Item 12N was executed successfully on GX10 immediately before this handoff.

It is intentionally recorded as `PARTIAL / NOT JOURNALED AS COMPLETE` because one dependency-detection result is known to be defective and must be corrected before the subsection is accepted.

### Artifact provenance

The three previously captured GX10 application executables remained unchanged:

- fetch SHA-256: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- ingest SHA-256: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- deterministic enrichment SHA-256: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

The pipeline service-unit SHA-256 remained:

`0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`

Post-inspection hashes matched the preconditions.

### Runtime identity contract

The pipeline service remained:

- loaded
- inactive between timer executions
- static
- `Type=oneshot`
- `DynamicUser=no`
- `PrivateTmp=yes`
- `ProtectHome=yes`
- `ProtectSystem=strict`
- `NoNewPrivileges=yes`
- `UMask=0027`

The private runtime account/group names remain withheld.

Proven identity metadata:

- runtime username SHA-256: `1d45b3f3754dd2028ff383a738a79a512024b18754509596eb284f352c69a467`
- runtime group-name SHA-256: `1d45b3f3754dd2028ff383a738a79a512024b18754509596eb284f352c69a467`
- UID: `994`
- GID: `981`
- system account: yes
- login shell basename: `nologin`
- private home-path SHA-256: `20c27a66309cedee8620290f0e532bdcc82bd1a5918dd6c9a36ad9f6190cbc26`
- home exists: yes
- supplementary group membership count: `1`
- sole membership is the primary runtime group

### Filesystem contract

Private literal paths remain withheld. The observed local path roles, path hashes, ownership classes, and modes were:

1. SSH-material parent directory
   - path SHA-256: `bcf74452f8bde6172f1c2b1c316ea82e9d251e34f8490b5894ef7b89dc4be822`
   - directory
   - mode `0700`
   - runtime-user/runtime-group owned

2. known-hosts file
   - path SHA-256: `1cef0996605f206e82d325e3dd594f28fc565918e405282104e734268033c2f9`
   - mode `0600`
   - runtime-user/runtime-group owned
   - size `978` bytes

3. SSH private-key file
   - path SHA-256: `9b1636c6cbf36526524a20274907ae9946c98a4127406e2d93b58ef35dc2fbaf`
   - mode `0600`
   - runtime-user/runtime-group owned
   - size `432` bytes

4. spool parent directory
   - path SHA-256: `e35eb3808d32cb52de2935433e8f10564f8e8a93c5f2db79db2b75d234819d4f`
   - mode `0750`
   - runtime-user/runtime-group owned

5. incoming spool directory
   - path SHA-256: `0d8370eff17ecb4797b08d3641a9eb7ca27568d85736b57735612203adf7cba8`
   - mode `0750`
   - runtime-user/runtime-group owned

6. processed spool directory
   - path SHA-256: `3f1ecf8867b67cf95df7d3c752cc3760f1d2764bed26e695a30a35aa3f5f5beb`
   - mode `0750`
   - runtime-user/runtime-group owned

7. temporary spool directory
   - path SHA-256: `d46ebb1ffdebb60c4675e704167001591d1881a3502f3faa75052daa91fd1083`
   - mode `0750`
   - runtime-user/runtime-group owned

8. application-state/database parent directory
   - path SHA-256: `26ab131666ce1b9e9e8c28192666061c1e265b4584f6399e3153f5cd72a7927b`
   - mode `0750`
   - runtime-user/runtime-group owned

9. application SQLite database
   - path SHA-256: `bb6b9179d182ada7a636a1fe40bdeb79b6874382c013d3604a67db2d53a1a430`
   - mode `0640`
   - runtime-user/runtime-group owned
   - observed size during item 12N: `1801150464` bytes

The database-size difference from the earlier 12M metadata checkpoint is consistent with the live system continuing to ingest while rediscovery was in progress; it is not treated as schema drift.

### SSH/SFTP security-material metadata

Exactly one SSH private-key path and one known-hosts path were resolved from the fetcher source.

Their path hashes, sizes, modes, and ownership are captured above.

Item 12N did not read:

- SSH private-key contents
- known-hosts contents
- authorized-keys contents

### Systemd filesystem sandbox

Exactly two `ReadWritePaths` entries were present.

One corresponds to the application-state/database parent path:

`26ab131666ce1b9e9e8c28192666061c1e265b4584f6399e3153f5cd72a7927b`

The other corresponds to the spool parent path:

`e35eb3808d32cb52de2935433e8f10564f8e8a93c5f2db79db2b75d234819d4f`

Additional observed service contract:

- `ReadOnlyPaths` count: `0`
- `InaccessiblePaths` count: `0`
- `StateDirectory` count: `0`
- `CacheDirectory` count: `0`
- `RuntimeDirectory` count: `0`
- `LogsDirectory` count: `0`
- working directory: unset
- inline environment-variable count: `0`
- environment-file count: `0`

### Python runtime/dependency contract

All imports across the three known custom application executables are standard-library modules.

Observed imports by component:

- deterministic enrichment: `datetime,json,re,sqlite3,sys`
- fetch: `datetime,hashlib,os,pathlib,re,sqlite3,subprocess,sys`
- ingest: `datetime,io,json,os,pathlib,sqlite3,subprocess,sys`

Union count:

`10`

Third-party Python import count:

`0`

Runtime versions:

- Python `3.12.3`
- Python SQLite runtime `3.45.1`

Python executable package provenance:

- package: `python3.12-minimal`
- version: `3.12.3-1ubuntu0.15`

### Known 12N validator defect

The item-12N external-executable detector reported:

`external_tool_source_reference_count=0`

and:

`external_tool_dependency_count=0`

Those values must not be accepted as the application dependency contract.

They conflict with already-proven earlier rediscovery:

- item 12C established external SFTP and Zstandard usage in the fetch component
- item 12D captured the strict SFTP command contract and Zstandard verification using `-q -t`
- item 12F captured streaming Zstandard decompression using `-dc`

Therefore the zero external-tool result is classified as a validator defect.

The new direct-access VM must rerun only this narrow dependency/provenance slice with a corrected detector before item 12N is journaled as complete.

Do not infer that SFTP or Zstandard disappeared from the live implementation.

### Item 12N safety result

The successful runtime-contract inspection did not:

- print custom source
- print private runtime account names
- print private live paths
- read SSH private-key contents
- read known-hosts contents
- read authorized keys
- print systemd environment values
- open the production application database
- read production event rows
- make a network request
- execute a pipeline component
- request a filesystem write

The overall runtime-contract analysis and postcheck both returned PASS, subject to the external-dependency detector correction above.

## Execution-environment transition

The remaining project execution will move to an operator-controlled VM with direct authenticated access to:

- the collector reference system
- GX10
- the public GitHub repository

The human operator should no longer be required to act as the routine copy/paste transport for shell commands and outputs.

Credentials, keys, private addresses, and other environment-specific identity remain outside the public repository.

Direct access changes the execution mechanism, not the safety or publication rules.

## Required resume sequence on the new VM

Before materially continuing work:

1. verify the local repository and public `main` state against this handoff checkpoint
2. verify authenticated connectivity to both reference systems without publishing private connection values
3. verify the three GX10 application executable hashes and pipeline unit hash still match the captured values
4. rerun the corrected narrow external-executable dependency/provenance check for item 12N
5. reconcile that result with the already-proven SFTP and Zstandard contracts
6. journal and publish item 12N only after the corrected dependency check passes
7. run the final bounded GX10 rediscovery closure audit
8. publish a durable rediscovery-complete checkpoint
9. only then begin GX10 public rebuild implementation and later execution-order items

## Human-intervention boundary

The direct-access workflow should proceed autonomously for bounded read-only discovery, implementation, validation, repository maintenance, and ordinary reversible operations.

Human intervention remains appropriate when required for:

- credentials or authentication that cannot safely be delegated through the execution environment
- destructive or difficult-to-reverse production actions
- decisions that materially change the architecture or project scope
- ambiguous findings where operator intent is required
- external infrastructure that the execution environment cannot access directly

Availability of credentials must not be interpreted as blanket authorization for destructive changes.

## Publication and continuity rules remain in force

The migration to direct access does not change these project rules:

- `docs/CURRENT_STATE.md` remains execution authority with exactly one `NEXT` item
- validated completed subsections are journaled and pushed before materially proceeding
- meaningful intermediate checkpoints are published when they materially reduce recovery risk
- public-repository safety gates remain mandatory
- private identities, addresses, credentials, keys, and production-derived sensitive material remain outside the public repository
- working reference systems are not used as clean-machine rebuild targets
- verified current behavior is preserved during reconstruction unless a deliberate later change is separately designed and validated
