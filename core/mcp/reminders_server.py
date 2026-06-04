#!/usr/bin/env python3
"""
MCP Server for Apple Reminders Integration
Provides create, list, complete, delete, and search operations via JXA (JavaScript for Automation).
Uses a single "Amp" list in Apple Reminders for all tasks.
"""

import json
import logging
import platform
import subprocess
import sys
from datetime import datetime
from typing import Any, Optional

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("reminders-mcp")

AMP_LIST = "Amp"
IS_MACOS = platform.system() == "Darwin"

# ---------------------------------------------------------------------------
# JXA helpers
# ---------------------------------------------------------------------------

def _run_jxa(script: str, timeout: int = 30) -> Any:
    """Run a JXA script via osascript and return parsed JSON."""
    if not IS_MACOS:
        raise RuntimeError("Apple Reminders integration requires macOS. This server is not available on your platform.")
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"JXA error: {stderr}")
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Reminders operation timed out (30s)")
    except json.JSONDecodeError:
        return result.stdout.strip()


def _ensure_list_script() -> str:
    """JXA snippet that ensures the Amp list exists and assigns it to `list`."""
    return f"""
const Reminders = Application("Reminders");
let list;
try {{
    list = Reminders.lists.byName("{AMP_LIST}");
    list.name();
}} catch(e) {{
    list = Reminders.List({{name: "{AMP_LIST}"}});
    Reminders.lists.push(list);
}}
"""


def _js_escape(s: str) -> str:
    """Escape a string for safe embedding in JXA."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


PRIORITY_MAP = {"high": 1, "medium": 5, "low": 9, "none": 0}
PRIORITY_LABELS = {0: "none", 1: "high", 2: "high", 3: "high", 4: "high",
                   5: "medium", 6: "low", 7: "low", 8: "low", 9: "low"}

# ---------------------------------------------------------------------------
# Reminder operations
# ---------------------------------------------------------------------------

def create_reminder(title: str, notes: Optional[str] = None,
                    due_date: Optional[str] = None, due_time: Optional[str] = None,
                    priority: Optional[str] = None) -> dict:
    """Create a reminder in the Amp list."""
    props = [f'name: "{_js_escape(title)}"']
    if notes:
        props.append(f'body: "{_js_escape(notes)}"')
    if due_date:
        dt_str = due_date
        if due_time:
            dt_str += f"T{due_time}:00"
        else:
            dt_str += "T09:00:00"
        props.append(f'dueDate: new Date("{dt_str}")')
    if priority and priority.lower() in PRIORITY_MAP:
        props.append(f"priority: {PRIORITY_MAP[priority.lower()]}")

    props_str = ", ".join(props)
    script = _ensure_list_script() + f"""
const rem = Reminders.Reminder({{{props_str}}});
list.reminders.push(rem);
JSON.stringify({{
    id: rem.id(),
    name: rem.name(),
    body: rem.body() || null,
    dueDate: rem.dueDate() ? rem.dueDate().toISOString() : null,
    priority: rem.priority(),
    completed: false,
    created: true
}});
"""
    return _run_jxa(script)


def list_reminders(include_completed: bool = False) -> list:
    """List reminders from the Amp list. Uses batch property access for speed."""
    completed_filter = "" if include_completed else "if (completeds[i]) continue;"
    script = _ensure_list_script() + f"""
const names = list.reminders.name();
const ids = list.reminders.id();
const bodies = list.reminders.body();
const dueDates = list.reminders.dueDate();
const priorities = list.reminders.priority();
const completeds = list.reminders.completed();
const completionDates = list.reminders.completionDate();
const result = [];
for (let i = 0; i < names.length; i++) {{
    {completed_filter}
    result.push({{
        id: ids[i],
        name: names[i],
        body: bodies[i] || null,
        dueDate: dueDates[i] ? dueDates[i].toISOString() : null,
        priority: priorities[i],
        completed: completeds[i],
        completionDate: completionDates[i] ? completionDates[i].toISOString() : null
    }});
}}
JSON.stringify(result);
"""
    return _run_jxa(script) or []


def complete_reminder(reminder_id: str) -> dict:
    """Mark a reminder as complete by ID. Uses batch access for speed."""
    esc_id = _js_escape(reminder_id)
    script = _ensure_list_script() + f"""
const ids = list.reminders.id();
const rems = list.reminders();
let found = false;
for (let i = 0; i < ids.length; i++) {{
    if (ids[i] === "{esc_id}") {{
        rems[i].completed = true;
        found = true;
        break;
    }}
}}
JSON.stringify({{found: found, id: "{esc_id}", completed: found}});
"""
    return _run_jxa(script)


def delete_reminder(reminder_id: str) -> dict:
    """Delete a reminder by ID. Uses batch access for speed."""
    esc_id = _js_escape(reminder_id)
    script = _ensure_list_script() + f"""
const ids = list.reminders.id();
const rems = list.reminders();
let found = false;
for (let i = 0; i < ids.length; i++) {{
    if (ids[i] === "{esc_id}") {{
        Reminders.delete(rems[i]);
        found = true;
        break;
    }}
}}
JSON.stringify({{found: found, id: "{esc_id}", deleted: found}});
"""
    return _run_jxa(script)


def search_reminders(query: str, include_completed: bool = False) -> list:
    """Search reminders by keyword in name or body. Uses batch access for speed."""
    esc_query = _js_escape(query).lower()
    completed_filter = "" if include_completed else " && !completeds[i]"
    script = _ensure_list_script() + f"""
const names = list.reminders.name();
const ids = list.reminders.id();
const bodies = list.reminders.body();
const dueDates = list.reminders.dueDate();
const priorities = list.reminders.priority();
const completeds = list.reminders.completed();
const q = "{esc_query}";
const result = [];
for (let i = 0; i < names.length; i++) {{
    const name = (names[i] || "").toLowerCase();
    const body = (bodies[i] || "").toLowerCase();
    if ((name.includes(q) || body.includes(q)){completed_filter}) {{
        result.push({{
            id: ids[i],
            name: names[i],
            body: bodies[i] || null,
            dueDate: dueDates[i] ? dueDates[i].toISOString() : null,
            priority: priorities[i],
            completed: completeds[i]
        }});
    }}
}}
JSON.stringify(result);
"""
    return _run_jxa(script) or []


def sync_tasks_to_reminders(tasks: list) -> dict:
    """Push Amp tasks to Reminders, skipping duplicates matched by task ID in notes."""
    if not tasks:
        return {"created": 0, "skipped": 0, "details": []}

    # Build task creation snippets
    task_snippets = []
    for t in tasks:
        title = _js_escape(t.get("title", "Untitled"))
        task_id = _js_escape(t.get("task_id", ""))
        notes = _js_escape(t.get("notes", ""))
        body = f"^{task_id}"
        if notes:
            body += f"\\n{notes}"
        pri = PRIORITY_MAP.get(t.get("priority", "none"), 0)
        due_js = ""
        if t.get("due_date"):
            due_time = t.get("due_time", "09:00")
            due_js = f', dueDate: new Date("{_js_escape(t["due_date"])}T{due_time}:00")'

        task_snippets.append(f"""
if (!existingIds.has("{_js_escape(task_id)}")) {{
    const rem = Reminders.Reminder({{name: "{title}", body: "{body}", priority: {pri}{due_js}}});
    list.reminders.push(rem);
    results.push({{id: rem.id(), name: "{title}", taskId: "{_js_escape(task_id)}", created: true}});
}} else {{
    results.push({{name: "{title}", taskId: "{_js_escape(task_id)}", skipped: true}});
}}""")

    script = _ensure_list_script() + """
const existingBodies = list.reminders.body();
const existingIds = new Set();
for (let i = 0; i < existingBodies.length; i++) {
    const b = existingBodies[i] || "";
    const m = b.match(/\\^(task-\\d{8}-\\d{3})/);
    if (m) existingIds.add(m[1]);
}
const results = [];
""" + "\n".join(task_snippets) + """
JSON.stringify({created: results.filter(r => r.created).length, skipped: results.filter(r => r.skipped).length, details: results});
"""
    return _run_jxa(script, timeout=60)


def pull_completed_reminders() -> list:
    """Find reminders completed in the Amp list that have a task ID in notes.
    Returns list of {task_id, name, completionDate} for syncing back to Amp."""
    script = _ensure_list_script() + """
const names = list.reminders.name();
const bodies = list.reminders.body();
const completeds = list.reminders.completed();
const completionDates = list.reminders.completionDate();
const ids = list.reminders.id();
const result = [];
for (let i = 0; i < names.length; i++) {
    if (!completeds[i]) continue;
    const body = bodies[i] || "";
    const m = body.match(/\\^(task-\\d{8}-\\d{3})/);
    if (m) {
        result.push({
            reminder_id: ids[i],
            task_id: m[1],
            name: names[i],
            completionDate: completionDates[i] ? completionDates[i].toISOString() : null
        });
    }
}
JSON.stringify(result);
"""
    return _run_jxa(script) or []


def pull_new_captures() -> list:
    """Find incomplete reminders in the Amp list that have NO task ID in notes.
    These are user-created from phone/watch and need triage into Amp."""
    script = _ensure_list_script() + """
const names = list.reminders.name();
const bodies = list.reminders.body();
const completeds = list.reminders.completed();
const dueDates = list.reminders.dueDate();
const priorities = list.reminders.priority();
const ids = list.reminders.id();
const result = [];
for (let i = 0; i < names.length; i++) {
    if (completeds[i]) continue;
    const body = bodies[i] || "";
    const hasTaskId = /\\^task-\\d{8}-\\d{3}/.test(body);
    if (!hasTaskId) {
        result.push({
            reminder_id: ids[i],
            name: names[i],
            body: bodies[i] || null,
            dueDate: dueDates[i] ? dueDates[i].toISOString() : null,
            priority: priorities[i]
        });
    }
}
JSON.stringify(result);
"""
    return _run_jxa(script) or []


def complete_reminder_by_task_id(task_id: str) -> dict:
    """Mark a reminder as complete by matching its Amp task ID in notes."""
    esc_id = _js_escape(task_id)
    script = _ensure_list_script() + f"""
const bodies = list.reminders.body();
const rems = list.reminders();
let found = false;
for (let i = 0; i < bodies.length; i++) {{
    const body = bodies[i] || "";
    if (body.includes("^{esc_id}")) {{
        rems[i].completed = true;
        found = true;
        break;
    }}
}}
JSON.stringify({{found: found, task_id: "{esc_id}", completed: found}});
"""
    return _run_jxa(script)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_reminder(r: dict) -> str:
    """Format a single reminder for display."""
    status = "✅" if r.get("completed") else "⬜"
    priority_label = PRIORITY_LABELS.get(r.get("priority", 0), "none")
    priority_str = f" [{priority_label}]" if priority_label != "none" else ""
    due_str = ""
    if r.get("dueDate"):
        try:
            dt = datetime.fromisoformat(r["dueDate"].replace("Z", "+00:00"))
            due_str = f" (due {dt.strftime('%Y-%m-%d %H:%M')})"
        except (ValueError, TypeError):
            due_str = f" (due {r['dueDate']})"
    body_str = f"\n  Notes: {r['body']}" if r.get("body") else ""
    return f"{status} {r['name']}{priority_str}{due_str}{body_str}\n  ID: {r['id']}"


def _format_reminder_list(reminders: list) -> str:
    """Format a list of reminders for display."""
    if not reminders:
        return "No reminders found."
    lines = [_format_reminder(r) for r in reminders]
    return f"Found {len(reminders)} reminder(s):\n\n" + "\n\n".join(lines)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

app = Server("amp-reminders-mcp")


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="create_reminder",
            description="Create a reminder in Apple Reminders (Amp list). Syncs to iPhone/Apple Watch.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Reminder title"},
                    "notes": {"type": "string", "description": "Additional notes or context"},
                    "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format"},
                    "due_time": {"type": "string", "description": "Due time in HH:MM format (24h). Defaults to 09:00 if due_date is set."},
                    "priority": {"type": "string", "enum": ["high", "medium", "low", "none"], "description": "Priority level"}
                },
                "required": ["title"]
            }
        ),
        types.Tool(
            name="list_reminders",
            description="List reminders from the Amp list in Apple Reminders.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_completed": {"type": "boolean", "description": "Include completed reminders", "default": False}
                }
            }
        ),
        types.Tool(
            name="complete_reminder",
            description="Mark a reminder as complete in Apple Reminders.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "The reminder ID (x-apple-reminder:// URI)"}
                },
                "required": ["reminder_id"]
            }
        ),
        types.Tool(
            name="delete_reminder",
            description="Delete a reminder from Apple Reminders.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "The reminder ID (x-apple-reminder:// URI)"}
                },
                "required": ["reminder_id"]
            }
        ),
        types.Tool(
            name="search_reminders",
            description="Search reminders by keyword in title or notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword"},
                    "include_completed": {"type": "boolean", "description": "Include completed reminders", "default": False}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="sync_tasks_to_reminders",
            description="Push Amp tasks to Apple Reminders in bulk. Skips duplicates by matching task ID in notes. Use for daily plan sync.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "List of task objects with title, task_id, priority (high/medium/low/none), optional notes and due_date (YYYY-MM-DD)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "task_id": {"type": "string", "description": "Amp task ID (e.g. task-20260303-001)"},
                                "priority": {"type": "string", "enum": ["high", "medium", "low", "none"]},
                                "notes": {"type": "string"},
                                "due_date": {"type": "string", "description": "YYYY-MM-DD"},
                                "due_time": {"type": "string", "description": "HH:MM (24h)"}
                            },
                            "required": ["title", "task_id"]
                        }
                    }
                },
                "required": ["tasks"]
            }
        ),
        types.Tool(
            name="pull_completed_reminders",
            description="Find reminders completed in Apple Reminders that have an Amp task ID. Returns task IDs to mark done in Amp.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="pull_new_captures",
            description="Find reminders created on phone/watch with no Amp task ID. These need triage into the Amp task system.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="complete_reminder_by_task_id",
            description="Mark a reminder as complete by matching its Amp task ID in the notes field. Use when completing a task in Amp to keep Reminders in sync.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Amp task ID (e.g. task-20260303-001)"}
                },
                "required": ["task_id"]
            }
        ),
    ]


@app.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    args = arguments or {}

    try:
        if name == "create_reminder":
            result = create_reminder(
                title=args["title"],
                notes=args.get("notes"),
                due_date=args.get("due_date"),
                due_time=args.get("due_time"),
                priority=args.get("priority")
            )
            return [types.TextContent(
                type="text",
                text=f"Reminder created:\n\n{_format_reminder(result)}"
            )]

        elif name == "list_reminders":
            reminders = list_reminders(
                include_completed=args.get("include_completed", False)
            )
            return [types.TextContent(
                type="text",
                text=_format_reminder_list(reminders)
            )]

        elif name == "complete_reminder":
            result = complete_reminder(args["reminder_id"])
            if result.get("found"):
                return [types.TextContent(type="text", text="Reminder marked complete.")]
            else:
                return [types.TextContent(type="text", text=f"Reminder not found: {args['reminder_id']}")]

        elif name == "delete_reminder":
            result = delete_reminder(args["reminder_id"])
            if result.get("found"):
                return [types.TextContent(type="text", text="Reminder deleted.")]
            else:
                return [types.TextContent(type="text", text=f"Reminder not found: {args['reminder_id']}")]

        elif name == "search_reminders":
            reminders = search_reminders(
                query=args["query"],
                include_completed=args.get("include_completed", False)
            )
            return [types.TextContent(
                type="text",
                text=_format_reminder_list(reminders)
            )]

        elif name == "sync_tasks_to_reminders":
            result = sync_tasks_to_reminders(args["tasks"])
            return [types.TextContent(
                type="text",
                text=f"Synced to Reminders: {result.get('created', 0)} created, {result.get('skipped', 0)} already existed."
            )]

        elif name == "pull_completed_reminders":
            completed = pull_completed_reminders()
            if not completed:
                return [types.TextContent(type="text", text="No completed reminders with Amp task IDs found.")]
            lines = [f"- {r['name']} (^{r['task_id']}, completed {r.get('completionDate', 'unknown')})" for r in completed]
            return [types.TextContent(
                type="text",
                text=f"Found {len(completed)} completed reminder(s) to sync back:\n\n" + "\n".join(lines)
            )]

        elif name == "pull_new_captures":
            captures = pull_new_captures()
            if not captures:
                return [types.TextContent(type="text", text="No new phone-captured reminders to triage.")]
            pri_labels = {0: "none", 1: "high", 5: "medium", 9: "low"}
            lines = []
            for r in captures:
                pri = pri_labels.get(r.get("priority", 0), "none")
                due = ""
                if r.get("dueDate"):
                    try:
                        dt = datetime.fromisoformat(r["dueDate"].replace("Z", "+00:00"))
                        due = f" (due {dt.strftime('%Y-%m-%d')})"
                    except (ValueError, TypeError):
                        pass
                lines.append(f"- {r['name']} [{pri}]{due}\n  ID: {r['reminder_id']}")
            return [types.TextContent(
                type="text",
                text=f"Found {len(captures)} phone-captured reminder(s) to triage:\n\n" + "\n".join(lines)
            )]

        elif name == "complete_reminder_by_task_id":
            result = complete_reminder_by_task_id(args["task_id"])
            if result.get("found"):
                return [types.TextContent(type="text", text=f"Reminder for ^{args['task_id']} marked complete in Apple Reminders.")]
            else:
                return [types.TextContent(type="text", text=f"No reminder found matching ^{args['task_id']}")]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except RuntimeError as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Unexpected error in {name}: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Unexpected error: {str(e)}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="amp-reminders-mcp",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main():
    import asyncio
    asyncio.run(_main())


if __name__ == "__main__":
    main()
