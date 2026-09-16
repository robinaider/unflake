# Security policy

Unflake is a static scanner + test scorer. It **reads** your tests and **runs**
only the commands you explicitly give `unflake run`. It never exfiltrates:
all analysis is local, the core is stdlib-only (no supply chain to poison).

## Reporting a vulnerability

**Please do not open a public issue for security reports.** Disclose privately via
https://github.com/robinaider/unflake/security/advisories/new
so we can fix before details go public.

Please include a minimal repro and the version (`unflake --version`).
We aim to acknowledge within 72 hours and share a fix plan within 14 days,
and will credit reporters in `CHANGELOG.md` unless you ask otherwise.
We follow coordinated vulnerability disclosure: please allow up to 90 days
before public disclosure of the vulnerability.

## Supported versions

| Version | Supported |
|---|---|
| Latest PyPI release (`pip install -U unflake`) | ✅ |
| Older releases | ⚠️ best-effort — please upgrade, re-test, and re-report |

## Scope notes

- `unflake scan` never executes scanned code.
- `unflake run` executes exactly the command you pass after `--` — review
  quarantine snippets before committing, as the CLI itself reminds you.
