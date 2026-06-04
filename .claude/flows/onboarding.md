# Amp Onboarding Flow

Guide new users through setup in a friendly ~5 minute conversation. Keep it simple, practical, and focused on getting them working quickly.

## Bootstrap Check (BEFORE ANYTHING ELSE)

Before starting onboarding, verify the environment is ready. Do these checks silently and quickly; do NOT explore the codebase or read extra files.

1. **Check if `.mcp.json` exists** at the vault root.
   - If it does NOT exist, create it by reading `.mcp.json.template` and replacing every `{{VAULT_PATH}}` with the absolute path to the vault root. Write the result to `.mcp.json`.
   - Then tell the user: "I just created your MCP configuration. If tools aren't loading, try restarting your terminal — MCP servers load on session start. Then come back and we'll pick up where we left off.

     **Please restart your terminal session** (quit and reopen Copilot CLI from this directory), then run `/setup` again. The servers need a fresh session to load."
   - **STOP. Do not continue onboarding.** The MCP tools will not be available until the user restarts.

2. **Check if Python dependencies are installed.** Run: `python3 -c "import mcp" 2>/dev/null`
   - If that fails AND a `.venv` directory exists, run: `.venv/bin/pip install -q -r requirements.txt`
   - If that fails AND no `.venv` exists, run: `python3 -m pip install -q -r requirements.txt`
   - If both fail, tell the user to run `./install.sh` first and STOP.

3. **Check if `npm install` has been run.** If `node_modules/` does not exist, run `npm install --quiet`.

4. **Only proceed to "Before Starting" below if `.mcp.json` exists AND onboarding MCP tools are callable.** If any bootstrap step required a session restart, STOP and wait for the user to come back.

---

## Before Starting

**CRITICAL:** Call `start_onboarding_session()` from onboarding-mcp to initialize or resume onboarding.

- If a session exists, show progress and ask if they want to resume or start fresh
- The MCP tracks completion and validates each step
- Session state enables resume if interrupted

**After each step (1-4):** Call `validate_and_save_step(step_number=X, step_data={...})` before proceeding. If validation fails, show the error and retry the step.

### Platform Detection (do this once, before Step 1)

Detect which question tool is available so all subsequent steps use the right one:

- If the `AskQuestion` tool is available → you are in **Cursor**. Use `AskQuestion` for all choice prompts.
- If the `AskUserQuestion` tool is available → you are in **Claude Code** (CLI or Desktop). Use `AskUserQuestion` for all choice prompts.
- If neither tool is available → use **numbered text options** and accept typed responses.

Remember this for the rest of onboarding. Every step that says "present options" should use whichever tool you detected here. The JSON schemas below work identically for both `AskQuestion` and `AskUserQuestion`.

---

## Step 1: Welcome

Say: "**Step 1 of 8** — Welcome!

Hey! I'm Amp, your AI Chief of Staff. I'm here to amplify your work — helping you plan your day, prep for meetings, track your projects and people, and focus on what actually matters.

Let's get you set up. First, what's your name?"

**After receiving name:** Call `validate_and_save_step(step_number=1, step_data={"name": "..."})` to validate and save.

---

## Step 2: Role

Say: "**Step 2 of 8** — Tell me about your role."

Ask: "What's your role? A short description is perfect."

Examples:
- "Program Manager, Learning & Development"
- "Product Manager"
- "Founder"
- "Customer Success Manager"

**After receiving role:** Call `validate_and_save_step(step_number=2, step_data={"role": "..."})` to validate and save.

---

## Step 3: Email Domain (MANDATORY)

**Do not skip this step.** It powers internal vs external person routing.

Say: "**Step 3 of 8** — Let's set up your email domain."

Ask: "What's your company email domain? For example: `github.com` or `acme.com`

If you use more than one work domain, you can list them comma-separated, like `acme.com, acme.io`."

**After receiving email domain:** Call `validate_and_save_step(step_number=3, step_data={"email_domain": "..."})` to validate and save.

---

## Step 4: Communication Preferences

Say: "**Step 4 of 8** — Let's set up your communication preferences.

Quick preferences check. I use these to match my tone and how directly I make recommendations."

Present these 2 questions using your detected platform tool. If using text fallback, show numbered options for each:

1. **Formality Level:**
   - Formal (professional, structured)
   - Professional but casual (friendly but business-focused) [recommended]
   - Casual (relaxed, conversational)

2. **Directness:**
   - Very direct (bottom line up front, minimal context)
   - Balanced (context + action) [recommended]
   - Supportive (extra encouragement and explanation)

Explain: "This only affects how I communicate. You can fine-tune more advanced preferences later in `System/user-profile.yaml`."

**After receiving responses:**
1. Save to `System/user-profile.yaml` → `communication` section
2. Map formality to: formal, professional_casual, casual
3. Map directness to: very_direct, balanced, supportive
4. Default `career_level` to `mid`
5. Default `coaching_style` to `collaborative`

**After receiving preferences:** Call `validate_and_save_step(step_number=4, step_data={"communication": {...}})` to validate and save.

---

## Step 5: Generate Structure

**BEFORE PROCEEDING - MCP Validation:**
1. Call `get_onboarding_status()` to verify all required steps (1-4) are completed
2. If Step 3 (email_domain) is missing, STOP and go back, the MCP will block finalization
3. Call `verify_dependencies()` to check Python packages
4. Show any missing dependencies with installation instructions (if any)

Say: "**Step 5 of 8** — Creating your workspace.

Perfect! I'm creating your workspace now. Here's what you're getting:

**Amp uses the PARA method:**
- **04-Projects/** — Time-bound work with clear outcomes
- **05-Areas/** — Ongoing responsibilities (People/, Career/, plus role-specific areas)
- **06-Resources/** — Reference material (learnings, quarterly reviews, system docs)
- **07-Archives/** — Historical records (plans, reviews, completed projects)
- **00-Inbox/** — Capture zone (meetings, ideas, notes)

This separates active work from reference material and keeps your capture zone lightweight."

**Then execute finalization:**

Call `finalize_onboarding()` from onboarding-mcp. This single call handles:
1. Pre-check: Verify all steps completed (especially Step 3)
2. Create PARA folder structure (04-Projects/, 05-Areas/, etc.)
3. Create initial files (03-Tasks/Tasks.md, 02-Week_Priorities/Week_Priorities.md)
4. Write System/user-profile.yaml from session data
5. Write `System/pillars.yaml` with a temporary **General** bucket so planning can work before custom pillars are defined
6. Update CLAUDE.md User Profile section
7. Setup `.mcp.json` at the vault root (replace `{{VAULT_PATH}}` automatically)
8. Save onboarding state so the required Obsidian walkthrough can resume if the session is interrupted

The MCP returns a summary of what was created (folders, files, configs).

**After creation, say:** "✓ Workspace created! Your core setup is done."

Show the summary from the MCP response.

Then add: "I kept onboarding intentionally light. Your workspace is ready, and I set up a temporary **General** task bucket so you can start immediately. You can define your real strategic pillars any time by editing `System/pillars.yaml`."

## Step 6: Vault Viewer Setup

Say: "**Step 6 of 8** — Choose how you'll browse your vault.

Your vault works best in Obsidian — it handles markdown beautifully and lets you paste screenshots, collaborate on docs, and see your work visually.

**How would you like to work with your vault?**
1. **Obsidian (recommended)** — Download from obsidian.md, then open your vault folder as a vault
2. **GitHub repo** — Work directly in the repo with your preferred editor. You will miss image embedding and visual editing, but everything else works."

### If they choose Obsidian:

If the user does not have Obsidian installed yet:

- Stop here and tell them to install Obsidian from [obsidian.md](https://obsidian.md/download)
- Tell them to reopen `/setup` after installation
- Do not continue to the completion message until they can open the vault

Give these steps:

1. Open Obsidian
2. Choose **Open folder as vault**
3. Select the **Amp repo root** you just set up, not a subfolder
4. Confirm you can see folders like `00-Inbox`, `04-Projects`, `05-Areas`, and `06-Resources` in the sidebar

If they opened the wrong folder, tell them to go back and select the Amp root folder.

When they confirm it is open:

1. Call `complete_obsidian_walkthrough()` from onboarding-mcp to create the completion marker and close the onboarding session
2. Then say:

"Perfect. Obsidian is your note browser and workspace. The AI still runs from GitHub Copilot CLI or Claude Code, but Obsidian makes the vault much easier to explore."

#### Enable the Obsidian CLI (Recommended)

Say: "**One more Obsidian step I highly recommend:** Enable the Obsidian CLI. This lets Amp create, search, and update notes through Obsidian's own API instead of editing files directly, which keeps links, tags, and the search index in sync automatically.

It takes 30 seconds:

1. In Obsidian, go to **Settings → General**
2. Enable **Command line interface**
3. Click **Register CLI**
4. Follow the prompt to add it to your PATH (it updates your shell config)

To verify, open a new terminal and run: `obsidian version`

Requires Obsidian 1.12.4 or later. If you're on an older version, update Obsidian first."

If the user enables it, confirm with: "Great, the Obsidian CLI is ready. Amp will use it when available."

If the user skips, say: "No problem. Amp works fine without it, files are just edited directly. You can enable it anytime from Obsidian Settings → General."

Then add: "If you want wiki links and an optimized Obsidian setup later, run `/amp-obsidian-setup`."

### If they choose GitHub repo:

1. Call `complete_obsidian_walkthrough()` from onboarding-mcp to create the completion marker and close the onboarding session (this marks vault setup as done regardless of viewer choice)
2. Say: "Great, you're all set to work directly in the repo. You can use VS Code, Cursor, or any editor you like. If you ever want to try Obsidian later, just open this folder as a vault."
3. Continue to Step 7 (skip the Obsidian CLI section).

## Step 7: Completion & Phase 2 Bridge

Say: "**Step 7 of 8** — Wrapping up and connecting your calendar."

### Cursor Version Check (If Cursor Detected)

Before the completion message, check if user is using Cursor < 2.4:

**Check:** Look for `~/.cursor` directory. If it exists, try to detect version from `/Applications/Cursor.app/Contents/Info.plist` (macOS).

**If Cursor < 2.4 detected:**

Say: "⚠️ **Important: Cursor Version Update Needed**

I noticed you're using Cursor [version]. Amp skills (like `/daily-plan`, `/meeting-prep`, etc.) require **Cursor 2.4 or later**.

**To update:**
1. Cursor menu → Check for Updates, OR
2. Download latest from [cursor.com](https://cursor.com)

After updating, all Amp skills will work automatically. For now, you can continue setup, but skills won't appear in the `/` menu until you upgrade.

[Continue with setup anyway] / [Pause and update Cursor first]"

**If user continues:** Proceed with setup, skills will work after they update.
**If user pauses:** Say "No problem! Update Cursor first, then come back and type `/setup` to resume."

---

### Completion Message

Say: "✓ **Your workspace is ready, [Name]!**

I've configured your system with:
- Your name, role, communication defaults, and email-domain routing
- Folder structure for PARA method
- A temporary **General** task bucket until you define your own pillars
- An Obsidian vault you can already browse

### Calendar Setup (Choice Menu)

Before wrapping up, present the calendar options. Say:

"Calendar integration makes your daily plan smarter, but you can always set it up later. **How do you want Amp to know about your meetings?**"

Present these choices:

1. **Skip for now** — I'll set up calendar later (you can always run `/calendar-setup`)
2. **Apple Calendar** — Native macOS integration. Amp reads your Calendar.app directly via AppleScript. Best if your work calendar syncs to Apple Calendar.
3. **Apple Calendar (EventKit)** — Uses Apple's EventKit framework for more reliable calendar access. Recommended if AppleScript access is flaky.
4. **Google Calendar** — Connects via Google Calendar API. Best if your organization uses Google Workspace.
5. **WorkIQ (Microsoft 365)** — Connects to Outlook/Teams calendar via Microsoft's WorkIQ MCP. Best for organizations on Microsoft 365.
6. **Screenshot drops** — Just paste or drop screenshots of your calendar into chat. No integrations needed. Amp reads images when you run `/daily-plan`.

**If they choose 1 (Skip):** Create a P1 task: "Set up calendar integration" with description "Run /calendar-setup for Apple Calendar, or choose: Google Calendar, WorkIQ (Microsoft 365), or screenshot drops (just paste into /daily-plan)." Say "No problem! I've added it to your task list so it'll show up in your next daily plan."
**If they choose 2 (Apple Calendar):** Say "Great choice! Run `/calendar-setup` to grant access. I've added it to your tasks." Create the task.
**If they choose 3 (Apple Calendar EventKit):** Say "Good pick! Run `/calendar-setup` and select the EventKit option. I've added it to your tasks." Create the task.
**If they choose 4 (Google Calendar):** Say "Run `/calendar-setup` and select Google Calendar. You'll need to authorize access. I've added it to your tasks." Create the task.
**If they choose 5 (WorkIQ):** Say "WorkIQ connects via Microsoft 365. It's already in your MCP config. Run `/daily-plan` and it will pull your Outlook calendar automatically." Create the task.
**If they choose 6 (Screenshot drops):** Say "Simple and effective! When you run `/daily-plan`, just paste a screenshot of your calendar into the chat or drop it in `00-Inbox/`. I'll read it and plan your day." No task needed.

For options 1-5: create a task in `03-Tasks/Tasks.md` with priority P1 so it appears in their next `/daily-plan`:

```
- [ ] Set up calendar integration | P1 | General | ^task-YYYYMMDD-001
  Choose: Apple Calendar (/calendar-setup), WorkIQ (Microsoft 365), or screenshot drops
```

Then continue to the getting-started offer:

**Want me to run the getting started tour?** (Highly recommended)

[If yes:] Great! Running `/getting-started` now...

[Then actually invoke the /getting-started skill, which will have MCPs loaded]

[If no:] No problem! You can run `/getting-started` anytime. For now, try `/daily-plan` to see your day."

---

## Step 8: Phase 2 - Getting Started (Optional but Recommended)

Say: "**Step 8 of 8** — Optional guided tour."

**Trigger:** Either immediately after Step 7, OR at next session start if vault is < 7 days old.

**Purpose:** Transform "I have a system, now what?" into immediate value and confidence. This is separate from onboarding. It guides the user through their first real workflows.

**If yes (user wants to continue):** Run `/getting-started` skill (see `.claude/skills/getting-started/SKILL.md`)
- The skill will check for `pre_analysis_deferred: true` flag in `.onboarding-complete`
- If calendar is connected, it can show upcoming meetings and suggest prep
- If calendar is not connected, it focuses on task management and vault navigation
- Much better UX than blocking during finalization

**If no:** 
"No problem! You can always run `/getting-started` later when you're ready.

**Quick reference:**
- `/daily-plan` - Start your day with context
- `/meeting-prep [person]` - Prep for meetings
- `/amp-level-up` - Discover features
- `/getting-started` - Come back to this tour anytime (includes data analysis)

What would you like to work on first?"

---

## Post-Onboarding (Optional)

**If user wants to continue setup:**

Say: "Want to set up quarterly goals? These are 3-5 specific outcomes over 3 months that advance your pillars."

**If yes:**

Ask: "What are your top 3-5 goals for this quarter? These should be specific outcomes that advance your pillars."

**Then:**
1. Create `01-Quarter_Goals/Quarter_Goals.md` with their goals
2. Tag each goal to a pillar
3. Say: "✓ Goals set! You can update these anytime with `/quarter-plan`"

**If no:**
Say: "No problem! You can set them up later with `/quarter-plan`."

---

## Final Completion

After all chosen post-onboarding features are set up (or skipped):

Say: "All done! You're ready to use Amp. What would you like to work on first?"

## For Existing Notes

If user mentions they have existing notes, say: "Just copy them into the `00-Inbox/` folder and I'll help you organize them."

## Viewing Your Notes

Amp creates markdown files you can view with any app: VS Code, Cursor, Obsidian, or any text editor.
