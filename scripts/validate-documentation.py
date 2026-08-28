#!/usr/bin/env python3
"""Validate the repository's human and agent documentation entry path."""
from __future__ import annotations

import re
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
}
STALE_SUMMARIES = {
    'README.md': ('complete through project item 42',),
    'docs/START_HERE.md': ('complete through item 42',),
    'docs/AI_HANDOFF.md': ('complete through execution-order item 41',),
    'docs/ACCEPTANCE.md': (
        'complete through item 42',
        'natural timer cadence evidence remains pending',
        'production activation and 15 natural cadences remain pending',
    ),
    'docs/DECISIONS.md': ('compatibility correction pending',),
    'components/gx10/REBUILD_STATUS.md': (
        'remaining local-producer stability gate',
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


def repository_markdown_files() -> tuple[Path, ...]:
    files = [ROOT / 'README.md']
    for directory in (DOCS_DIR, ROOT / 'components'):
        files.extend(
            path for path in directory.rglob('*.md')
            if not any(part.startswith('.') for part in path.relative_to(ROOT).parts)
        )
    return tuple(sorted(set(files)))


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


def main() -> int:
    try:
        validate_entry_contract()
        validate_links()
        validate_markdown_shape()
        validate_reference_index()
        print('DOCUMENTATION_ENTRY_PATH=PASS')
        print('DOCUMENTATION_LINKS_AND_ANCHORS=PASS')
        print('DOCUMENTATION_SHAPE_AND_INDEX=PASS')
        print('DOCUMENTATION_VALIDATION=PASS')
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
