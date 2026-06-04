---
name: capture
description: Process today's drop zone — route screenshots, Slack messages, links, and notes to the right places.
context: fork
---

## Purpose

Process items from today's drop zone document. The drop zone is a shared workspace in Obsidian where the user dumps screenshots, Slack messages, links, and quick notes throughout the day. This skill reads new entries and intelligently routes them to person pages, projects, tasks, or meetings.

## Usage

- `/capture` — Process today's drop zone
- "check my drop zone" — Same behavior

**Batch limit:** Process at most 20 items per invocation. If more are pending, process the 20 most recent and note the remainder.

---

## Tone Calibration

Before executing, read `System/user-profile.yaml` → `communication` section and adapt tone accordingly (see CLAUDE.md → "Communication Adaptation").

---

## Demo Mode Check

Before executing, check if demo mode is active:

1. Read `System/user-profile.yaml` and check `demo_mode`
2. **If `demo_mode: true`:**
   - Display: "Demo Mode Active — Using sample data"
   - Use `System/Demo/` paths instead of root paths
3. **If `demo_mode: false`:** Use normal vault paths

---

## Step 1: Locate Today's Drop Zone

1. Determine today's date in `YYYY-MM-DD` format
2. Look for `00-Inbox/Drop_Zone/YYYY-MM-DD - Drop Zone.md`
   - Also check for legacy `00-Inbox/Drop_Zone/YYYY-MM-DD-Drop-Zone.md` if the new format is not found

### If it does NOT exist:

Create the file with the template:

```markdown
# Drop Zone — YYYY-MM-DD

Paste screenshots, Slack messages, links, quick notes here.
Run `/capture` to have Amp process and route these items.

---

```

Then open it in Obsidian:

```bash
open "obsidian://open?vault=amp&file=00-Inbox%2FDrop_Zone%2FYYYY-MM-DD%20-%20Drop%20Zone"
```

Tell the user:

> "📋 Created today's drop zone and opened it in Obsidian. Paste your items there, then run `/capture` again when you're ready for me to process them."

**Stop here. Do not continue to processing.**

### If it DOES exist:

Read the file and proceed to Step 2.

---

## Step 2: Identify New Entries

Parse the drop zone content. Entries are separated by blank lines or `---` dividers below the header section.

**Processed entries** are marked with `✅ Processed` at the end of the entry block. Skip these entirely.

**New entries** are any content blocks that do NOT have `✅ Processed`.

If there are no new entries:

> "📋 Drop zone is clean. Nothing new to process."

**Stop here.**

---

## Step 3: Classify and Route Each Entry

For each new entry, analyze the content and determine the best route. Check in this priority order:

### 3.1 Load Context for Routing

Before processing entries, gather routing context:

1. **People index**: Call `lookup_person` from Work MCP or scan `05-Areas/People/` for known names
2. **Projects**: Scan `04-Projects/` for active project names
3. **Week Priorities**: Read `02-Week_Priorities/Week_Priorities.md` for current focus
4. **Pillars**: Read `System/pillars.yaml` for keyword matching

### 3.2 Route Each Entry

For each unprocessed entry, classify using these rules:

| Signal | Route | Action |
|--------|-------|--------|
| Mentions a known person by name | **Person page** | Append to `## Notes` or `## Context` section on their page in `05-Areas/People/` |
| Mentions an active project | **Project** | Append as a note or update in the project folder `04-Projects/` |
| Contains action items (`- [ ]`, "need to", "should", "TODO", "follow up", "remind me") | **Task** | Create task via Work MCP `create_task` or append to `03-Tasks/Tasks.md` |
| Looks like meeting notes (attendees, agenda, decisions, action items from a conversation) | **Meeting notes** | Create or append to `00-Inbox/Meetings/YYYY-MM-DD - [Topic].md` |
| Contains a URL/link with context | **Relevant destination** | Route based on surrounding context (person, project, or resource) |
| Screenshot or image reference | **Relevant destination** | Route based on any text context around it; if ambiguous, leave in drop zone |
| None of the above | **Leave in drop zone** | Keep as reference, do not mark as processed unless user confirms |

### 3.3 Routing Rules

- **Person pages**: Find the correct page in `05-Areas/People/Internal/` or `05-Areas/People/External/`. Append under a dated section: `### YYYY-MM-DD — Drop Zone Note` followed by the content.
- **Projects**: Append to the project's main file or a relevant sub-document in `04-Projects/[Project_Name]/`.
- **Tasks**: Use Work MCP `create_task` with smart pillar inference (see CLAUDE.md → "Task Creation"). Include source context: "From drop zone YYYY-MM-DD".
- **Meeting notes**: If a meeting file for today exists with a matching topic, append. Otherwise create a new one.
- **Multiple routes**: If an entry mentions both a person and a project, route to both (add context to person page AND project).

### 3.4 Semantic Matching (if QMD available)

Check if QMD MCP tools are available by calling `qmd_status`. **If available:**

For entries with no obvious keyword match, run:
```
qmd_search(query="[entry content first 100 words]", limit=3)
```

Use semantic results to find related projects, people, or goals that share meaning but not keywords.

**If QMD is not available:** Use keyword matching only. Skip silently.

---

## Step 4: Mark Processed Entries

After successfully routing an entry, append `✅ Processed` on a new line at the end of that entry block in the drop zone file.

For entries that were routed to multiple destinations, still mark once with:
`✅ Processed — routed to [destination 1], [destination 2]`

For entries left in the drop zone (no clear route), do NOT mark as processed. Leave them for the user to review or provide more context.

---

## Step 5: Report Results

Provide a concise summary:

```
📋 Drop Zone — Processed [X] of [Y] items:

- [N] tasks created
- [N] routed to person pages ([names])
- [N] routed to projects ([project names])
- [N] saved as meeting notes
- [N] items left in drop zone (no clear route — review manually)
```

If items were left unrouted, briefly explain why:

> "Left 2 items: a screenshot with no context and a link without description. Add a note next to them and run `/capture` again."

---

## Step 6: Track Usage (Silent)

Update `System/usage_log.md` to mark capture as used.

**Analytics (Silent):**

Call `track_event` with event_name `capture_completed` and properties:
- `items_processed`: number of items routed
- `items_skipped`: number left in drop zone
- `tasks_created`: number of tasks created
- `person_routes`: number routed to person pages
- `project_routes`: number routed to projects

This only fires if the user has opted into analytics. No action needed if it returns "analytics_disabled".

---

## Graceful Degradation

### No Work MCP
- Tasks cannot be created via MCP. Fall back to appending directly to `03-Tasks/Tasks.md`.
- Person lookup falls back to scanning `05-Areas/People/` directory.

### Fresh Vault
- If no person pages or projects exist yet, most items will stay in the drop zone.
- Suggest: "Your vault is new. As you add person pages and projects, `/capture` will route more intelligently."

### Empty Drop Zone
- If the file exists but has no content below the header, say: "Drop zone is empty. Paste some items and run `/capture` again."

---

## MCP Dependencies

| Integration | MCP Server | Tools Used |
|-------------|------------|------------|
| Work | work-mcp | `create_task`, `lookup_person`, `build_people_index` |
| Semantic Search | qmd-mcp | `qmd_search`, `qmd_status` (optional) |
| Improvements | amp-improvements-mcp | `track_event` (optional) |
