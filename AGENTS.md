# Amp agent instructions

This file gives framework-neutral guidance for agents that read `AGENTS.md`, including GitHub Copilot CLI. The canonical Amp behavior remains in `CLAUDE.md`; agent frameworks should treat references to "Claude" in existing docs as references to the active assistant unless a section is explicitly Claude Code-only.

## General agent behavior

- Follow `CLAUDE.md` and the user profile/configuration generated during onboarding.
- Keep user-specific preferences in the protected user extensions block, not in shared framework docs.
- Do not assume a specific agent runtime. Prefer portable shell, Node.js, Python, and MCP workflows documented in this repository.
- Before editing generated vault content, check the relevant templates and docs under `System/`, `06-Resources/`, and `.claude/skills/`.

## GitHub Copilot CLI notes

- **Hooks:** Copilot CLI hook adapters live in `.github/hooks/` and are configured by `.github/hooks/hooks.json`. They translate Copilot CLI hook payloads to the Claude Code-style payloads expected by existing `.claude/hooks/` scripts.
- **Claude Code hooks:** Legacy Claude Code hooks remain in `.claude/hooks/`. Keep both systems unless a migration is explicit and tested.
- **Project root:** Copilot CLI may not set `CLAUDE_PROJECT_DIR`. Adapter scripts derive the project root from hook input or `process.cwd()` and export `CLAUDE_PROJECT_DIR` before calling legacy hooks.
- **Skills:** Amp skills live in `.claude/skills/`. Copilot CLI can use those instructions directly when a matching workflow is requested.
- **MCP servers:** Configure MCP servers through Copilot CLI MCP configuration or from the repository's `.mcp.json.template` during onboarding. Do not commit local `.mcp.json` files or secrets.
- **Model selection:** Use the runtime's model selection command or UI. Keep model-specific assumptions out of shared docs unless they are optional guidance.
- **GitHub integration:** Prefer the GitHub tools available in the active runtime for issues, pull requests, code search, and reviews. Use `gh` non-interactively when working in a terminal.

See `docs/copilot-cli.md` and `.github/hooks/README.md` for adapter details.
