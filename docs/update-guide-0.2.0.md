# Amp 0.2.0 Safe Update Guide

Amp 0.2.0 is a safety-focused rollup. It adds update guidance, production templates, role starter material, and helper scripts while keeping your vault data local and user-owned.

## What changed

- Demo sample data and role starter packs are available as production templates for new installs and walkthroughs.
- LaunchAgent templates can automate morning brief, meeting prep, and end-of-day digest workflows after you opt in locally.
- Session continuity now documents optional identity and voice templates in `System/identity/`.
- Update safety guidance is centralized here so existing users can review what an update may touch before accepting it.
- A usage-log merge helper, `.scripts/merge-usage-log.py`, can preserve checked feature state while adding new feature entries from `System/Templates/usage_log.md`.

## What is preserved

Safe updates should preserve user-owned files and local configuration, including:

- `CLAUDE.md` user extensions and any manually added preferences.
- `.mcp.json`, `.env`, virtual environments, secrets, and local runtime state.
- Vault content in `00-Inbox/`, `01-Quarter_Goals/`, `02-Week_Priorities/`, `03-Tasks/`, `04-Projects/`, `05-Areas/`, `06-Resources/`, and `07-Archives/`.
- User configuration such as `System/user-profile.yaml`, `System/pillars.yaml`, `System/integrations/config.yaml`, and `System/usage_log.md`.
- Session continuity and memory files such as `System/Session_Learnings/` and `System/Memory/` when present.
- Active identity files such as `System/identity/amp/SOUL.md`, `System/identity/amp/STYLE.md`, `System/identity/user/SOUL.md`, and `System/identity/user/STYLE.md`.

Production templates may be updated, but active user files should not be overwritten without an explicit backup and confirmation.

## What may be removed or renamed

These notes are conservative and only cover production-safe migration facts:

- `meeting-intel` and Granola-related automation are legacy or optional local integrations. If you have Granola configured, preserve your local config and credentials, then re-enable only after confirming the updated integration path still exists.
- Demo-mode and ScreenPipe material may be template or beta content. Treat local demo data and ScreenPipe settings as optional, user-owned files.
- `ai-setup` and `ai-status` were setup/status era names in older workflows. Prefer the current setup, health, and update commands when available.
- If both `slack-intel-custom` and `slack-intel` exist, keep the custom skill as user-owned and review whether the production `slack-intel` skill now covers the same workflow before deleting anything.

When in doubt, keep the old file, move it to an archive, or compare changes before deleting.

## Preview changes before updating

From your Amp repo:

```bash
git status --short
```

Commit or copy any important local changes before updating. Then use the safe update command:

```text
/amp-update
```

If `/amp-show-changes` is available in your version, run it before `/amp-update` to review the files that would change. If it is not available yet, use this guide plus `git diff` and `git status` to inspect local changes.

## Merge usage-log updates safely

`System/usage_log.md` powers feature recommendations and contains your checked state. To add new template entries without clearing checkmarks:

```bash
python3 .scripts/merge-usage-log.py --dry-run --diff
```

If the diff looks safe, write the merge:

```bash
python3 .scripts/merge-usage-log.py
```

The helper preserves:

- Existing checked boxes for matching feature labels.
- Analytics consent answers.
- Legacy entries that are no longer in the current template, under `Legacy or Removed Features`.

Use `--source`, `--target`, and `--output` for nonstandard paths.

## Identity templates after update

Identity templates are optional. Updates may add or refresh template files, but they should not overwrite active identity files that you already customized.

To use the templates after updating:

1. Open `System/identity/README.md`.
2. Copy a template into an active file only if that file does not already exist, for example `System/identity/amp/SOUL.md.template` to `System/identity/amp/SOUL.md`.
3. Add only stable, user-declared guidance. Do not add secrets, runtime logs, tasks, projects, meeting notes, or inferred sensitive attributes.
4. Restart your agent session so the files are loaded at session start.

If you already have active identity files, review new templates manually and copy only the pieces you want.

## Rollback

If an update goes wrong:

1. Stop and avoid running additional migration helpers.
2. Check the current state:

   ```bash
   git status --short
   ```

3. Restore from your pre-update commit, branch, or backup. If `/amp-rollback` is available in your version, use it.
4. Reinstall dependencies only after the files are back in the expected state:

   ```bash
   npm install
   pip install -r requirements.txt
   ```

5. Run validation:

   ```bash
   npm test
   ```

If rollback affects user-owned files, restore those from your backup rather than from production templates.
