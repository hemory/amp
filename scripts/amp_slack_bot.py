#!/usr/bin/env python3
"""
Amp Slack Bot - Two-way Slack interface for Amp.

Runs in Socket Mode (local, no public URL needed). Listens for messages
in Slack and responds with Amp intelligence: task lookups, meeting prep,
daily plans, person lookups, and quick task capture.

Usage:
    source .venv/bin/activate && python3 scripts/amp_slack_bot.py

Commands (in Slack):
    "focus" or "what should I work on"  → Top 3 suggested tasks
    "prep <meeting name>"               → Meeting prep for upcoming meeting
    "tasks" or "my tasks"               → Open task summary
    "blocked"                           → Show blocked tasks
    "who is <name>"                     → Person page lookup
    "done <task description>"           → Mark a task complete
    "brief" or "morning brief"          → Trigger morning brief
    "add <task description>"            → Capture to inbox
    "goals" or "quarterly goals"        → Show goal progress
    "priorities" or "this week"         → Show weekly priorities
    "help"                              → Show available commands

Inbox Capture:
    Any message in #amp-inbox channel is auto-captured to 00-Inbox/Slack/
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.constants import TASKS_FILE, PEOPLE_DIR, INBOX_DIR

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    HAS_SLACK = True
except ImportError:
    HAS_SLACK = False

# Suppress noisy logs
logging.basicConfig(level=logging.WARNING)

VAULT_PATH = os.environ.get("VAULT_PATH", str(Path(__file__).resolve().parent.parent))
INBOX_CHANNEL = "amp-inbox"


def locked_file_append(filepath, content):
    """Append content to a file with file locking."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.touch(exist_ok=True)
    with open(filepath, 'a') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(content)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def locked_file_update(filepath, modifier_fn):
    """Read, modify, and write a file with locking."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.touch(exist_ok=True)
    with open(filepath, 'r+') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            content = f.read()
            new_content = modifier_fn(content)
            f.seek(0)
            f.truncate()
            f.write(new_content)
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_env():
    env_path = Path(VAULT_PATH) / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


load_env()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")


def validate_slack_config():
    """Validate that required Slack environment variables are set."""
    if not HAS_SLACK:
        print("Slack integration requires slack-bolt and slack-sdk. Install with: pip install slack-bolt slack-sdk", file=sys.stderr)
        sys.exit(1)
    missing = []
    if not SLACK_BOT_TOKEN:
        missing.append("SLACK_BOT_TOKEN")
    if not SLACK_APP_TOKEN:
        missing.append("SLACK_APP_TOKEN")
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        print("See docs/integrations.md for Slack setup.", file=sys.stderr)
        sys.exit(1)


app = None  # initialized in main() after validation


# ─── Helpers ───────────────────────────────────────────────────────────────

def parse_tasks():
    """Parse tasks from Tasks.md."""
    tasks_path = Path(VAULT_PATH) / TASKS_FILE
    if not tasks_path.exists():
        return {"open": [], "blocked": [], "started": []}

    content = tasks_path.read_text()
    open_tasks, blocked, started = [], [], []
    current_section = ""

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        match = re.match(r"^- \[(.)\] \*\*(.+?)\*\*(.*)$", line)
        if not match:
            continue

        status, title, rest = match.groups()
        priority = ""
        if "P0" in current_section:
            priority = "P0"
        elif "P1" in current_section:
            priority = "P1"
        elif "This Week" in current_section:
            priority = "🎯"

        task = {"title": title.strip(), "priority": priority, "section": current_section, "rest": rest.strip()}

        if status == " ":
            open_tasks.append(task)
        elif status == "s":
            started.append(task)
        elif status == "b":
            blocked.append(task)

    return {"open": open_tasks, "blocked": blocked, "started": started}


def parse_priorities():
    """Extract weekly priorities."""
    path = Path(VAULT_PATH) / "02-Week_Priorities" / "Week_Priorities.md"
    if not path.exists():
        return []

    content = path.read_text()
    priorities = []
    in_section = False

    for line in content.splitlines():
        line = line.strip()
        if "Top" in line and ("Week" in line or "Prior" in line):
            in_section = True
            continue
        if in_section:
            if line.startswith("## ") or line.startswith("---"):
                break
            m = re.match(r"^[\d\-\*]+\.?\s*\*?\*?(.+?)\*?\*?\s*$", line)
            if m and len(m.group(1).strip()) > 3:
                priorities.append(m.group(1).strip())

    return priorities[:5]


def parse_goals():
    """Extract quarterly goals with progress."""
    path = Path(VAULT_PATH) / "01-Quarter_Goals" / "Quarter_Goals.md"
    if not path.exists():
        return []

    content = path.read_text()
    goals = []

    for line in content.splitlines():
        # Match goal lines with progress indicators
        m = re.match(r"^[-\d\*]+\.?\s*\*?\*?(.+?)\*?\*?\s*(?:[-–]\s*(\d+)%)?", line)
        if m and len(m.group(1).strip()) > 5:
            goal = {"title": m.group(1).strip()}
            if m.group(2):
                goal["progress"] = int(m.group(2))
            goals.append(goal)

    return goals[:5]


def lookup_person(name):
    """Find a person's page and return context."""
    people_dir = Path(VAULT_PATH) / PEOPLE_DIR
    if not people_dir.exists():
        return None

    name_parts = name.strip().split()
    if not name_parts:
        return None

    for subdir in ["Internal", "External", ""]:
        search_dir = people_dir / subdir if subdir else people_dir
        if not search_dir.exists():
            continue

        for page in search_dir.glob("*.md"):
            page_name = page.stem.replace("_", " ").lower()
            if all(p.lower() in page_name for p in name_parts):
                content = page.read_text()
                info = {"name": page.stem.replace("_", " ")}

                role_m = re.search(r"(?:Role|Title|Position):\s*(.+)", content, re.IGNORECASE)
                if role_m:
                    info["role"] = role_m.group(1).strip()

                company_m = re.search(r"(?:Company|Organization):\s*(.+)", content, re.IGNORECASE)
                if company_m:
                    info["company"] = company_m.group(1).strip()

                # Recent meetings
                meetings = re.findall(r"\[\[(\d{4}-\d{2}-\d{2}.*?)\]\]", content)
                if meetings:
                    info["recent_meetings"] = meetings[-3:]

                # Open actions
                actions = []
                for l in content.splitlines():
                    if re.match(r"^- \[ \]", l):
                        actions.append(re.sub(r"^- \[ \] ", "", l).strip()[:100])
                if actions:
                    info["open_actions"] = actions[:3]

                # Key context
                ctx_m = re.search(r"(?:## Context|## Notes|## Key Context)\n([\s\S]*?)(?:\n## |\Z)", content)
                if ctx_m:
                    info["context"] = ctx_m.group(1).strip()[:300]

                return info
    return None


def get_upcoming_meetings(hours=4):
    """Get meetings in the next N hours."""
    eventkit_path = Path(VAULT_PATH) / "core" / "mcp" / "scripts" / "calendar_eventkit.py"
    if not eventkit_path.exists():
        return []

    try:
        result = subprocess.run(
            [sys.executable, str(eventkit_path), "events", "Calendar", "0", "1"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        if not isinstance(data, list):
            return []

        now = datetime.now()
        horizon = now + timedelta(hours=hours)
        upcoming = []

        for event in data:
            if event.get("all_day"):
                continue
            start_str = event.get("start", "")
            try:
                dt = datetime.strptime(start_str[:19], "%Y-%m-%d %H:%M:%S")
                if now <= dt <= horizon:
                    event["_start"] = dt
                    upcoming.append(event)
            except ValueError:
                continue

        return sorted(upcoming, key=lambda e: e["_start"])
    except Exception:
        return []


def capture_to_inbox(text, user_name="User"):
    """Save a message to the Slack inbox folder."""
    inbox_dir = Path(VAULT_PATH) / INBOX_DIR / "Slack"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    inbox_file = inbox_dir / f"{today} - Slack Captures.md"

    timestamp = datetime.now().strftime("%M %p").replace("", "", 0)  # see below
    entry = f"- [ ] [{timestamp}] {text}\n"

    if inbox_file.exists():
        locked_file_append(inbox_file, entry)
    else:
        header = f"# Slack Captures - {today}\n\nCaptured from Amp Slack inbox.\n\n"
        locked_file_update(inbox_file, lambda c: c if c else header + entry)

    return str(inbox_file.relative_to(VAULT_PATH))


def mark_task_done(description):
    """Find and mark a matching task as done in Tasks.md."""
    tasks_path = Path(VAULT_PATH) / TASKS_FILE
    if not tasks_path.exists():
        return None

    content = tasks_path.read_text()
    lines = content.splitlines()
    desc_lower = description.lower().strip()
    best_match = None
    best_idx = -1

    for i, line in enumerate(lines):
        m = re.match(r"^- \[(.)\] \*\*(.+?)\*\*(.*)$", line)
        if not m or m.group(1) in ["x"]:
            continue

        title = m.group(2).strip()
        # Fuzzy match: all words from description appear in title
        desc_words = [w for w in desc_lower.split() if len(w) > 2]
        if all(w in title.lower() for w in desc_words):
            best_match = title
            best_idx = i
            break

    if best_match is None or best_idx < 0:
        return None

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    match_idx = best_idx

    def modifier(file_content):
        mod_lines = file_content.splitlines()
        if match_idx < len(mod_lines):
            old_line = mod_lines[match_idx]
            new_line = re.sub(r"^- \[.\]", "- [x]", old_line)
            if "✅" not in new_line:
                new_line = new_line.rstrip() + f" ✅ {now_str}"
            mod_lines[match_idx] = new_line
        return "\n".join(mod_lines)

    locked_file_update(tasks_path, modifier)
    return best_match


# ─── Command Handlers ──────────────────────────────────────────────────────

def handle_focus(say):
    """Suggest top tasks to focus on."""
    tasks = parse_tasks()
    priorities = parse_priorities()

    text = "*🎯 Focus Suggestions*\n\n"

    if priorities:
        text += "*This Week's Priorities:*\n"
        for i, p in enumerate(priorities[:3]):
            text += f"  {i+1}. {p}\n"
        text += "\n"

    # Show started tasks first, then P0, P1, This Week
    focus = tasks["started"][:2] + [t for t in tasks["open"] if t["priority"] in ["P0", "🎯"]][:3]
    if focus:
        text += "*Top Tasks:*\n"
        for t in focus[:5]:
            started = "🔄 " if t in tasks["started"] else ""
            prio = f"[{t['priority']}] " if t.get("priority") else ""
            text += f"  • {started}{prio}{t['title']}\n"

    if tasks["blocked"]:
        text += f"\n⚠️ {len(tasks['blocked'])} task(s) blocked"

    say(text)


def handle_tasks(say):
    """Show open task summary."""
    tasks = parse_tasks()
    total = len(tasks["open"]) + len(tasks["started"])

    text = f"*✅ Tasks ({total} open)*\n\n"

    if tasks["started"]:
        text += "*In Progress:*\n"
        for t in tasks["started"]:
            text += f"  • 🔄 {t['title']}\n"
        text += "\n"

    sections = {}
    for t in tasks["open"]:
        s = t["section"]
        if s not in sections:
            sections[s] = []
        sections[s].append(t)

    for section, items in list(sections.items())[:4]:
        text += f"*{section}:*\n"
        for t in items[:5]:
            prio = f"[{t['priority']}] " if t.get("priority") else ""
            text += f"  • {prio}{t['title']}\n"
        if len(items) > 5:
            text += f"  _...+{len(items)-5} more_\n"
        text += "\n"

    say(text)


def handle_blocked(say):
    """Show blocked tasks."""
    tasks = parse_tasks()
    if not tasks["blocked"]:
        say("No blocked tasks right now. 🎉")
        return

    text = f"*🚫 Blocked Tasks ({len(tasks['blocked'])})*\n\n"
    for t in tasks["blocked"]:
        text += f"• *{t['title']}*\n"
        if t.get("rest"):
            text += f"  _{t['rest'][:150]}_\n"
    say(text)


def handle_person(name, say):
    """Look up a person."""
    info = lookup_person(name)
    if not info:
        say(f"I don't have a page for \"{name}\". Check `05-Areas/People/` in the vault.")
        return

    text = f"*👤 {info['name']}*\n"
    if info.get("role"):
        text += f"_{info['role']}_"
        if info.get("company"):
            text += f" at {info['company']}"
        text += "\n"

    if info.get("context"):
        text += f"\n{info['context']}\n"

    if info.get("recent_meetings"):
        text += f"\n*Recent meetings:* {', '.join(info['recent_meetings'])}\n"

    if info.get("open_actions"):
        text += "\n*Open items:*\n"
        for a in info["open_actions"]:
            text += f"  • {a}\n"

    say(text)


def handle_prep(query, say):
    """Prep for a meeting."""
    meetings = get_upcoming_meetings(hours=12)
    if not meetings:
        say("No upcoming meetings found in the next 12 hours.")
        return

    # Find matching meeting
    target = None
    query_lower = query.lower().strip()
    for m in meetings:
        if query_lower in m.get("title", "").lower():
            target = m
            break

    if not target and meetings:
        target = meetings[0]

    title = target.get("title", "Meeting")
    start = target.get("_start", datetime.now())
    attendees = target.get("attendees", [])

    text = f"*📋 Prep: {title}*\n"
    text += f"🕐 {start.hour % 12 or 12}:{start.strftime('%M %p')}\n"

    if target.get("location"):
        text += f"📍 {target['location']}\n"
    if target.get("url"):
        text += f"🔗 <{target['url']}|Join>\n"

    if attendees:
        text += f"\n*Attendees ({len(attendees)}):*\n"
        for a in attendees[:8]:
            name = a.get("name", a.get("email", "?"))
            person = lookup_person(name)
            role_str = f" - _{person['role']}_" if person and person.get("role") else ""
            text += f"  • {name}{role_str}\n"

    say(text)


def handle_done(description, say):
    """Mark a task as done."""
    matched = mark_task_done(description)
    if matched:
        say(f"✅ Done! Marked complete: *{matched}*")
    else:
        say(f"Couldn't find a matching open task for \"{description}\". Check the exact wording in Tasks.md.")


def handle_goals(say):
    """Show quarterly goals."""
    goals = parse_goals()
    if not goals:
        say("No quarterly goals found. Run `/quarter-plan` in Amp to set them up.")
        return

    text = "*📊 Quarterly Goals*\n\n"
    for g in goals:
        progress = g.get("progress", "?")
        bar = ""
        if isinstance(progress, int):
            filled = progress // 10
            bar = f" {'█' * filled}{'░' * (10-filled)} {progress}%"
        text += f"• {g['title']}{bar}\n"

    say(text)


def handle_priorities(say):
    """Show weekly priorities."""
    priorities = parse_priorities()
    if not priorities:
        say("No weekly priorities set. Run `/week-plan` in Amp to set them.")
        return

    text = "*🎯 This Week's Priorities*\n\n"
    for i, p in enumerate(priorities):
        text += f"{i+1}. {p}\n"
    say(text)


def handle_brief(say):
    """Trigger morning brief."""
    say("Generating morning brief... ☀️")
    try:
        result = subprocess.run(
            [sys.executable, str(Path(VAULT_PATH) / "scripts" / "morning_brief.py")],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "VAULT_PATH": VAULT_PATH}
        )
        if result.returncode == 0:
            say("Morning brief posted! Check #amp-briefings.")
        else:
            say(f"Brief generation had an issue: {result.stderr[:200]}")
    except Exception as e:
        say(f"Error running brief: {e}")


def handle_met(text, say):
    """Create or update a person page from a quick 'met' message."""
    # Parse: met Name, Role at Company, context notes
    text = text.strip()
    parts = text.split(",", 1)
    name = parts[0].strip()

    if not name:
        say("Usage: `met Sarah Chen, VP Design at Figma, discussed partnership`")
        return

    role = ""
    company = ""
    context = ""

    if len(parts) > 1:
        rest = parts[1].strip()
        # Check for "Role at Company, notes" pattern
        rest_parts = rest.split(",", 1)
        role_part = rest_parts[0].strip()

        if " at " in role_part:
            role, company = role_part.rsplit(" at ", 1)
            role = role.strip()
            company = company.strip()
        else:
            role = role_part

        if len(rest_parts) > 1:
            context = rest_parts[1].strip()

    # Determine internal vs external
    people_dir = Path(VAULT_PATH) / PEOPLE_DIR
    # Sanitize name to prevent path traversal
    import re as _re
    safe_name = _re.sub(r'[^a-zA-Z0-9_\-]', '', name.replace(" ", "_"))
    if not safe_name:
        say("Invalid name. Use only letters, numbers, and spaces.")
        return
    file_name = safe_name
    today = datetime.now().strftime("%Y-%m-%d")

    # Check if page already exists
    existing = None
    for subdir in ["Internal", "External", ""]:
        check_dir = people_dir / subdir if subdir else people_dir
        candidate = check_dir / f"{file_name}.md"
        if candidate.exists():
            existing = candidate
            break

    if existing:
        # Append new context to existing page
        addition = f"\n\n## Update - {today}\n"
        if context:
            addition += f"{context}\n"
        else:
            addition += f"Encountered again on {today}.\n"

        locked_file_append(existing, addition)
        say(f"👤 Updated *{name}*'s page with new context.\n📄 `{existing.relative_to(VAULT_PATH)}`")
    else:
        # Create new page in External by default
        ext_dir = people_dir / "External"
        ext_dir.mkdir(parents=True, exist_ok=True)
        new_file = ext_dir / f"{file_name}.md"

        # Verify resolved path stays within People directory
        if not new_file.resolve().is_relative_to(people_dir.resolve()):
            say("Invalid name.")
            return

        page_content = f"# {name}\n\n"
        if role:
            page_content += f"**Role:** {role}\n"
        if company:
            page_content += f"**Company:** {company}\n"
        page_content += f"**First Met:** {today}\n"
        page_content += f"\n## Context\n\n"
        if context:
            page_content += f"{context}\n"
        page_content += f"\n## Meetings\n\n"
        page_content += f"\n## Action Items\n\n"

        new_file.write_text(page_content)
        say(f"👤 Created page for *{name}*"
            + (f" ({role}" + (f" at {company})" if company else ")") if role else "")
            + f"\n📄 `{new_file.relative_to(VAULT_PATH)}`")


def handle_start_task(description, say):
    """Mark a task as started (in progress)."""
    tasks_path = Path(VAULT_PATH) / TASKS_FILE
    if not tasks_path.exists():
        say("No tasks file found.")
        return

    content = tasks_path.read_text()
    lines = content.splitlines()
    desc_lower = description.lower().strip()
    desc_words = [w for w in desc_lower.split() if len(w) > 2]

    for i, line in enumerate(lines):
        m = re.match(r"^- \[ \] \*\*(.+?)\*\*(.*)$", line)
        if not m:
            continue
        title = m.group(1).strip()
        if all(w in title.lower() for w in desc_words):
            match_idx = i

            def modifier(file_content, idx=match_idx):
                mod_lines = file_content.splitlines()
                if idx < len(mod_lines):
                    mod_lines[idx] = mod_lines[idx].replace("- [ ]", "- [s]", 1)
                return "\n".join(mod_lines)

            locked_file_update(tasks_path, modifier)
            say(f"🔄 Started: *{title}*")
            return

    say(f"Couldn't find an open task matching \"{description}\".")


def handle_block_task(text, say):
    """Mark a task as blocked with a reason."""
    # Parse: block Task Name - reason
    parts = text.split(" - ", 1)
    description = parts[0].strip()
    reason = parts[1].strip() if len(parts) > 1 else ""

    tasks_path = Path(VAULT_PATH) / TASKS_FILE
    if not tasks_path.exists():
        say("No tasks file found.")
        return

    content = tasks_path.read_text()
    lines = content.splitlines()
    desc_lower = description.lower().strip()
    desc_words = [w for w in desc_lower.split() if len(w) > 2]

    for i, line in enumerate(lines):
        m = re.match(r"^- \[[ s]\] \*\*(.+?)\*\*(.*)$", line)
        if not m:
            continue
        title = m.group(1).strip()
        if all(w in title.lower() for w in desc_words):
            match_idx = i
            block_reason = reason

            def modifier(file_content, idx=match_idx, rsn=block_reason):
                mod_lines = file_content.splitlines()
                if idx < len(mod_lines):
                    new_line = re.sub(r"^- \[.\]", "- [b]", mod_lines[idx])
                    if rsn and rsn not in new_line:
                        new_line = new_line.rstrip() + f" Blocked: {rsn}"
                    mod_lines[idx] = new_line
                return "\n".join(mod_lines)

            locked_file_update(tasks_path, modifier)
            say(f"🚫 Blocked: *{title}*" + (f"\n_{reason}_" if reason else ""))
            return

    say(f"Couldn't find a task matching \"{description}\".")


def handle_help(say):
    """Show available commands."""
    text = """*🤖 Amp Slack Commands*

*Daily:*
  `focus` - What should I work on?
  `brief` - Trigger morning brief
  `tasks` - Show open tasks
  `blocked` - Show blocked tasks
  `priorities` - This week's priorities
  `goals` - Quarterly goal progress

*Meetings:*
  `prep <meeting name>` - Meeting prep
  `prep` - Prep for next meeting

*People:*
  `who is <name>` - Person lookup
  `met <name>, <role> at <company>, <notes>` - Quick add person

*Actions:*
  `done <task>` - Mark task complete
  `start <task>` - Mark task in progress
  `block <task> - <reason>` - Mark task blocked
  `add <anything>` - Capture to inbox

*Inbox:*
  Any message in #amp-inbox auto-saves to your vault
"""
    say(text)


# ─── Message Router ────────────────────────────────────────────────────────

def handle_message(event, say, client):
    """Route incoming messages to appropriate handlers."""
    text = event.get("text", "").strip()
    channel = event.get("channel", "")
    subtype = event.get("subtype", "")

    # Ignore bot messages and message edits
    if subtype or event.get("bot_id"):
        return

    # Check if this is the inbox channel (capture everything)
    try:
        channel_info = client.conversations_info(channel=channel)
        channel_name = channel_info["channel"]["name"]
    except Exception:
        channel_name = ""

    if channel_name == INBOX_CHANNEL:
        file_path = capture_to_inbox(text)
        say(f"📥 Captured to `{file_path}`")
        return

    # Route commands
    text_lower = text.lower().strip()

    if text_lower in ["help", "commands", "?"]:
        handle_help(say)
    elif text_lower in ["focus", "what should i work on", "what's next", "suggest"]:
        handle_focus(say)
    elif text_lower in ["tasks", "my tasks", "open tasks", "task list"]:
        handle_tasks(say)
    elif text_lower in ["blocked", "blockers", "stuck"]:
        handle_blocked(say)
    elif text_lower in ["brief", "morning brief", "daily brief"]:
        handle_brief(say)
    elif text_lower in ["goals", "quarterly goals", "q1 goals", "goal progress"]:
        handle_goals(say)
    elif text_lower in ["priorities", "this week", "weekly priorities", "prios"]:
        handle_priorities(say)
    elif text_lower.startswith("prep"):
        query = text[4:].strip()
        handle_prep(query, say)
    elif text_lower.startswith("who is ") or text_lower.startswith("whois "):
        name = re.sub(r"^who\s*is\s*", "", text, flags=re.IGNORECASE).strip()
        handle_person(name, say)
    elif text_lower.startswith("done ") or text_lower.startswith("completed ") or text_lower.startswith("finished "):
        desc = re.sub(r"^(done|completed|finished)\s+", "", text, flags=re.IGNORECASE).strip()
        handle_done(desc, say)
    elif text_lower.startswith("start "):
        desc = text[6:].strip()
        handle_start_task(desc, say)
    elif text_lower.startswith("block "):
        desc = text[6:].strip()
        handle_block_task(desc, say)
    elif text_lower.startswith("met "):
        desc = text[4:].strip()
        handle_met(desc, say)
    elif text_lower.startswith("add ") or text_lower.startswith("capture ") or text_lower.startswith("inbox "):
        item = re.sub(r"^(add|capture|inbox)\s+", "", text, flags=re.IGNORECASE).strip()
        file_path = capture_to_inbox(item)
        say(f"📥 Captured: \"{item}\"\nSaved to `{file_path}`")
    else:
        say("I didn't understand that. Try `help` for commands, or `add <text>` to capture to inbox.")


def handle_mention(event, say):
    """Handle @Amp mentions."""
    text = event.get("text", "")
    # Strip the mention
    clean = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    # Reuse message handler logic
    handle_message({"text": clean, "channel": event.get("channel", "")}, say, app.client)


# ─── Main ──────────────────────────────────────────────────────────────────

LAST_SEEN_FILE = Path(VAULT_PATH) / "System" / ".slack_bot_last_seen.json"


def get_last_seen_ts():
    """Get the timestamp of when the bot was last online."""
    if LAST_SEEN_FILE.exists():
        try:
            data = json.loads(LAST_SEEN_FILE.read_text())
            return data.get("last_seen_ts")
        except Exception:
            pass
    return None


def save_last_seen_ts():
    """Save current time as the last-seen timestamp."""
    ts_data = json.dumps({
        "last_seen_ts": str(datetime.now().timestamp()),
        "last_seen_human": datetime.now().isoformat()
    })
    locked_file_update(LAST_SEEN_FILE, lambda _: ts_data)


def catchup_missed_messages():
    """Scan #amp-inbox for messages sent while the bot was offline."""
    last_ts = get_last_seen_ts()
    if not last_ts:
        print("   First run, no catchup needed.")
        save_last_seen_ts()
        return

    print(f"   Checking for messages missed since {datetime.fromtimestamp(float(last_ts)).strftime('%Y-%m-%d ') + f"{int(PLACEHOLDER.hour % 12 or 12)}:" + PLACEHOLDER.strftime('%M %p')}...")

    try:
        # Find the inbox channel
        channels = app.client.conversations_list(types="public_channel")
        inbox_id = None
        for ch in channels["channels"]:
            if ch["name"] == INBOX_CHANNEL:
                inbox_id = ch["id"]
                break

        if not inbox_id:
            print(f"   #{INBOX_CHANNEL} channel not found, skipping catchup.")
            save_last_seen_ts()
            return

        # Get messages since last seen
        result = app.client.conversations_history(
            channel=inbox_id,
            oldest=last_ts,
            limit=100
        )

        messages = result.get("messages", [])
        # Filter out bot messages and only get user messages
        user_messages = [
            m for m in messages
            if not m.get("bot_id") and not m.get("subtype") and m.get("text", "").strip()
        ]

        if not user_messages:
            print("   No missed messages.")
            save_last_seen_ts()
            return

        # Process oldest first
        user_messages.reverse()
        captured = 0

        for msg in user_messages:
            text = msg.get("text", "").strip()
            ts = msg.get("ts", "")

            # Skip if already captured (check by comparing timestamps)
            if not text:
                continue

            file_path = capture_to_inbox(text)
            captured += 1

        if captured > 0:
            print(f"   📥 Caught up {captured} missed message(s) from #amp-inbox")
            # Notify in the channel
            try:
                app.client.chat_postMessage(
                    channel=inbox_id,
                    text=f"📥 Back online! Caught up *{captured}* message(s) that were sent while I was away."
                )
            except Exception:
                pass

    except Exception as e:
        print(f"   Catchup error: {e}")

    save_last_seen_ts()


def main():
    global app
    validate_slack_config()

    app = App(token=SLACK_BOT_TOKEN)

    # Register event handlers
    app.event("message")(handle_message)
    app.event("app_mention")(handle_mention)

    print("🤖 Amp Slack Bot starting...")
    print(f"   Vault: {VAULT_PATH}")
    print(f"   Inbox channel: #{INBOX_CHANNEL}")

    # Catch up on missed messages before going live
    catchup_missed_messages()

    print(f"   Type 'help' in Slack to see commands")
    print()

    # Start a background thread to update last_seen periodically
    import threading
    import time

    def heartbeat():
        while True:
            save_last_seen_ts()
            time.sleep(300)  # every 5 minutes

    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()

    handler = SocketModeHandler(app, SLACK_APP_TOKEN)

    def shutdown(signum, frame):
        print(f"\nShutting down (signal {signum})...")
        save_last_seen_ts()
        handler.close()
        sys.exit(0)

    import signal
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    handler.start()


if __name__ == "__main__":
    main()
