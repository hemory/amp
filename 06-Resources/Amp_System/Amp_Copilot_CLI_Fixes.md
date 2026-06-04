# Amp + Copilot CLI: Fixes & Workarounds

This file tracks product-safe setup issues and resolutions for Amp in GitHub Copilot CLI. Keep entries generic and reusable. Do not include user names, private repo paths, credentials, internal programs, or personal work narratives.

## Entry Template

```markdown
## Fix 001: Short Title

**Severity:** High | Medium | Low
**Symptom:** What users see.
**Root cause:** Why it happens.
**Fix:** What changed.
**Recommendation for users:** What a new user should do.
```

## Known Product-Safe Fixes

### Fix 001: Preferences Must Persist in `CLAUDE.md`

**Severity:** High
**Symptom:** Behavioral preferences can be forgotten between sessions when stored only in optional preference files.
**Root cause:** Agents reliably load `CLAUDE.md`, but may not load every auxiliary preference file.
**Fix:** Store durable behavioral preferences in the `USER_EXTENSIONS` block in `CLAUDE.md`. Mirror only machine-readable settings to `System/user-profile.yaml`.
**Recommendation for users:** Put durable behavior rules in `CLAUDE.md`, not in an unreferenced notes file.

### Fix 002: Integration Config Must Stay Local

**Severity:** High
**Symptom:** API tokens, workspace IDs, or sync-state files can be accidentally committed.
**Root cause:** Integration config is user-owned runtime state.
**Fix:** Track only `System/integrations/*.example.yaml` and ignore real integration config files.
**Recommendation for users:** Copy examples locally, keep credentials in `.env` or MCP config, and never commit tokens.
