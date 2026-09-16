# Unflake adapters — one repo, every harness

The skill source of truth is `skills/unflake/SKILL.md`. Everything else is a thin adapter.

| Host | Install |
|---|---|
| Claude Code | copy `skills/unflake/` to `~/.claude/skills/unflake/` (plugin manifest in `.claude-plugin/plugin.json`) |
| Any agent (fallback) | `AGENTS.md` is auto-loaded from the repo root |
| Gemini / Antigravity | `gemini-extension.json` (`gemini extensions install <repo-url>`) |
| Cursor | `.cursor/rules/unflake.md` auto-loads |
| Copilot (IDE + CLI) | `.github/copilot-instructions.md` auto-loads |
| Codex / Pi / OpenCode / Windsurf / Cline / Qoder | read `AGENTS.md` from checkout root — zero setup |
| CI (any) | `python3 -m unflake scan …` + `--format sarif` → upload to code scanning |

Adding a new harness adapter is a perfect first PR: copy the pattern, add a row here. See `CONTRIBUTING.md`.
