---
name: career-self-review
description: Generate a comprehensive yearly self-review for annual performance reviews
---

## Purpose

Generate a comprehensive yearly self-review for annual performance reviews. Aggregates career evidence, quarterly goals, and work history to build an evidence-backed reflection covering accomplishments, competencies, growth areas, and forward-looking goals.

## Prerequisites

Run `/career-setup` first to establish baseline (job description, career ladder, latest review, growth goals).

## File Paths

- **Output:** `05-Areas/Career/Reviews/YYYY - Self-Review.md`
- **Evidence:** `05-Areas/Career/Evidence/`
- **Growth Goals:** `05-Areas/Career/Growth_Goals.md`
- **Career Ladder:** `05-Areas/Career/Career_Ladder.md`
- **Review History:** `05-Areas/Career/Review_History.md`
- **User Profile:** `System/user-profile.yaml`

## MCP Integration

### Career MCP
- `scan_evidence()` — Get all evidence (no date filter for full year)
- `parse_ladder()` — Understand competency framework
- `timeline_analysis(period: "last-12-months")` — Year-over-year growth
- `scan_work_for_evidence(date_range: "last-12-months")` — Find uncaptured work

### Work MCP
- `get_quarterly_goals()` — For each quarter in review period to see all goals
- `get_goal_status(goal_id)` — Completion and linked priorities per goal

This shows what you PLANNED to achieve vs what you ACTUALLY achieved. Completed high-impact goals are strong self-review evidence.

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

Accept whatever the user shares about their year. If they start with nothing, prompt:

```markdown
## Self-Review Session

**Let's build your annual self-review.** Think about the full year:
- What are you most proud of?
- What were the biggest challenges?
- How did you grow?
- What feedback have you received?

Share what comes to mind — I'll pull in your evidence, goals, and work history to build a comprehensive review.
```

### Phase 2: Clarifying Questions

Ask **3-5 targeted questions** to fill gaps. Adapt to career level:

**Early Career:** "What was your biggest learning this year?" "Who mentored you and how?"
**Mid Career:** "What was the measurable impact of your biggest project?" "How did you influence outcomes beyond your direct work?"
**Senior:** "How did your work advance the team/company strategy?" "Who did you develop this year?"

Focus areas:
1. **Major Accomplishments** — What shipped? What impact?
2. **Competency Growth** — What skills developed?
3. **Challenges & Resilience** — What was hardest? How did you adapt?
4. **Leadership & Influence** — How did you lift others?
5. **Goals Progress** — How did you do against last year's goals?

Ask conversationally, 2-3 at a time. Wait for answers before follow-ups.

### Phase 3: Gather Data

Call MCP tools to build the evidence base:

**Career MCP:**
```
scan_evidence()
parse_ladder()
timeline_analysis(period: "last-12-months")
scan_work_for_evidence(date_range: "last-12-months")
```

**Work MCP:**
```
get_quarterly_goals()  # for each quarter
get_goal_status(goal_id)  # for each goal
```

Combine MCP data with user's brain dump to build the review.

### Phase 4: Generate Self-Review

```markdown
# Self-Review — [YEAR]

**Prepared by:** [User Name]
**Date:** YYYY-MM-DD
**Review Period:** [START DATE] to [END DATE]

---

## Executive Summary

[2-3 paragraphs summarizing the year: major themes, overall impact, key growth areas]

---

## Major Accomplishments

### [Accomplishment 1]
**Impact:** [Quantifiable outcome/business value]
**Context:** [Background and challenge]
**Approach:** [What I did]
**Skills Demonstrated:** [Relevant competencies]

### [Accomplishment 2]
**Impact:** [Quantifiable outcome/business value]
**Context:** [Background and challenge]
**Approach:** [What I did]
**Skills Demonstrated:** [Relevant competencies]

### [Accomplishment 3]
**Impact:** [Quantifiable outcome/business value]
**Context:** [Background and challenge]
**Approach:** [What I did]
**Skills Demonstrated:** [Relevant competencies]

---

## Core Competencies Demonstrated

### [Competency 1: e.g., Technical Leadership]
**Evidence:**
- [Example 1 from work]
- [Example 2 from work]
- [Example 3 from work]

**Growth:** [How this skill developed over the year]

### [Competency 2: e.g., Cross-Functional Collaboration]
**Evidence:**
- [Example 1 from work]
- [Example 2 from work]
- [Example 3 from work]

**Growth:** [How this skill developed over the year]

### [Competency 3: e.g., Strategic Thinking]
**Evidence:**
- [Example 1 from work]
- [Example 2 from work]
- [Example 3 from work]

**Growth:** [How this skill developed over the year]

---

## Growth Areas

### Challenges Overcome

**[Challenge 1]**
- **Situation:** [What was difficult]
- **Approach:** [How I addressed it]
- **Outcome:** [What I learned / how I grew]

**[Challenge 2]**
- **Situation:** [What was difficult]
- **Approach:** [How I addressed it]
- **Outcome:** [What I learned / how I grew]

### Skills Developed

- **[Skill 1]:** [How I developed this throughout the year]
- **[Skill 2]:** [How I developed this throughout the year]
- **[Skill 3]:** [How I developed this throughout the year]

---

## Leadership & Collaboration

### Influence & Impact
[Examples of how I influenced outcomes, led initiatives, or drove change]

### Teamwork & Partnerships
[Examples of effective collaboration, cross-functional work, supporting teammates]

### Mentorship & Development
[Examples of helping others grow, knowledge sharing, elevating the team]

---

## Goals Achievement

### Goals from Previous Review

**Goal 1:** [What it was]
- **Progress:** [What I achieved]
- **Status:** ✅ Achieved / 🔄 In Progress / ⏸️ Deferred

**Goal 2:** [What it was]
- **Progress:** [What I achieved]
- **Status:** ✅ Achieved / 🔄 In Progress / ⏸️ Deferred

**Goal 3:** [What it was]
- **Progress:** [What I achieved]
- **Status:** ✅ Achieved / 🔄 In Progress / ⏸️ Deferred

---

## Looking Ahead

### Continued Growth Areas

1. **[Development Area 1]**
   - Why: [Motivation]
   - How: [Approach]

2. **[Development Area 2]**
   - Why: [Motivation]
   - How: [Approach]

3. **[Development Area 3]**
   - Why: [Motivation]
   - How: [Approach]

### Career Aspirations

[Where I see myself growing, what I'm working toward]

---

## Feedback Received

### Consistent Strengths (from manager/peers)
- [Strength 1]
- [Strength 2]
- [Strength 3]

### Areas for Development (from manager/peers)
- [Area 1]
- [Area 2]

---

## Supporting Evidence

[Reference key projects, metrics, or documents that support this review]

---

*This self-review was prepared using evidence captured in Amp throughout [YEAR]. See `05-Areas/Career/Evidence/` for detailed examples.*
```

### Phase 5: Post-Review

```markdown
## ✅ Self-Review Ready

**Saved to:** `05-Areas/Career/Reviews/YYYY - Self-Review.md`

**Next Steps:**
- Review and refine before submitting
- Add any missing accomplishments
- Ensure metrics/impact are specific and quantifiable
- Reference this during your review meeting

**Want to:**
- Add more detail to any section?
- Include additional accomplishments?
- Adjust tone or emphasis?
```

---

## Post-Session: Evidence Capture

If the session revealed new achievements worth capturing:

```markdown
## Capture Career Evidence?

Based on this review session, I noticed some achievements not yet in your evidence folder:
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

## Action Items
- [ ] [Response action 1]
- [ ] [Response action 2]

## Reflections
[My thoughts on this feedback]
```

---

## Update Review History

If this was a reflection on formal feedback:

```markdown
## Add to Review History?

Want me to append these reflections to `05-Areas/Career/Review_History.md`?
This keeps a timeline of your feedback and progress.
```

---

## Conversation Style

- **Be thorough** — Annual reviews deserve comprehensive treatment
- **Connect dots** — Link achievements to competencies and career ladder
- **Challenge understatement** — "You're underselling this. The impact was..."
- **Encourage specificity** — "Can you quantify that?" "What was the before/after?"

---

## Quality Checks

Before finalizing output:
- [ ] Specific examples with measurable outcomes (not vague)
- [ ] Honest assessment (not inflated or understated)
- [ ] Connected to career ladder competencies
- [ ] Actionable forward-looking goals
- [ ] Appropriate tone for career level
- [ ] Previous goals addressed (achieved/in-progress/deferred)

---

## Track Usage (Silent)

Update `System/usage_log.md` to mark career coaching as used.

Call `track_event` with event_name `career_coach_session` and properties:
- `mode`: "self-review"

This only fires if the user has opted into analytics.
