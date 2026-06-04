# Amp Skills Reference

Amp ships with 72 built-in skills. Invoke any skill with `/skill-name`. Run `/amp-level-up` to see which ones you haven't tried yet.

Skills should gather relevant vault context before producing substantive deliverables, and they should check local integration configuration before relying on external tools. If an integration is disabled or unavailable, a skill should fall back to a vault-only workflow when possible.

## Planning and Daily Work

| Skill | Description |
|-------|-------------|
| `/daily-plan` | Morning briefing with calendar, tasks, priorities, and scheduling suggestions |
| `/daily-review` | End-of-day review with plan tracking, learning capture, meeting follow-ups, and commitment scanning |
| `/week-plan` | Set 3-5 weekly priorities linked to quarterly goals |
| `/week-review` | Weekly patterns, progress assessment, and learnings |
| `/quarter-plan` | Set 3-5 quarterly goals with success criteria |
| `/quarter-review` | Quarterly retrospective and goal scoring |
| `/journal` | Start a journal entry (morning, evening, or weekly) |

## Meetings and Inbox

| Skill | Description |
|-------|-------------|
| `/meeting-prep` | Pre-meeting research with attendee context, history, and talking points |
| `/process-meetings` | Batch process meeting notes into person pages and tasks |
| `/triage` | Route inbox items to the right folders, extract scattered tasks |
| `/commitment-scan` | Scan for uncommitted asks and promises across your data |

## Career Development

| Skill | Description |
|-------|-------------|
| `/career-coach` | Career coaching in 4 modes: weekly reports, monthly reflections, self-reviews, promotion assessments |
| `/career-setup` | Initialize career tracking folder and templates |
| `/resume-builder` | Build resume and LinkedIn profile through guided interview |
| `/identity-snapshot` | Generate a profile of your working patterns, decision tendencies, and growth areas |

## Projects

| Skill | Description |
|-------|-------------|
| `/project-health` | Scan active projects for status, blockers, and next steps |
| `/product-brief` | Extract product ideas through guided questions and generate a PRD |

## Integrations

| Skill | Description |
|-------|-------------|
| `/setup` | Initial onboarding (run once) |
| `/getting-started` | Interactive post-onboarding tour |
| `/calendar-setup` | Connect Apple Calendar |
| `/google-workspace-setup` | Connect Gmail, Calendar, Docs |
| `/todoist-setup` | Connect Todoist for task sync |
| `/things-setup` | Connect Things 3 for task sync |
| `/ms-teams-setup` | Connect Microsoft Teams |
| `/atlassian-setup` | Connect Jira and Confluence |
| `/trello-setup` | Connect Trello boards |
| `/zoom-setup` | Connect Zoom meetings |
| `/screenpipe-setup` | Enable ambient work intelligence via screen OCR |
| `/amp-obsidian-setup` | Enable Obsidian integration and wiki links |
| `/amp-add-mcp` | Add an MCP server manually |
| `/integrate-mcp` | Install MCP servers from Smithery.ai or GitHub |
| `/create-mcp` | Build a custom MCP integration from scratch |
| `/create-skill` | Create a custom skill protected from updates |

## System Management

| Skill | Description |
|-------|-------------|
| `/health-check` | Diagnose MCP servers, config, and recent errors |
| `/amp-level-up` | Discover unused features based on your usage patterns |
| `/amp-backlog` | View and rank system improvement ideas |
| `/amp-improve` | Workshop an improvement idea into an implementation plan |
| `/amp-show-changes` | Preview production changes before updating, without applying them |
| `/amp-update` | Update Amp safely with backup and merge |
| `/amp-rollback` | Undo the last Amp update |
| `/amp-whats-new` | Check for system improvements and Claude updates |
| `/amp-demo` | Toggle demo mode for safe exploration with sample data |
| `/save-insight` | Capture learnings from completed work |
| `/prompt-improver` | Transform vague prompts into structured, effective ones |
| `/scrape` | Scrape web pages with stealth fetching and anti-bot bypass |
| `/xray` | Deep system analysis and diagnostics |
| `/reset` | Reset vault state for testing |

## AI Configuration

| Skill | Description |
|-------|-------------|
| `/ai-setup` | Configure budget cloud models or offline mode |
| `/ai-status` | Check current model, configuration, and credits |
| `/beta-activate` | Activate a beta feature using an activation code |
| `/beta-status` | View your activated beta features and their status |
| `/enable-semantic-search` | Enable local AI-powered semantic search across your vault |

## Creative Tools (Anthropic Skills)

These work in any Amp vault. No external dependencies.

| Skill | Description |
|-------|-------------|
| `/anthropic-frontend-design` | Create production-grade frontend interfaces |
| `/anthropic-canvas-design` | Create visual art in PNG and PDF |
| `/anthropic-algorithmic-art` | Generative art with p5.js |
| `/anthropic-pdf` | Create, merge, split, and fill PDF documents |
| `/anthropic-docx` | Create and edit Word documents |
| `/anthropic-pptx` | Create and edit PowerPoint presentations |
| `/anthropic-xlsx` | Create and analyze spreadsheets |
| `/anthropic-doc-coauthoring` | Structured workflow for co-authoring documentation |
| `/anthropic-internal-comms` | Write internal communications (status reports, FAQs, etc.) |
| `/anthropic-mcp-builder` | Guide for creating MCP servers |
| `/anthropic-skill-creator` | Guide for creating custom skills |
| `/anthropic-brand-guidelines` | Apply Anthropic brand colors and typography |
| `/anthropic-theme-factory` | Style artifacts with pre-set or custom themes |
| `/anthropic-web-artifacts-builder` | Build multi-component HTML artifacts |
| `/anthropic-webapp-testing` | Test web apps with Playwright |
| `/anthropic-slack-gif-creator` | Create animated GIFs for Slack |

## Custom Skills

Create your own with `/create-skill`. Custom skills are suffixed with `-custom` and are never overwritten by updates.

When authoring a custom skill, document:

1. What context it should gather before execution.
2. Which integrations are optional versus required.
3. Where it should write durable outputs or session learnings.
4. What private data must never be copied into public artifacts.


The repo includes a few example custom skills:

| Skill | Description |
|-------|-------------|
| `/weekly-review-custom` | Extended weekly review with structured doc routing |
| `/weekly-status-custom` | Generate external-ready weekly status reports |
| `/townhall-recap-custom` | Multi-step event analysis for town halls |

Skills are markdown files in `.claude/skills/SKILL_NAME/SKILL.md`. Each defines a workflow that Amp follows when you invoke it.
