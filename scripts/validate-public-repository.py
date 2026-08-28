#!/usr/bin/env python3
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CURRENT_STATE = ROOT / 'docs' / 'CURRENT_STATE.md'
NEXT_RE = re.compile(r'(?m)^\d+\. `NEXT`')
IPV4_RE = re.compile(
    r'(?<![0-9])'
    r'(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})'
    r'(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}'
    r'(?![0-9])'
)
HISTORY_IPV4_PATTERN = r'([0-9]{1,3}\.){3}[0-9]{1,3}'
IPV6_CANDIDATE_RE = re.compile(
    r'(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,7}'
    r'[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f:])'
)
HISTORY_IPV6_PATTERN = (
    r'([0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{0,4}'
    r'|::[0-9A-Fa-f]{1,4}(:[0-9A-Fa-f]{0,4}){0,6}'
)
MARKDOWN_LINK_RE = re.compile(r'\[[^\]]+\]\(([^)]+)\)')
ROLLBACK_TAG_RE = re.compile(r'^pre-[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{8}$')
ALLOWED_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        '0.0.0.0/32',
        '127.0.0.0/8',
        '192.0.2.0/24',
        '198.51.100.0/24',
        '203.0.113.0/24',
    )
)
ALLOWED_IPV6_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        '::/128',
        '::1/128',
        '2001:db8::/32',
    )
)
NON_ADDRESS_VERSION_LITERALS = {'26.3.17.110'}
LOCAL_DENYLIST_ENV = 'NETWORK_LOG_PUBLIC_DENYLIST_FILE'
GRAFANA_DASHBOARD_DIRECTORY = PurePosixPath(
    'components/collector/grafana/dashboards'
)
PORTABLE_GRAFANA_METADATA_KEYS = {'name', 'namespace'}
PRIVATE_KEY_MARKERS = (
    '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----',
    '-----BEGIN ' + 'RSA PRIVATE KEY-----',
    '-----BEGIN ' + 'EC PRIVATE KEY-----',
    '-----BEGIN ' + 'DSA PRIVATE KEY-----',
    '-----BEGIN ' + 'PRIVATE KEY-----',
)
PRIVATE_PATH_MARKERS = ('/' + 'Users/', '/' + 'home/')
SECRET_PATTERNS = (
    re.compile(('github_' + 'pat_') + r'[A-Za-z0-9_]{20,}'),
    re.compile(r'\b' + ('gh' + '[pousr]_') + r'[A-Za-z0-9]{20,}\b'),
    re.compile(r'\bAKIA[A-Z0-9]{16}\b'),
    re.compile(r'\b' + ('sk-' + '(?:proj-)?') + r'[A-Za-z0-9_-]{20,}\b'),
    re.compile(r'\b' + ('xox' + '[baprs]-') + r'[A-Za-z0-9-]{10,}\b'),
    re.compile(r'\b' + ('AIza' + '[A-Za-z0-9_-]{20,}') + r'\b'),
)
CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r'(?i)(?:^|[^A-Za-z0-9_])'
    r'(?:pass' + 'word|passwd|passphrase|secret|api[_-]?key|access[_-]?token|'
    r'auth[_-]?token|client[_-]?secret)'
    r'[ \t]*[=:][ \t]*([^\s,;#]+)'
)
URL_USERINFO_RE = re.compile(
    r'(?i)\b(?:https?|ssh|sftp)://[^/@\s]+:[^/@\s]+@'
)
AUTHORIZATION_LITERAL_RE = re.compile(
    r'(?i)\b' + 'Authorization' +
    r'\s*:\s*(?:Basic|Bearer)\s+[A-Za-z0-9._~+/=-]{8,}'
)
JWT_RE = re.compile(
    r'\b' + 'eyJ' +
    r'[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'
)
EMAIL_RE = re.compile(
    r'(?i)\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b'
)
ALLOWED_EMAIL_DOMAINS = {'example.com', 'example.org', 'example.net'}
FORBIDDEN_BASENAMES = {
    '.env',
    '.netrc',
    '.npmrc',
    '.pypirc',
    '.public-gate-local.txt',
    'admin.txt',
    'id_dsa',
    'id_ecdsa',
    'id_ed25519',
    'id_rsa',
    'known_hosts',
    'operator-inputs.env',
    'password.txt',
    'passwd',
    'token.txt',
}
FORBIDDEN_SUFFIXES = {
    '.db',
    '.kdbx',
    '.key',
    '.p12',
    '.pem',
    '.pfx',
    '.pyc',
    '.sqlite',
    '.sqlite3',
}
FORBIDDEN_DIRECTORIES = {'credentials', 'secrets'}


def git(*arguments, check=True):
    return subprocess.run(
        ['git', *arguments],
        cwd=ROOT,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def repository_files():
    output = git(
        'ls-files',
        '--cached',
        '--others',
        '--exclude-standard',
        '-z',
    ).stdout
    return tuple(
        ROOT / value.decode('utf-8')
        for value in output.split(b'\0')
        if value
    )


def sensitive_path(path):
    pure = PurePosixPath(path)
    if pure.name.lower() in FORBIDDEN_BASENAMES:
        return True
    if pure.name.lower().startswith('.env.'):
        return True
    if pure.suffix.lower() in FORBIDDEN_SUFFIXES:
        return True
    return any(part.lower() in FORBIDDEN_DIRECTORIES for part in pure.parts)


def allowed_ipv4(value):
    if value in NON_ADDRESS_VERSION_LITERALS:
        return True
    address = ipaddress.ip_address(value)
    return any(address in network for network in ALLOWED_NETWORKS)


def ipv6_literals(text):
    """Yield syntactically valid IPv6 literals from prose or source text."""
    for match in IPV6_CANDIDATE_RE.finditer(text):
        try:
            address = ipaddress.ip_address(match.group(0))
        except ValueError:
            continue
        if isinstance(address, ipaddress.IPv6Address):
            yield address


def allowed_ipv6(address):
    return any(address in network for network in ALLOWED_IPV6_NETWORKS)


def safe_credential_assignment(value):
    raw = value.strip()
    quoted = (
        len(raw) >= 2
        and raw[0] in '"\'`'
        and raw[-1] == raw[0]
    )
    cleaned = raw[1:-1] if quoted else raw
    lowered = cleaned.lower()
    if not cleaned:
        return True
    if (
        re.fullmatch(r'\$\{?[A-Z][A-Z0-9_]*\}?', cleaned)
        or re.fullmatch(r'__[A-Z][A-Z0-9_]*__', cleaned)
        or re.fullmatch(r'<[A-Z][A-Z0-9_. -]*>', cleaned)
        or re.fullmatch(r'(?i)SECRET\[[A-Za-z0-9_.-]+\]', cleaned)
    ):
        return True
    if quoted:
        # Quoted values are data, not code indirections. Only the explicit
        # placeholders above are safe to publish.
        return False
    if cleaned.startswith(('/operator/', '/run/', '/etc/')):
        return True
    if re.fullmatch(
        r'(?:[A-Za-z_][A-Za-z0-9_]*\.)*'
        r'[A-Za-z_][A-Za-z0-9_]*\([^\r\n]*',
        cleaned,
    ):
        return True
    if re.fullmatch(
        r'(?:args|config|settings|secrets)\.'
        r'[A-Za-z_][A-Za-z0-9_]*',
        cleaned,
    ):
        return True
    if re.fullmatch(
        r'os\.environ\[["\'][A-Z][A-Z0-9_]*["\']\]',
        cleaned,
    ):
        return True
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', cleaned):
        return lowered in {
            'bytes',
            'password',
            'passwd',
            'passphrase',
            'secret',
            'str',
            'token',
        }
    return False


def validate_grafana_dashboard_capture(path, text, label):
    try:
        relative = PurePosixPath(path.relative_to(ROOT).as_posix())
    except (TypeError, ValueError):
        return
    if relative.parent != GRAFANA_DASHBOARD_DIRECTORY or path.suffix != '.json':
        return
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f'{label}: malformed dashboard capture') from exc
    if document.get('apiVersion') != 'dashboard.grafana.app/v2':
        raise ValueError(f'{label}: unexpected dashboard apiVersion')
    if document.get('kind') != 'Dashboard':
        raise ValueError(f'{label}: unexpected dashboard kind')
    metadata = document.get('metadata')
    if not isinstance(metadata, dict) or not metadata.get('name'):
        raise ValueError(f'{label}: dashboard metadata.name missing')
    if set(metadata) != PORTABLE_GRAFANA_METADATA_KEYS:
        raise ValueError(f'{label}: dashboard contains server-owned metadata')
    if not metadata.get('namespace'):
        raise ValueError(f'{label}: dashboard metadata.namespace missing')
    if document.get('status') != {}:
        raise ValueError(f'{label}: dashboard contains server-owned status')
    if 'spec' not in document:
        raise ValueError(f'{label}: dashboard spec missing')


def load_local_denylist():
    configured = os.environ.get(LOCAL_DENYLIST_ENV)
    if not configured:
        return ()
    path = Path(configured)
    if path.is_symlink() or not path.is_file():
        raise ValueError('local denylist must be a regular non-symlink file')
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError('local denylist must be outside the repository')
    if resolved.stat().st_mode & 0o077:
        raise ValueError('local denylist must not be group/world accessible')
    terms = []
    for raw_line in resolved.read_text(encoding='utf-8', errors='strict').splitlines():
        term = raw_line.strip()
        if not term or term.startswith('#'):
            continue
        if len(term) < 3 or any(character in '\0\r\n' for character in term):
            raise ValueError('local denylist contains an invalid term')
        terms.append(term.casefold())
    if not terms:
        raise ValueError('local denylist contains no terms')
    return tuple(dict.fromkeys(terms))


def validate_local_denylist_text(text, label, terms):
    folded = text.casefold()
    if any(term in folded for term in terms):
        # Never place the private term itself in output or an exception.
        raise ValueError(f'{label}: environment-specific publication finding')


def validate_extended_sensitive_text(text, label):
    if URL_USERINFO_RE.search(text):
        raise ValueError(f'{label}: URL contains embedded credentials')
    if AUTHORIZATION_LITERAL_RE.search(text):
        raise ValueError(f'{label}: literal authorization credential')
    if JWT_RE.search(text):
        raise ValueError(f'{label}: JWT-like credential')
    for match in EMAIL_RE.finditer(text):
        if match.group(1).lower() not in ALLOWED_EMAIL_DOMAINS:
            raise ValueError(f'{label}: non-documentation email identity')
    for match in CREDENTIAL_ASSIGNMENT_RE.finditer(text):
        if not safe_credential_assignment(match.group(1)):
            raise ValueError(f'{label}: literal credential assignment')


def validate_text(path, text, label):
    if any(marker in text for marker in PRIVATE_PATH_MARKERS):
        raise ValueError(f'{label}: private workstation path')
    if any(marker in text for marker in PRIVATE_KEY_MARKERS):
        raise ValueError(f'{label}: private key material')
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise ValueError(f'{label}: token/access-key pattern')
    validate_extended_sensitive_text(text, label)
    for match in IPV4_RE.finditer(text):
        if not allowed_ipv4(match.group(0)):
            raise ValueError(f'{label}: non-public IPv4 literal')
    for address in ipv6_literals(text):
        if not allowed_ipv6(address):
            raise ValueError(f'{label}: non-public IPv6 literal')
    validate_grafana_dashboard_capture(path, text, label)


def validate_current_tree(files, local_terms=()):
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'{relative}: non-regular repository artifact')
        if sensitive_path(relative):
            raise ValueError(f'{relative}: generated/private artifact path')
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError(f'{relative}: unexpected binary artifact') from exc
        validate_text(path, text, relative)
        validate_local_denylist_text(text, relative, local_terms)


def validate_markdown_links(files):
    for path in files:
        if path.suffix.lower() != '.md':
            continue
        text = path.read_text(encoding='utf-8')
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group(1).strip()
            if target.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            target = target.split('#', 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError as exc:
                raise ValueError(f'{path.relative_to(ROOT)}: link escapes repository') from exc
            if not resolved.exists():
                raise ValueError(
                    f'{path.relative_to(ROOT)}: missing local link target {target}'
                )


def validate_execution_authority():
    text = CURRENT_STATE.read_text(encoding='utf-8')
    next_count = len(NEXT_RE.findall(text))
    completed = (
        'End-to-end working-system target: `COMPLETE`' in text
        and 'There is no remaining `NEXT` item.' in text
    )
    if (completed and next_count != 0) or (not completed and next_count != 1):
        raise ValueError(
            'docs/CURRENT_STATE.md must contain exactly one numbered NEXT while '
            'work remains, or explicit end-to-end COMPLETE state with none'
        )


def history_paths():
    result = git('log', '--all', '--name-only', '--format=', '-z').stdout
    return {
        value.decode('utf-8')
        for value in result.split(b'\0')
        if value
    }


def validate_history_paths():
    for path in history_paths():
        if sensitive_path(path):
            raise ValueError(f'history contains sensitive artifact path: {path}')


def history_grep(pattern):
    problems = []
    commits = git('rev-list', '--all').stdout.decode('ascii').splitlines()
    for commit in commits:
        result = git(
            'grep',
            '-I',
            '-n',
            '-E',
            pattern,
            commit,
            '--',
            check=False,
        )
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(result.returncode, result.args)
        if result.returncode == 0:
            for raw in result.stdout.decode('utf-8', errors='strict').splitlines():
                _, path, _, line = raw.split(':', 3)
                problems.append((commit, path, line))
    return problems


def validate_history_local_denylist(terms):
    if not terms:
        return
    commits = git('rev-list', '--all').stdout.decode('ascii').splitlines()
    patterns = ('\n'.join(terms) + '\n').encode('utf-8')
    for commit in commits:
        result = subprocess.run(
            [
                'git',
                'grep',
                '-I',
                '-l',
                '-i',
                '-F',
                '-f',
                '-',
                commit,
                '--',
            ],
            cwd=ROOT,
            check=False,
            input=patterns,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(result.returncode, result.args)
        if result.returncode == 0:
            raw = result.stdout.decode('utf-8', errors='strict').splitlines()[0]
            path = raw.split(':', 1)[-1]
            raise ValueError(
                'history environment-specific publication finding: '
                f'{commit[:12]}:{path}'
            )


def validate_history_content():
    secret_pattern = '|'.join(
        (
            'github_' + 'pat_[A-Za-z0-9_]{20,}',
            '\\b' + ('gh' + '[pousr]_') + '[A-Za-z0-9]{20,}\\b',
            'AKIA[A-Z0-9]{16}',
            '\\b' + ('sk-' + '(proj-)?') + '[A-Za-z0-9_-]{20,}\\b',
            '\\b' + ('xox' + '[baprs]-') + '[A-Za-z0-9-]{10,}\\b',
            '\\b' + ('AIza' + '[A-Za-z0-9_-]{20,}') + '\\b',
            '-----BEGIN (OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----',
            '/' + 'Users/',
            '/' + 'home/',
        )
    )
    secret_findings = history_grep(secret_pattern)
    if secret_findings:
        commit, path, _ = secret_findings[0]
        raise ValueError(f'history secret/path finding: {commit[:12]}:{path}')

    extended_pattern = '|'.join(
        (
            '(https?|ssh|sftp)://[^/@[:space:]]+:[^/@[:space:]]+@',
            'Authorization[[:space:]]*:[[:space:]]*(Basic|Bearer)'
            '[[:space:]]+[A-Za-z0-9._~+/=-]{8,}',
            r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
            r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
            '(^|[^A-Za-z0-9_])('
            + 'pass' + 'word|passwd|passphrase|secret|api[_-]?key|'
            'access[_-]?token|auth[_-]?token|client[_-]?secret)'
            '[[:space:]]*[=:][[:space:]]*[^[:space:],;#]+',
        )
    )
    for commit, path, line in history_grep(extended_pattern):
        try:
            validate_extended_sensitive_text(line, f'{commit[:12]}:{path}')
        except ValueError as exc:
            raise ValueError(f'history sensitive-content finding: {exc}') from exc

    ipv4_findings = history_grep(HISTORY_IPV4_PATTERN)
    for commit, path, line in ipv4_findings:
        for match in IPV4_RE.finditer(line):
            if not allowed_ipv4(match.group(0)):
                raise ValueError(f'history IPv4 finding: {commit[:12]}:{path}')

    ipv6_findings = history_grep(HISTORY_IPV6_PATTERN)
    for commit, path, line in ipv6_findings:
        for address in ipv6_literals(line):
            if not allowed_ipv6(address):
                raise ValueError(f'history IPv6 finding: {commit[:12]}:{path}')


def validate_ref_topology():
    local_heads = git(
        'for-each-ref',
        '--format=%(refname)',
        'refs/heads',
    ).stdout.decode('utf-8').splitlines()
    if local_heads != ['refs/heads/main']:
        raise ValueError('unexpected local branch topology')
    tags = git('tag', '--list').stdout.decode('utf-8').splitlines()
    for tag in tags:
        if not ROLLBACK_TAG_RE.fullmatch(tag):
            raise ValueError(f'unexpected public tag topology: {tag}')
        object_type = git(
            'cat-file',
            '-t',
            f'refs/tags/{tag}',
        ).stdout.decode('utf-8').strip()
        if object_type != 'tag':
            raise ValueError(f'rollback tag must be annotated: {tag}')


def main():
    try:
        files = repository_files()
        local_terms = load_local_denylist()
        if not files:
            raise ValueError('repository inventory is empty')
        validate_current_tree(files, local_terms)
        validate_markdown_links(files)
        validate_execution_authority()
        validate_history_paths()
        validate_history_content()
        validate_history_local_denylist(local_terms)
        validate_ref_topology()
        print('PUBLIC_REPOSITORY_CURRENT_TREE=PASS')
        print('PUBLIC_REPOSITORY_HISTORY=PASS')
        print('PUBLIC_REPOSITORY_LINKS=PASS')
        print('PUBLIC_REPOSITORY_REF_TOPOLOGY=PASS')
        print(
            'PUBLIC_REPOSITORY_LOCAL_DENYLIST='
            + ('PASS' if local_terms else 'NOT_CONFIGURED')
        )
        print('PUBLIC_REPOSITORY_VALIDATION=PASS')
        return 0
    except (
        OSError,
        UnicodeError,
        subprocess.CalledProcessError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
