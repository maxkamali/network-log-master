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

Its synthetic tests are:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'

Do not weaken a deny list merely to make a gate pass. Fix the content instead.

## Operational separation

Production secrets remain external to Git. The collector and GX10 use independent least-privilege credentials for input and output paths. Public documentation describes the trust model without publishing live secrets or allowlists.

## Security reports

Do not open a public issue containing a secret or live operational detail. Remove or rotate exposed credentials immediately before documenting the incident safely.
