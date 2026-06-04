# Amp

**Your AI Chief of Staff. Your work, amplified.**

> Your vault lives on your machine. No cloud database. No third-party sync. Conversations pass through your chosen AI provider.

Amp turns your terminal AI agent into a personal operating system for work. It plans your day, preps you for meetings, tracks your projects and people, and learns how you work over time. Everything lives in plain markdown files. Nothing leaves your laptop.

## What a day with Amp looks like

```
8:00 AM   You open your terminal and type /daily-plan.

          Amp pulls your calendar, checks your task backlog, surfaces
          commitments you made yesterday, and builds a focused plan.
          It knows your weekly priorities and flags what's slipping.

          "You have 3 meetings today. The 2pm is with someone you
           haven't met with in 3 weeks. Here's what you discussed
           last time and what you owe them."

Throughout  You capture meeting notes, create tasks in natural language,
the day    and mark things done. Amp updates person pages, links tasks
           to projects, and keeps your vault organized.

5:00 PM   You type /daily-review.

          Amp compares what you planned vs. what you shipped, captures
          learnings, and surfaces follow-ups you might have missed.
```

That's it. No dashboards. No browser tabs. Just your terminal and a vault of markdown files that get smarter every day.

## What you get

| | |
|---|---|
| **Planning pyramid** | Pillars → Quarter Goals → Week Priorities → Daily Tasks. Everything ladders up. |
| **People CRM** | Person pages with meeting history, context, and action items. Auto-routed by email domain. |
| **Meeting intelligence** | Auto-prep with attendee context, follow-up extraction, commitment tracking. |
| **Task management** | Priority-based backlog with pillar alignment. Create and complete tasks in plain English. |
| **Career tracking** | Evidence capture, promotion readiness, skills gap analysis. |
| **71 skills** | `/daily-plan`, `/week-review`, `/meeting-prep`, `/career-coach`, and 67 more. |
| **Self-improving** | Captures your preferences, tracks what works, suggests features you haven't tried. |
| **Session continuity** | Uses local session learnings, durable memory, and optional identity templates to pick up where you left off. |

## Quick start

### 1. Install Homebrew (if you don't have it)

[Homebrew](https://brew.sh) is the package manager for macOS. Skip this if `brew --version` already works.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After installing, **quit Terminal and reopen it** so `brew` is on your PATH.

### 2. Install GitHub Copilot CLI

[Copilot CLI](https://docs.github.com/en/copilot/github-copilot-in-the-cli) is the AI agent that powers Amp. You can also use [Claude Code](https://docs.anthropic.com/en/docs/claude-code) instead.

```bash
brew install gh
gh auth login
gh extension install github/gh-copilot
```

Verify it works:

```bash
copilot
```

> **Note:** Copilot CLI requires a [GitHub Copilot subscription](https://github.com/features/copilot).

### 3. Install Obsidian

[Obsidian](https://obsidian.md/download) is a free markdown editor you'll use to browse your Amp vault. Download and install it before continuing.

### 4. Verify other prerequisites

Make sure you have Git, Node.js 18+, and Python 3.10+:

```bash
git --version && node --version && python3 --version
```

If any are missing:

```bash
brew install git node python
```

### 5. Install Amp

```bash
git clone https://github.com/hemory/amp.git my-amp
cd my-amp
./install.sh
```

### Getting updates

```bash
cd my-amp
copilot
```

Then run `/amp-update` inside Copilot CLI. It handles the safe update flow: downloads changes, preserves user-owned data, updates dependencies. For the 0.2.0 rollout, review [the update guide](docs/update-guide-0.2.0.md) first. If `/amp-show-changes` is available in your install, run it before updating to preview what will change.

### First launch

```bash
cd my-amp
copilot          # or: claude
```

Type `/setup` and follow the 5-minute onboarding. Amp will ask your name, role, email domain, and communication preferences, then build your workspace and walk you through opening it in Obsidian.

> **Tip:** If `/setup` doesn't respond, quit Terminal, reopen it, and try again. MCP servers load at session start.

## How it works

```
You (terminal) → AI Agent (Copilot CLI / Claude) → MCP Servers → Your Vault (markdown)
```

Everything stays local. No cloud accounts. No subscriptions. No telemetry unless you opt in.

Amp also keeps continuity local. Session summaries live in `System/Session_Learnings/`, durable events can live in `System/Memory/episodic-index.jsonl`, and optional identity guidance lives in `System/identity/`. These files are templates or user-owned notes, not a cloud profile.

Your vault uses the [PARA method](https://fortelabs.com/blog/para/): Projects, Areas, Resources, Archives. Amp organizes your files, but they're just markdown. Open them in Obsidian, VS Code, or any text editor.

## After setup

| When | What | Command |
|------|------|---------|
| **First day** | Plan your day | `/daily-plan` |
| **Before a meeting** | Get attendee context and prep | `/meeting-prep` |
| **End of day** | Reflect and capture learnings | `/daily-review` |
| **Monday morning** | Set weekly priorities | `/week-plan` |
| **Friday** | Review the week | `/week-review` |
| **Start of quarter** | Set 3-5 goals | `/quarter-plan` |
| **Anytime** | Discover what you're not using | `/amp-level-up` |

## Documentation

- **[System Guide](docs/system-guide.md)** -- How the planning pyramid, vault, and workflows fit together
- **[Skills Reference](docs/skills.md)** -- All 71 built-in skills by category
- **[Integrations](docs/integrations.md)** -- Calendar, Slack, Google Workspace, task managers
- **[Customization](docs/customization.md)** -- Pillars, preferences, identity templates, custom skills, role templates
- **[0.2.0 Update Guide](docs/update-guide-0.2.0.md)** -- Safe update flow, usage-log merge helper, identity template migration, rollback

## License

MIT -- See [LICENSE](LICENSE)
