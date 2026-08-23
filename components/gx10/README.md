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
- transitional deterministic enrichment exists and is useful as a migration parity reference
- the proven automatic chain is `timer -> fetch -> ingest`
- deterministic enrichment has no discovered automatic invocation mechanism
- Ollama is active with six complete model manifests, but no application-specific observability-pipeline caller was discovered
- secure collector-side AI-result return transport is proven, but no GX10 result producer was discovered
- the long-lived deterministic incident engine and production LLM orchestration remain future build phases

Transitional enrichment should be retired only after collector-side normalization and replay parity are proven.

Live-system rediscovery is complete. The authoritative reconstruction checkpoint, captured contracts, preserved absences, and next implementation order are in `REBUILD_STATUS.md`.
