---
name: setup
description: Initial Amp setup - conversational onboarding for new users
---

# Set Up Amp

This skill runs the full onboarding flow. It reads `.claude/flows/onboarding.md` for the detailed conversation script.

## How This Skill Works

1. **Bootstrap first (do this silently and quickly, do NOT explore the codebase):**
   - If `.mcp.json` does not exist, generate it from `.mcp.json.template` (replace `{{VAULT_PATH}}` with the vault root). Tell the user to restart their terminal session, then STOP.
   - If `python3 -c "import mcp"` fails, install deps via `.venv/bin/pip` or `python3 -m pip`.
   - If `node_modules/` does not exist, run `npm install --quiet`.
2. Read `.claude/flows/onboarding.md` for the full conversation flow
3. Follow it step by step - it covers introduction, core setup, workspace creation, a required Obsidian walkthrough, and the handoff to first-use workflows
4. Use the onboarding MCP for state tracking and validation

## Quick Summary

The onboarding has 5 phases:

**Phase 1: Introduction** - Explain what Amp does and how the daily workflow works
**Phase 2: Core Setup** - 4 questions: name, role, email domain, communication preferences
**Phase 3: Workspace Creation** - Verify dependencies and generate the vault structure and config
**Phase 4: Obsidian Walkthrough** - Require opening the new vault in Obsidian before finishing
**Phase 5: Completion & Next Step** - End onboarding cleanly and offer the getting-started tour

## Important

- Read the full flow file before starting
- Call `start_onboarding_session()` to initialize MCP tracking
- Call `validate_and_save_step()` after each core step (1-4)
- Call `finalize_onboarding()` during Step 5 after dependency checks pass
- Call `complete_obsidian_walkthrough()` after the user confirms the vault is open in Obsidian
- Do not do integration discovery during onboarding, save that for later workflows like `/getting-started` or `/integrate-mcp`
- Offer the getting-started tour before the user leaves, it's the bridge into real daily use
