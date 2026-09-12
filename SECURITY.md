# Security Policy

## Reporting a vulnerability

If you find a security issue in this project, please open a
[private security advisory](../../security/advisories/new) on GitHub rather
than a public issue — that gives us a chance to fix it before it's public.

This is a portfolio/demo project, not a production service handling real
user data, but the same reporting flow you'd use for any real project
applies here.

## What's actually enforced here

This isn't just a policy document — the scanning it describes runs on every
push and pull request (`.github/workflows/security.yml` and `codeql.yml`):

| Check | Tool | Catches |
|---|---|---|
| Secrets | [gitleaks](https://github.com/gitleaks/gitleaks) | Committed credentials, tokens, keys |
| Dependency CVEs | [pip-audit](https://github.com/pypa/pip-audit) | Known vulnerabilities in pinned Python packages |
| Dependency review | GitHub `dependency-review-action` | New high-severity dependencies introduced by a PR |
| SAST | [Semgrep](https://semgrep.dev/) (`p/ci` ruleset) + [CodeQL](https://codeql.github.com/) | Insecure code patterns (injection, unsafe deserialization, etc.) |
| Dockerfile | [hadolint](https://github.com/hadolint/hadolint) | Container build anti-patterns |
| Filesystem / image CVEs | [Trivy](https://trivy.dev/) | OS package and dependency vulnerabilities, misconfigurations |
| Supply chain | [cosign](https://github.com/sigstore/cosign) (keyless) | Every published image is signed and has an attached SBOM, so provenance is verifiable |

A CRITICAL/HIGH finding from Trivy or a `pip-audit --strict` failure blocks
the pipeline — it isn't just advisory.

## Supported versions

Only the `main` branch / latest published image is supported. There is no
LTS branch for a demo project like this.
