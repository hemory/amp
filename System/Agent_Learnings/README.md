# Agent Learnings

This directory stores reusable learnings for specialist agents and skills.

## How it works

1. Before delegating repeatable specialist work, Amp checks for `System/Agent_Learnings/{agent-or-skill-name}.md`.
2. After significant specialist work, Amp captures only reusable patterns, preferences, past decisions, and anti-patterns.
3. Learnings stay concise, deduplicated, and user-editable.

## File format

```markdown
# {agent-name} - Agent Learnings

**Last updated:** YYYY-MM-DD

## Preferences
- Reusable style, tool, or approach preferences.

## Patterns
- Workflows or approaches that worked well.

## Past Decisions
- YYYY-MM-DD: Specific decision with context.

## Anti-Patterns
- Things to avoid next time.
```

Do not store secrets, private transcripts, or one-off task details here.
