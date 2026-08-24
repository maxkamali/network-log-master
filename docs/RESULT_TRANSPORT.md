# GX10 Result Return Transport

## Status

Execution-order item 30 remains in progress. The collector-side durable acceptance-ledger candidate passes 11 focused local tests and the same 11 tests from an exact temporary tree on the collector. The working collector still runs the prior gate at this checkpoint; no writer credential, sender, or result transmission is installed.

## Replay problem

The GX10 result producer derives one deterministic filename and canonical JSONL payload per successful reasoning run. A future sender can therefore retry exactly. The unsafe window is:

1. the remote upload completes
2. the sender is interrupted before moving the local file from `ready` to `delivered`
3. the next sender cycle uploads the same name again

The prior collector gate rejected a duplicate only while a same-name file remained in its ready directory. If that ready file was later removed, the same filename could be accepted again and Vector could insert it into ClickHouse again. The current ClickHouse result table is not itself a file-identity deduplication boundary.

## Durable collector acceptance

The candidate gate creates `.accepted-v1.sqlite3` inside the protected ready directory. Vector reads only `*.jsonl`, so the ledger and any short-lived SQLite journal are outside its source glob.

Each immutable ledger row stores:

- basename-only JSONL filename
- lowercase SHA-256 of exact file bytes
- byte size and validated record count
- timezone-aware acceptance timestamp

The gate verifies ledger ownership, mode `0640`, single-link metadata, schema version, exact columns, exact immutable triggers, SQLite quick check, and every row before processing incoming files. Rows cannot be updated or deleted through SQLite.

At startup the gate validates every existing ready JSONL file. Missing rows are inserted before incoming enumeration; an existing row with different file evidence fails the entire service. This bootstraps historical ready files and recovers a crash after ready publication but before ledger commit.

First acceptance uses this durable order:

1. validate stable incoming metadata and exact bytes
2. create the same-inode ready name without overwriting an existing destination
3. persist the ready directory
4. remove the incoming name and persist the incoming directory
5. insert and synchronously commit the immutable acceptance row
6. persist the ready directory again

If interruption occurs between creating the ready name and removing the incoming name, the next cycle accepts only the explained two-link same-inode state, removes the incoming link, and resumes reconciliation. Unexplained hard links fail closed.

## Duplicate outcomes

- Same filename and exact accepted digest/size/count: quarantine as an exact already-accepted replay.
- Same filename with different evidence: quarantine as a conflict with durable acceptance.
- Existing ready file with evidence different from its ledger row: fail the gate service before processing incoming files.
- Invalid input: quarantine without creating an acceptance row.

Exact replay is operationally safe and expected after sender interruption. It is still quarantined so collector operators can distinguish transport retries from first acceptance. A divergent replay is a stronger integrity finding.

## Sender acknowledgment contract

The future sender must upload the already-validated local ready file under its unchanged deterministic basename. It must never generate a second transport identity or rewrite content during retry. Only after the transport client reports successful completion may it atomically move the local file from `ready` to `delivered` under the existing shared outbox lock.

`delivered` means transport completion, not proven collector ingestion. Collector gate failures, rejected files, Vector ingestion, and ClickHouse row/provenance evidence remain independent end-to-end gates. The sender must retain bounded logs/metrics that expose retries and failures without result content.

## Passed repository/copy gates

The 11 focused tests prove:

- first acceptance and durable identity creation
- preexisting ready-file bootstrap
- exact replay while ready exists
- exact replay after ready removal
- divergent replay after ready removal
- malformed rejection without acceptance
- immutable ledger update/delete refusal
- ledger mode tamper refusal
- ready/ledger divergence refusal
- crash after ready publication before ledger commit
- crash between no-overwrite link and incoming unlink

The exact candidate passed the same suite on the collector's Linux/Python runtime from temporary storage. A metadata-only preflight proved the live gate still matched the published predecessor, its timer was enabled/active with zero restarts, the service was idle, all three result spool directories contained zero files, and no acceptance ledger existed.

## Remaining gates

1. Publish and independently verify the repository/copy checkpoint.
2. Guardedly replace only the collector gate executable with exact rollback bytes while its timer is stopped.
3. Bootstrap and independently verify the live empty acceptance ledger, exact service/timer health, and unchanged empty spool counts.
4. Build and test the deterministic GX10 sender without installing a credential or transmitting.
5. Stage/install the sender inactive, then provision the write-only key separately.
6. Transmit a bounded first file and prove collector acceptance, Vector/ClickHouse ingestion, complete `raw_json` provenance, local delivered transition, and all preexisting schedule health.
7. Prove an exact replay creates no second ClickHouse row and a controlled malformed/divergent file remains isolated.
