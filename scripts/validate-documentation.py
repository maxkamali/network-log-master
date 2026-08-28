#!/usr/bin/env python3
"""Validate the repository's human and agent documentation entry path."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / 'docs'
GUIDE = DOCS_DIR / 'DOCUMENTATION_GUIDE.md'
MARKDOWN_LINK_RE = re.compile(r'\[[^\]]+\]\(([^)]+)\)')
HEADING_RE = re.compile(r'(?m)^#{1,6}\s+(.+?)\s*#*\s*$')
INLINE_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')
REQUIRED_FILES = (
    'README.md',
    'docs/START_HERE.md',
    'docs/CURRENT_STATE.md',
    'docs/ARCHITECTURE.md',
    'docs/OPERATIONS.md',
    'docs/ROADMAP.md',
    'docs/DECISIONS.md',
    'docs/PROJECT_JOURNAL.md',
    'docs/DOCUMENTATION_GUIDE.md',
)
ENTRY_REFERENCES = {
    'README.md': ('docs/START_HERE.md', 'docs/CURRENT_STATE.md'),
    'docs/START_HERE.md': (
        '../README.md',
        'ARCHITECTURE.md',
        'CURRENT_STATE.md',
        'DOCUMENTATION_GUIDE.md',
    ),
    'docs/DOCUMENTATION_GUIDE.md': ('../SECURITY.md', 'PROJECT_JOURNAL.md'),
}
STALE_SUMMARIES = {
    'README.md': ('complete through project item 42',),
    'docs/START_HERE.md': ('complete through item 42',),
    'docs/AI_HANDOFF.md': ('complete through execution-order item 41',),
    'docs/DECISIONS.md': (
        'compatibility correction pending',
        'item 12n remains partial across the environment transition',
        'accepted and implemented unscheduled',
        'accepted; configured-inactive production gate passed',
        'accepted as the item-42 production candidate',
        'future work may proceed to production-normalizer integration design',
        'authority for strict execution order and must contain exactly one `next` item',
        'deterministic enrichment exists but has no discovered automatic invocation',
        'ollama is active with six complete models but has no discovered application-specific observability-pipeline caller',
        'the collector result-return boundary exists but has no discovered gx10 producer',
    ),
    'docs/CURRENT_STATE.md': (
        'clean-machine end-to-end execution remains a later collector validation gate',
    ),
    'components/gx10/REBUILD_STATUS.md': (
        'remaining local-producer stability gate',
        'nothing is installed and no writer credential or transmission was used',
        'no credential or transmission exists; timer-only cadence evidence is next',
        '## deterministic incident candidate',
        'the version-1 candidate consumes only classification-version-4 projections',
        'ollama/model infrastructure is present without an identified observability-pipeline caller',
        'the collector result-return boundary is present without an identified gx10 producer',
    ),
    'components/collector/README.md': (
        'queue placement uses `entity_type = interface`',
        'current active rebuild-capture milestone',
        'original seven plus enhanced eight ai dashboard queries',
        'project-wide two-server documentation and acceptance reconciliation follows',
    ),
    'docs/NORMALIZER_MIGRATION.md': (
        'current_state.md` now advances to the managed projection',
    ),
    'docs/RESULT_OUTBOX.md': (
        'the new timer is disabled',
        'the guarded upgrader now waits',
    ),
    'docs/TWO_SERVER_REBUILD.md': (
        'current reconstructed gx10 does not install or use',
        'current gx10 rebuild has no discovered result producer',
        'confirmation that no gx10 result producer',
        'public tree currently lacks that retained two-host evidence package',
        'one activation-blocking retained-tooling gap remains explicit',
        'until the first-live verifier exists and passes',
    ),
    'components/gx10/CLEAN_MACHINE_RUNBOOK.md': (
        'it remains a separate future implementation decision',
        'repository currently lacks the retained two-host qualification package',
        'until the minimal evidence-capture/verifier contract',
    ),
    'docs/REASONING_PACKETS.md': (
        'the packet table is empty, the builder has never run',
        'remain separate later items',
    ),
    'docs/PUBLICATION_CHECKLIST.md': (
        'contains exactly one item marked `next`',
    ),
    'components/collector/normalizer/README.md': (
        'promotion of gx10 to normalized output is a separate later gate',
    ),
    'components/collector/REBUILD_STATUS.md': (
        'not part of the clean-machine reconstruction path',
        'gx10 still needs the same complete capture/rebuild treatment',
        'four dashboards are captured',
        'the live queues now contain',
    ),
    'docs/MANAGED_CORRELATION.md': (
        'the next gate is deterministic llm wake selection',
    ),
    'components/gx10/systemd/PROVENANCE.md': (
        'item-29 implementation candidates',
    ),
    'docs/OPERATIONS.md': (
        'no current pipeline caller is claimed',
        'missing gx10 result producer or ollama caller',
        'managed reasoning and hidden triage retain pending/no-result work',
        'reasoning and hidden triage retain pending/no-result work for later retry',
    ),
    'docs/INCIDENT_ENGINE.md': ('remain later milestones',),
    'docs/ACCEPTANCE.md': (
        'complete through item 42',
        'natural timer cadence evidence remains pending',
        'production activation and 15 natural cadences remain pending',
        'next stability/retirement gate',
        'strict first-live result provenance remains an explicit retained-tooling gap',
        'without that helper, the clean rebuild must stop',
    ),
    'docs/GRAFANA.md': (
        'item 40 requests compact explore panes',
        'the exact current grafana integration task',
    ),
    'components/gx10/README.md': ('next implementation order',),
    'docs/RESULT_TRANSPORT.md': (
        '## remaining gates',
        'the candidate gate creates',
        'not reconstructable from the public tree',
        'until that retained package is implemented',
        'configured inactive with zero transport',
    ),
    'docs/ROADMAP.md': (
        'reconstruct the current collector on a clean server',
        'reconstruct the current functional gx10 on a clean server',
    ),
}
REQUIRED_CURRENT_CONTRACTS = {
    'components/collector/README.md': (
        'at least 10 exact interface-down transitions',
        'a single down or a port that remains down is intentionally hidden',
        'clickhouse syslog, ai-update, and incident-lifecycle sinks',
        'current original seven plus enhanced six ai dashboard queries',
    ),
    'docs/DATA_CONTRACTS.md': (
        'one-observation protocol candidate',
        'rather than\nresolving',
        'reasoning-v1.sql',
        'inference-v1.sql',
        'triage-v1.sql',
    ),
    'docs/REASONING_PACKETS.md': (
        'item 29 later activated packet building',
        'MANAGED_REASONING.md',
    ),
    'docs/TWO_SERVER_REBUILD.md': (
        'current functional target',
        'not a complete\nreconstruction of the current application',
        'activate normalizer shadow before gx10 correlation',
        'verifier-enumerated initialized application state',
        'result-writer private key',
        'prepare -> collector\npreflight -> one manual send -> finalize -> collector final',
        'exactly `record_count` matching rows for a lifecycle batch',
    ),
    'components/gx10/CLEAN_MACHINE_RUNBOOK.md': (
        'phase 11: current result/lifecycle extensions',
        'gx10_result_sender_configured_inactive=pass',
        'capture-first-live-evidence.py prepare',
        'collector_first_live_provenance=pass',
        'phase 12: full-system acceptance and reboot recovery',
    ),
    'components/gx10/README.md': (
        'not directly scheduled, but invoked by the active managed-reasoning owner',
        'post-rediscovery implementation artifacts',
        'ordinary incident assessment records unavailable or invalid model work as an immutable terminal no-result',
        'hidden uncovered-event triage instead retains its batch pending for bounded retry',
    ),
    'docs/DECISIONS.md': (
        'item 12n is complete',
        'accepted and active through item 30',
        'current state is recorded in `docs/current_state.md`',
        'exactly one `next` item while work remains and none after explicit completion',
        'the reconstructed result/lifecycle producers and recurring sender are active now',
    ),
    'components/gx10/systemd/PROVENANCE.md': (
        'item-29 implementation artifacts',
        'scheduled-cadence gates passed on the working system',
    ),
    'docs/OPERATIONS.md': (
        'read-only backlog role and write-only result role',
        'ordinary incident assessment records an immutable terminal no-result',
        'hidden triage instead retains its immutable batch pending for bounded retry',
    ),
    'docs/RESULT_TRANSPORT.md': (
        'gate-owned temporary file',
        'same-owner, no-overwrite publication marker',
        'the active gate maintains `.accepted-v1.sqlite3`',
        'components/gx10/install/capture-first-live-evidence.py prepare',
        'components/collector/sbin/verify-first-live-provenance.py',
        'a lifecycle batch requires exactly its\n`record_count` rows',
    ),
    'docs/RESULT_OUTBOX.md': (
        'selective rollback-journal snapshot',
        'nonempty bounded `device`',
    ),
    'docs/ARCHITECTURE.md': (
        'uncovered-event selector',
        'only no incident evidence',
        'projection --> uncovered',
        'exclude existing incident evidence',
        'deterministic wake policy<br/>and packet builder',
        'wake -->|selected assessment only| reasoning',
    ),
    'components/collector/REBUILD_STATUS.md': (
        'all six current dashboards are captured',
        'clickhouse incident-lifecycle sink',
        '`observability.incident_updates`, including the additive default-zero recurrence column',
        'those counts are historical evidence, not a current queue inventory',
    ),
    'components/gx10/REBUILD_STATUS.md': (
        'current additive sqlite schema groups',
        'active engine version 3',
        'current managed gemma caller and hidden-triage coordinator',
        'current result/lifecycle producers and recurring sender',
        'historical base reconstruction order',
    ),
    'docs/CURRENT_STATE.md': (
        'no historical gx10 application producer',
        'the reconstructed producers/sender are active now',
        'complete rediscovered base sqlite schema',
        'ordinary incident assessment records unavailable or invalid inference as an immutable terminal no-result',
        'only hidden uncovered-event triage retains its immutable batch pending for bounded retry',
    ),
    'docs/ROADMAP.md': (
        'reconstruct the base collector',
        'reconstruct the base gx10',
        'current full-system reconstruction contract',
    ),
    'docs/NORMALIZER_HANDOFF.md': (
        'clean-host executable activation',
        'verify-runtime.sh --transport-view handoff',
        'verify-runtime.sh --transport-view raw',
    ),
    'docs/GRAFANA.md': (
        'noc reconstruction input contract',
        'exact organization and account sequence',
        'exact datasource and dashboard sequence',
        'explore, preferences, and playlist',
        'build-noc-organization-captures.py',
    ),
    'docs/ACCEPTANCE.md': (
        'executable first-live provenance helpers',
        'remaining acceptance risk is empirical clean-host execution, not missing first-live tooling',
    ),
}


def slug(value: str) -> str:
    value = INLINE_LINK_RE.sub(r'\1', value)
    value = re.sub(r'[`*_~]', '', value).lower()
    value = re.sub(r'[^a-z0-9\s-]', '', value)
    return re.sub(r'-+', '-', re.sub(r'\s+', '-', value)).strip('-')


def anchors(path: Path) -> set[str]:
    text = path.read_text(encoding='utf-8')
    result: set[str] = set()
    for match in HEADING_RE.finditer(text):
        result.add(slug(match.group(1)))
    return result


def resolve_link(source: Path, raw_target: str) -> tuple[Path, str]:
    target = unquote(raw_target.strip())
    location, _, anchor = target.partition('#')
    if not location:
        return source, anchor
    resolved = (source.parent / location).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(
            f'{source.relative_to(ROOT)}: link escapes repository: {raw_target}'
        ) from exc
    return resolved, anchor


def validate_links() -> None:
    for source in ROOT.rglob('*.md'):
        text = source.read_text(encoding='utf-8')
        for match in MARKDOWN_LINK_RE.finditer(text):
            raw_target = match.group(1).strip()
            if raw_target.startswith(('http://', 'https://', 'mailto:')):
                continue
            target, anchor = resolve_link(source, raw_target)
            if not target.exists():
                raise ValueError(
                    f'{source.relative_to(ROOT)}: missing local link target '
                    f'{raw_target}'
                )
            if anchor and target.suffix.lower() == '.md':
                if slug(anchor) not in anchors(target):
                    raise ValueError(
                        f'{source.relative_to(ROOT)}: missing anchor '
                        f'{raw_target}'
                    )


def local_markdown_links(source: Path) -> tuple[Path, ...]:
    """Return in-repository Markdown targets linked by one document."""
    result: list[Path] = []
    text = source.read_text(encoding='utf-8')
    for match in MARKDOWN_LINK_RE.finditer(text):
        raw_target = match.group(1).strip()
        if raw_target.startswith(('http://', 'https://', 'mailto:')):
            continue
        target, _ = resolve_link(source, raw_target)
        if target.suffix.lower() == '.md' and target.is_file():
            result.append(target)
    return tuple(result)


def repository_markdown_files() -> tuple[Path, ...]:
    """Return every tracked or non-ignored Markdown file in the repository.

    Git inventory is authoritative in the real checkout. A filesystem fallback
    keeps focused validator tests useful in their temporary, non-Git trees.
    """
    result = subprocess.run(
        [
            'git',
            'ls-files',
            '--cached',
            '--others',
            '--exclude-standard',
            '-z',
        ],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        return tuple(sorted(
            ROOT / raw.decode('utf-8')
            for raw in result.stdout.split(b'\0')
            if raw and raw.decode('utf-8').lower().endswith('.md')
        ))
    return tuple(sorted(
        path for path in ROOT.rglob('*')
        if path.is_file() and path.suffix.lower() == '.md'
    ))


def validate_documentation_reachability() -> None:
    """Ensure the entry README can navigate to every maintained Markdown page."""
    entry = ROOT / 'README.md'
    expected = set(repository_markdown_files())
    reachable: set[Path] = set()
    pending = [entry]
    while pending:
        source = pending.pop()
        if source in reachable:
            continue
        reachable.add(source)
        pending.extend(
            target for target in local_markdown_links(source)
            if target not in reachable
        )
    missing = sorted(
        path.relative_to(ROOT).as_posix() for path in expected - reachable
    )
    if missing:
        raise ValueError(
            'README.md: unreachable maintained Markdown documents: '
            + ', '.join(missing)
        )


def validate_markdown_shape(files: tuple[Path, ...] | None = None) -> None:
    for path in files or repository_markdown_files():
        text = path.read_text(encoding='utf-8')
        if len(re.findall(r'(?m)^#\s+\S', text)) != 1:
            raise ValueError(
                f'{path.relative_to(ROOT)}: expected exactly one level-1 title'
            )
        open_fence = None
        for line in text.splitlines():
            stripped = line.lstrip()
            marker = stripped[:3]
            if marker not in ('```', '~~~'):
                continue
            if open_fence is None:
                open_fence = marker
            elif marker == open_fence:
                open_fence = None
        if open_fence is not None:
            raise ValueError(
                f'{path.relative_to(ROOT)}: unbalanced Markdown code fence'
            )


def validate_reference_index() -> None:
    guide_text = GUIDE.read_text(encoding='utf-8')
    for path in sorted(DOCS_DIR.glob('*.md')):
        if path == GUIDE:
            continue
        if f']({path.name})' not in guide_text:
            raise ValueError(
                f'docs/DOCUMENTATION_GUIDE.md: unindexed document {path.name}'
            )


def validate_entry_contract() -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            raise ValueError(f'missing required document: {relative}')
    for relative, expected in ENTRY_REFERENCES.items():
        text = (ROOT / relative).read_text(encoding='utf-8')
        for target in expected:
            if target not in text:
                raise ValueError(
                    f'{relative}: missing required entry reference {target}'
                )
    for relative, stale_values in STALE_SUMMARIES.items():
        text = (ROOT / relative).read_text(encoding='utf-8').casefold()
        for value in stale_values:
            if value.casefold() in text:
                raise ValueError(f'{relative}: stale current-summary wording')


def validate_current_contracts() -> None:
    for relative, required_values in REQUIRED_CURRENT_CONTRACTS.items():
        text = (ROOT / relative).read_text(encoding='utf-8').casefold()
        for value in required_values:
            if value.casefold() not in text:
                raise ValueError(f'{relative}: missing current contract wording')


def main() -> int:
    try:
        validate_entry_contract()
        validate_current_contracts()
        validate_links()
        validate_markdown_shape()
        validate_reference_index()
        validate_documentation_reachability()
        print('DOCUMENTATION_ENTRY_PATH=PASS')
        print('DOCUMENTATION_LINKS_AND_ANCHORS=PASS')
        print('DOCUMENTATION_SHAPE_AND_INDEX=PASS')
        print('DOCUMENTATION_REACHABILITY=PASS')
        print('DOCUMENTATION_VALIDATION=PASS')
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
