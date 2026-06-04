---
name: amp-update
description: Safely update Amp with one command (handles everything automatically)
---

## What This Command Does

**For non-technical users:** Updates Amp to the latest version automatically. No command line knowledge needed — just run the command and follow the prompts.

**When to use:**
- After `/amp-whats-new` shows new version available
- When you want the latest features and bug fixes

**What it handles:**
- Downloads updates automatically
- Protects your data (never touches your notes, tasks, projects)
- Preserves protected user blocks and user-owned MCP entries
- Resolves conflicts with a guided choice (no manual merge editor)
- Shows clear progress and confirmation

**Time:** 2-5 minutes

> **Unsure about compatibility?** Run `/amp-update-preflight` first for environment checks, dependency scanning, and a go/no-go recommendation.

---

## Process

### Step 1: Quick Environment Check

Verify Git and a valid remote are available. If issues are found, suggest running `/amp-update-preflight` for detailed diagnostics.

```bash
git --version && git remote -v
```

**Detect the correct remote name.** Users who cloned directly have `origin`. Users who forked have `upstream`. Check in this order:

```bash
# Prefer "upstream" if it exists, fall back to "origin"
if git remote | grep -q '^upstream$'; then
  AMP_REMOTE="upstream"
else
  AMP_REMOTE="origin"
fi
```

Use `$AMP_REMOTE` for all fetch/merge commands in this process.

If Git is missing or no remote is configured, redirect: "Run `/amp-update-preflight` to diagnose and fix your setup."

Check for updates:
```
check_for_updates(force=True)
```

If no updates: show "✅ You're already on the latest version" and exit.
If updates available: show version summary and proceed.

---

### Step 2: Pre-Update Safety Check

Before changing anything, capture a protected-content inventory. This inventory is used for post-update verification and the final update summary.

```bash
python3 - <<'PY'
import json, os, pathlib, re
root = pathlib.Path('.')
protected_dirs = ['00-Inbox','01-Quarter_Goals','02-Week_Priorities','03-Tasks','04-Projects','05-Areas','06-Resources','07-Archives']
claude = root / 'CLAUDE.md'
text = claude.read_text(errors='ignore') if claude.exists() else ''
user_block = bool(re.search(r'USER_EXTENSIONS_START.*USER_EXTENSIONS_END', text, re.S))
custom_mcp = []
if (root / '.mcp.json').exists():
    data = json.loads((root / '.mcp.json').read_text())
    custom_mcp = sorted(k for k in data.get('mcpServers', {}) if k.startswith('custom-'))
custom_skills = sorted(p.name for p in (root / '.claude' / 'skills').glob('*-custom') if p.is_dir())
inventory = {
    'user_extensions': user_block,
    'custom_mcp': custom_mcp,
    'custom_skills': custom_skills,
    'user_data_dirs': [d for d in protected_dirs if (root / d).exists()],
    'user_profile': (root / 'System' / 'user-profile.yaml').exists(),
    'pillars': (root / 'System' / 'pillars.yaml').exists(),
    'env_present': (root / '.env').exists(),
}
print(json.dumps(inventory, indent=2))
PY
```

Treat every item in this inventory as user-owned. Do not replace it with Amp defaults during the update.

**A. Check for uncommitted changes**

Run: `git status --porcelain`

**If there are changes:**
```
💾 Saving your work...

Amp found unsaved changes in your vault.
Let me save them before updating.
```

Run:
```bash
git add .
git commit -m "Auto-save before Amp update to v1.3.0"
```

Show:
```
✓ Your work is saved
```

**B. Create backup reference (safety net)**

Run:
```bash
git tag backup-before-v1.3.0
```

This creates a snapshot user can revert to if needed.

---

### Step 4: Download and Apply Updates

```
⬇️ Downloading updates from GitHub...
```

Run:
```bash
git fetch $AMP_REMOTE
```

**If network error:**
```
❌ Couldn't connect to GitHub

Please check your internet connection and try again.

[Retry]
[Cancel]
```

**Optional breaking-change registry check:**

If Sprint 1's manifest exists, use it in addition to the update-checker response. Do not fail if it is absent.

```bash
for manifest in System/update-manifest.json System/breaking-changes.json core/update-manifest.json core/breaking-changes.json; do
  if [ -f "$manifest" ]; then
    echo "Using update manifest: $manifest"
    python3 - <<'PY' "$manifest"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
items = data.get('breaking_changes') or data.get('breakingChanges') or []
print(json.dumps(items, indent=2))
PY
    break
  fi
done
```

If the manifest contains breaking changes for the target version range, show them before continuing. If no manifest exists, rely on `breaking_changes` from `check_for_updates` and release notes.

**If `breaking_changes: true` in update response or optional manifest:**
```
⚠️ Important: This update includes major changes

[Show what's changing]

This is safe to proceed, but some folders or configs may change.
Migration will run automatically.

[Continue with update]
[Cancel — I'll read the details first]
```

If cancelled, show link to release notes and exit gracefully.

---

### Step 6: Apply Updates

```
🔄 Applying updates...
```

**A. Merge updates**

Run:
```bash
git merge $AMP_REMOTE/main --no-edit
```

**B. Handle merge outcome**

**Case 1: Clean merge (no conflicts)**
```
✓ Updates applied successfully
```

Continue to Step 7.

---

**Case 2: Merge conflicts**

Check which files have conflicts:
```bash
git status | grep "both modified"
```

**Automatic conflict resolution (protected blocks + guided choices):**

**Protected user blocks (preserved verbatim):**
- `CLAUDE.md` contains a user block:
  - `USER_EXTENSIONS_START` ... `USER_EXTENSIONS_END`

**Custom MCP servers (preserved by name):**
- Any MCP server name starting with `custom-` is preserved
- Example: `custom-gmail`, `custom-hubspot`

**Custom skills (preserved by name):**
- Any skill folder ending with `-custom` is preserved
- Example: `meeting-prep-custom`, `daily-plan-custom`

**When conflicts occur:**

1. **If file is user data** (00-07, System/user-profile.yaml, System/pillars.yaml):
   - Keep user version
   - Run: `git checkout --ours <file>`

2. **If file contains protected user block** (CLAUDE.md):
   - Take upstream version
   - Re-insert preserved user block(s) verbatim
   - Validate markers still present

3. **If file is .mcp.json**:
   - Preserve any MCP entries named `custom-*`
   - Continue with Amp core updates for all other MCPs

4. **If skill folder ends with `-custom`**:
   - Preserve entirely, never modify
   - These are user's personal skills

5. **If file is core Amp** (skills, core MCP, scripts) **and user edited it**:
   - Use AskUserQuestion to resolve, instead of a merge editor

**AskUserQuestion flow (generic, parameterized):**
```
Title: Amp update conflict: {{item_name}}

Your change:
{{user_change_summary}}
Enables: {{user_use_case_summary}}

Amp update:
{{amp_change_summary}}
Enables: {{amp_use_case_summary}}

Options:
1) Keep my version (preserve my changes)
2) Use Amp version (take upstream changes)
3) Keep both (rename one)
4) Let me tell you what to do (I'll write instructions)
```

**If AskUserQuestion is not available (non-Claude Code):**

Use the tracked CLI helper instead of opening a merge editor:

```bash
.scripts/amp-merge-resolver.sh
```

The helper must show each conflicted file, a conflict preview, and the same four choices:
1. Keep mine: preserve local version, skip Amp changes for that file
2. Use Amp: take the update version, discard local edits for that file
3. Keep both: keep the local file and save the Amp version as `<file>.amp-update`
4. Instructions: collect user instructions in `System/update-conflict-instructions.md` and leave the conflict unresolved for follow-up

If the user types an invalid choice twice, default to "Use Amp version" for core Amp files only. For user data, `System/user-profile.yaml`, `System/pillars.yaml`, `.env`, `custom-*` MCPs, and `*-custom` skills, keep the user's version.

**If user chooses "Keep both":**
- MCP: `name` → `name-custom`
- Skill folder: `name/` → `name-custom/`

**After resolving all conflicts:**
```bash
git add <file>
git commit --no-edit
```

**Show to user:**
```
✓ Updates applied successfully

Handled conflicts:
• Preserved your protected blocks
• Updated core Amp features
• Resolved overlapping changes with your choice

[See what changed]
```

---

**Case 3: Merge failed (rare)**

```
❌ Update couldn't complete automatically

This is rare, but sometimes updates need manual review.

**What happened:**
[Error message]

**Options:**
[Restore to before update] — Uses the backup we created
[Get help] — Opens GitHub issue template
```

If restore:
```bash
git merge --abort
git reset --hard backup-before-v1.3.0
```

---

### Step 7: Post-Update Steps

**A. Check for migration needs**

If breaking_changes was true, check for migration script:

```bash
ls core/migrations/v*-to-v*.sh
```

If found:
```
🔧 Running migration...

This update requires a one-time migration to update your data structure.
This is safe and automatic.
```

Run:
```bash
./core/migrations/v1-to-v2.sh --auto
```

Show migration output.

**B. Update dependencies**

```
📦 Updating dependencies...
```

Run:
```bash
npm install
pip3 install -r requirements.txt
```

**C. Sync MCP Configuration (Automatic)**

Check if new MCP servers were added in the update by comparing `.mcp.json.template` entries against the user's live `.mcp.json`.

For each entry in `.mcp.json.template` that is NOT in the user's `.mcp.json`:
1. Read the entry from `.mcp.json.template`
2. Replace `{{VAULT_PATH}}` with the actual vault path
3. Add to the user's `.mcp.json`
4. Log: "✓ Added new MCP server: [name]"

**Never remove or modify existing user MCP entries.** Only add missing ones.

**Example:** If `.mcp.json.template` has `amp-analytics` but user's config doesn't:
```json
"amp-analytics": {
  "type": "stdio",
  "command": "python",
  "args": ["<vault_path>/core/mcp/analytics_server.py"],
  "env": { "VAULT_PATH": "<vault_path>" }
}
```

Add to summary if new MCPs added: "✓ Added new MCP servers: amp-analytics"

**MCP validation after sync:**

Never copy a private `.mcp.json` from another vault. Validate only the user's live file after template entries are merged.

```bash
python3 - <<'PY'
import json, pathlib
root = pathlib.Path('.').resolve()
config_path = root / '.mcp.json'
if not config_path.exists():
    raise SystemExit('Missing .mcp.json after update')
data = json.loads(config_path.read_text())
servers = data.get('mcpServers', {})
errors = []
for name, server in servers.items():
    blob = json.dumps(server)
    if '{{VAULT_PATH}}' in blob:
        errors.append(f'{name}: template placeholder not replaced')
    env_path = (server.get('env') or {}).get('VAULT_PATH')
    args = server.get('args') or []
    if env_path and pathlib.Path(env_path).expanduser().resolve() != root:
        errors.append(f'{name}: VAULT_PATH does not match this vault')
    for arg in args:
        if isinstance(arg, str) and 'core/mcp/' in arg:
            resolved = pathlib.Path(arg).expanduser()
            if not resolved.is_absolute():
                resolved = root / resolved
            if not resolved.exists():
                errors.append(f'{name}: arg path missing: {arg}')
if errors:
    raise SystemExit('\n'.join(errors))
print('✓ MCP config valid')
PY
```

If validation fails, stop before dismissing the update notification and show the exact server names to fix.

**D. Sync Usage Log Features (Automatic)**

Merge new feature entries from the template `System/usage_log.md` into the user's existing `System/usage_log.md`.

**Merge logic:**
1. Read the upstream template `System/usage_log.md` (from the just-updated amp-core files)
2. Read the user's existing `System/usage_log.md`
3. For each `- [ ]` or `- [x]` line in the template:
   - Extract the feature description (text after the checkbox)
   - Search the user's file for a line containing the same feature description
   - **If found:** Keep the user's version (preserves their `[x]` state)
   - **If NOT found:** This is a new feature — add it to the same section in the user's file
4. Preserve ALL user state: checked boxes, consent decisions, journey metadata, dates
5. Update the feature count in `Feature adoption score: X/Y` (Y = new total)

**Section matching:** Match new entries to the correct section by the `## Section Name` headers (e.g., "## Core Workflows", "## Advanced"). If a new section exists in the template but not in the user's file, add the entire section.

**Never:**
- Uncheck a user's checked box
- Change consent or metadata values
- Remove entries the user has

Log: "✓ Added N new features to usage_log.md" (or "✓ Usage log up to date" if nothing added)

**E. Enable new background automations (Automatic)**

Check for automation scripts that need installation. These run silently without prompting.

**Meeting Sync (if Granola detected):**

Check if Granola is installed:
```bash
ls "$HOME/Library/Application Support/Granola/cache-v3.json" 2>/dev/null
```

If Granola cache exists AND meeting automation not yet installed:
```bash
# Check if already installed
launchctl list | grep com.amp.meeting-intel
```

If not installed:
```bash
cd .scripts/meeting-intel && ./install-automation.sh 2>/dev/null
```

Add to summary if installed: "✓ Enabled automatic meeting sync (runs every 30 min)"

**Future automations:** This pattern extends to other background services. Check for the prerequisite (e.g., app installed, API key present), then run the installer silently.

---

### Step 8: Verification

```
✓ Update complete! Now testing...
```

**Quick smoke test:**

1. Check key files exist:
   - `03-Tasks/Tasks.md`
   - `System/user-profile.yaml`
   - `.claude/skills/daily-plan/SKILL.md`

2. Check MCP configuration:
   - `.mcp.json` exists and is valid JSON
   - No `{{VAULT_PATH}}` placeholders remain
   - Every `env.VAULT_PATH` matches this vault
   - Every local `core/mcp/*.py` arg exists
   - Custom MCP entries (`custom-*`) from the inventory still present

3. Check custom content preservation:
   - `USER_EXTENSIONS_START/END` markers still present if they existed before
   - `*-custom` skill folders from the inventory still present
   - User data folders from the inventory still present
   - `System/user-profile.yaml`, `System/pillars.yaml`, and `.env` presence matches the inventory

4. Try loading user profile:
   - Read `System/user-profile.yaml`

5. Produce an update summary:
   - Write `System/update-summary.md`
   - Print the same summary in chat
   - Include versions, files changed, conflicts resolved, MCPs added, custom items preserved, validation results, and rollback tag

**If all pass:**
```
✅ Update successful!
```

**If something fails:**
```
⚠️ Update completed but found an issue

[Details of what failed]

Your data is safe, but you may want to:
[Restore to previous version]
[Report this issue]
[Continue anyway]
```

---

### Step 9: Summary

Write this to `System/update-summary.md` and display it to the user. This file is user-local runtime output, not a production template.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Amp Updated: v1.2.0 → v1.3.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

What's new:
• Career coach improvements
• Task deduplication fix
• Meeting intelligence enhancement

Your data:
✓ User data folders preserved
✓ USER_EXTENSIONS preserved
✓ custom-* MCP entries preserved
✓ *-custom skills preserved
✓ user-profile, pillars, and .env presence preserved

Validation:
✓ MCP config valid
✓ Smoke checks passed
✓ Summary written to System/update-summary.md

[View full changelog]
[Start using new features]
```

**If new automations were enabled:**
```
🤖 New automations enabled:
✓ Automatic meeting sync (runs every 30 min)
```

**If there were conflicts:**
```
🔍 Changes applied:
• Updated 12 core files
• Kept 5 of your customized files
• Protected all your data folders

[See detailed change list]
```

---

### Step 9b: Check New Integrations (After Success)

After successful update, check if new integration features are available:

```python
from core.integrations import get_post_update_integration_message, should_show_integration_prompt

if should_show_integration_prompt():
    msg = get_post_update_integration_message()
    if msg:
        print(msg)
```

**If integrations are available but not configured:**
```
---

## 🔌 New: Productivity Integrations

This update includes integrations for your favorite tools:

- **Notion** — Search your workspace, pull docs into meeting prep
- **Slack** — Search conversations, get context about people
- **Google** — Gmail search, email context in person pages

**Set up now?** These are optional but unlock powerful features like:
- "What did Sarah say about the Q1 budget?" → Searches Slack
- Meeting prep pulls relevant docs from Notion
- Person pages show email/Slack history

Run `/integrate-notion`, `/integrate-slack`, or `/integrate-google` to set up.
```

**If user has integrations that could be upgraded:**
```
---

## 🔄 Integration Upgrade Available

You have some integrations that could be upgraded to Amp recommended packages:

### Notion
- **Current:** custom-notion-mcp
- **Recommended:** @notionhq/notion-mcp-server
- **Benefits:** Official from Notion, Best maintained, Full API coverage

**Options:**
1. **Keep existing** — Your current setup works fine
2. **Upgrade** — Run `/integrate-notion` to switch to recommended
```

---

### Step 10: Track Usage (Silent)

Update `System/usage_log.md` to mark Amp update as used.

**Analytics (Silent):**

Call `track_event` with event_name `amp_update_completed` and properties:
- `from_version`
- `to_version`

This only fires if the user has opted into analytics. No action needed if it returns "analytics_disabled".

**Clear update notification:**

Call `dismiss_update()` from the Update Checker MCP to remove the `System/.update-available` file. This stops the daily update reminder from appearing in future sessions.

---

## Error Recovery

### If Update Fails at Any Point

User always has escape hatch:

```
🔙 Restoring to before update...
```

Run:
```bash
git merge --abort 2>/dev/null || true
git reset --hard backup-before-v1.3.0
git clean -fd
```

```
✓ Restored to v1.2.0

Nothing was changed. Your Amp is exactly as it was.

[Try update again]
[Report issue]
[Cancel]
```

---

## Migration Support (for Breaking Changes)

### Auto-Migration Flag

If migration script supports `--auto` flag, run non-interactively:

```bash
./core/migrations/v1-to-v2.sh --auto
```

**Migration script must:**
- Accept `--auto` flag
- Skip confirmation prompts
- Return exit code 0 on success
- Log to `System/.migration-log`

### Manual Migration Required

If script doesn't support `--auto`:

```
⚠️ Manual step required

This update needs you to run a migration script.

Don't worry - it's one command and takes 30 seconds.

**In Cursor's terminal (bottom panel), run:**

./core/migrations/v1-to-v2.sh

**Then come back here when it's done.**

[I've run the migration — continue]
[Show me what the migration does]
[Cancel update]
```

---

## Alternative: ZIP Download Path

For users who can't/won't use Git, provide manual instructions:

```
📥 Manual Update Method

If automatic updates don't work, you can update manually:

1. **Download latest Amp:**
   https://github.com/hemory/amp/archive/refs/heads/main.zip

2. **Copy your data and custom blocks:**
   From OLD Amp folder, copy these to NEW Amp folder:
   
   ✓ System/user-profile.yaml
   ✓ System/pillars.yaml
   ✓ 00-Inbox/ (entire folder)
   ✓ 01-Quarter_Goals/ (entire folder)
   ✓ 02-Week_Priorities/ (entire folder)
   ✓ 03-Tasks/ (entire folder)
   ✓ 04-Projects/ (entire folder)
   ✓ 05-Areas/ (entire folder)
   ✓ 07-Archives/ (entire folder)
   ✓ .env (if it exists)
   ✓ Your `USER_EXTENSIONS` block from `CLAUDE.md`
   ✓ Any custom MCP entries named `custom-*` from `.mcp.json`
   ✓ Any custom skills ending with `-custom`

3. **DON'T copy:**
   ✗ .claude/skills/ (use new version)
   ✗ core/mcp/ (use new version)
   ✗ README.md (use new version)

4. **Open new folder in Cursor**

5. **Run /setup to verify**

[Download now]
[Copy step-by-step instructions to clipboard]
```

---

## Related Commands

- `/amp-update-preflight` — Pre-update checks, compatibility verification, dependency scanning
- `/amp-whats-new` — Check what's new without updating
- `/amp-rollback` — Undo last update (if something went wrong)

---

## Philosophy

**Automatic where possible:**
- Git commands run silently
- Conflicts resolved automatically
- Dependencies updated automatically
- Migrations run automatically (when safe)

**Interactive where necessary:**
- Breaking changes: confirm understanding
- Manual migration: clear instructions
- Errors: always offer restoration

**Safe always:**
- Backup created before any changes
- User data never at risk (gitignored)
- One-command rollback if issues
- Clear status at every step

**No jargon:**
- Don't say "merge conflict" - say "overlapping changes"
- Don't say "upstream" - say "main Amp repository"
- Don't say "git fetch" - say "downloading updates"
- Don't say "rebase" - just don't use rebase
