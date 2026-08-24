# GX10 Application Source Provenance

## Captured reconstruction baseline

The original three public application files in this directory were captured from the working GX10 reference system after rediscovery closed.

Live SHA-256 checkpoints:

- `fetch-spool.py`: `662ef297a900b107a12d252f21524db20816244b0c74320a6990c299db3fec6b`
- `ingest-spool.py`: `6d9509c320a8beaf409264ca461b54336dc231dafd0f4d0f1b74f3a155c8b618`
- `enrich-events.py`: `6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

The public copies intentionally do not have those byte hashes because deployment-specific literals were removed and the resulting AST was rendered into neutral public formatting.

The capture changed only configuration binding:

- database, spool, SSH key, and known-hosts paths now come from `runtime_config.py`
- SFTP host, port, and user now come from a protected rendered runtime configuration
- the already-public `/spool/%Y/%m/%d/%H` chroot path contract remains fixed
- public system executable paths for `sftp` and `zstd` remain fixed

At the reconstruction checkpoint, all 27 function ASTs matched the live sources exactly after excluding the Python 3.12-only `type_params` metadata field. The comparison included every fetch, ingest, and transitional deterministic-enrichment function.

The public capture gate also verified that no deployment IPv4 literal or non-public absolute path survived.

The source capture did not execute any application, open the production database, contact SFTP, or write to the reference system.

## Post-cutover canonical projection

After the verified normalized handoff became authoritative on 2026-08-24, item 24 deliberately replaced the repository's transitional vendor/message reparser at the compatibility filename `enrich-events.py` with a schema-version-1 canonical projector.

Repository projection candidate SHA-256:

`f3ae8984f72b1fe8ec6c44fb14d2011976e9e2ba200b7e46fd2003e5117b2079`

The original live transitional-enrichment SHA-256 remains the exact rollback identity:

`6cd979c286410e7cae00b76c14b515798ac16791875a7db21cdf688085e3f7e0`

The projector:

- accepts only the exact normalized schema-version-1 key/type contract
- treats collector-normalized event, entity, protocol, state, signal, repeat, and attribute fields as authoritative
- performs no vendor or message classification
- retains the existing GX10-local enabled suppression-rule overlay
- preserves historical classification-version-3 rows
- writes classification version 4 for canonical projections
- advances an atomic `agent_state` cursor with each projection batch
- is idempotent and fails closed on malformed canonical input or newer projection state
- remains absent from the automatic `timer -> fetch -> ingest` chain

The candidate was rehearsed twice against an on-server SQLite backup: the first run scanned `949845` events and projected `2781` canonical rows while preserving `24207` historical version-3 rows; the second projected zero rows. All projected fields matched an independent re-read, `1984` rows received the existing local suppression policy, and the live database remained unchanged.
