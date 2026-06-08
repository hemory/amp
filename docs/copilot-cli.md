# GitHub Copilot CLI support

Amp can run in GitHub Copilot CLI alongside Claude Code. The two runtimes expose similar agent workflows, but their lifecycle hooks and environment details are different.

## Runtime differences

| Area | Claude Code | GitHub Copilot CLI |
| --- | --- | --- |
| Hook configuration | `.claude/settings.json` or user Claude settings | `.github/hooks/hooks.json` |
| Hook scripts | `.claude/hooks/` | `.github/hooks/` adapters that call `.claude/hooks/` when available |
| Hook input | Claude Code-style JSON on stdin | Copilot CLI-style JSON on stdin |
| Project root | Usually available as `CLAUDE_PROJECT_DIR` | May be absent; adapters derive it from hook input or current directory |
| Skills | `.claude/skills/` | Reads the same skill instructions when invoked by the runtime |
| MCP config | Claude Code MCP settings or local `.mcp.json` | User-level Copilot MCP config for Amp tools; workspace `.mcp.json` stays empty by default |
| Model selection | Claude Code runtime controls | Copilot CLI runtime controls |
| GitHub operations | Shell, MCP, or runtime tools | Native GitHub integration and `gh` CLI are available |

## Hook coexistence

Amp keeps Claude Code hooks in `.claude/hooks/` and Copilot CLI adapters in `.github/hooks/`. Do not delete the Claude Code hooks just because Copilot CLI adapters exist. The adapter layer allows both runtimes to share the same core safety and context logic while preserving each runtime's expected hook payload format.

The current adapter flow is:

1. Copilot CLI fires a hook configured in `.github/hooks/hooks.json`.
2. The adapter reads Copilot CLI JSON from stdin.
3. The adapter normalizes field names such as `toolName`, `tool_name`, `toolArgs`, `tool_args`, and `args`.
4. The adapter exports `CLAUDE_PROJECT_DIR` when needed.
5. The adapter calls the matching legacy hook in `.claude/hooks/` if that hook exists.

If a future Copilot CLI-native hook replaces a legacy hook completely, keep the old hook until the migration path is documented and both runtimes have been tested.

## MCP configuration

Do not commit local MCP runtime files that contain machine paths or credentials. Amp keeps workspace `.mcp.json` empty by default for Copilot CLI so opening the repository does not auto-start every local Python MCP server.

For Copilot CLI, configure Amp MCP tools as user-level servers:

```bash
scripts/setup-copilot-mcp.sh
```

The script registers a curated set:

- `amp-work`
- `amp-improvements`
- `session-memory`

Each server uses the repository virtualenv and sets `VAULT_PATH` plus `PYTHONPATH` explicitly. Add heavier integrations, such as calendar or resume workflows, only when needed and test them one at a time.

For first-time onboarding in Copilot CLI, temporarily add the onboarding MCP:

```bash
scripts/setup-copilot-mcp.sh --with-onboarding
```

After `/setup` completes, remove the setup-only server:

```bash
scripts/setup-copilot-mcp.sh --remove-onboarding
```

Claude Code users should use Claude's MCP configuration flow, but the same principle applies: prefer the repository virtualenv, add only the MCP servers you need, and avoid broad auto-start defaults.

## Validation

After changing Copilot CLI hook support, run syntax checks for every changed shell and Node.js hook. When feasible, run the repository test suite with `npm test`.
