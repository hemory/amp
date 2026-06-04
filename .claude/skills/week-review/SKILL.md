---
name: week-review
description: Review week's progress with concrete accomplishments (not fake percentages), pattern detection, and goal tracking.
context: fork
---

## Purpose

Create a synthesis of the week reviewing activity, progress, and what was accomplished. **Uses concrete metrics, not vague percentages.**

---

## Data Sources

### 1. Task Progress
- `03-Tasks/Tasks.md` — Task completion status
- `02-Week_Priorities/Week_Priorities.md` — Weekly priorities

### 2. Project Activity
- `04-Projects/**/*.md` — Modified this week

### 3. Meetings & People
- `00-Inbox/Meetings/*.md` — Meeting notes from this week
- `People/**/*.md` — Person pages updated

### 4. Learnings
- `06-Resources/Learnings/**/*.md` — Explicit learnings
- `System/Session_Learnings/*.md` — Auto-captured session learnings

### 5. Daily Reviews
- `07-Archives/Reviews/YYYY-MM-DD - Daily Review.md` — This week's reviews (fall back to `Daily_Review_YYYY-MM-DD.md` for legacy naming)

### 6. Journals (If Enabled)
- `00-Inbox/Journals/YYYY/MM-Month/` — Morning/evening journals

### 7. Slack Channels (If Enabled)
- Configured channels from `System/user-profile.yaml` > `slack_intel`
- Pulled via `gh slack-aggregator review` with weekly date range

---

## Analysis Process

### 1. Weekly Priority Completion (Concrete, Not Percentages)

**Don't say:** "Goal X went from 40% to 55%"
**Do say:** "You completed 2 of 3 weekly priorities"

```
Use: get_week_progress()
```

For each weekly priority:
- **Complete:** ✅ What was the deliverable? When did you finish?
- **In Progress:** 🔄 What specifically got done? What's left?
- **Not Started:** ❌ Why? Should it carry forward?

**Surface concrete accomplishments:**

> "**This week's priorities:**
> 
> 1. ✅ **Ship pricing page** — Complete (pushed to prod Wednesday)
>    - Deliverable: New pricing page live at /pricing
>    - Tasks completed: 5 of 5
> 
> 2. 🔄 **Write Q1 strategy doc** — 60% complete
>    - Done: Outline, competitive analysis, recommendations
>    - Remaining: Executive summary, financial projections
>    - 2 tasks left
> 
> 3. ❌ **Customer interviews** — Not started
>    - Reason: Calendar was too stacked
>    - Recommendation: Carry to next week with protected time"

### 1.5 Semantic Goal-to-Work Mapping (if QMD available)

**Check if semantic search is available** by looking for `qmd` in PATH.

If available, enhance the weekly priority review with meaning-based analysis:

1. **Auto-detect goal contributions:** For each completed task this week, search:
   ```
   qmd query "task title/description" --limit 3
   ```
   against quarterly goals. Catch tasks that advanced goals without explicit links.
   - Example: "Built customer health dashboard" semantically matches goal "Improve NPS tracking" — different words, same work.

2. **Cross-priority connections:** Search for work that bridges multiple priorities:
   ```
   qmd query "priority 1 description" --limit 5
   ```
   Surface tasks that contributed to more than one priority.

3. **Thematic patterns:** Search for recurring themes across the week's work:
   ```
   qmd query "common theme from meetings/tasks" --limit 5
   ```
   Detect patterns like "most of your work this week clustered around customer retention" even when tasks used different terminology.

**Integration:** Merge findings into the Quarterly Goals table — add a "Hidden contributions" row for semantically-detected but not explicitly-linked work. Only show genuinely new connections, not things already captured by keyword matching.

**If QMD unavailable:** Skip silently. Task completion stats still work fine.

### 2. Task Completion Stats (Concrete Numbers)

Scan `03-Tasks/Tasks.md` for completion timestamps from this week:
- Count tasks completed (look for `✅ YYYY-MM-DD` in date range)
- Count tasks added mid-week
- Count tasks carried over

**Surface:**

> "**Tasks this week:**
> - Completed: 14 tasks
> - Added mid-week: 6 tasks (scope creep?)
> - Carried over: 3 tasks
> 
> **Completion rate:** 82% (14 of 17 planned)"

### 3. Quarterly Goals Progress (Concrete Milestones)

**Don't use fake percentages.** Use milestone counts and specific accomplishments.

```
Use: get_quarterly_goals()
Use: get_goal_status(goal_id) for each goal
```

For each goal:
- Milestones completed this week
- Total milestones done vs. total
- Weeks since last milestone
- Specific accomplishments that moved the goal

> "**Quarterly Goals Progress:**
> 
> | Goal | Milestones | This Week | Status |
> |------|------------|-----------|--------|
> | Launch v2.0 | 3 of 5 | +1 (Pricing page shipped) | On track |
> | Improve NPS | 1 of 4 | No change | ⚠️ Stalled (3 weeks) |
> | Team Capacity | 2 of 3 | No change | On track |
> 
> **Goal 1** advanced because you completed Priority 1.
> **Goal 2** needs attention — no linked work completed this week."

### 4. Daily Completion Rate Trend (NEW)

If daily reviews exist, calculate completion trends:

> "**Daily plan completion this week:**
> 
> | Day | Planned | Done | Rate |
> |-----|---------|------|------|
> | Mon | 3 | 2 | 67% |
> | Tue | 3 | 3 | 100% |
> | Wed | 3 | 2 | 67% |
> | Thu | 3 | 1 | 33% |
> | Fri | 3 | 2 | 67% |
> 
> **Week average:** 67%
> **Pattern:** Thursday was rough (too many meetings?)"

### 5. Meeting Analysis

Review meeting notes from the week:
- Meetings held
- Key decisions
- Action items created
- Follow-ups that might have slipped

### 5.5 Commitment Health Analysis (NEW)

If ScreenPipe and Commitment Detection are available, show aggregate stats:

```
Use: get_commitment_stats(
    start_date="YYYY-MM-DD",  # Monday of this week
    end_date="YYYY-MM-DD"     # Today
)
```

**Surface to user:**

> "📊 **Commitment Health This Week**
>
> **Detected across apps:** 12 potential commitments
> **Already had tasks:** 7 (58%)
> **Created from prompts:** 3
> **Dismissed as handled:** 2
>
> **Apps with most uncaptured asks:**
> 1. Slack - 5 items
> 2. Email - 4 items
> 3. Notion - 3 items
>
> **People who asked most of you:**
> 1. Sarah Chen - 4 asks
> 2. Product team - 3 asks
>
> 💡 *Consider: Check Slack more frequently for asks, or run `/commitment-scan` mid-week*"

**If no commitment data:**
Skip this section silently (user may not have ScreenPipe or commitment detection enabled).

### 5.8 Email Communication Stats (if Gmail connected)

Check `System/integrations/config.yaml` for `google-workspace.enabled: true`.

If enabled and Google Workspace MCP is healthy:
- **Emails sent this week** — count of sent messages in the review period
- **Average response time** — how quickly you replied to incoming emails
- **Threads still open** — conversations with no resolution (back-and-forth still active)
- **Follow-up detection** — emails waiting > 48h for a reply from you or from others

Surface in the review:

> "**Email this week:**
>
> | Metric | Value |
> |--------|-------|
> | Emails sent | 47 |
> | Avg response time | 3.2 hours |
> | Open threads | 12 |
> | Awaiting your reply (> 48h) | 3 |
>
> **Observation:** You have 3 emails waiting for replies longer than 48 hours. Consider clearing those early next week."

If unhealthy or not enabled: skip this section silently.

### 5.9 Slack Intelligence (if configured)

Check `System/user-profile.yaml` > `slack_intel.enabled`.

If enabled and `gh slack-aggregator` is installed, run the `/slack-intel` skill workflow:

1. Pull each configured channel using `gh slack-aggregator review --channel <url> --from <monday> --to <today>`
2. Analyze exported markdown against active projects, people, and pillars
3. Categorize findings: 🎯 Action Items, 📋 Project Context, 👤 People Signals, 📊 Org Intel
4. Present findings to the user for confirmation and routing
5. Route confirmed items to tasks, project notes, person pages
6. Save summary to `00-Inbox/Slack_Intel/Week_of_YYYY-MM-DD.md`
7. Clean up temporary export files

**Full workflow details:** See `.claude/skills/slack-intel-custom/SKILL.md`

Surface in the review:

> "📡 **Slack Intelligence**
>
> **Channels scanned:** 3
> **Items found:** X action items, X project updates, X people signals
>
> [Categorized findings presented for user confirmation]"

Action items from Slack Intel feed into the "Next Week" suggestions section.

If not enabled or aggregator not installed: skip this section silently.

### 6. Learning Compilation & Pattern Detection

Review `System/Session_Learnings/` files from this week:

**Pattern Detection:**
- **Recurring issues:** Same mistake 2+ times? Suggest adding to Mistake_Patterns.md
- **Consistent preferences:** User repeatedly mentioned a workflow preference?

> "This week's session learnings revealed:
> 
> **Recurring Issues:**
> - Calendar overload (mentioned 3 times) — Consider blocking focus time
> 
> **Workflow Preferences:**
> - Prefer morning for deep work (mentioned 2 times)
> 
> Should I add these to your pattern files?"

---

## Output Format

Create `00-Inbox/YYYY-MM-DD - Weekly Synthesis.md`.

> **Dual-format lookup:** When reading previous weekly synthesis files (e.g., for trend comparison), check both the current format `00-Inbox/YYYY-MM-DD - Weekly Synthesis.md` and the legacy format `00-Inbox/Weekly_Synthesis_YYYY-MM-DD.md`. Prefer the current format if both exist.

Template:

```markdown
# Weekly Synthesis — Week of [Date]

## TL;DR

- **Weekly priorities:** [X] of 3 complete
- **Tasks:** [X] completed / [Y] planned — [Z]% completion
- **Meetings:** [N] total
- **Key wins:** [1-2 bullets]
- **Carried over:** [1-2 items]

---

## 🎯 Weekly Priorities

### 1. [Priority 1] — ✅ Complete

**Deliverable:** [What was shipped/finished]
**Completed:** [Day]
**Tasks:** 5 of 5

### 2. [Priority 2] — 🔄 In Progress (60%)

**Done this week:**
- [Specific accomplishment]
- [Specific accomplishment]

**Remaining:**
- [Specific task]
- [Specific task]

### 3. [Priority 3] — ❌ Not Started

**Why:** [Reason]
**Recommendation:** [Carry forward / Deprioritize / Defer]

---

## 📊 Task Completion

| Metric | Count |
|--------|-------|
| Tasks completed | 14 |
| Tasks added mid-week | 6 |
| Tasks carried over | 3 |
| **Completion rate** | **82%** |

**Observation:** [Any patterns — e.g., lots of scope creep]

---

## 🎯 Quarterly Goals

| Goal | Milestones | This Week | Status |
|------|------------|-----------|--------|
| [Goal 1] | X of Y | +Z | [Status] |
| [Goal 2] | X of Y | — | [Status] |
| [Goal 3] | X of Y | +Z | [Status] |

**Goals advancing:** [Which ones moved]
**Goals stalled:** [Which ones need attention]

---

## 📊 Daily Completion Trend

| Day | Planned | Done | Rate |
|-----|---------|------|------|
| Mon | 3 | 2 | 67% |
| Tue | 3 | 3 | 100% |
| Wed | 3 | 2 | 67% |
| Thu | 3 | 1 | 33% |
| Fri | 3 | 2 | 67% |

**Week average:** [X]%
**Observation:** [Pattern noticed]

---

## 📅 Meetings & People

### Meetings Held

| Date | Topic | Key Outcome |
|------|-------|-------------|
| [Day] | [Topic] | [Decision/insight] |

### New Contacts
- [Name] at [Company] — [context]

### Action Items from Meetings
- [ ] [Action] — for [who] — due [when]

---

## 📡 Slack Intelligence

*Channels: [list of channels scanned]*
*Period: YYYY-MM-DD to YYYY-MM-DD*

### Action Items Captured
- [ ] [Action] — from #[channel], [date] — [priority/pillar]

### Project Updates
- **[Project Name]:** [Key update or context from thread]

### People Signals
- **[Person]:** [Signal — role change, feedback, preference, etc.]

### Org Intel
- [Announcement or trend relevant to L&D programs]

---

## 💡 Learnings

### Session Learnings (Auto-Captured)
- [Learning 1]
- [Learning 2]

### Patterns Identified
- **Recurring issue:** [Issue] (appeared X times)
- **Preference noted:** [Preference]

### Actionable Improvements
- [ ] [Specific improvement to make]

---

## 📊 Pillar Balance

| Pillar | Tasks Done | Focus |
|--------|------------|-------|
| [Pillar 1] | X tasks | Heavy |
| [Pillar 2] | X tasks | Light |
| [Pillar 3] | X tasks | None |

**Observation:** [Balance assessment]

---

## ➡️ Next Week

### Suggested Priorities

Based on this week's progress:

1. **[Priority]** — [Why: carries over / goal needs attention / commitment]
2. **[Priority]** — [Why]
3. **[Priority]** — [Why]

### Blocked Items Needing Resolution

| Item | Blocked Since | What Would Unblock It |
|------|---------------|-----------------------|
| [Item] | [Date] | [Action needed] |

---

## 🏆 Career Evidence (If Career System Enabled)

**Significant accomplishments worth capturing:**

- [Accomplishment] — demonstrates [skill]
- [Accomplishment] — shows [impact]

> "Want to save any of these as career evidence?"

---

*Generated: [timestamp]*
*Weekly completion: X of 3 priorities*
*Task completion: X%*
```

---

## Innovation Concierge: Top 3 This Week

At the end of the weekly review, surface the top backlog ideas:

1. Call `list_ideas(status="active", min_score=70)` from Improvements MCP
2. Pick the top 3 ideas by score that haven't been surfaced in the last week review
3. Include in the output format as a section:

```markdown
## 🤖 Top 3 Amp Improvement Ideas

Your AI-curated backlog has surfaced these high-impact ideas:

1. **[idea-XXX]** Title (Score: XX)
   Why now: [Brief evidence or timeliness reason]

2. **[idea-XXX]** Title (Score: XX)
   Why now: [Brief evidence]

3. **[idea-XXX]** Title (Score: XX)
   Why now: [Brief evidence]

> Interested? Run `/amp-improve [idea-id]` to workshop any of these.
> Run `/amp-backlog` to see the full ranked backlog.
```

**Rules:**
- Only show ideas with score >= 70 (don't surface low-value noise)
- Prefer ideas with recent "Why Now?" evidence
- If fewer than 3 qualifying ideas, show however many exist
- If no qualifying ideas, skip this section entirely
- This is a gentle nudge, not a sales pitch

---

## Skill Quality Insights

After generating the synthesis, call `get_skill_ratings()` from Work MCP (no filter — get all skills).

**If ratings exist for any skills:**
Add a section to the review:

```markdown
## Skill Quality This Week

| Skill | Avg Rating | Trend | Note |
|-------|-----------|-------|------|
| [skill] | [avg]/5 | [improving/stable/declining] | [most recent note] |
```

**Only surface skills that are declining or below 3.0.** If everything is stable/good, skip this section entirely. One line for healthy, only details for problems.

**Then:** Run `/identity-snapshot` to update `System/identity-model.md` with fresh data from this week.

---

## Vault Hygiene Check (Silent)

Run the vault maintenance checker as part of the weekly review:

```bash
node .claude/hooks/maintenance.cjs
```

If any issues are found, add a section to the synthesis:

```markdown
## 🧹 Vault Hygiene

| Check | Count | Action |
|-------|-------|--------|
| Stale inbox files (>30d) | [N] | Archive or delete |
| Broken WikiLinks | [N] | Fix or remove |
| Orphaned person pages | [N] | Review for relevance |
| Stale agent memory (>90d) | [N] | Safe to clean up |
```

If all counts are zero, skip this section entirely (clean vault, nothing to report).

Only list the top 3-5 items per category. Don't overwhelm the review with maintenance details.

---

## System Improvement Scan (Proactive)

After the main synthesis, scan 7 data sources for improvement opportunities and generate a proposal file. This is the weekly intelligence layer that spots patterns across your entire workflow.

### Data Sources to Scan

**1. Session History (session_store)**

Query the session store for the past 7 days:

```sql
-- Most-used tools this week
SELECT content, source_type FROM search_index
WHERE search_index MATCH 'tool OR edit OR create OR bash'
AND source_type = 'turn'
ORDER BY rank LIMIT 20;

-- Sessions with many turns (potential friction)
SELECT s.id, s.summary, COUNT(t.turn_index) as turns
FROM sessions s JOIN turns t ON t.session_id = s.id
WHERE s.created_at >= date('now', '-7 days')
GROUP BY s.id
ORDER BY turns DESC LIMIT 5;

-- Failed tool calls or retries
SELECT content FROM search_index
WHERE search_index MATCH 'error OR failed OR retry OR broken'
AND source_type = 'turn'
ORDER BY rank LIMIT 10;
```

Look for:
- Tools called repeatedly in sequence (automation opportunity)
- Sessions with 10+ turns for a simple task (friction)
- Repeated error patterns (reliability issue)
- Files read/edited most often (hot paths worth optimizing)

**2. Usage Adoption Gaps**

Read `System/usage_log.md` and count:
- Total features available vs. checked off
- Categories with zero adoption (entire feature areas unused)
- Features checked recently vs. long ago

Compare against the user's role and pillars. Flag features that would directly help their work but haven't been tried.

**3. Skill Quality Trends**

Read `System/Skill_Ratings/ratings.jsonl` (if it exists):
- Skills with average rating below 3.0
- Skills with declining trend (last 3 ratings decreasing)
- Skills used frequently but never rated (blind spots)

If no ratings exist, note this as an observation: "No skill quality data yet. Rating skills after use helps me improve over time."

**4. File Structure Growth**

Scan key vault directories:

```bash
# File counts per top-level directory
find 00-Inbox -type f -name "*.md" | wc -l
find 04-Projects -type f -name "*.md" | wc -l
find 05-Areas -type f -name "*.md" | wc -l

# Files not touched in 60+ days
find 04-Projects 05-Areas -type f -name "*.md" -mtime +60 | head -10

# Recently created files (new growth)
find . -type f -name "*.md" -mtime -7 -not -path "./node_modules/*" -not -path "./.claude/*" | wc -l
```

Look for:
- Inbox growing faster than it's being processed (triage needed)
- Projects with no recent activity (stale projects)
- Missing expected files (no daily reviews, empty quarter goals)
- Naming inconsistencies across similar files

**5. Vault Hygiene**

Reuse the output from `maintenance.cjs` already run in this review. Don't re-run it.

**6. Hook & Tool Health**

Check `.logs/error-queue.json` for:
- Tools that errored 3+ times this week (reliability problem)
- MCP servers with unacknowledged errors
- Tools available in MCP config but never called (from session history)

Check `.claude/hooks/` for:
- Hook files that exist but aren't in `.github/hooks/hooks.json` (unwired hooks)

**7. Workflow Friction Patterns**

Use Work MCP data:

```
list_tasks(include_done=false) — check for:
  - Tasks in "started" status for 5+ days (stuck work)
  - P0 tasks open more than 3 days (urgency leak)

get_week_priorities() for last 3 weeks — check for:
  - Same priority appearing 2+ weeks (chronic carryover)
  - Priorities with no linked tasks (goal without action)

get_quarterly_goals() — check for:
  - Goals with 0% progress and weeks passing
  - Goals with no linked weekly priorities
```

### Synthesis Rules

After gathering all observations:

1. **Deduplicate against last proposal.** Read `System/Improvement_Proposals/` for the most recent file. Skip anything you suggested last week that hasn't changed.

2. **Rank by impact.** Use three tiers:
   - 🔴 **High Impact** — Directly affects daily productivity, saves significant time, or fixes broken workflows. Limit to 1-3 items.
   - 🟡 **Medium Impact** — Would improve quality of life but isn't urgent. 2-4 items.
   - 🟢 **Low Impact** — Nice to have, cosmetic, or speculative. 1-3 items.

3. **Be specific.** Every suggestion must include:
   - What you observed (with data/counts)
   - Why it matters (concrete impact)
   - What to do about it (actionable fix, not vague advice)
   - Effort estimate (quick win / medium / deep work)
   - Files affected

4. **Don't be noisy.** If fewer than 3 total observations are worth flagging, that's fine. "Nothing new to suggest this week" is a valid outcome. Don't pad with low-value filler.

5. **Auto-capture high-impact items.** For any 🔴 High Impact suggestion, call `capture_idea()` from the Improvements MCP to add it to the formal backlog (with dedup check).

### Output

Write the proposal to `System/Improvement_Proposals/YYYY-MM-DD.md`:

```markdown
# System Improvement Proposal — Week of YYYY-MM-DD

## Summary

[2-3 sentences: X opportunities found across Y categories. Z are quick wins.]

---

## 🔴 High Impact

### 1. [Clear, specific title]

**What I noticed:** [Concrete observation with data. E.g., "You ran `lookup_person` 14 times this week, but the person context injector hook should be doing this automatically."]

**Why it matters:** [Impact. E.g., "Each manual lookup costs ~5 seconds of context. The hook would make this invisible."]

**Suggested fix:** [Specific action. E.g., "Fix the path in person-context-injector.cjs from 'People/' to '05-Areas/People/'. I can do this now."]

**Effort:** Quick win
**Files:** `.claude/hooks/person-context-injector.cjs`

---

## 🟡 Medium Impact

### 2. [Title]
...

---

## 🟢 Low Impact

### 3. [Title]
...

---

## 📊 System Health Snapshot

| Metric | This Week | Trend |
|--------|-----------|-------|
| Tasks completed | X | ↑/↓/→ |
| Skills invoked | X unique | |
| Tool errors | X | |
| Vault files | X total | |
| Inbox backlog | X files | |

---

## Skipped

[Brief list of things you considered but decided weren't worth flagging, with one-line reasoning. This shows your work and helps the user understand your judgment.]
```

Open the file in Obsidian after writing:
```bash
source scripts/obsidian-cli.sh && obs_open "YYYY-MM-DD"
```

### Presentation to User

After generating the proposal, add a brief section to the week-review output:

```
## 🔬 System Improvement Proposal

Generated `System/Improvement_Proposals/YYYY-MM-DD.md` with [N] suggestions:
- 🔴 [count] high impact: [one-line summary of top item]
- 🟡 [count] medium impact
- 🟢 [count] low impact

[Opened in Obsidian for review.]
```

If no improvements were found: "System scan complete. Nothing new to suggest this week."

---

## Follow-up Actions

After synthesis:
1. Update Tasks.md with new priorities
2. Archive completed items
3. Update project pages with status changes
4. Offer to run `/week-plan` for next week

---

## MCP Dependencies

| Integration | MCP Server | Tools Used |
|-------------|------------|------------|
| Work | work-mcp | `list_tasks`, `get_week_progress`, `get_quarterly_goals`, `get_goal_status` |
| Calendar | calendar-mcp | `calendar_get_events_with_attendees` |
| Improvements | amp-improvements-mcp | `list_ideas` |
| Analytics | amp-analytics | `track_event` |

---

## Track Usage (Silent)

Update `System/usage_log.md` to mark weekly review as used.

**Analytics (Silent):**

Call `track_event` with event_name `week_review_completed` and properties:
- `priorities_completed`: number of priorities completed
- `priorities_total`: total number of priorities
- `tasks_completed`: number of tasks completed this week. This only fires if the user has opted into analytics. No action needed if it returns "analytics_disabled".
