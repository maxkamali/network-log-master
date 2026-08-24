# Normalizer Production Integration

## Status

Design: `DONE`.

Repository implementation and synthetic validation: `DONE`.

Bounded live shadow deployment: `ACTIVE`; explicit authorization and a private trusted platform inventory were supplied on 2026-08-23.

Bounded catch-up and steady-state verification: `PASS` for 11,983 files and 1,107,749 records, with exact cardinality, zero parser errors, zero incomplete ledger rows, and zero pending work after each reviewed steady-state cycle.

Production cutover remains unauthorized.

## Objective

Move the validated deterministic normalizer onto the collector without allowing a normalizer defect, unavailable private inventory, or deployment mistake to interrupt raw syslog capture, ClickHouse delivery, or the current GX10 backlog.

The design is intentionally shadow-first and fail-open with respect to evidence preservation.

## Current production boundary

Vector currently fans each parsed/raw-preserved syslog observation to:

- the ClickHouse raw syslog sink
- the compressed `/var/spool/vector-ai` backlog consumed read-only by GX10

The production Vector/ClickHouse/GX10 path does not call Python. The collector-side normalizer runs beside it as an isolated durable-file shadow worker; its output is not consumed by GX10 or any production sink.

## Chosen architecture

The first production integration is a separate collector-local durable-file worker.

```text
Vector normalize_udp / normalize_tcp
        |                         |
        | unchanged               | unchanged
        v                         v
ClickHouse raw syslog      /var/spool/vector-ai
                                    |
                                    | read-only, settled files
                                    v
                         normalizer shadow worker
                                    |
                                    v
                 /var/spool/network-log-normalizer-shadow
```

The worker is not inserted inline between Vector and either existing sink. This preserves the proven capture path while shadow evidence accumulates.

The design deliberately avoids a best-effort socket loop between Vector and Python. The existing file backlog already supplies a durable, replayable boundary, and file-level hashing makes completeness and idempotency independently auditable.

## Runtime identities and paths

Public rebuild defaults:

| Purpose | Contract |
| --- | --- |
| Runtime account | dedicated unprivileged `network-log-normalizer` system account |
| Source backlog | `/var/spool/vector-ai` mounted/readable without write permission |
| Shadow output | `/var/spool/network-log-normalizer-shadow` |
| Durable ledger | `/var/lib/network-log-normalizer/state.sqlite3` |
| Private platform inventory | `/etc/network-log-normalizer/platform-inventory.json` |
| Service | `network-log-normalizer-shadow.service` |
| Schedule | `network-log-normalizer-shadow.timer` |

The worker needs no network access, ClickHouse credentials, SSH key, AI-result writer role, Ollama access, or permission to modify the source backlog.

## Private platform-inventory contract

Vendor-specific parsing requires an operator-maintained private mapping keyed by the collector's stable `source_ip` identity.

Schema version 1:

```json
{
  "schema_version": 1,
  "platforms": {
    "192.0.2.10": {
      "vendor_hint": "cisco",
      "os_family_hint": "nxos"
    }
  }
}
```

Requirements:

- regular nonsymlink file
- owned by root and readable only by root plus the normalizer runtime group
- no group write or world permissions
- exactly one entry per canonical IP address
- only supported canonical vendor/OS values
- no hostname/message fingerprint fallback as runtime authority
- missing source identities remain generic, attention-eligible observations
- the real inventory and production device identities remain outside the public repository

The worker injects hints into an in-memory copy of each record before calling `normalize_record`; it does not add private inventory contents to raw input files.

## Source-file eligibility

Only the captured relative-path pattern is eligible:

```text
YYYY/MM/DD/HH/syslog-YYYYMMDD-HHMM.jsonl.zst
```

A file must:

- be a regular nonsymlink file beneath the source root
- have a modification time at least 120 seconds old
- pass Zstandard integrity validation
- remain unchanged in size, modification time, and SHA-256 through processing

The 120-second threshold is intentionally longer than the captured Vector file sink's ten-second idle timeout. The worker never renames, truncates, deletes, locks, or changes source metadata.

## Deterministic output contract

Each physical JSONL input line produces exactly one schema-version-1 normalized JSON object in the same order.

The output relative path mirrors the source partition beneath the shadow root and uses a `.normalized.jsonl.zst` suffix. Publication is atomic:

1. write an owner-only temporary file in the destination directory
2. flush and synchronize file contents
3. validate the compressed output
4. calculate output SHA-256
5. rename without overwriting an unexpected existing artifact
6. synchronize the destination directory
7. commit the ledger transaction

JSON object keys and JSON separators are stable so repeated processing of the same immutable source and inventory version produces the same uncompressed records.

Malformed JSON or an over-limit input line does not disappear. The file fails without a success-ledger entry and the original source remains authoritative for investigation/retry. Individual mapping records that contain malformed field values still pass through the normalizer's capture-first coercion behavior.

## Durable ledger and idempotency

One ledger row per completed source file records at least:

- source relative path, size, modification time, and SHA-256
- inventory SHA-256
- normalizer schema/package version
- output relative path, size, and SHA-256
- input/output record counts
- generic, vendor-enriched, inventory-miss, and parser-error counts
- completion timestamp

Behavior:

- an exact completed tuple is skipped after output verification
- a missing or hash-mismatched recorded output fails closed
- a previously completed source path whose content changes fails closed for operator investigation
- incomplete temporary output is ignored and may be safely regenerated
- SQLite uses explicit transactions, foreign-key enforcement, a busy timeout, and an independently verified schema

## Failure isolation

Normalizer failures must not affect Vector, ClickHouse, `/var/spool/vector-ai`, or GX10's current raw-backlog view.

The service:

- is non-root and has read-only source access
- writes only its output and state paths
- has no restart coupling to Vector
- returns nonzero on file/inventory/ledger/output inconsistency
- leaves source evidence untouched
- emits structured summary/error records to the local service journal without logging raw messages or inventory contents
- is bounded by systemd filesystem, privilege, syscall, memory, CPU, and task restrictions

If the private inventory is missing or invalid, the service does not silently normalize everything as unknown; the run fails before claiming a successful shadow cycle.

## Shadow observability and acceptance

Every cycle exposes public-safe counters and ages:

- eligible, completed, skipped, and failed files
- input and output record counts
- source and output bytes
- oldest eligible unprocessed-file age
- inventory-hit/miss counts
- generic/vendor-enriched/parser-error counts
- cycle duration and last successful completion time

Promotion requires:

- repository implementation/tests and package verification pass
- sanitized replay remains deterministic and preserves the existing 21 strict / 3 intentional / 0 unexpected parity result
- every eligible shadow source has exactly one verified output
- input and output line counts match for every completed file
- no unexplained source mutation, output hash, ledger, parser-error, or backlog-age failure
- platform-inventory misses are reviewed rather than guessed
- a bounded production shadow period is explicitly authorized and reviewed
- the handoff switch and rollback are rehearsed without deleting either spool

No duration or event-volume threshold is invented before actual production rate and coverage are observed. The operator must approve the bounded live shadow step and its evidence threshold.

## Promotion boundary

Promotion does not replace the Vector raw path. It changes only the read-only GX10 handoff view from the raw backlog root to a verified forward-only normalized handoff root.

Before that switch:

- normalized output must retain the required `timestamp` and `message` strings
- GX10 ingest replay/idempotency must pass against sanitized normalized fixtures
- the source/output file relationship must be auditable through the ledger
- current raw ClickHouse and raw backlog paths must remain unchanged
- the exact mount/bind configuration and service ordering must have a reviewed rollback command sequence

Transitional GX10 vendor enrichment is retired only after normalized handoff stability is proven. It is not silently deleted as part of the first switch.

## Rollback

Rollback changes the GX10 read-only handoff view back to `/var/spool/vector-ai` and restores the prior verified transport configuration.

Rollback must not:

- delete shadow output or ledger evidence
- delete raw backlog files
- alter ClickHouse raw observations
- attempt to reverse already-ingested GX10 rows in place

Because GX10 idempotency is keyed by source file and record number, cutover and rollback use the explicit forward-only file-identity plan in `docs/NORMALIZER_HANDOFF.md`. Verified normalized outputs at or after one immutable inclusive floor are copied into a separate handoff root under their original raw transport names. History before the floor is never exposed through that view. This preserves the current `/spool/<source_path>` namespace across cutover and rollback while avoiding historical replay.

## Implementation sequence

1. `DONE` — build the inventory validator and atomic durable-file worker
2. `DONE` — build the ledger schema/verifier and synthetic replay fixtures
3. `DONE` — package the dedicated account, directories, service, timer, and hardening
4. `DONE` — add a repository-only installer/verifier that does not activate the worker by default
5. `DONE` — prove source immutability, exact record cardinality, deterministic output, resume, mutation refusal, and failure isolation
6. `DONE` — publish the repository implementation checkpoint
7. `DONE` — received explicit authorization, established the private inventory, staged the package, and activated it in shadow-only mode
8. `DONE` — collected/reviewed complete historical catch-up and five normal-cadence steady-state cycles; corrected and live-proved active verifier concurrency handling
9. `DONE` — designed and synthetically rehearsed the forward-only, file-identity-safe GX10 handoff switch and rollback without changing the live handoff
10. `NEXT` — explicit production-cutover authorization is recorded; publish/stage the validated exact-hash handoff package and execute the documented preflight/cutover evidence gate

## Non-goals

This phase does not:

- change live Vector inputs, raw ClickHouse delivery, or current GX10 handoff
- infer platforms from message text at runtime; the installed worker trusts only the protected private inventory
- implement the incident engine or an Ollama caller
- enable a GX10 AI-result producer
- retire transitional GX10 parsing
- run clean-machine rebuild installers against reference systems
