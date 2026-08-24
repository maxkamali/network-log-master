# Normalizer Migration

## Goal

Move deterministic vendor/event normalization from the transitional GX10 enrichment path to the collector-side Python normalizer without changing capture semantics or silently losing event coverage.

This is a controlled migration, not a rewrite-in-place.

## Source precedence during migration

1. live checked-out code and tests
2. live production/transitional behavior used as a parity reference
3. this repository's current-state and component documentation
4. older planning documents

`docs/CURRENT_STATE.md` controls whether migration work is currently active. This document defines migration gates; it does not override the project's current execution order.

## Repository consolidation status

The source-code consolidation step is complete.

The live normalizer checkout and standalone public repository were reconciled at:

```text
f95db38 Enable NX-OS ETHPORT parser in default registry
58 tests passing
clean working tree
```

That verified history was imported into this repository under `components/normalizer/` with a history-preserving Git subtree merge:

```text
8d55320 Import normalizer component history
```

The import commit records `f95db38` as the subtree split and parent. The normalizer test suite was then run from the new master-repository path in an isolated virtual environment with all 58 tests passing.

New normalizer feature work now belongs in this master repository. The former standalone normalizer repository is historical/migration reference only.

## Current parser checkpoint

Implemented collector-side parser coverage:

- Arista EOS BGP adjacency changes
- Cisco IOS XR BGP adjacency changes
- Cisco NX-OS ETHPORT interface state changes
- Cisco NX-OS OSPF neighbor retransmission degradation
- Cisco NX-OS OSPFv3 neighbor retransmission degradation

The framework also includes generic capture-first normalization, event-envelope extraction, explicit platform hints/trust boundaries, and fail-open parser dispatch.

## Parity reference

The transitional GX10 enrichment executable remains captured and is useful for comparing:

- event family
- vendor/platform interpretation
- protocol
- entity type
- deterministic entity key
- state
- signal type
- structured attributes

It must not be removed until collector-side fixtures, replay, and controlled production integration establish equivalent or intentionally improved behavior.

## Platform trust during replay and production

Stored-observation replay established that platform-specific parsing requires an external trust decision.

The migration contract is:

- use a private operator-maintained platform inventory keyed by the deployment's stable syslog `source_ip` identity
- inject trusted `vendor_hint` and `os_family_hint` before vendor-specific normalization
- do not treat Vector fallback parser labels as vendor/platform identity
- do not infer runtime platform authority solely from message fingerprints
- fingerprints may bootstrap or audit the private inventory
- unmapped sources remain generic observations
- private device identities and the inventory itself remain outside the public repository

This keeps platform identity separate from message decoding and preserves capture-first behavior when inventory coverage is incomplete.

## Known intentional improvement

Measured live GX10 v3 behavior for the reviewed Cisco NX-OS OSPFv3 retransmission observations is generic: those events do not enter its OSPF retransmission classification branch and receive no OSPF entity key.

The collector-side implementation intentionally improves this behavior while preserving:

```text
OSPF   -> event_family ospf
OSPFv3 -> event_family ospfv3
```

Real stored-observation replay has verified collector-side OSPFv3 neighbor degradation classification with `ospfv3-N` process identity.

This is an intentional parity difference, not a requirement to reproduce the transitional limitation.

## Migration gates for each parser

1. inspect real message layouts privately
2. create sanitized synthetic fixtures/tests
3. implement parser behind an explicit platform trust boundary
4. prove normal layouts enrich correctly
5. prove malformed layouts remain generic observations
6. prove future/unknown event codes remain generic
7. prove other platforms cannot enter the parser
8. run the full test suite
9. register in the default parser registry only after isolated tests pass
10. replay representative stored observations
11. compare against transitional GX10 output
12. document intentional differences

## Production cutover gate

Do not wire the collector-side normalizer into the production ingest/handoff path until:

- parser coverage for the selected migration scope is complete
- fixture and negative-path suites pass
- replay is deterministic
- parity differences are understood
- unknown events remain visible and attention-eligible
- raw messages remain replayable
- production integration observability is defined
- rollback is straightforward

After cutover proves stable, retire duplicate vendor parsing on GX10 deliberately.

## Replay/parity gate completed

The selected pre-cutover replay/parity milestone passed.

Across 24 representative stored observations, collector output produced 21 strict semantic matches, 3 intentional OSPFv3 differences, and 0 unexpected differences against transitional GX10 v3.

Two genuine collector gaps found by parity were corrected: EOS peer-AS preservation and NX-OS ETHPORT protocol identity.

The IOS XR reason/detail difference was confirmed as representation-only and did not justify weakening the collector parser.

Sanitized repeated replay is deterministic and the full normalizer suite passes 73 tests.

This replay milestone alone did not authorize production cutover. The later shadow, handoff, and explicit operator-authorization gates completed separately, culminating in the 2026-08-24 production activation recorded in `docs/NORMALIZER_HANDOFF.md`.

## Production integration design status

The production integration design and forward-only handoff activation are complete in `docs/NORMALIZER_PRODUCTION_INTEGRATION.md` and `docs/NORMALIZER_HANDOFF.md`.

The selected architecture is a collector-local durable-file worker that reads settled source backlog files without modifying them and writes atomic normalized shadow files with a durable idempotency ledger. Vector's raw ClickHouse and backlog outputs remain unchanged. Verified at/after-floor normalized files are now copied into a separate handoff view under their original GX10 transport identities.

The next gate collects bounded post-cutover stability evidence before deliberately retiring transitional GX10 vendor parsing. `docs/CURRENT_STATE.md` remains the execution authority; this migration document is not the execution queue.
