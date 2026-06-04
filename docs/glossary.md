# Glossary

Key terms used in Amp, explained plainly.

## Amp
Your AI Chief of Staff. A system that amplifies your work by planning your day, prepping for meetings, tracking people and projects, and capturing the chaos of knowledge work. Runs locally on your machine.

## Vault
Your local folder of markdown files. Contains everything Amp knows: notes, tasks, projects, people, and resources. It is just a folder on your computer, no cloud sync required.

## PARA
The organizational method Amp uses. Stands for Projects (time-bound work), Areas (ongoing responsibilities), Resources (reference material), and Archives (completed work). Each maps to a numbered folder in your vault.

## MCP (Model Context Protocol)
The system that connects Amp's AI to your data. MCP servers are small programs that give Amp tools: reading your calendar, managing tasks, looking up people. They run locally and load when you start a session.

## Pillar
A strategic focus area you define during onboarding. Pillars help Amp prioritize your work. Example: "Talent Development" or "Learning Programs." Tasks and goals ladder up to pillars.

## Skill
A slash command that extends what Amp can do. Run `/daily-plan` for a daily plan, `/meeting-prep` to prepare for a meeting, `/daily-review` for an end-of-day review. There are 70+ skills available.

## Hook
Code that runs automatically on specific events. Session-start hooks inject your goals and priorities. Safety hooks block dangerous commands. Hooks run in the background without you needing to trigger them.

## Chief of Staff Loop
The core workflow Amp enables: (1) Pull the plan, (2) Gather the context, (3) Prep the repeatable work, (4) Capture the chaos, (5) Come back as the decision-maker.

## Drop Zone
A daily Obsidian document where you dump screenshots, Slack messages, links, and notes throughout the day. Amp creates it during your daily plan. Run `/capture` to have Amp process and route the items.

## Person Page
A markdown file tracking everything Amp knows about someone you interact with. Meeting history, context, action items, and relationship notes. Lives in `05-Areas/People/`.

## Triage
The process of reviewing your inbox and routing items to the right place. Run `/triage` to process captured notes, meeting artifacts, and drop zone items.

## Daily Plan
A context-aware plan for your day, built from your calendar, active tasks, priorities, and recent work. Not a generic to-do list. Run `/daily-plan` each morning.

## USER_EXTENSIONS
A protected block in your CLAUDE.md file where your personal preferences and customizations live. Amp updates never overwrite this block. Add your writing rules, workflow preferences, and behavioral instructions here.

## CLAUDE.md
The master instruction file that defines Amp's behavior. Contains your user profile, core behaviors, skill references, and the USER_EXTENSIONS block. Every session reads this file first. The template version (`CLAUDE.md.template`) ships with the repo; your personalized copy is generated during onboarding.

## Safety Guard
A hook that inspects every tool call before execution. Blocks dangerous commands like `rm -rf /` or operations that could damage your system. Runs automatically on every bash/shell action. Lives in `.github/hooks/copilot-safety-guard.sh`.

## Context Injector
A hook that automatically surfaces relevant person or company context when you open files. If you view a meeting note mentioning "Sarah Chen," the person injector fetches her page and adds it to the conversation. Lives in `.github/hooks/copilot-context-injector.cjs`.

## Work MCP
The primary MCP server for task management. Handles creating tasks, updating status, managing quarter goals, week priorities, person pages, and the people index. The largest server in the system. Lives in `core/mcp/work_server.py`.

## Feature Flag
A toggle in `System/integrations/config.yaml` or `.claude/config/beta-features.yaml` that enables or disables experimental features. Used to gate beta capabilities without changing code. Skills check flags before activating optional behaviors.
