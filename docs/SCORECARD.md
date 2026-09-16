# OpenSSF Scorecard — where the 10 comes from

Target: 10/10. Run it: `.github/workflows/scorecard.yml` (weekly + every
push to main). Badge: `https://api.scorecard.dev/projects/github.com/robinaider/unflake/badge`.

## Earned in code (this repo)

| Check | Evidence |
|---|---|
| Dangerous-Workflow | no `${{ }}` interpolation in any `run:` block (inputs pass via `env:`) |
| Pinned-Dependencies | every third-party Action pinned to a full SHA; `pytest==8.3.5`, `build==1.2.2` |
| Token-Permissions | `permissions:` minimal on every workflow/job |
| License | `LICENSE` (MIT) |
| Security-Policy | `SECURITY.md` |
| Dependency-Update-Tool | `.github/dependabot.yml` (actions, pip, npm — weekly) |
| SAST | `.github/workflows/codeql.yml` (Python + JavaScript) |
| Signed-Releases | `release.yml`: Sigstore attestation on every `v*` tag build |
| Packaging | `release.yml`: PyPI OIDC trusted publishing, npm `--provenance` |
| Binary-Artifacts | none committed (vendored `npm/unflake_core/` is generated at pack, gitignored) |
| Vulnerabilities | zero runtime dependencies (stdlib core + zero-dep shim) |
| Maintained | commit/issue activity (keep the cadence) |

## Needs clicks, not code (do after creating the repo)

1. **Branch protection** (Settings → Branches → Add rule for `main`):
   require PR before merging, require 1 approval, require status checks
   (`ci`, `codeql`), dismiss stale approvals, block force pushes + deletions.
2. **Private vulnerability reporting** (Settings → Security → enable).
3. **Tag protection** for `v*` (Settings → Tags) once releases flow.
4. **CII Best Practices badge** (bestpractices.coreinfrastructure.org) — apply
   after the first release; it's a questionnaire, not code.
5. **Code review habit** — the Code-Review check reads history; review every
   PR (even contributor ones) from day one.
6. **Contributors** — invite early contributors; shared maintenance scores.

Realistic arc: high 8s on day one (history-gated checks lag), 10 after
protection + reviews + the CII badge land. The workflow publishes every
score — the trend is the content.
