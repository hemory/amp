---
name: career-promotion
description: Evaluate promotion readiness against your career ladder with gap analysis and action plan
---

## Purpose

Compare demonstrated competencies against your career ladder to assess promotion readiness. Generates a detailed gap analysis, strengths alignment, development plan, and manager conversation prep.

## Prerequisites

Run `/career-setup` first to establish baseline (job description, career ladder, latest review, growth goals).

## File Paths

- **Output:** `05-Areas/Career/Assessments/YYYY-MM-DD - Promotion Assessment.md`
- **Evidence:** `05-Areas/Career/Evidence/`
- **Growth Goals:** `05-Areas/Career/Growth_Goals.md`
- **Career Ladder:** `05-Areas/Career/Career_Ladder.md`
- **User Profile:** `System/user-profile.yaml`

## MCP Integration

### Career MCP
1. `scan_evidence()` — Get overview of all career evidence
2. `parse_ladder()` — Get structured competency requirements
3. `analyze_coverage()` — Map evidence to competencies with coverage stats
4. `timeline_analysis()` — Evidence trends over time
5. `scan_work_for_evidence(date_range: "last-12-months", impact_level: "high")` — Find uncaptured high-impact work

### Work MCP
1. `get_quarterly_goals()` — See delivered outcomes for recent quarters
2. `get_goal_status(goal_id)` — Completion, linked work, skills developed per goal

**Why both matter:**
- Career evidence = What you captured (documented achievements, feedback)
- Work MCP data = What you delivered (completed goals, shipped priorities)
- Promotion readiness = Both combined, proving you operate at the next level

**Example MCP workflow:**
```
[Career MCP: scan_evidence() - returns 42 files]
[Career MCP: parse_ladder() - returns 8 competencies]
[Career MCP: analyze_coverage() - returns evidence counts per competency]
[Work MCP: get_quarterly_goals() - returns 12 goals, 8 completed]
[Work MCP: scan_work_for_evidence() - finds 5 high-impact completed goals]
[Now interpret combined data and generate assessment]
```

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

Accept whatever the user shares about their promotion aspirations. If they start with nothing, prompt:

```markdown
## Promotion Assessment Session

**Let's evaluate your promotion readiness.** Tell me:
- What role/level are you targeting?
- What do you think your strongest areas are?
- Where do you feel gaps?
- Any feedback from your manager about readiness?

Share what's on your mind — I'll cross-reference your evidence, goals, and career ladder to build a thorough assessment.
```

### Phase 2: Clarifying Questions

Ask **3-5 targeted questions** to fill gaps. Adapt to career level:

**Mid Career:** "What's the biggest project where you operated above your level?" "How do you demonstrate influence beyond your team?"
**Senior:** "Where are you already operating at the target level daily?" "What would your skip-level say about your readiness?"
**Leadership:** "How are you developing your replacement?" "What organizational impact can you point to?"

Focus areas:
1. **Target Level Clarity** — What does the next level actually require?
2. **Strongest Evidence** — Where are you already exceeding current level?
3. **Known Gaps** — Where do you feel least confident?
4. **Manager Perspective** — What has your manager said about readiness?
5. **Timeline** — When would you ideally want to be promoted?

Ask conversationally, 2-3 at a time. Wait for answers before follow-ups.

### Phase 3: Gather Data

Call MCP tools:

**Career MCP:**
```
scan_evidence()
parse_ladder()
analyze_coverage()
timeline_analysis()
scan_work_for_evidence(date_range: "last-12-months", impact_level: "high")
```

**Work MCP:**
```
get_quarterly_goals()  # for recent quarters
get_goal_status(goal_id)  # for each goal
```

Combine MCP data with user input. Identify which competencies are well-evidenced and which have gaps.

### Phase 4: Generate Assessment

```markdown
# Promotion Assessment — [TARGET ROLE]

**Current Role:** [CURRENT LEVEL]
**Target Role:** [TARGET LEVEL]
**Assessment Date:** YYYY-MM-DD

---

## Executive Summary

[2-3 paragraphs: overall readiness, strongest areas, key gaps to address]

---

## Competency Gap Analysis

### [Competency Category 1]

#### Requirement: [What target role requires]

**Current Demonstration:**
- ✅ [Evidence of meeting this requirement]
- ✅ [Evidence of meeting this requirement]
- ⚠️ [Partial evidence / room for more]

**Gap Assessment:** [None / Minor / Moderate / Significant]

**What's Needed:** [Additional evidence to strengthen the case]

---

### [Competency Category 2]

#### Requirement: [What target role requires]

**Current Demonstration:**
- ✅ [Evidence of meeting this requirement]
- ⚠️ [Partial evidence / room for more]
- ❌ [Not yet demonstrated]

**Gap Assessment:** [None / Minor / Moderate / Significant]

**What's Needed:** [Additional evidence to strengthen the case]

---

### [Competency Category 3]

[Same structure as above]

---

## Strengths Alignment

Areas where you're **already operating at the target level:**

1. **[Strength 1]**
   - Evidence: [Examples from work]
   - Ladder match: [How this maps to promotion criteria]

2. **[Strength 2]**
   - Evidence: [Examples from work]
   - Ladder match: [How this maps to promotion criteria]

3. **[Strength 3]**
   - Evidence: [Examples from work]
   - Ladder match: [How this maps to promotion criteria]

---

## Development Areas

Areas needing **additional evidence or growth:**

### High Priority

**[Development Area 1]**
- **Why it matters:** [Impact on promotion case]
- **Current state:** [Where you are now]
- **Target state:** [What target level requires]
- **What's missing:** [Specific gap]

**[Development Area 2]**
- **Why it matters:** [Impact on promotion case]
- **Current state:** [Where you are now]
- **Target state:** [What target level requires]
- **What's missing:** [Specific gap]

### Lower Priority

**[Development Area 3]**
- **Why it matters:** [Impact on promotion case]
- **Current state:** [Where you are now]
- **What's missing:** [Specific gap]

---

## Evidence Needed

To strengthen your promotion case, focus on capturing:

1. **[Evidence Type 1]** — [Why this matters, how to capture it]
2. **[Evidence Type 2]** — [Why this matters, how to capture it]
3. **[Evidence Type 3]** — [Why this matters, how to capture it]

---

## Readiness Assessment

**Overall Promotion Readiness:** [Not Ready / Developing / Nearly Ready / Ready]

**Rationale:**
[Detailed explanation based on competency analysis]

**Confidence Level:** [Low / Medium / High]

**Key Considerations:**
- [Factor 1 influencing readiness]
- [Factor 2 influencing readiness]
- [Factor 3 influencing readiness]

---

## Action Plan

### Immediate Actions (This Quarter)

1. **[Action 1]**
   - What: [Specific activity]
   - Why: [Which gap it addresses]
   - How to measure: [Success criteria]

2. **[Action 2]**
   - What: [Specific activity]
   - Why: [Which gap it addresses]
   - How to measure: [Success criteria]

3. **[Action 3]**
   - What: [Specific activity]
   - Why: [Which gap it addresses]
   - How to measure: [Success criteria]

### Next 6 Months

- [Longer-term development action 1]
- [Longer-term development action 2]
- [Longer-term development action 3]

### Promotion Timeline

**Realistic Timeline:** [Estimated timeframe]

**Factors:**
- [Factor influencing timeline]
- [Factor influencing timeline]

---

## Conversation Prep

When discussing promotion with your manager, emphasize:

1. **[Talking Point 1]** — [Your strongest evidence]
2. **[Talking Point 2]** — [Growth you've demonstrated]
3. **[Talking Point 3]** — [Commitment to closing gaps]

**Questions to Ask Your Manager:**
- [Question about their assessment of your readiness]
- [Question about specific gaps they see]
- [Question about timeline and next steps]

---

## Supporting Evidence

[Reference specific files in `05-Areas/Career/Evidence/` that demonstrate competency]

---

*This assessment is based on your career ladder and evidence captured in Amp. Discuss with your manager to validate and refine.*
```

### Phase 5: Post-Assessment

```markdown
## ✅ Promotion Assessment Complete

**Saved to:** `05-Areas/Career/Assessments/YYYY-MM-DD - Promotion Assessment.md`

**This is a snapshot based on current evidence.** As you continue working, Amp captures more examples that strengthen your case.

**Suggested Next Steps:**

1. **Review with your manager** — Get their perspective on gaps and timeline
2. **Focus on high-priority development areas** — Prioritize actions from the plan
3. **Capture evidence proactively** — When you demonstrate target-level work, note it
4. **Re-run this assessment quarterly** — Track progress toward readiness

**Want to:**
- Discuss any of the gaps in more detail?
- Brainstorm ways to close specific gaps?
- Draft talking points for a manager conversation?
```

---

## Post-Session: Evidence Capture

If the session revealed achievements not yet documented:

```markdown
## Capture Career Evidence?

Based on this assessment, I noticed undocumented achievements:
- [Achievement 1]
- [Achievement 2]

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

**Feedback:** `05-Areas/Career/Evidence/YYYY-MM-DD - Feedback from [Person].md`

```markdown
# Feedback from [Person Name]

**Date:** YYYY-MM-DD
**Context:** [1:1, review, project retro, etc.]

## Positive Feedback
- [Strength 1]
- [Strength 2]

## Constructive Feedback
- [Area 1]
- [Area 2]

## Reflections
[My thoughts on this feedback]
```

---

## Update Growth Goals

If the assessment revealed new priorities:

```markdown
## Update Growth Goals?

Based on the gap analysis, your growth goals may need updating.
Want me to revise `05-Areas/Career/Growth_Goals.md` to align with the promotion action plan?
```

---

## Conversation Style

- **Be honest about gaps** — Don't sugarcoat; the user needs to know where they stand
- **Be specific about evidence** — "You need 2-3 more examples of X at the Y level"
- **Be strategic** — "Here's how to create opportunities to demonstrate this"
- **Be encouraging about strengths** — "This is strong. Your manager would agree."

---

## Quality Checks

Before finalizing output:
- [ ] Every competency from career ladder addressed
- [ ] Evidence is specific with measurable outcomes
- [ ] Honest assessment (not inflated or understated)
- [ ] Gap analysis has actionable remediation
- [ ] Action plan is time-bound and measurable
- [ ] Conversation prep included for manager discussion
- [ ] Appropriate tone for career level

---

## Track Usage (Silent)

Update `System/usage_log.md` to mark career coaching as used.

Call `track_event` with event_name `career_coach_session` and properties:
- `mode`: "promotion"

This only fires if the user has opted into analytics.
