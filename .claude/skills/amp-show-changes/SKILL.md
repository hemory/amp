---
name: amp-show-changes
description: Preview what will change between your installed Amp and latest production without applying updates
---

## Purpose

Show a read-only preview of the changes available before running `/amp-update`. This command helps users understand what is new, what may be removed or renamed, what customizations will be protected, and whether any breaking-change warning is available.

**When to use:**
- Before `/amp-update` when you want a plain-English preview.
- When `/amp-whats-new` says an update is available and you want file-level detail.
- When you have custom skills, MCP entries, or protected user instructions and want to confirm they are visible before updating.

**Read-only guarantee:** This workflow does not merge, reset, checkout, stash, commit, or apply updates. It only reads local files and, when Git is available, runs `git fetch` so the remote comparison point is current.

---

## Inputs

`$ARGUMENTS` is optional.

Supported modes:
- No argument: compare current `HEAD` with the latest production `main`.
- `--no-fetch`: skip network fetch and compare against the currently cached remote-tracking branch.
- `--full`: include raw commit subjects and a longer changed-file summary.

---

## Step 1: Detect Git and Remote

Check whether the current Amp install is a Git repository:

```bash
git rev-parse --is-inside-work-tree
```

If Git is unavailable or the command fails, continue with a limited local-only preview:

```text
⚠️ Git preview unavailable

I could not compare your install with production because this folder is not a Git checkout or Git is not installed.

What I can still show:
- Protected customizations I can detect locally
- Manual update guidance

To enable full previews, install Amp from the Git repository instead of a ZIP download.
```

When Git is available, detect the production remote. Prefer `upstream`, fall back to `origin`:

```bash
if git remote | grep -qx 'upstream'; then
  AMP_REMOTE='upstream'
elif git remote | grep -qx 'origin'; then
  AMP_REMOTE='origin'
else
  AMP_REMOTE=''
fi
```

If no remote exists, explain that remote comparison is unavailable and continue with the protected customizations inventory.

---

## Step 2: Refresh Production Main Without Applying Updates

Unless `--no-fetch` is present, fetch the production branch only:

```bash
git fetch "$AMP_REMOTE" main:refs/remotes/$AMP_REMOTE/main --prune
```

Set the comparison target:

```bash
AMP_TARGET="$AMP_REMOTE/main"
```

Validate the target exists:

```bash
git rev-parse --verify "$AMP_TARGET"
```

If fetch fails, use the cached remote-tracking branch if available. If no target is available, report the failure and continue with local inventory only.

---

## Step 3: Look for an Update Manifest, Then Fall Back to Git Diff

A production update manifest may be available. If one exists locally or in the fetched target, use it to enrich the preview. Check likely manifest paths without assuming one is present:

```bash
for path in \
  System/update-manifest.json \
  System/update-manifest.yaml \
  System/update-manifest.yml \
  .amp/update-manifest.json \
  amp-update-manifest.json \
  release-manifest.json; do
  if [ -f "$path" ]; then
    echo "local:$path"
    break
  fi
  if git cat-file -e "$AMP_TARGET:$path" 2>/dev/null; then
    echo "remote:$path"
    break
  fi
done
```

If a local manifest is found, read it from the working tree. If a remote manifest is found, read it from the target tree with `git show "$AMP_TARGET:$path"`. Use any available fields for:
- Version or release name
- Summary
- Added features
- Removed features
- Renamed features
- Breaking changes
- Migrations
- Protected paths or customization rules

If no manifest is found, say so plainly and generate the preview from Git diff data:

```text
No update manifest found on production main yet, so this preview is based on Git commits and changed files.
```

---

## Step 4: Compare Commits and Files

Collect the commit range and changed files:

```bash
git log --oneline --decorate --no-merges HEAD.."$AMP_TARGET"
git diff --name-status HEAD.."$AMP_TARGET"
git diff --stat HEAD.."$AMP_TARGET"
```

If there are no commits in `HEAD..$AMP_TARGET`, report:

```text
✅ You're already aligned with production main.

No update is waiting. I still checked protected customizations below.
```

For normal output, summarize:
- Number of commits ahead on production.
- Top commit subjects, grouped when possible by prefix or area.
- Changed file counts by area: skills, MCP/core, scripts, docs, templates, tests.
- File status counts: added, modified, deleted, renamed.

---

## Step 5: Identify Added, Removed, and Renamed Features

Use manifest data first when available. Otherwise infer cautiously from file paths.

Feature path patterns:
- Skills: `.claude/skills/<skill-name>/SKILL.md`
- MCP servers: `core/mcp/*_server.py`
- User docs: `docs/*.md`, `README.md`, `CLAUDE.md.template`, `AGENTS.md`
- Templates: `System/Templates/*`, `06-Resources/Templates/*`
- Scripts: `scripts/*`, `.scripts/*`

From `git diff --name-status`:
- `A .claude/skills/foo/SKILL.md` means added skill `/foo`.
- `D .claude/skills/foo/SKILL.md` means removed skill `/foo`.
- `R... old new` under `.claude/skills/` means renamed skill.
- Apply the same pattern to MCP servers, docs, and templates when names clearly map to user-visible features.

Do not overstate inferred changes. Use labels:
- **From manifest** when the manifest says it directly.
- **Inferred from file paths** when derived from Git diff.
- **Needs review** when the file changed but the user impact is not obvious.

---

## Step 6: Breaking-Change Warnings

Use manifest breaking-change fields first. If the manifest contains `breaking_changes`, `breakingChanges`, `warnings`, `migrations`, or `requires_action`, surface them exactly and prominently.

If there is no manifest, scan commit subjects and changed file paths for likely warning terms:

```bash
git log --format='%s' HEAD.."$AMP_TARGET" | grep -Ei 'breaking|migration|required|remove|rename|deprecat|manual' || true
git diff --name-status HEAD.."$AMP_TARGET" | grep -Ei 'migration|template|CLAUDE|AGENTS|requirements|package-lock|install|setup' || true
```

Output one of:

```text
⚠️ Breaking-change warnings
- [Manifest-provided warning or cautious inferred warning]
```

or:

```text
✓ No breaking-change warning found in the manifest or commit/file scan.
```

When warnings are inferred, say they are inferred and recommend reading the related commits before updating.

---

## Step 7: Protected Customizations Inventory

Inventory local customizations that `/amp-update` should preserve. Do not print private content. Report counts and names only when names are safe and useful.

Check:

```bash
# Protected user instruction block
if [ -f CLAUDE.md ] && grep -q 'USER_EXTENSIONS_START' CLAUDE.md && grep -q 'USER_EXTENSIONS_END' CLAUDE.md; then
  echo 'user_extensions_block=present'
else
  echo 'user_extensions_block=not_found'
fi

# Custom skills
find .claude/skills -maxdepth 1 -type d -name '*-custom' -print 2>/dev/null | sed 's#^.claude/skills/##'

# Custom MCP servers by name only
python3 - <<'PY'
import json
from pathlib import Path
path = Path('.mcp.json')
if not path.exists():
    print('custom_mcp=[]')
else:
    data = json.loads(path.read_text())
    names = sorted(k for k in data.get('mcpServers', {}) if k.startswith('custom-'))
    print('custom_mcp=' + repr(names))
PY

# Locally modified tracked files
git status --short
```

Report:

```text
🛡️ Protected customizations inventory

- User extension block: present/not found
- Custom skills: N found
- Custom MCP servers: N found
- Local uncommitted changes: N files

I did not print private instruction text, MCP command values, environment values, notes, tasks, projects, people pages, or meeting notes.
```

If custom items are missing, avoid implying data loss. Say only that none were detected.

---

## Step 8: Produce the Preview

Use this structure:

```text
# Amp update preview

Compared: current HEAD → <remote>/main
Remote: <remote>
Mode: manifest-enriched | git-diff only | local inventory only

## Summary
- <N> commits available
- <N> files changed: <A> added, <M> modified, <D> deleted, <R> renamed
- Biggest areas: skills, docs, core, templates, tests

## Added features
- /skill-name, from manifest or inferred from file path

## Removed features
- None found, or list items

## Renamed features
- None found, or old → new

## Breaking-change warnings
- None found, or list warnings

## Protected customizations inventory
- User extension block: present/not found
- Custom skills: count
- Custom MCP servers: count
- Local modified tracked files: count

## What this means for you
Plain-English explanation of likely impact:
- What new capability they get
- Whether any behavior may change
- Whether anything needs review before `/amp-update`
- Whether it looks safe to proceed

## Next step
- If comfortable: run `/amp-update`
- If cautious: run `/amp-update-preflight`
- If warnings appeared: read the listed commits or release notes first
```

Keep the final recommendation grounded in evidence. Do not claim an update is safe if breaking warnings exist, the diff could not be fetched, or there are uncommitted local changes that may need review.
