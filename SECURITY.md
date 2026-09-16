# Security policy

Unflake is a static scanner + test scorer. It **reads** your tests and **runs**
only the commands you explicitly give `unflake run`. It never exfiltrates:
all analysis is local, the core is stdlib-only (no supply chain to poison).

## Reporting a vulnerability

Open a GitHub issue titled `[security] …` (or email the maintainer address
listed on the repo). Please include a minimal repro. We aim to acknowledge
within 72 hours and will credit reporters in `CHANGELOG.md` unless you ask
otherwise.

## Scope notes

- `unflake scan` never executes scanned code.
- `unflake run` executes exactly the command you pass after `--` — review
  quarantine snippets before committing, as the CLI itself reminds you.
