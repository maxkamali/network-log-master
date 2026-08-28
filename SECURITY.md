# Security and Public-Repository Policy

This repository is public. Publication safety is a release gate, not a cleanup task.

## Never commit

- passwords, API tokens, access tokens, credentials, or secret material
- SSH private keys or private certificates
- production addresses, firewall allowlists, or private routing details
- customer-identifying logs or unredacted production payloads
- private operational paths that expose access methods
- local secret files or environment-specific credentials
- restricted historical branding or organization identifiers

## Public fixtures

Use synthetic names and documentation-only address ranges:

```text
192.0.2.0/24
198.51.100.0/24
203.0.113.0/24
2001:db8::/32
```

IPv6 unspecified/loopback literals (`::` and `::1`) are acceptable only where
they describe local listener behavior. All other IPv6 examples must use the
documentation prefix above. The same IPv4/IPv6 policy is enforced in the
current tree and reachable history.

Examples should preserve message structure while removing production identity.

## Publication workflow

Before any public commit or push:

1. stage only intended files
2. run repository sanitation/secret scanning
3. scan for banned terms and environment identifiers
4. run syntax/lint checks applicable to the changed files
5. run the full relevant test suite
6. inspect the staged diff
7. commit only after all gates pass

Run the repository-wide current-tree/history/link/ref gate from repository root:

    scripts/validate-public-repository.py

The gate rejects sensitive filenames and directories, private keys, common
provider-token formats, literal credential assignments, embedded URL
credentials, literal Basic/Bearer authorization values, JWT-like values,
non-documentation email identities, private workstation paths, and every IPv4
literal outside loopback/unspecified or the RFC documentation ranges. The
current-tree gate also parses every native Grafana dashboard capture and rejects
server/account-owned metadata or nonempty resource status. These checks apply
to both the current tree and all reachable Git history where the corresponding
history scanner is supported. Runtime credential
references and operator-supplied placeholders are allowed; literal values are
not.

The credential-assignment check treats quoted, dotted, underscored, and short
values as data rather than automatically trusting their shape. Only explicit
placeholders, private file paths, function calls, or narrowly recognized code
indirections are allowed.

Generic patterns cannot know every private hostname, account label, device name,
or historical environment identifier. For any change derived from a live
environment, create a private mode-`0600` one-term-per-line file outside the
checkout, then run:

```text
NETWORK_LOG_PUBLIC_DENYLIST_FILE=/operator/private/publication-denylist.txt \
  scripts/validate-public-repository.py
```

Blank lines and `#` comments are ignored. Terms are matched case-insensitively
against the current tree and with fixed-string matching across reachable
history. The validator reports only the file/commit location, never the private
matched term. A missing optional file is reported as `NOT_CONFIGURED`; when a
live-environment change is being published, that status is not sufficient
evidence.

## Portable Grafana captures

Native dashboard resources in Git contain only `metadata.name`,
`metadata.namespace`, dashboard `spec`, and an empty required `status` object.
Grafana-returned UIDs, generations, timestamps, resource versions, account
annotations, internal labels, and live status are server-owned and must be
removed before publication. Restore tooling independently strips them, and the
repository validator rejects their recurrence.

Existing public Git history is not rewritten solely to remove non-secret legacy
server metadata. Treat historical captures as audit evidence, not rebuild input;
only the sanitized current captures are authoritative. A history rewrite would
be a separate destructive incident-response decision.

## Indirect identifiers and Git metadata

Do not publish environment-derived screenshots, raw API responses, payload
samples, filenames, exact object inventories, or hashes merely because they are
not passwords. Hash only a documented portable projection, such as a canonical
dashboard `spec`, and review whether equality itself reveals a private system.
Never use a hash as a substitute for sanitation.

Public commits expose author/committer identity. Use an intentionally public Git
identity (for example, a hosting-provider no-reply address) and review both the
current commit and all refs before push. This does not authorize publishing an
operator workstation identity, production account label, or private endpoint.

Its synthetic tests are:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'

Do not weaken a deny list merely to make a gate pass. Fix the content instead.

## Operational separation

Production secrets remain external to Git. The collector and GX10 use independent least-privilege credentials for input and output paths. Public documentation describes the trust model without publishing live secrets or allowlists.

Public Git hosting necessarily exposes repository-owner and contributor commit
metadata. That public Git identity is distinct from prohibited production host,
device, customer, account, network, and credential identity.

## Security reports

Do not open a public issue containing a secret or live operational detail. Remove or rotate exposed credentials immediately before documenting the incident safely.
