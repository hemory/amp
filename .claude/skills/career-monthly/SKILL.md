---
name: career-monthly
description: Monthly reflection that spots patterns, trends, and growth areas across recent work
---

## Purpose

Analyze patterns across recent work to generate a monthly reflection. Identifies recurring themes, skill development trends, productivity patterns, and focus recommendations for the month ahead.

## Prerequisites

Run `/career-setup` first to establish baseline (job description, career ladder, latest review, growth goals).

## File Paths

- **Output:** `05-Areas/Career/Reflections/YYYY-MM - Monthly Reflection.md`
- **Evidence:** `05-Areas/Career/Evidence/`
- **Growth Goals:** `05-Areas/Career/Growth_Goals.md`
- **Career Ladder:** `05-Areas/Career/Career_Ladder.md`
- **User Profile:** `System/user-profile.yaml`

## Career MCP Integration

This mode uses **Career MCP tools** for data aggregation:
- `scan_evidence(date_range: "last-30-days")` — Get recent evidence
- `timeline_analysis(period: "last-6-months", group_by: "month")` — See trends over time

MCP tools provide structured data; you interpret and coach.

## Coach Personality

Adapt coaching style based on `System/user-profile.yaml` > `communication.career_level`:

| Level | Style | Focus |
|-------|-------|-------|
| Junior (0-3 yrs) | Encouraging | Learning, confidence building |
| Mid (3-7 yrs) | Collaborative | Ownership, impact measurement |
| Senior (7+ yrs) | Challenging | Strategy, scaling, systems-thinking |
| Leadership/C-Suite | Challenging | Team development, org impact |

User's explicit `coaching_style` preference overrides defaults.

### Role-Specific Emphasis

- **Product Managers:** User impact, prioritization, cross-functional influence
- **Engineers:** Technical depth, system design, mentorship
- **Designers:** User experience, design systems, stakeholder communication
- **Managers:** Team development, culture, delegation

---

## Process

### Phase 1: Brain Dump

Accept whatever the user shares about their month. If they start with nothing, prompt:

```markdown
## Monthly Reflection Session

**Let's look at the bigger picture.** Tell me about your month:
- What themes or patterns are you noticing?
- Any projects that shifted direction?
- Where did you grow? Where did you struggle?
- What's top of mind as you look ahead?

Just share what comes to mind — I'll pull in your evidence data to spot patterns.
```

### Phase 2: Clarifying Questions

Ask **3-5 targeted questions** to fill gaps. Adapt to career level:

**Early Career:** "What was the biggest thing you learned this month?" "What would you do differently?"
**Mid Career:** "What trade-offs did you navigate?" "How did you influence outcomes?"
**Senior:** "What's the 6-month play here?" "What patterns are you seeing across the team?"

Focus areas:
1. **Recurring Themes** — What kept coming up?
2. **Skill Development** — Where did you stretch? Where are you plateauing?
3. **Productivity** — What's working? What's draining?
4. **Relationships** — How are key relationships evolving?

Ask conversationally, 2-3 at a time. Wait for answers before follow-ups.

### Phase 3: Gather Data

Call Career MCP tools:
```
scan_evidence(date_range: "last-30-days")
timeline_analysis(period: "last-6-months", group_by: "month")
```

Interpret the aggregated data to identify patterns, then generate:

### Phase 4: Generate Reflection

```markdown
# Monthly Reflection — [MONTH YEAR]

**Date:** YYYY-MM-DD

---

## Overview

[High-level summary of the month's work and themes]

---

## Recurring Themes

### [Theme 1]
**What I noticed:** [Pattern observed]
**Why it matters:** [Significance]
**Examples:**
- [Instance 1]
- [Instance 2]
- [Instance 3]

### [Theme 2]
**What I noticed:** [Pattern observed]
**Why it matters:** [Significance]
**Examples:**
- [Instance 1]
- [Instance 2]

---

## Skill Development Trends

### Skills Strengthening
- **[Skill 1]:** [Evidence of growth]
- **[Skill 2]:** [Evidence of growth]
- **[Skill 3]:** [Evidence of growth]

### Skills to Focus On
- **[Skill 1]:** [Why this needs attention]
- **[Skill 2]:** [Why this needs attention]

---

## Productivity Patterns

### What's Working Well
- [Pattern 1]
- [Pattern 2]
- [Pattern 3]

### What Needs Adjustment
- [Pattern 1] → [Suggested change]
- [Pattern 2] → [Suggested change]

---

## Focus Recommendations

Based on this month's patterns, here are 2-3 areas to prioritize next month:

1. **[Focus Area 1]**
   - Why: [Rationale]
   - How: [Specific approach]

2. **[Focus Area 2]**
   - Why: [Rationale]
   - How: [Specific approach]

3. **[Focus Area 3]**
   - Why: [Rationale]
   - How: [Specific approach]

---

## Action Items

Specific steps for next month:

- [ ] [Action 1]
- [ ] [Action 2]
- [ ] [Action 3]
- [ ] [Action 4]

---

## Reflections & Notes

[Space for user's own thoughts and observations]

---

*This reflection synthesizes patterns from daily reviews, meeting notes, and career evidence captured in Amp.*
```

### Phase 5: Post-Reflection

```markdown
## ✅ Monthly Reflection Complete

**Saved to:** `05-Areas/Career/Reflections/YYYY-MM - Monthly Reflection.md`

**Suggested Actions:**
- Review this at the start of next month
- Share relevant insights with your manager in your next 1:1
- Update `Growth_Goals.md` if priorities have shifted

**Want to revise any section?**
```

---

## Post-Session: Evidence Capture

If the session revealed achievements or skills development:

```markdown
## Capture Career Evidence?

Based on what you shared, I noticed:
- [Achievement/skill 1]
- [Achievement/skill 2]

**Want me to save these to `05-Areas/Career/Evidence/`?**
```

### Evidence Templates

**Achievement:** `05-Areas/Career/Evidence/YYYY-MM-DD - [Achievement Name].md`

```markdown
# [Achievement Name]

**Date:** YYYY-MM-DD
**Project:** [Project name]
**Category:** [Impact / Technical / Leadership]

## What I Did
[Description]

## Impact
- [Measurable outcome 1]
- [Measurable outcome 2]

## Skills Demonstrated
- [Skill 1]
- [Skill 2]

## Ladder Alignment
**Maps to:** [Career ladder competency]
```

**Skill Development:** `05-Areas/Career/Evidence/YYYY-MM-DD - [Skill] Development.md`

```markdown
# [Skill Name] Development

**Date:** YYYY-MM-DD

## What I'm Learning
[Description and why it matters]

## Recent Examples
### [Example 1]
**Project:** [Project name]
**What I did:** [How I applied/practiced]
**Outcome:** [What happened]

## Growth Over Time
**Where I started:** [Baseline]
**Where I am now:** [Current state]
**Where I'm going:** [Target state]
```

---

## Update Growth Goals

If the session revealed new priorities:

```markdown
## Update Growth Goals?

It sounds like [NEW PRIORITY] is becoming important.
Want me to add this to `05-Areas/Career/Growth_Goals.md`?
```

---

## Conversation Style

- **Connect dots** — "You mentioned X last week and Y today — I'm seeing a pattern..."
- **Reframe** — "What if you looked at this as an opportunity to..."
- **Challenge** — "Is this the right problem to solve, or a symptom of something bigger?"

---

## Quality Checks

Before finalizing output:
- [ ] Specific examples with measurable outcomes (not vague)
- [ ] Honest assessment (not inflated or understated)
- [ ] Connected to career ladder competencies where relevant
- [ ] Actionable next steps (not just observations)
- [ ] Appropriate tone for career level

---

## Track Usage (Silent)

Update `System/usage_log.md` to mark career coaching as used.

Call `track_event` with event_name `career_coach_session` and properties:
- `mode`: "monthly"

This only fires if the user has opted into analytics.
