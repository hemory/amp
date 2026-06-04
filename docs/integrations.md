# Amp Integrations

Amp works standalone with just your vault and terminal. Connecting tools makes it more powerful, but none are required.

## Apple Calendar

**What it enables:** Meeting awareness for daily planning, meeting prep, scheduling intelligence.

**Setup:**
```
/calendar-setup
```

Amp uses Apple's EventKit via Python to read your calendar. Works with any calendar synced to Calendar.app (Google, Outlook, iCloud). macOS only.

**Configuration:** Set your work calendar in `System/user-profile.yaml`:
```yaml
calendar:
  work_calendar: "Work"  # or your calendar name
```

## WorkIQ (Microsoft 365)

**What it enables:** Outlook calendar, Teams context, and Microsoft 365 integration.

**How it works:** WorkIQ is Microsoft's official MCP server. To add it, run:

```
/amp-add-mcp
```

Or add it manually to your `.mcp.json`:
```json
"workiq": {
  "command": "npx",
  "args": ["-y", "@microsoft/workiq@latest", "mcp"]
}
```

When configured, `/daily-plan` will pull your Outlook calendar automatically.

## Obsidian

**What it enables:** Visual vault browsing, graph view of connections, rich editing.

**Setup:**
```
/amp-obsidian-setup
```

Point Obsidian at your Amp vault directory. Amp will auto-open files in Obsidian when creating notes, plans, and person pages.

**Obsidian CLI (recommended):** Enable the official CLI in Obsidian Settings > General > Command line interface. This lets Amp interact through Obsidian's API for proper link and index sync. Requires Obsidian 1.12.4+.

## Slack

**What it enables:** Mobile access, proactive briefings (morning brief, meeting prep, EOD digest).

**Setup:**

1. Create a Slack app at https://api.slack.com/apps
2. Enable Socket Mode
3. Add Bot Token Scopes: `chat:write`, `channels:history`, `channels:read`, `im:history`, `im:read`
4. Install to your workspace
5. Add tokens to `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   ```
6. Start the bot:
   ```bash
   ./scripts/amp-slack-bot.sh
   ```

**Slack Commands:**
| Command | What It Does |
|---------|-------------|
| `focus` | Top 3 suggested tasks |
| `tasks` | Open task summary |
| `brief` | Morning briefing |
| `prep [meeting]` | Meeting context |
| `who is [name]` | Person lookup |
| `done [task]` | Mark task complete |
| `add [item]` | Capture to inbox |

## Google Workspace

**What it enables:** Gmail scanning, Google Calendar, Google Docs access.

**Setup:**
```
/google-workspace-setup
```

## Task Managers

**What they enable:** Two-way task sync with your existing task manager.

| Manager | Setup |
|---------|-------|
| Todoist | `/todoist-setup` |
| Things 3 | `/things-setup` |

## Custom Integrations

Build your own MCP server for any tool:
```
/create-mcp
```

Or install from the Smithery.ai marketplace:
```
/integrate-mcp
```
