---
name: amp-update-preflight
description: Pre-update checks, compatibility verification, dependency scanning, and what's-changed analysis
---

## Purpose

Run this before `/amp-update` to verify your environment is ready, check what's changed, and identify potential issues before applying updates. Provides a go/no-go recommendation.

**When to use:**
- Before running `/amp-update` if you're unsure about compatibility
- To preview what an update will change without applying it
- To diagnose why a previous update failed
- To verify Git setup is correct

**Time:** 30-60 seconds

---

## Step 1: Git Environment Check

### A. Check if Git is available

```bash
git --version
```

**If Git not found:**
```
❌ Git not detected

Amp updates require Git. Here's how to install:

**Mac:**
1. Open Terminal (Cmd+Space, type "Terminal")
2. Run: xcode-select --install
3. Click Install when prompted
4. Come back here when done

**Windows:**
1. Download from: https://git-scm.com/download/win
2. Run installer with default options
3. Restart Cursor
4. Try again

[Skip] — I'll do this later
```

If user skips, exit gracefully with: "Run `/amp-update-preflight` again once Git is installed."

---

### B. Check repository setup

Run: `git remote -v`

**Scenario 1: Not a Git repository (downloaded as ZIP)**
```
⚠️ ZIP Download Detected

Your Amp was downloaded as a ZIP file, not cloned with Git.

**Options:**
1. **Convert to Git** (recommended for future auto-updates):
   - I can set this up for you now (~2 minutes)
2. **Stay with ZIP** (manual updates):
   - Download latest: https://github.com/hemory/amp/archive/refs/heads/main.zip
   - See `06-Resources/Amp_System/Updating_Amp.md` for manual steps

**Your data is safe either way.** Updates never touch your notes, tasks, or projects.
```

**Scenario 2: Cloned directly (origin points to hemory/amp)**

If `git remote -v` shows "origin" pointing to `hemory/amp`:
```
✓ Git repository detected
✓ Remote configured (origin → hemory/amp)

Updates will use "origin". No additional setup needed.
```

**Scenario 3: Forked (origin is user's fork, upstream is hemory/amp)**

If `git remote -v` shows "upstream" pointing to `hemory/amp`:
```
✓ Git repository detected
✓ Upstream remote configured
```

**Scenario 4: Forked but no upstream remote**

If `git remote -v` shows only "origin" pointing to a user's fork (not hemory/amp):
```
✓ Git repository detected
⚠️ Upstream remote not configured

I'll set this up automatically during the update.
```

---

## Step 2: Check for Updates

Call update checker:
```
check_for_updates(force=True)
```

**If no updates available:**
```
✅ You're already on the latest version (vX.Y.Z)

No update needed. Everything looks good!
```
Exit.

**If updates available, show summary:**
```
🎁 Update Available

Current version: vX.Y.Z
Latest version:  vA.B.C

What's new:
- [Change 1]
- [Change 2]
- [Change 3]

[View full release notes]
```

---

## Step 3: Breaking Changes Analysis

Parse the update response from Step 2.

Also check for Sprint 1 update metadata if it exists. This is optional and must not block preflight when absent.

```bash
for manifest in System/update-manifest.json System/breaking-changes.json core/update-manifest.json core/breaking-changes.json; do
  if [ -f "$manifest" ]; then
    echo "Using update manifest: $manifest"
    python3 - <<'PY' "$manifest"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
items = data.get('breaking_changes') or data.get('breakingChanges') or []
print(json.dumps({'breaking_changes': items}, indent=2))
PY
    break
  fi
done
```

If a manifest is present, include its breaking-change entries in the recommendation. If it is absent, say "No update manifest found, using release metadata only."

**If `breaking_changes: true`:**
```
⚠️ Major Update Detected (Breaking Changes)

This update includes changes that may require extra steps:
- [Breaking change 1]
- [Breaking change 2]

**What this means:**
- Some folders may be renamed
- Configuration format may change
- A migration script will run automatically

**Impact on your data:** None. Your notes, tasks, and projects are never modified.

**Recommendation:** Read the release notes before proceeding.
[View release notes]
```

**If `breaking_changes: false`:**
```
✓ No breaking changes — safe for automatic update
```

---

## Step 4: Dependency Scan

Check current dependency status:

```bash
# Check Node dependencies
npm ls --depth=0 2>&1 | tail -5

# Check Python dependencies
pip3 list --format=freeze 2>&1 | head -5
```

**Report:**
```
📦 Dependencies

Node packages: [X installed]
Python packages: [Y installed]

⚠️ Issues found:
- [Missing package or version conflict]

✓ No issues — dependencies are healthy
```

---

## Step 5: Local Changes Check

```bash
git status --porcelain
```

**If uncommitted changes exist:**
```
💾 Uncommitted Changes Detected

You have unsaved changes:
- [Modified file 1]
- [Modified file 2]

These will be auto-saved before the update (committed with message "Auto-save before Amp update").

✓ Your changes are safe — they'll be preserved.
```

**If clean:**
```
✓ Working directory clean — no uncommitted changes
```

---

## Step 6: Protected Content Inventory

Create a concrete inventory of user-owned content that `/amp-update` must preserve. Do not copy or print secret values. Report presence, counts, and names only where names are non-secret.

```bash
python3 - <<'PY'
import json, pathlib, re
root = pathlib.Path('.')
protected_dirs = ['00-Inbox','01-Quarter_Goals','02-Week_Priorities','03-Tasks','04-Projects','05-Areas','06-Resources','07-Archives']
claude = root / 'CLAUDE.md'
text = claude.read_text(errors='ignore') if claude.exists() else ''
user_extensions = bool(re.search(r'USER_EXTENSIONS_START.*USER_EXTENSIONS_END', text, re.S))
custom_mcp = []
if (root / '.mcp.json').exists():
    data = json.loads((root / '.mcp.json').read_text())
    custom_mcp = sorted(k for k in data.get('mcpServers', {}) if k.startswith('custom-'))
custom_skills = sorted(p.name for p in (root / '.claude' / 'skills').glob('*-custom') if p.is_dir())
summary = {
    'USER_EXTENSIONS': user_extensions,
    'custom_mcp_entries': custom_mcp,
    'custom_skills': custom_skills,
    'user_data_folders': [d for d in protected_dirs if (root / d).exists()],
    'user_profile_yaml': (root / 'System' / 'user-profile.yaml').exists(),
    'pillars_yaml': (root / 'System' / 'pillars.yaml').exists(),
    'env_present': (root / '.env').exists(),
}
print(json.dumps(summary, indent=2))
PY
```

**Report:**
```
🛡️ Protected Content

✓ USER_EXTENSIONS block: present
✓ Custom MCP servers: 2 entries
✓ Custom skills: 1 folder
✓ User data folders: 7 present
✓ user-profile.yaml: present
✓ pillars.yaml: present
✓ .env: present, values not displayed

All listed items must be present after update smoke verification.
```

If `CLAUDE.md` exists but the markers are missing, flag as a warning. If `.env` exists, never display its contents.

---

## Step 7: MCP Configuration Validation Preview

Validate the live `.mcp.json` shape before update so `/amp-update` knows whether post-sync failures are new or pre-existing. Never replace it with a private or template config during preflight.

```bash
python3 - <<'PY'
import json, pathlib
root = pathlib.Path('.').resolve()
path = root / '.mcp.json'
if not path.exists():
    print('⚠️ .mcp.json missing, /setup or /amp-update can create it from template')
    raise SystemExit(0)
data = json.loads(path.read_text())
errors = []
for name, server in (data.get('mcpServers') or {}).items():
    blob = json.dumps(server)
    if '{{VAULT_PATH}}' in blob:
        errors.append(f'{name}: contains unreplaced VAULT_PATH placeholder')
    env_path = (server.get('env') or {}).get('VAULT_PATH')
    if env_path and pathlib.Path(env_path).expanduser().resolve() != root:
        errors.append(f'{name}: VAULT_PATH does not match vault root')
    for arg in server.get('args') or []:
        if isinstance(arg, str) and 'core/mcp/' in arg:
            candidate = pathlib.Path(arg).expanduser()
            if not candidate.is_absolute():
                candidate = root / candidate
            if not candidate.exists():
                errors.append(f'{name}: missing arg path {arg}')
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print('✓ MCP config passes placeholder, VAULT_PATH, and args checks')
PY
```

Add any validation warnings to the go/no-go recommendation.

---

## Step 8: Preflight Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Preflight Check Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Environment:
✓ Git available (vX.Y.Z)
✓ Upstream remote configured
✓ Dependencies healthy

Update:
✓ Update available: vX.Y.Z → vA.B.C
✓ No breaking changes
✓ Protected inventory captured and ready for smoke verification

Local State:
✓ Working directory clean
✓ Ready to update, including MCP validation and custom-content preservation checks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ RECOMMENDATION: Safe to update

Run `/amp-update` to apply.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**If issues found:**
```
⚠️ RECOMMENDATION: Fix issues before updating

Issues to resolve:
1. [Issue 1 — how to fix]
2. [Issue 2 — how to fix]

Run `/amp-update-preflight` again after resolving.
```

---

## Settings Reference

Update behavior is configured in `System/user-profile.yaml`:

```yaml
updates:
  auto_check: true              # Check during /daily-plan
  check_interval_days: 7        # How often to check
  auto_update: false            # Never auto-update without asking
  backup_before_update: true    # Always create backup tag
```

---

## Related Commands

- `/amp-update` — Apply the update after preflight passes
- `/amp-whats-new` — Check what's new without updating
- `/amp-rollback` — Undo last update if something went wrong
