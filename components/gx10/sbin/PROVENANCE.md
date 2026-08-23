# GX10 Application Source Provenance

The three public application files in this directory were captured from the working GX10 reference system after rediscovery closed.

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

All 27 function ASTs match the live sources exactly after excluding the Python 3.12-only `type_params` metadata field. The comparison includes every fetch, ingest, and deterministic-enrichment function.

The public capture gate also verified that no deployment IPv4 literal or non-public absolute path survived.

The source capture did not execute any application, open the production database, contact SFTP, or write to the reference system.
