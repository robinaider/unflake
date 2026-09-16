# Releasing Unflake

1. Bump version in `pyproject.toml`, `src/unflake/__init__.py`,
   `.claude-plugin/plugin.json`, `gemini-extension.json`.
2. Add a `CHANGELOG.md` entry (honest numbers only — see `benchmarks/BENCH.md`).
3. Full verify: fresh venv → `pip install -e .` → `unittest discover` →
   `bash demo.sh` → e2e (`pip install pytest` + `unittest tests.test_e2e`).
4. Tag `vX.Y.Z`, push, create GitHub Release from the CHANGELOG entry.
5. Publish: `python -m build && twine upload dist/*` (maintainers only).
   Then npm: `cd npm && npm publish` (prepack re-vendors + pins the version;
   package name is `unflake-ci` — `unflake` was taken).
   Preferred: tag `vX.Y.Z` and let `release.yml` do it — PyPI via OIDC
   trusted publishing (one-time setup: PyPI → project → Publishing →
   add GitHub publisher for this repo + workflow), npm via `--provenance`
   (needs `NPM_TOKEN` secret; enable 2FA on the npm account first).
6. Post-release: confirm `pip install unflake==X.Y.Z` works from a clean machine
   and the pre-commit hook `rev:` still resolves.
