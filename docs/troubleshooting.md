# Troubleshooting

Common issues and how to fix them.

## MCP Servers Not Loading

**Symptom:** Skills don't work, tools aren't available, "MCP" errors in output.

**Cause:** `.mcp.json` is missing, malformed, or the terminal was not restarted after creation.

**Fix:**
1. Check if `.mcp.json` exists in the repo root: `ls -la .mcp.json`
2. If missing, copy from template: `cp .mcp.json.template .mcp.json`
3. Replace `{{VAULT_PATH}}` with your actual vault path
4. Restart your terminal (MCP servers load on session start)

## Python Version Mismatch

**Symptom:** MCP servers crash with syntax errors or import failures.

**Cause:** Amp requires Python 3.10+.

**Fix:**
1. Check your version: `python3 --version`
2. If below 3.10, upgrade: `brew install python@3.12` (macOS)
3. Re-run: `pip3 install -r requirements.txt`

## Node.js Version Mismatch

**Symptom:** Install script fails, hooks don't run.

**Cause:** Amp requires Node.js 18+.

**Fix:**
1. Check your version: `node --version`
2. If below 18, upgrade: `brew install node@20` (macOS) or use nvm

## Obsidian Vault Not Opening

**Symptom:** `open obsidian://...` commands don't work.

**Cause:** Obsidian isn't installed, or the vault isn't registered.

**Fix:**
1. Install Obsidian from https://obsidian.md
2. Open Obsidian → "Open folder as vault" → select your Amp repo folder
3. The vault name should be "amp" (this is what the open commands expect)

## Calendar Integration Failing

**Symptom:** `/daily-plan` shows no calendar events, calendar tools return errors.

**Cause:** EventKit permissions not granted, or Calendar.app not running.

**Fix:**
1. Open System Settings → Privacy & Security → Calendars
2. Ensure your terminal app (Terminal, iTerm, etc.) has calendar access
3. Open Calendar.app at least once (it needs to be running for EventKit)
4. Re-run `/calendar-setup` to reconfigure

## Integration Appears Enabled but Skills Cannot Use It

**Symptom:** A skill mentions an integration, but no tools are available or the output does not include expected external context.

**Cause:** Local configuration and MCP server availability are out of sync, or the integration is disabled in one place and enabled in another.

**Fix:**
1. Check `System/integrations/config.yaml` for the integration's enabled state.
2. Check `.mcp.json` for the matching MCP server, without pasting secrets into chat or logs.
3. Restart your terminal after changing MCP configuration.
4. If the integration is intentionally disabled, use the vault-only workflow instead.

## Daily Plan Returns Empty

**Symptom:** `/daily-plan` runs but has no tasks, projects, or calendar events.

**Cause:** The system needs context before it can plan. New installations start empty.

**Fix:** Feed the system your current work:
1. Add your current tasks to `03-Tasks/Tasks.md`
2. Create project folders in `04-Projects/` for active work
3. Set up calendar integration with `/calendar-setup`
4. See `docs/first-24-hours.md` for a full walkthrough

## Session Continuity Looks Stale

**Symptom:** Amp forgets recent work, repeats old context, or starts without a useful "since last time" summary.

**Cause:** Session summaries or durable memory files are missing, placeholder-only, or not being read by the agent.

**Fix:**
1. Check `System/Session_Learnings/` for recent non-placeholder summaries.
2. Check `System/Memory/episodic-index.jsonl` if you use durable memory.
3. Make sure `CLAUDE.md` still contains the Session Continuity Protocol from `CLAUDE.md.template` after updates.
4. If the files are missing, run a daily or weekly review to generate fresh context.

## Identity Templates Not Loading

**Symptom:** Amp ignores custom voice or operating-principle guidance.

**Cause:** Identity templates were not copied to active files, or `CLAUDE.md` does not point to them.

**Fix:**
1. Copy `System/identity/amp/SOUL.md.template` to `System/identity/amp/SOUL.md` if you want active Amp principles.
2. Copy `System/identity/amp/STYLE.md.template` to `System/identity/amp/STYLE.md` if you want active Amp style rules.
3. Add user voice files under `System/identity/user/` only with user-declared guidance.
4. Restart the agent session so the files are loaded at session start.

## Hooks Not Running

**Symptom:** Session start/end hooks don't fire, person context not injected.

**Cause:** Different hook mechanisms for Claude Code vs Copilot CLI.

**Fix:**
1. **Copilot CLI:** Hooks live in `.github/hooks/hooks.json`
2. **Claude Code:** Hooks live in `.claude/hooks/`
3. Check that hook files are executable: `chmod +x .claude/hooks/*.sh`
4. Some hooks require `CLAUDE_HOOK_CONTEXT` (only available in Claude Code, not Copilot CLI)

## Update Preview or Rollback Questions

**Symptom:** You are not sure what `/amp-update` will change, or an update touched files you care about.

**Cause:** Production templates changed, or local user-owned files were mixed with template files.

**Fix:**
1. Review the [0.2.0 safe update guide](update-guide-0.2.0.md).
2. Run `git status --short` before and after updating.
3. If `/amp-show-changes` is available in your version, run it before `/amp-update` to preview changes.
4. Preserve user-owned files such as `CLAUDE.md`, `.mcp.json`, `.env`, `System/user-profile.yaml`, `System/pillars.yaml`, `System/usage_log.md`, and all vault content.
5. If `/amp-rollback` is available, use it to revert the update. Otherwise, restore from your pre-update commit, branch, or backup.

## Usage Log Checkmarks Reset

**Symptom:** `/amp-level-up` acts as if previously used features are unused.

**Cause:** `System/usage_log.md` was replaced with a newer template instead of merged.

**Fix:**
1. Restore the old `System/usage_log.md` from backup if needed.
2. Preview a safe merge: `python3 .scripts/merge-usage-log.py --dry-run --diff`.
3. If the diff looks right, run: `python3 .scripts/merge-usage-log.py`.

