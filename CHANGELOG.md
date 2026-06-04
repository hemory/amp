# Changelog

All notable changes to Amp are documented here.

## [0.2.0] - 2026-03-08

### Added
- **Update safety metadata**
  - Added `System/update-manifest.json` as a structured release manifest for scripts and skills
  - Added `System/breaking-changes.json` as a production-safe registry of conservative migration signals
  - Added JSON parseability and required-field validation to `npm test`
- **Demo sample data** (System/Demo/)
  - 13 tasks across 4 priority levels with realistic content
  - 3 quarterly goals with progress tracking and milestones
  - 3 weekly priorities linked to goals
  - 3 person pages (2 internal, 1 external) with meeting history
  - 1 meeting note with decisions and action items
  - Demo pillars.yaml with 3 strategic focus areas
- **5 role starter packs** (System/Role_Packs/)
  - Engineering Manager, Product Manager, Program Manager, Sales, L&D
  - Each includes suggested pillars with keywords and recommended skills
- **LaunchAgent configs** (scripts/launchagents/)
  - Morning brief at 8 AM, EOD digest at 5 PM, meeting prep every 30 min
  - manage-agents.sh for one-command install/uninstall
  - All use {{VAULT_PATH}} template substitution

## [0.1.0] - 2026-03-08

### Added
- Initial release of Amp: Personal AI Chief of Staff Kit
- **Core Architecture**
  - CLAUDE.md.template: Templatized system prompt with user extensions block
  - AGENTS.md: Multi-agent support (Copilot CLI + Claude Code)
  - .mcp.json.template: MCP server configuration with {{VAULT_PATH}} substitution
  - PARA vault structure (00-Inbox through 07-Archives)
- **12 MCP Servers (45+ tools)**
  - Work server: Tasks, goals, priorities, people, companies, scheduling (30 tools)
  - Calendar server: Apple Calendar + Reminders via EventKit (15 tools)
  - Career server: Evidence, ladder parsing, promotion readiness (8 tools)
  - Onboarding server: 9-step setup wizard with validation
  - Improvements server: Backlog capture and AI-ranking
  - Session memory server: Cross-session context and recall
  - Resume server: Resume building and LinkedIn profiles
  - Update checker: Version management and notifications
  - Analytics server: Optional anonymous usage tracking
- **70 Pre-built Skills**
  - Planning: daily-plan, review, week-plan, week-review, quarter-plan
  - Meetings: meeting-prep, process-meetings, triage
  - Career: career-coach, resume-builder
  - System: amp-level-up, amp-backlog, amp-update, health-check
  - Integrations: calendar, Slack, Google Workspace, Obsidian, Todoist
  - And 50+ more
- **Hooks System**
  - Claude Code hooks: session-start, session-end, context injectors
  - Copilot CLI hooks: adapter layer with hooks.json
  - Person and company context auto-injection
- **Automation Scripts**
  - Morning brief (Slack push at 8 AM)
  - Meeting prep auto (every 30 min)
  - EOD digest (Slack push at 5 PM)
  - Two-way Slack bot (13 commands)
- **Install & Onboarding**
  - One-command install.sh (prerequisites, deps, config, vault)
  - Conversational onboarding (9 steps, resumable, MCP-validated)
- **Test Suite**
  - 38 tests across 7 categories
  - Structure, templates, MCP servers, skills, hooks, privacy, scripts
- **Documentation**
  - System guide, skills reference, integrations, customization
  - README with quick start
  - CONTRIBUTING guide
