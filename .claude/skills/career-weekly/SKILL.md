---
name: career-weekly
description: Generate a professional weekly report for your manager based on a coaching conversation
---

## Purpose

Generate a manager-ready weekly report through a coaching conversation. Brain dump about your week and get a polished, structured update highlighting accomplishments, challenges, and priorities.

## Prerequisites

Run `/career-setup` first to establish baseline (job description, career ladder, latest review, growth goals).

## File Paths

- **Output:** `05-Areas/Career/Reports/YYYY-MM-DD - Weekly Report.md`
- **Evidence:** `05-Areas/Career/Evidence/`
- **Growth Goals:** `05-Areas/Career/Growth_Goals.md`
- **Career Ladder:** `05-Areas/Career/Career_Ladder.md`
- **User Profile:** `System/user-profile.yaml`

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

Accept whatever the user shares. If they start with nothing, prompt:

```markdown
## Weekly Report Session

**Let's build your weekly update.** Tell me about your week:
- What projects did you work on?
- Any wins or breakthroughs?
- Challenges or blockers?
- Anything you need support on?

Just brain dump — I'll structure it into a polished report.
```

### Phase 2: Clarifying Questions

Ask **3-5 targeted questions** to fill gaps. Adapt to career level:

**Early Career:** "What did you learn?" "Who helped you?"
**Mid Career:** "What was the measurable impact?" "What trade-offs did you navigate?"
**Senior:** "How does this advance strategic goals?" "Who are you developing?"

Focus areas:
1. **Outcomes & Impact** — What actually shipped or moved forward?
2. **Stakeholders** — Who was involved? Key interactions?
3. **Challenges** — What was hard? How did you handle it?
4. **Next Week** — What's the priority?

Ask conversationally, 2-3 at a time. Wait for answers before follow-ups.

### Phase 3: Generate Report

```markdown
# Weekly Update — [Week of DATE]

**Prepared by:** [User Name]
**Date:** YYYY-MM-DD

---

## Projects & Deliverables

### [Project 1]
- [Key work completed]
- [Progress made]
- [Current status]

### [Project 2]
- [Key work completed]
- [Progress made]
- [Current status]

---

## Key Achievements

- [Specific win 1 with outcome/impact]
- [Specific win 2 with outcome/impact]
- [Specific win 3 with outcome/impact]

---

## Challenges Encountered

### [Challenge 1]
**Situation:** [What happened]
**Approach:** [How I addressed it]
**Outcome:** [Current state]

### [Challenge 2]
**Situation:** [What happened]
**Approach:** [How I addressed it]
**Outcome:** [Current state]

---

## Support Needed

- [Area 1] — [Specific ask]
- [Area 2] — [Specific ask]

---

## Next Week's Priorities

1. [Priority 1]
2. [Priority 2]
3. [Priority 3]

---

*Generated via Amp Career Coach*
```

### Phase 4: Post-Report

```markdown
## ✅ Weekly Report Ready

**Want me to:**
- Save to `05-Areas/Career/Reports/YYYY-MM-DD - Weekly Report.md`?
- Copy to clipboard for easy pasting?
- Draft an email to your manager?

**Any sections to revise before sharing?**
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
This builds your repository for future reviews and promotion discussions.
```

Save as `05-Areas/Career/Evidence/YYYY-MM-DD - [Achievement Name].md`:

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

---

## Conversation Style

- **Challenge constructively** — "Is that really the issue, or is it something else?"
- **Reframe** — "What if you looked at this as an opportunity to..."
- **Encourage** — "That's growth. Six months ago, this would've been harder for you."

---

## Quality Checks

Before finalizing output:
- [ ] Specific examples with measurable outcomes (not vague)
- [ ] Honest assessment (not inflated or understated)
- [ ] Actionable next steps
- [ ] Appropriate tone for career level

---

## Track Usage (Silent)

Update `System/usage_log.md` to mark career coaching as used.

Call `track_event` with event_name `career_coach_session` and properties:
- `mode`: "weekly"

This only fires if the user has opted into analytics.
