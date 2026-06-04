---
name: daily-plan
description: Generate context-aware daily plan with calendar, tasks, and priorities. Includes midweek awareness, meeting intelligence, commitment tracking, and smart scheduling suggestions.
context: fork
---

## Purpose

Generate your daily plan with full context awareness. Automatically gathers information from your calendar, tasks, meetings, relationships, and weekly progress to create a focused plan with genuine situational awareness.

## Usage

- `/daily-plan` — Create today's daily plan
- `/daily-plan tomorrow` — Plan for tomorrow (evening planning)
- `/daily-plan --setup` — Re-run integration setup

**Batch limit:** Include at most 20 calendar events and 20 tasks in a single plan. Summarize overflow items as a count.

---

## Tone Calibration

Before executing this command, read `System/user-profile.yaml` → `communication` section and adapt tone accordingly (see CLAUDE.md → "Communication Adaptation").

---

## Step 0: Demo Mode Check

Before anything else, check if demo mode is active:

1. Read `System/user-profile.yaml`
2. Check `demo_mode` value
3. **If `demo_mode: true`:**
   - Display banner: "Demo Mode Active — Using sample data from System/Demo/"
   - Use demo paths and skip live integrations
4. **If `demo_mode: false`:** Proceed normally

---

## Step 0.5: Prerequisite Check — Calendar

Before generating the plan, check if calendar integration is configured:
- Look for a `calendar_integration` key in `System/user-profile.yaml`
- OR check if calendar MCP tools are available (e.g., `calendar_get_today`)

**If calendar is NOT configured**, add this note at the start of the plan output (before the greeting):

> 💡 **Calendar integration available.** Your daily plan can include meetings and prep suggestions. Options:
> - **Apple Calendar** (direct) — Fast, uses AppleScript
> - **Apple Calendar via EventKit** — More reliable, needs permissions
> - **Google Calendar** — For Google Workspace users
>
> Run `/calendar-setup` to connect.

**If calendar IS configured**, skip this note entirely. This hint is informational and does not block plan generation.

---

## Step 1: Background Checks (Silent)

Run these silently without user-facing output:

1. **Update check**: `check_for_updates(force=False)` - store notification if available
2. **Self-learning checks**: Run changelog and learning review scripts if due
3. **Search index refresh**: Run `qmd update && qmd embed` to refresh vault search index with any overnight changes (meetings processed, files edited, etc.). If `qmd` is not installed, skip silently.
4. **People index refresh**: Call `build_people_index` from Work MCP. This keeps the People Directory current so person lookups throughout the day are fast. Takes <2 seconds.
5. **Innovation synthesis** (silent): Call `synthesize_changelog()` and `synthesize_learnings()` from Improvements MCP. These run in background and populate the backlog — results are surfaced in Step 1.5 below.
6. **Granola migration check** (silent): Run `node .scripts/meeting-intel/check-granola-migration.cjs 2>/dev/null || echo '{"status":"not_applicable"}'`. If status is `migration_available`, store this fact and append a brief note at the END of the daily plan output (after all other sections): *"Granola now syncs phone recordings too. Run `/process-meetings` to set it up."* If the script does not exist or returns any other status, skip silently. Never interrupt the planning flow for this check.

---

## Step 1.5: Innovation Spotlight (Concierge)

After background checks complete, check for noteworthy backlog activity:

1. Call `list_ideas(status="active", min_score=70)` from Improvements MCP
2. Check `System/.synthesis-state.json` for recent synthesis activity (last 7 days)
3. If there are AI-authored or recently enriched ideas, pick the most impactful one

**Surface as a brief spotlight in the plan output (1-2 lines max):**

> **Innovation Spotlight:** Claude Code shipped native memory (v2.1.32) — this could simplify idea-006 (Session Memory MCP). Run `/amp-improve idea-006` to explore.

**Rules:**
- Show at most 1 spotlight per daily plan (don't overwhelm)
- Rotate through ideas — don't show the same one twice in a row
- Only show if there's genuine "Why Now?" urgency (new evidence in last 7 days)
- If no recent synthesis activity, skip this section entirely
- Never block the plan for this — it's a helpful aside, not a gate

---

## Step 2: Morning Journal Check (If Enabled)

If `journaling.morning: true` in user-profile.yaml, check for today's morning journal and prompt if missing.

---

## Step 3: Monday Weekly Planning Gate

If today is Monday and week isn't planned, offer to run `/week-plan` first.

---

## Step 4: Yesterday's Review Check (Soft Gate)

Check for yesterday's review and extract context (open loops, tomorrow's focus, blocked items).

---

## Step 5: Context Gathering (ENHANCED)

Gather context from all available sources. **This is where the magic happens.**

### 5.1 Midweek Progress Check (NEW)

```
Use: get_week_progress()
```

This is critical for genuine situational awareness. Extract:
- Day of week and days remaining
- Weekly priority status (complete / in_progress / not_started)
- Warnings for priorities with no activity

**Surface this prominently:**

> "It's **Wednesday**. Here's where you are on this week's priorities:
> 
> 1. ✅ **Ship pricing page** — Complete (finished Monday)
> 2. 🔄 **Review proposal** — In progress (2 of 5 tasks done)
> 3. ⚠️ **Customer interviews** — Not started (no activity yet)
> 
> You have 2 days left this week. Priority 3 needs attention."

### 5.2 Calendar Capacity Analysis (NEW)

```
Use: analyze_calendar_capacity(days_ahead=1, events=[...from calendar MCP...])
```

Understand the *shape* of today:

- **Day type**: stacked / moderate / open
- **Meeting count and hours**
- **Free blocks available**
- **Recommendation**: What kind of work fits today

**Surface this:**

> "📅 **Today's shape:** Moderate (4 meetings, 3 hours total)
> 
> **Free blocks:**
> - 8:00-9:30 AM (90 min) — Morning focus time
> - 2:00-4:00 PM (120 min) — Afternoon block
> 
> **Recommendation:** Good for medium tasks and meeting prep. Deep work fits the 2-4pm block."

### 5.3 Meeting Intelligence (NEW)

For each meeting today:

```
Use: get_meeting_context(meeting_title="...", attendees=[...])
```

Get genuine context, not just attendee names:
- **Related project**: What project is this connected to?
- **Project status**: What's outstanding? What's blocked?
- **Outstanding tasks with attendees**: What do you owe them? What do they owe you?
- **Prep suggestions**: What should you review before this meeting?

**Surface this with surprise and delight:**

> "📍 **Meeting: [Meeting Title]** (2pm with [Attendee 1], [Attendee 2])
> 
> **Related project:** [Project Name]
> - Status: On track, but [section] still in draft
> - Outstanding: You owe [Attendee 1] the [deliverable]
> 
> **Prep suggestion:** Review [relevant doc], prepare [talking points]. Block 30 min before this meeting?"

### 5.4 Commitment Tracking (NEW)

```
Use: get_commitments_due(date_range="today")
```

Surface things you said you'd do:

> "⚡ **Commitments due today:**
> 
> - You told [Person] you'd get back to them by Wednesday (from Monday 1:1)
> - Follow up on [deliverable] (from [meeting name])"

### 5.5 Task Scheduling Suggestions (NEW)

```
Use: suggest_task_scheduling(include_all_tasks=False, calendar_events=[...])
```

Match tasks to available time based on effort classification:

> "📋 **Scheduling suggestions:**
> 
> | Task | Effort | Suggested Time |
> |------|--------|----------------|
> | Write Q1 strategy doc | Deep work (2-3h) | Tomorrow (you have a 3h morning block) |
> | Review [Person]'s proposal | Medium (1h) | Today 2-3pm (before [meeting]) |
> | Reply to [Person] | Quick (15min) | Between meetings |
> 
> ⚠️ **Heads up:** You have 2 deep work tasks but today's too fragmented. Consider protecting tomorrow morning."

### 5.6 Semantic Context Enrichment (if QMD available)

**This step runs automatically when QMD is installed via `/enable-semantic-search`.** It adds a semantic search layer on top of the standard context gathering to surface connections that keyword search misses.

Check if QMD MCP tools are available by calling `qmd_status`. **If available:**

1. **For each meeting today**, run:
   ```
   qmd_search(query="[meeting topic] [attendee names]", limit=3)
   ```
   Surface: past discussions, related decisions, relevant commitments that share **meaning** but not keywords with this meeting. Example: a meeting about "customer onboarding" finds notes about "activation rates" and "time to value".

2. **For each weekly priority that's lagging**, run:
   ```
   qmd_search(query="[priority description]", limit=3)
   ```
   Surface: vault content that advances or relates to this priority but wouldn't appear in a keyword search. Especially useful for finding forgotten context about stalled work.

3. **Cross-topic connection scan:**
   ```
   qmd_search(query="[today's key themes combined]", limit=5)
   ```
   Surface: unexpected connections between today's meetings, tasks, and priorities. This is where semantic search shines — finding that a 2pm customer call relates to a PRD you wrote last month using completely different terminology.

4. **Merge with existing context** — only add genuinely new insights. Don't duplicate what Steps 5.1-5.5 already found. Mark semantic results with their source so the plan output can distinguish them.

**What this enables in the plan output:**
- Meeting context sections include "**Also relevant:**" with thematically related past discussions
- Priority recommendations cite relevant vault content discovered by meaning
- "Heads Up" section catches connections between seemingly unrelated items
- Focus recommendations are informed by deeper vault knowledge

**If QMD is not available:** Skip silently. Steps 5.1-5.5 and 5.7 provide full context via standard methods.

---

### 5.7 Todoist Completion Sync (Amp Today → Amp)

Check if any tasks were completed in Todoist since the last plan:

```
Use: todoist-mcp-listTasks(filter="@amp & completed")
```

For each completed item:
- Match to a Amp task by title
- Update task status via Work MCP: `update_task_status(task_title="...", status="d")`
- Surface what was synced:

> "📱 **Synced from Todoist:**
> - ✅ "Follow up with [contact]" — marked done in Amp"

**If nothing to sync:** Skip silently.

### 5.8 Email Intelligence (if Gmail connected)

Check `System/integrations/config.yaml` for `google-workspace.enabled: true`.

If enabled and MCP healthy:
1. Get unread count and priority emails from monitored labels
2. Flag emails needing reply (> 48h since received, from key contacts in `05-Areas/People/`)
3. Surface email threads with today's meeting attendees

Include in plan:

> "Email: [X] unread, [Y] need replies. [Z] threads with today's meeting attendees."

If unhealthy: skip silently (graceful degradation -- no error to user).

### 5.9 Teams Intelligence (if Teams connected)

Check `System/integrations/config.yaml` for `teams.enabled: true`.

If enabled and MCP healthy:
1. Get unread messages from priority channels
2. Surface DMs needing response
3. Check for mentions

Include in plan:

> "**Teams:** [X] unread chats, [Y] mentions. [Z] threads with today's meeting attendees."

If BOTH Slack and Teams enabled:
- Show both digests, clearly labeled: "**Slack:** ..." and "**Teams:** ..."
- Deduplicate if the same person appears in both (merge context, label the source)
- Present side by side in the plan output under a combined "Chat Intelligence" heading

If unhealthy: skip silently (graceful degradation -- no error to user).

### 5.10a Mobile Capture Check (Apple Reminders)

Check for reminders created on iPhone/Watch that need triage into Amp:

```
Use: pull_new_captures() from reminders MCP
```

If items found, surface:

> 📱 **Captured in Apple Reminders** (3 items):
>
> 1. "Follow up with Peter about roadmap"
> 2. "Look into Rovo for in-app guides"
> 3. "Send Anastasia the productized offering doc"
>
> **Triage these now?** I'll help assign pillars and priorities.

**Triage flow:**
- Present each item
- Infer pillar (using existing smart pillar inference)
- Confirm with user
- Create task via Work MCP `process_inbox_with_dedup`
- After task is created with a task_id, update the reminder's notes to include `^task-ID` by deleting and recreating it (or note the association)
- Alternatively, delete the phone-captured reminder and let the new Amp task sync create a proper one

**If nothing to sync:** Skip silently.

### 5.10a.2 Reminders Completion Sync (Apple Reminders → Amp)

Check if any tasks were completed in Apple Reminders since the last plan:

```
Use: pull_completed_reminders() from reminders MCP
```

For each completed item that has an Amp task ID:
- Update task status via Work MCP: `update_task_status(task_id="...", status="d")`
- Surface what was synced:

> "📱 **Synced from Apple Reminders:**
> - ✅ "Follow up with Nick Liffen" — marked done in Amp"

**If nothing to sync:** Skip silently.

### 5.10a.3 Todoist Capture Check (Todoist Inbox)

```
Use: todoist-mcp-listTasks(filter="@amp & no date")
```

If items found, surface:

> 📱 **Captured in Todoist** (3 items):
>
> 1. "Follow up with Peter about roadmap"
> 2. "Look into Rovo for in-app guides"
> 3. "Send Anastasia the productized offering doc"
>
> **Triage these now?** I'll help assign pillars and priorities.

**Triage flow:**
- Present each item
- Infer pillar (using existing smart pillar inference)
- Confirm with user
- Create task via Work MCP `process_inbox_with_dedup`
- Complete the Todoist item via `todoist-mcp-completeTask`

**If no items found:** Skip silently (no "0 items captured" noise).

### 5.10b Standard Context Gathering

Also gather:
- **Calendar**: Today's meetings with times and attendees
- **Tasks**: P0, P1, started-but-not-completed, overdue
- **Week Priorities**: This week's Top 3
- **Work Summary**: Quarterly goals context (if enabled)
- **People**: Context for meeting attendees
- **Self-Learning Alerts**: Changelog updates, pending learnings

---

## Step 6: Synthesis

Combine all gathered context into actionable recommendations:

### Focus Recommendation

Generate 3 recommended focus items based on:
- P0 tasks (highest weight)
- Weekly priority alignment (especially lagging priorities!)
- Meeting prep needs
- Commitments due

**The system should actively recommend, not just list:**

> "Based on your week progress and today's shape, I recommend focusing on:
> 
> 1. **Prep for [meeting]** — Priority 2 is lagging and this meeting is critical
> 2. **Reply to [Person]** — Commitment due today
> 3. **Task X from Priority 1** — Keeps momentum on your shipped priority"

### Meeting Prep (Enhanced)

For each meeting, show:
- Who's attending + People/ context
- Related project status
- Outstanding tasks with attendees
- Suggested prep time and what to prepare

### Heads Up (Enhanced)

Flag potential issues:
- Weekly priorities with no activity (midweek warning)
- Commitments due today
- Back-to-back meetings
- P0 items with no time blocked
- Deep work tasks with no suitable slot this week

---

## Step 6.5: Daily Plan Greeting

Start each daily plan with a context-aware greeting as the FIRST line of output, before any content sections. Read the user's name from `System/user-profile.yaml` and use it naturally (e.g., "[Name],..." or "..., [Name]."). If no name is available, omit it.

Choose ONE greeting based on the most relevant context signal. **Priority order:** Day-specific > Calendar load > Task state. Never stack multiple greetings.

**Day-specific:**
- Monday → "New week, [Name]. Here's what's carrying over and what's fresh."
- Friday → "It's Friday, [Name]. Let's close the week strong."
- Wednesday/Thursday → "Midweek check, [Name]. How's the week shaping up against your priorities?"

**Calendar-based (if calendar data available from Step 5.2):**
- 4+ meetings → "Packed schedule today, [Name]. Let's make sure you're prepped for the ones that matter."
- 0-1 meetings → "Light on meetings today. Good window for deep work."

**Task-based (from Step 5.5 / 5.10b):**
- Overdue or rolled-over tasks from yesterday → "A few things carried over, [Name]. Let's figure out what still matters."
- No carryover (clean slate) → "Clean slate today. What do you want to move forward?"

**Tone rules:**
- Direct and warm. Think colleague, not cheerleader.
- No exclamation marks. No "Have a great day!" or "Let's crush it!" energy.
- The greeting should feel like a quick read on the day, not a motivational poster.

---

## Step 7: Generate Daily Plan

Create `00-Inbox/Plans/YYYY-MM-DD - Daily Plan.md` (ensure the `00-Inbox/Plans/` folder exists first):

```markdown
---
date: YYYY-MM-DD
type: daily-plan
integrations_used: [calendar, tasks, people, work-intelligence]
---

# Daily Plan — {{Day}}, {{Month}} {{DD}}

> {{Context-aware greeting from Step 6.5}}

## TL;DR
- {{1-2 sentence summary including week progress}}
- {{X}} meetings today, day is {{stacked/moderate/open}}
- {{Key focus area based on week priorities}}

---

## 📊 Week Progress (Midweek Check)

**Day {{X}} of 5** — {{days_remaining}} days left this week

| Priority | Status | Notes |
|----------|--------|-------|
| {{Priority 1}} | ✅ Complete | Finished {{day}} |
| {{Priority 2}} | 🔄 In progress | {{X}} of {{Y}} tasks done |
| {{Priority 3}} | ⚠️ Not started | Needs attention |

**This week's focus:** {{Recommendation based on lagging priorities}}

---

## 📅 Today's Shape

**Day type:** {{stacked/moderate/open}} ({{X}} meetings, {{Y}} hours)

**Free blocks:**
- {{Time range}}: {{Size}} — {{Recommended use}}

**Best for:** {{Quick tasks only / Medium tasks / Deep work opportunity}}

---

## ⚡ Commitments Due Today

- [ ] {{Commitment}} — from {{source}}
- [ ] {{Commitment}} — from {{source}}

---

## 🎯 Today's Focus

**If I only do three things today:**

1. [ ] {{Focus item 1}} — {{Pillar}} *(supports Week Priority #X)*
2. [ ] {{Focus item 2}} — {{Pillar}} *(supports Week Priority #Y)*
3. [ ] {{Focus item 3}} — {{Pillar}}

---

## 📍 Meetings (with Context)

### {{Time}} — {{Meeting Title}}

**Attendees:** {{Names}}
**Related project:** {{Project name}} ({{status}})
**Outstanding with them:**
- {{Task/commitment}}

**Prep needed:** {{What to review/prepare}}
**Suggested prep time:** {{Block X min before}}

---

### {{Time}} — {{Meeting Title}}

[Repeat for each meeting]

---

## 📋 Task Scheduling

| Task | Effort | Suggested Slot | Reason |
|------|--------|----------------|--------|
| {{Task}} | Deep work | {{Day/time}} | {{Reason}} |
| {{Task}} | Medium | {{Day/time}} | {{Reason}} |
| {{Task}} | Quick | Between meetings | Batch these |

{{If deep work capacity warning}}
> ⚠️ You have {{X}} deep work tasks but only {{Y}} suitable slots this week. Consider protecting time or deferring.

---

## ⚠️ Heads Up

- {{Warning about lagging weekly priority}}
- {{Commitment due today}}
- {{Back-to-back meetings}}
- {{Other flags}}

---

*Generated: {{timestamp}}*
*Week progress: {{X}}/{{Y}} priorities on track*
```

---

## Step 7.5: Push Focus Tasks to Apple Reminders

After generating the plan, push today's P0 and P1 focus tasks to Apple Reminders for iPhone/Watch visibility:

1. **Push today's focus items:**
   For each P0/P1 task in today's focus:
   ```
   Use: sync_tasks_to_reminders(tasks=[
       {"title": "Task title", "task_id": "task-YYYYMMDD-XXX", "priority": "high", "notes": "From daily plan focus", "due_date": "YYYY-MM-DD"}
   ]) from reminders MCP
   ```
   Priority mapping: P0/P1 → high, P2 → medium, P3 → low

2. **Confirm silently:**
   > "📱 Pushed 3 focus tasks to Apple Reminders (syncs to iPhone/Watch)"

**If Reminders MCP unavailable:** Skip silently.

---

## Step 7.5b: Push Focus Tasks to Todoist (if configured)

After generating the plan, push today's P0 and P1 focus tasks to Todoist for mobile access:

1. **Push today's focus items:**
   For each P0/P1 task in today's focus:
   ```
   Use: todoist-mcp-createTask(
       content="Task title",
       description="From Amp daily plan",
       dueDate="YYYY-MM-DD",
       labels=["amp"]
   )
   ```

2. **Confirm silently:**
   > "📱 Pushed 3 focus tasks to Todoist"

**If Todoist MCP unavailable:** Skip silently.

---

## Step 7.6: Create Today's Drop Zone

After generating the daily plan, ensure today's drop zone document exists:

1. Check if `00-Inbox/Drop_Zone/YYYY-MM-DD - Drop Zone.md` exists (also check legacy `00-Inbox/Drop_Zone/YYYY-MM-DD-Drop-Zone.md`)
2. **If neither exists**, create it with this template:

```markdown
# Drop Zone — YYYY-MM-DD

Paste screenshots, Slack messages, links, quick notes here.
Run `/capture` to have Amp process and route these items.

---

```

3. Open the drop zone in Obsidian:

```bash
open "obsidian://open?vault=amp&file=00-Inbox%2FDrop_Zone%2FYYYY-MM-DD%20-%20Drop%20Zone"
```

4. **If it already exists**, skip creation but still open it in Obsidian.

5. Append this line to the daily plan output (after the plan content, before the generated timestamp):

> 📋 Drop zone ready — paste screenshots, links, and notes in Obsidian. Run `/capture` when you want me to process them.

---

## Step 7.7: Milestone Check

After generating the plan, check for milestone thresholds. Show ONE milestone max per session (pick the most impressive one).

**Data sources:**
1. Read `System/usage_log.md` for feature usage and tracking metadata (e.g., `First daily plan` date)
2. Count vault files: `find . -name "*.md" -not -path "./node_modules/*" | wc -l`
3. Count completed tasks in `03-Tasks/Tasks.md` (lines matching `- [x]`)
4. Count meeting files in `00-Inbox/Meetings/`
5. Count person pages in `05-Areas/People/`
6. Calculate daily plan streak from `00-Inbox/Plans/` and `07-Archives/Plans/` (consecutive days with a plan file in either location)

**Thresholds:**
- Daily plan streak: 7, 14, 30, 60, 90 consecutive days
- Tasks completed: 25, 50, 100, 200, 500 lifetime
- Meetings processed: 10, 25, 50, 100
- Person pages: 10, 25, 50
- Vault notes: 100, 200, 500

**Format:** Single line at the very end of the plan output, not blocking:
- "📈 14 days of daily plans. The system is compounding."
- "🎯 50 tasks completed this quarter."
- "Your vault just crossed 200 notes."

**Tone:** Observational, not celebratory. Think "noting momentum" not "throwing a party."

**Rules:**
- Only show when a NEW threshold is crossed (not every day)
- Max one milestone per session
- If no threshold crossed, show nothing (no filler)
- Check `System/usage_log.md` for a `## Milestones Shown` section. If the threshold was already shown there, skip it.
- After showing a milestone, append it to `System/usage_log.md` under `## Milestones Shown`:
  ```
  - YYYY-MM-DD: [threshold name] ([value])
  ```

---

## Step 8: Track Usage (Silent)

Update `System/usage_log.md` to mark daily planning as used.

**Analytics (Silent):**

Call `track_event` with event_name `daily_plan_completed` and properties:
- `meetings_count`: number of meetings today
- `tasks_surfaced`: number of tasks shown
- `priorities_count`: number of priorities

This only fires if the user has opted into analytics. No action needed if it returns "analytics_disabled".

---

## Graceful Degradation

The plan works at multiple levels:

### Fresh Vault (First Day)
If the vault is less than 1 day old OR there are no tasks, no meetings, and no weekly priorities:
- Acknowledge it: "Your vault is brand new, so today's plan is lightweight. It will get richer as you add data."
- Suggest concrete next steps instead of showing empty sections:
  1. Create 2-3 tasks: "What are you working on today?" and create them via Work MCP
  2. Set weekly priorities: "Run `/week-plan` to set this week's focus"
  3. Connect your calendar: remind them of the choice they made during onboarding
- Still generate the daily plan file, but fill focus items with the setup tasks above

### Full Context (All MCPs available)
- Complete week progress, meeting intelligence, scheduling suggestions
- Maximum "surprise and delight"

### Partial Context (Work MCP only)
- Week progress and task scheduling
- No meeting context (prompt user to add manually)

### Minimal Context (No MCPs)
- Interactive flow asking about priorities
- Basic daily note

---

## MCP Dependencies (Updated)

| Integration | MCP Server | Tools Used |
|-------------|------------|------------|
| Calendar | calendar-mcp | `calendar_get_today`, `calendar_get_events_with_attendees` |
| Apple Reminders | reminders-mcp | `sync_tasks_to_reminders`, `pull_completed_reminders`, `pull_new_captures`, `complete_reminder_by_task_id` |
| Todoist | todoist-mcp | `listTasks`, `createTask`, `completeTask` |
| Work | work-mcp | `list_tasks`, `get_week_progress`, `get_meeting_context`, `get_commitments_due`, `analyze_calendar_capacity`, `suggest_task_scheduling` |
| Improvements | amp-improvements-mcp | `synthesize_changelog`, `synthesize_learnings`, `list_ideas` |
| Google Workspace | google-workspace-mcp | Gmail query, email search (if enabled) |
| Teams | teams-mcp | `teams_list_chats`, `teams_search_messages`, `teams_health_check` (if enabled) |