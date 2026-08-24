# GX10 systemd provenance

The public service and timer were captured from the working GX10 reference system by exact live unit hash.

Live hashes:

- service: `0f8e99bb4101e52e028dcedfb98f3998b2ebc4008adac0d38c04aa1716ebecbb`
- timer: `5371995539846d4cca6014a70548e95c942e9f601d0736b06f4bda61c1ccc0f5`

Public hashes:

- `network-log-gx10.service`: `6970f861fcde7e2f1c59a80264fa79ddda6a6ceb2f9dc3511afbd5c88bf694bf`
- `network-log-gx10.timer`: `25939b7ce8f424840cef35ebc58635919d706b104408094d164e342081a77436`

The public units differ only where live values are identity-bearing:

- unit descriptions and filenames use neutral project naming
- service user/group use the public runtime identity
- executable paths use the public libexec layout
- writable paths use the public state/spool layout
- the timer's target unit uses the public service filename

The service/timer behavior and all other directives are retained from the live files.

The sanitizer required fetch then ingest `ExecStart` order, exactly two known writable path roles, zero environment directives, no unknown absolute paths, and no IPv4 literals.

Deterministic enrichment remains absent from the service by design because no live automatic invocation was discovered.

## Managed correlation target units

`network-log-gx10-correlation.service` and `.timer` are deliberate item-26 implementation artifacts, not rediscovered historical units. They preserve the recovered fetch/ingest unit unchanged and provide a separately disableable offline boundary for exact `projection -> incident` ordering.

The service is a hardened non-root oneshot with no network access, a private drop-in that limits write scope to the validated database parent, explicit CPU/memory/task/time limits, and no inline environment. The timer uses a monotonic one-minute inactive cadence with a five-minute boot delay. Installation does not enable either unit; the separate validated activation gate completed on the working system after initial zero-lag backfill and before multi-cadence verification.

## Managed reasoning target units

`network-log-gx10-reasoning.service` and `.timer` are deliberate item-29 implementation candidates, not rediscovered historical units. They preserve both active deterministic schedules unchanged and provide a third separately disableable `packet build -> one local inference` boundary.

The service is a hardened non-root oneshot with a three-minute timeout, explicit CPU/memory/task limits, write access limited by a private drop-in to the validated database parent, and address-family plus IP policy limited to Unix sockets and IPv4 loopback. The timer uses a five-minute inactive cadence with a 15-minute boot delay. Repository installation does not enable it; protected-copy, inactive-install, initial bounded activation, and scheduled-cadence gates remain separate.

## Ollama service

`ollama.service` reproduces the separately captured local-model runtime unit.

- live unit SHA-256: `11758d469d3f103e53a9612a8ffcb3a3e61834c994c08d412bb051f3c827dbd3`
- public unit SHA-256: `d8774a8a664856242805d0e5a78297db31865e2b56727edd8d16764921858cd4`

Only the identity-bearing description was changed. The executable, service identity, restart behavior, service environment, enablement target, and absence of pipeline application references are preserved.

The effective live file-descriptor limits are platform/service-manager state rather than explicit directives in the captured fragment. Platform/runtime verification must check effective state instead of inventing an explicit unit directive and presenting it as recovered configuration.
