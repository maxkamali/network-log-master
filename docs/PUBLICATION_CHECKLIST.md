# Public Publication Checklist

Use this checklist before every public commit that adds or changes operational material, fixtures, configuration examples, scripts, imported code, rebuild artifacts, or recovery documentation.

## Content safety

- [ ] no passwords, tokens, API keys, credentials, or private key material
- [ ] no production IP addresses or firewall allowlists
- [ ] no private DNS names, operator identity, or environment-specific access endpoints
- [ ] no customer/device-identifying hostnames, payloads, or raw logs
- [ ] no certificate private keys or copied live secret fragments
- [ ] no restricted historical branding or organization identifiers
- [ ] no local secret files, credential caches, generated databases, or runtime state

## Fixture/example safety

- [ ] synthetic device names only
- [ ] IPv4 examples use `192.0.2.0/24`, `198.51.100.0/24`, or `203.0.113.0/24`
- [ ] IPv6 examples use `2001:db8::/32`
- [ ] examples preserve event/configuration structure without preserving production identity
- [ ] production sample hashes, screenshots, or other indirect identity-bearing artifacts are not published unless explicitly reviewed safe

## Engineering gates

- [ ] run `scripts/validate-public-repository.py`
- [ ] run the sanitation gate's synthetic unit tests under `scripts/`
- [ ] stage only intended files
- [ ] run secret/sanitation scanning against staged and tracked content
- [ ] run restricted-term/environment-identifier scanning
- [ ] run syntax/lint checks applicable to changed files
- [ ] run the complete relevant test/verifier suite
- [ ] run whitespace/diff validation
- [ ] inspect the staged diff manually
- [ ] confirm documentation matches the verified implementation state
- [ ] preserve known-good behavior unless an intentional behavior change is documented and validated

## Rebuild-artifact gates

For installers, renderers, verifiers, and captured configuration:

- [ ] clean-machine scripts are clearly distinguished from live/reference-system verification scripts
- [ ] no clean-machine installer is accidentally executed against a working reference system
- [ ] environment-specific values are placeholders, renderer inputs, or operator-owned file inputs
- [ ] secrets are not placed directly in command-line arguments where a safer stdin/file mechanism exists
- [ ] package versions and externally required dependencies are explicit
- [ ] service startup order and dependency assumptions are documented
- [ ] temporary/bootstrap exposure is minimized, especially before credentials/TLS configuration is established
- [ ] rebuild verification is independent enough to detect drift rather than merely echo installer assumptions

## Migration gates

When importing code from another repository or live checkout:

- [ ] record source repository/commit provenance
- [ ] compare the live checkout to its remote first
- [ ] preserve working tests and test fixtures
- [ ] sanitize history/content before public consolidation
- [ ] avoid creating a second writable copy that can silently drift
- [ ] update `CURRENT_STATE.md` and `PROJECT_JOURNAL.md`

## Continuity/documentation gates

- [ ] `docs/CURRENT_STATE.md` accurately reflects current implementation state
- [ ] `docs/CURRENT_STATE.md` contains exactly one item marked `NEXT`
- [ ] the completed sub-section has an append-only entry in `docs/PROJECT_JOURNAL.md`
- [ ] component `REBUILD_STATUS.md` is updated when its verified rebuild state changes
- [ ] durable architecture decisions are reflected in `docs/DECISIONS.md`
- [ ] `docs/ARCHITECTURE.md` and data/operations contracts are updated if the underlying design changed
- [ ] recovery instructions in `docs/START_HERE.md` / `docs/AI_HANDOFF.md` still point to the correct authority documents
- [ ] milestone commits record their SHA and remote verification in the journal

## Publication rule

Do not remove, weaken, or bypass a safety/validation check merely to make publication pass. Fix the content or explicitly document and review why a check is being changed before publication.

After a completed validated project sub-section is published, push the corresponding `PROJECT_JOURNAL.md` update before materially proceeding to the next sub-section.
