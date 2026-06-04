# Copilot CLI hook adapters

This directory contains GitHub Copilot CLI hook configuration for Amp.

## Files

- `hooks.json`: Copilot CLI hook configuration.
- `copilot-session-start.sh`: Normalizes session-start input and calls `.claude/hooks/session-start.sh` when present.
- `copilot-session-end.sh`: Normalizes session-end input and calls `.claude/hooks/session-end.sh` when present.
- `copilot-safety-guard.sh`: Converts Copilot CLI pre-tool input to the Claude Code-style payload expected by `.claude/hooks/amp-safety-guard.sh`.
- `copilot-context-injector.cjs`: Converts file-read hook input and calls context injectors in `.claude/hooks/` when present.

## Why adapters exist

Claude Code and Copilot CLI use different hook configuration paths and payload shapes. Amp's original hook implementations live in `.claude/hooks/`. These adapters keep that implementation reusable without forcing a hard migration.

The adapters accept multiple Copilot CLI payload naming conventions, including `toolName`/`toolArgs`, `tool_name`/`tool_args`, and `tool`/`args`. They also set `CLAUDE_PROJECT_DIR` for legacy hooks that expect it.

## Coexistence with Claude Code hooks

Keep `.claude/hooks/` and `.github/hooks/` side by side. `.claude/hooks/` remains the Claude Code implementation, while `.github/hooks/` is the Copilot CLI compatibility layer. Remove or replace legacy hooks only after documenting the migration and validating both runtimes.

## Validation

Run these checks after editing adapters:

```bash
bash -n .github/hooks/copilot-session-start.sh
bash -n .github/hooks/copilot-session-end.sh
bash -n .github/hooks/copilot-safety-guard.sh
node --check .github/hooks/copilot-context-injector.cjs
```
