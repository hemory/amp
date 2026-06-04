---
name: career-coach
description: "Personal career coach with 4 modes: weekly reports, monthly reflections, self-reviews, promotion assessments"
context: fork
hooks:
  PostToolUse:
    - matcher: Write
      type: command
      command: "node .claude/hooks/career-evidence-capture.cjs"
---

## Career Coaching — Mode Router

Your personal career development coach. Brain dump about your work, reflect on challenges, and get coaching that adapts to your role and career level.

### Prerequisites

Run `/career-setup` first to establish baseline (job description, career ladder, latest review, growth goals).

---

## Choose Your Mode

| Mode | Command | Best For |
|------|---------|----------|
| **Weekly Report** | `/career-weekly` | Professional weekly update for your manager |
| **Monthly Reflection** | `/career-monthly` | Spot patterns, trends, and growth areas across recent work |
| **Self-Review** | `/career-self-review` | Comprehensive yearly reflection for annual performance reviews |
| **Promotion Assessment** | `/career-promotion` | Evaluate readiness against your career ladder with gap analysis |

---

## Quick Start

**Know what you need?** Jump directly to the sub-skill above.

**Not sure?** Tell me what's on your mind and I'll recommend the right mode:

- Processing a tough week? → `/career-weekly`
- Noticing recurring themes? → `/career-monthly`
- Annual review coming up? → `/career-self-review`
- Wondering about promotion readiness? → `/career-promotion`

---

## How It Works

Each mode follows the same flow:
1. **Brain dump** — Share whatever's on your mind
2. **Clarifying questions** — I ask 3-5 targeted questions adapted to your career level
3. **Generate output** — Polished document saved to `05-Areas/Career/`
4. **Evidence capture** — Option to save achievements to your evidence repository

All modes adapt to your career level and coaching style preference from `System/user-profile.yaml`.

---

## Integration with Amp

- **During `/daily-review`:** Career-relevant achievements are flagged for evidence capture
- **During `/quarter-review`:** Prompted to run a promotion assessment or monthly reflection
- **Meeting processing:** Manager feedback extracted and appended to review history
- **Evidence builds over time:** Regular use creates a rich base for reviews and promotion discussions

---

## File Paths

- **Reports:** `05-Areas/Career/Reports/`
- **Reflections:** `05-Areas/Career/Reflections/`
- **Reviews:** `05-Areas/Career/Reviews/`
- **Assessments:** `05-Areas/Career/Assessments/`
- **Evidence:** `05-Areas/Career/Evidence/`
- **Growth Goals:** `05-Areas/Career/Growth_Goals.md`
- **Career Ladder:** `05-Areas/Career/Career_Ladder.md`
- **Review History:** `05-Areas/Career/Review_History.md`
