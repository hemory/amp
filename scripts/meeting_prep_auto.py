#!/usr/bin/env python3
"""
Amp Auto Meeting Prep - Posts meeting prep to Slack before upcoming meetings.

Checks for meetings starting in the next 60 minutes, gathers attendee context
from person pages, and posts a prep summary to Slack.

Usage:
    python3 scripts/meeting_prep_auto.py              # Check and post prep
    python3 scripts/meeting_prep_auto.py --dry-run    # Preview without posting
    python3 scripts/meeting_prep_auto.py --horizon 90  # Check next 90 minutes

Scheduling:
    Run every 30 minutes via LaunchAgent or cron.
    Tracks already-prepped meetings to avoid duplicates.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.utils.vault import load_env, post_to_slack

VAULT_PATH = os.environ.get("VAULT_PATH", str(Path(__file__).resolve().parent.parent))
WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
CALENDAR_NAME = "Calendar"
HORIZON_MINUTES = 60
PREPPED_FILE = Path(VAULT_PATH) / "System" / ".meeting_prep_cache.json"


def get_prepped_meetings():
    """Load set of already-prepped meeting keys to avoid duplicates."""
    if PREPPED_FILE.exists():
        try:
            data = json.loads(PREPPED_FILE.read_text())
            # Clean entries older than 24 hours
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            return {k: v for k, v in data.items() if v > cutoff}
        except Exception:
            pass
    return {}


def save_prepped_meeting(key):
    """Mark a meeting as prepped."""
    import fcntl
    PREPPED_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = PREPPED_FILE.parent / ".prepped.lock"
    with open(lock_path, 'w') as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            prepped = get_prepped_meetings()
            prepped[key] = datetime.now().isoformat()
            PREPPED_FILE.write_text(json.dumps(prepped, indent=2))
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)


def get_upcoming_events(horizon_minutes):
    """Get calendar events starting within the next N minutes."""
    eventkit_path = Path(VAULT_PATH) / "core" / "mcp" / "scripts" / "calendar_eventkit.py"
    if not eventkit_path.exists():
        return []

    try:
        result = subprocess.run(
            [sys.executable, str(eventkit_path), "events", CALENDAR_NAME, "0", "1"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        if not isinstance(data, list):
            return []

        now = datetime.now()
        horizon = now + timedelta(minutes=horizon_minutes)
        upcoming = []

        for event in data:
            if event.get("all_day"):
                continue

            start_str = event.get("start", "")
            try:
                # Parse various EventKit date formats
                event_start = None
                for fmt in ["%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        event_start = datetime.strptime(start_str[:19], fmt[:19])
                        break
                    except ValueError:
                        continue

                if event_start and now <= event_start <= horizon:
                    event["_parsed_start"] = event_start
                    upcoming.append(event)
            except Exception:
                continue

        return sorted(upcoming, key=lambda e: e["_parsed_start"])
    except Exception:
        return []


def lookup_person(name):
    """Look up a person from person pages. Returns context dict or None."""
    people_dir = Path(VAULT_PATH) / "05-Areas" / "People"
    if not people_dir.exists():
        return None

    # Normalize name for file matching
    name_parts = name.strip().split()
    if not name_parts:
        return None

    # Try exact match first, then fuzzy
    for subdir in ["Internal", "External", ""]:
        search_dir = people_dir / subdir if subdir else people_dir
        if not search_dir.exists():
            continue

        for page in search_dir.glob("*.md"):
            page_name = page.stem.replace("_", " ").lower()
            search_name = name.lower().strip()

            if page_name == search_name or all(p.lower() in page_name for p in name_parts):
                content = page.read_text()
                context = {"name": name, "file": str(page.relative_to(VAULT_PATH))}

                # Extract role
                role_match = re.search(r"(?:Role|Title|Position):\s*(.+)", content, re.IGNORECASE)
                if role_match:
                    context["role"] = role_match.group(1).strip()

                # Extract company
                company_match = re.search(r"(?:Company|Organization|Org):\s*(.+)", content, re.IGNORECASE)
                if company_match:
                    context["company"] = company_match.group(1).strip()

                # Extract last interaction
                meeting_refs = re.findall(r"\d{4}-\d{2}-\d{2}", content)
                if meeting_refs:
                    context["last_seen"] = sorted(meeting_refs)[-1]

                # Extract key context (notes, working style, etc.)
                context_match = re.search(r"(?:## Context|## Notes|## Key Context)\n([\s\S]*?)(?:\n## |\Z)", content)
                if context_match:
                    notes = context_match.group(1).strip()[:200]
                    if notes:
                        context["notes"] = notes

                # Extract open action items
                actions = []
                for line in content.splitlines():
                    if re.match(r"^- \[ \]", line):
                        clean = re.sub(r"^- \[ \] ", "", line).strip()
                        if clean:
                            actions.append(clean[:100])
                if actions:
                    context["open_actions"] = actions[:3]

                return context
    return None


def find_related_tasks(meeting_title, attendee_names):
    """Find tasks related to meeting topic or attendees."""
    tasks_path = Path(VAULT_PATH) / "03-Tasks" / "Tasks.md"
    if not tasks_path.exists():
        return []

    content = tasks_path.read_text()
    related = []
    keywords = meeting_title.lower().split()

    for line in content.splitlines():
        task_match = re.match(r"^- \[(.)\] \*\*(.+?)\*\*(.*)$", line)
        if not task_match or task_match.group(1) in ["x"]:
            continue

        title = task_match.group(2).lower()

        # Check if task mentions any attendee or meeting keyword
        for name in attendee_names:
            if name.lower().split()[0] in title:
                related.append(task_match.group(2))
                break
        else:
            for kw in keywords:
                if len(kw) > 3 and kw in title:
                    related.append(task_match.group(2))
                    break

    return related[:5]


def format_time(dt):
    """Format datetime for display."""
    return f"{dt.hour % 12 or 12}:{dt.strftime('%M %p')}"


def build_prep_blocks(event, attendee_contexts, related_tasks):
    """Build Slack blocks for meeting prep."""
    title = event.get("title", "Untitled Meeting")
    start = event.get("_parsed_start", datetime.now())
    minutes_until = int((start - datetime.now()).total_seconds() / 60)
    location = event.get("location", "")
    url = event.get("url", "")
    notes = event.get("notes", "")
    attendees = event.get("attendees", [])

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📋 Meeting Prep: {title}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"⏰ Starting in *{minutes_until} minutes* at {format_time(start)}"}]
        },
        {"type": "divider"},
    ]

    # Meeting details
    details = f"*🕐 Time:* {format_time(start)}"
    if location:
        details += f"\n*📍 Location:* {location}"
    if url:
        details += f"\n*🔗 Link:* <{url}|Join Meeting>"
    if notes:
        details += f"\n*📝 Notes:* {notes[:200]}"

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": details}})

    # Attendees with context
    if attendees:
        attendee_text = f"*👥 Attendees ({len(attendees)})*\n"
        for att in attendees[:8]:
            name = att.get("name", att.get("email", "Unknown"))
            status_emoji = {"Accepted": "✅", "Tentative": "❓", "Declined": "❌"}.get(att.get("status", ""), "⬜")
            role_str = ""

            # Add person page context
            ctx = attendee_contexts.get(name)
            if ctx:
                if ctx.get("role"):
                    role_str = f" - _{ctx['role']}_"
                if ctx.get("last_seen"):
                    role_str += f" (last met: {ctx['last_seen']})"

            attendee_text += f"• {status_emoji} *{name}*{role_str}\n"

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": attendee_text}})

    # Person context deep-dive (for attendees with rich profiles)
    for name, ctx in attendee_contexts.items():
        if ctx and (ctx.get("notes") or ctx.get("open_actions")):
            person_text = f"*💡 Context: {name}*\n"
            if ctx.get("notes"):
                person_text += f"{ctx['notes']}\n"
            if ctx.get("open_actions"):
                person_text += "*Open items:*\n"
                for action in ctx["open_actions"]:
                    person_text += f"  • {action}\n"
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": person_text}})

    # Related tasks
    if related_tasks:
        task_text = "*🔗 Related Tasks*\n"
        for t in related_tasks:
            task_text += f"• {t}\n"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": task_text}})

    # Footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"_Amp Meeting Prep | {datetime.now().hour % 12 or 12}:{datetime.now().strftime('%M %p')}_"}]
    })

    return blocks


def main():
    global WEBHOOK_URL
    load_env(VAULT_PATH)
    WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", WEBHOOK_URL)

    dry_run = "--dry-run" in sys.argv
    horizon = HORIZON_MINUTES

    # Parse --horizon flag
    for i, arg in enumerate(sys.argv):
        if arg == "--horizon" and i + 1 < len(sys.argv):
            horizon = int(sys.argv[i + 1])

    print(f"Checking for meetings in the next {horizon} minutes...")
    upcoming = get_upcoming_events(horizon)

    if not upcoming:
        print("No upcoming meetings to prep for.")
        sys.exit(0)

    prepped = get_prepped_meetings()
    new_meetings = []

    for event in upcoming:
        key = f"{event.get('title', '')}_{event.get('start', '')}"
        if key not in prepped:
            new_meetings.append(event)

    if not new_meetings:
        print("All upcoming meetings already prepped.")
        sys.exit(0)

    print(f"Found {len(new_meetings)} meeting(s) to prep:")

    for event in new_meetings:
        title = event.get("title", "Untitled")
        start = event.get("_parsed_start", datetime.now())
        print(f"  Prepping: {title} at {format_time(start)}")

        # Gather attendee context
        attendees = event.get("attendees", [])
        attendee_names = [a.get("name", "") for a in attendees if a.get("name")]
        attendee_contexts = {}
        for name in attendee_names:
            ctx = lookup_person(name)
            if ctx:
                attendee_contexts[name] = ctx

        # Find related tasks
        related_tasks = find_related_tasks(title, attendee_names)

        # Build and post
        blocks = build_prep_blocks(event, attendee_contexts, related_tasks)
        if dry_run:
            print(json.dumps({"blocks": blocks}, indent=2))
            success = True
        else:
            success = post_to_slack(blocks, WEBHOOK_URL)

        if success and not dry_run:
            key = f"{title}_{event.get('start', '')}"
            save_prepped_meeting(key)
            print(f"  Posted prep for: {title}")

    print("Done.")


if __name__ == "__main__":
    main()
