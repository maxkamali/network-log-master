# Normalizer Component

The normalizer converts capture-first records into deterministic structured network observations while preserving raw replayability.

This directory is the active development home for the normalizer inside the master repository. Its standalone repository history was imported here with a history-preserving Git subtree merge.

Consolidation checkpoint:

```text
source checkpoint: f95db38 Enable NX-OS ETHPORT parser in default registry
master import:      8d55320 Import normalizer component history
verification:       58 tests passing from components/normalizer/
```

Current verified feature checkpoint:

```text
18ec113 Fix public repo gate for monorepo layout
7f7f592 Add Cisco NX-OS OSPF retransmission parser
81a3812 Enable NX-OS OSPF parser in default registry
70 tests passing
public repository gate passing
```

Current coverage includes:

- generic capture-first normalization
- event-code/event-family envelope extraction
- explicit vendor/OS platform hints and trust boundaries
- ordered fail-open parser dispatch
- Arista EOS BGP adjacency parsing
- Cisco IOS XR BGP adjacency parsing
- Cisco NX-OS ETHPORT state parsing
- Cisco NX-OS OSPF neighbor retransmission degradation
- Cisco NX-OS OSPFv3 neighbor retransmission degradation

The NX-OS OSPF parser supports the exact retransmission event codes and preserves `ospf` versus `ospfv3` event-family identity. It uses deterministic `OSPF|device|process|neighbor` identity, requires event-code/process consistency, and leaves malformed, future, ambiguous, or cross-platform observations on the generic capture-first path.

The former standalone normalizer repository is retained for historical provenance only. New normalizer feature development occurs here.

## Production integration status

Selected replay/parity is complete: 24 representative observations produced 21 strict semantic matches, 3 intentional OSPFv3 improvements, and 0 unexpected differences. The full suite now includes durable shadow-worker tests in addition to parser/replay coverage.

The approved collector integration is a separate durable-file shadow worker implemented in `src/network_log_normalizer/shadow.py`. Packaging, systemd hardening, a non-activating installer, and an independent verifier are under `components/collector/normalizer/`.

Do not add parser breadth by default. Live shadow deployment and production promotion remain separate authorization/evidence gates in `docs/NORMALIZER_PRODUCTION_INTEGRATION.md`.
