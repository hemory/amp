# Amp System Guide

## What is Amp?

Amp is your AI Chief of Staff. Your work, amplified. It's a personal operating system that runs inside GitHub Copilot CLI or Claude Code. It manages your tasks, preps you for meetings, tracks your projects and people, and helps you plan your days, weeks, and quarters.

Everything lives in plain markdown files on your machine. No cloud, no subscriptions, no data leaves your laptop.

## How It Works

```
You (terminal) → AI Agent → MCP Servers → Your Vault (markdown files)
```

1. **You** type commands in your terminal AI agent
2. **Amp** (the AI) reads your vault, calls MCP tools, and generates smart responses
3. **MCP servers** handle the heavy lifting: task management, calendar access, career tracking
4. **Your vault** stores everything in organized markdown files

## The Planning Pyramid

This is the core of Amp. Everything ladders up:

```
Strategic Pillars (2-4 focus areas you define)
    └── Quarterly Goals (3-5 per quarter)
        └── Weekly Priorities (3-5 per week)
            └── Daily Tasks (from your backlog)
```

Every task is tagged with a pillar. Weekly priorities link to quarterly goals. Amp warns you about orphaned work and tracks your velocity.

## The Vault (PARA Method)

Your vault is organized using the PARA method:

| Folder | What Goes Here |
|--------|---------------|
| `00-Inbox/` | Quick captures: meeting notes, ideas, Slack messages |
| `01-Quarter_Goals/` | 3-5 strategic goals per quarter |
| `02-Week_Priorities/` | Top 3-5 outcomes for the week |
| `03-Tasks/` | Master task backlog by priority (P0-P3) |
| `04-Projects/` | Active time-bound work (one folder per project) |
| `05-Areas/` | Ongoing responsibilities: People, Companies, Career |
| `06-Resources/` | Reference material, templates, guides |
| `07-Archives/` | Completed work (moved here when done) |
| `System/` | Configuration: user-profile.yaml, pillars.yaml, session learnings, optional identity templates |

## Session Continuity

Amp works best when each session starts with local context instead of a blank slate. The production template points the agent at these optional continuity sources:

| Location | Purpose |
|----------|---------|
| `System/Session_Learnings/` | Compact summaries from meaningful past sessions |
| `System/Memory/episodic-index.jsonl` | Short durable events such as decisions, milestones, task completions, and config changes |
| `System/identity/` | Optional stable identity and voice guidance for Amp and the user |
| `System/pattern-model.md` or `System/identity-model.md` | Working-pattern context when present |

Continuity should be factual and local. If a file is missing, Amp should proceed from available context rather than guessing.

## Identity and Voice Templates

Identity files are optional templates, not required setup. Use them when you want stable guidance that is more durable than a single prompt but more structured than scattered preferences.

- `System/identity/amp/SOUL.md` - Amp's principles and quality bar
- `System/identity/amp/STYLE.md` - Amp's response style
- `System/identity/user/SOUL.md` - user-declared identity and working context
- `System/identity/user/STYLE.md` - the user's voice for drafts written on their behalf

Only store user-declared facts. Do not infer sensitive attributes from names, roles, companies, or collaborator networks.


## Update Safety Metadata

Amp includes two production-safe JSON metadata files that scripts and skills can parse during update planning:

| File | Purpose |
|------|---------|
| `System/update-manifest.json` | Structured release manifest with versioned changes, touched production paths, migration impact, PR references, and links to breaking-change entries |
| `System/breaking-changes.json` | Conservative registry of removed, renamed, or legacy feature signals with migration guidance |

These files are product metadata, not user state. They should not contain private vault content, credentials, logs, runtime state, person pages, meeting notes, or local machine paths.

## Daily Workflow

```
8:00 AM  → /daily-plan     Your briefing: calendar, tasks, priorities
           Throughout day   Capture tasks, prep for meetings, mark things done
5:00 PM  → /daily-review   Reflect, capture learnings, preview tomorrow
```

## Weekly Workflow

```
Monday    → /week-plan      Set 3-5 priorities linked to quarterly goals
Wednesday → Check progress   Review priorities and adjust
Friday    → /week-review    What worked, what didn't, capture learnings
```

## Quarterly Workflow

```
Week 1    → /quarter-plan   Set 3-5 goals with success criteria
Monthly   → /project-health Scan all active projects
Last week → /quarter-review Score goals, capture insights
```

## Key Commands

| Command | What It Does |
|---------|-------------|
| `/daily-plan` | Plan your day with calendar and task awareness |
| `/daily-review` | End-of-day reflection, plan tracking, and learning capture |
| `/week-plan` | Set weekly priorities linked to goals |
| `/meeting-prep` | Prep for a meeting with attendee context |
| `/process-meetings` | Batch process meeting notes |
| `/triage` | Sort inbox items into the right places |
| `/career-coach` | Career development coaching |
| `/amp-level-up` | Discover features you haven't tried |
| `/health-check` | System health diagnostic |

## People CRM

Amp maintains person pages for everyone you interact with:

- **Internal/** - Colleagues (matched by email domain)
- **External/** - Customers, partners, vendors

Each page tracks: role, meeting history, action items, context notes. Pages update automatically when you process meetings.

## Task Management

Tasks live in `03-Tasks/Tasks.md`:

```markdown
- [ ] **Task title** - Context notes #pillar ^task-20260305-001
```

Priority levels: P0 (max 3), P1 (max 5), P2 (max 10), P3 (backlog).

Tell Amp to create or complete tasks in natural language:
- "Create a task to review the proposal"
- "Mark the design review as done"
- "What should I work on next?"

## Customization

- **Pillars**: Edit `System/pillars.yaml` to replace the default `General` bucket with your real focus areas
- **Preferences**: Edit `System/user-profile.yaml` for tone, style, integrations
- **Custom behaviors**: Add to the USER_EXTENSIONS block in `CLAUDE.md`
- **Custom skills**: Run `/create-skill` to build your own workflows
- **Custom integrations**: Run `/create-mcp` for new tool connections

## Integration Reality Checks

Integrations are optional and should be treated as local capabilities, not assumptions. Before a skill references Slack, Google Workspace, Todoist, a calendar, or any other external system, Amp should check:

1. `System/user-profile.yaml` for user preferences.
2. `System/integrations/config.yaml` if present for enabled or disabled integrations.
3. `.mcp.json` for configured MCP servers, without exposing secrets.

If an integration is disabled or unavailable, Amp should fall back to vault-only workflows and explain the limitation briefly.

## Optional Integrations

| Tool | Purpose | Setup |
|------|---------|-------|
| Obsidian | Visual vault browser + graph view | `/amp-obsidian-setup` |
| Apple Calendar | Meeting awareness for daily planning | `/calendar-setup` |
| WorkIQ | Microsoft 365 calendar and context | `/amp-add-mcp` |
| Google Workspace | Gmail, Calendar, Docs | `/google-workspace-setup` |
| Todoist / Things 3 | Two-way task sync | `/todoist-setup` or `/things-setup` |
| Slack | Mobile access + proactive briefings | See [integrations](integrations.md) |

None of these are required. Amp works with just your vault and terminal.

## Getting Help

- `/health-check` - Diagnose system issues
- `/amp-level-up` - Find features you're not using
- `/getting-started` - Guided tour of capabilities
