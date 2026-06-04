#!/usr/bin/env python3
"""
Amp Morning Brief - Push-based daily briefing to Slack.

Reads calendar events, tasks, and weekly priorities from the vault,
then formats and posts a morning briefing to Slack via webhook.

Usage:
    python3 scripts/morning_brief.py              # Post morning brief
    python3 scripts/morning_brief.py --dry-run    # Preview without posting
    python3 scripts/morning_brief.py --test       # Send a test message

Scheduling (macOS LaunchAgent):
    See ~/Library/LaunchAgents/com.amp.morning-brief.plist
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.utils.vault import load_env, parse_tasks, post_to_slack, format_event_time

VAULT_PATH = os.environ.get("VAULT_PATH", str(Path(__file__).resolve().parent.parent))
WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
CALENDAR_NAME = "Calendar"

# Day greetings based on time
GREETINGS = {
    range(5, 12): "Good morning",
    range(12, 17): "Good afternoon",
    range(17, 24): "Good evening",
}


def get_greeting():
    hour = datetime.now().hour
    for time_range, greeting in GREETINGS.items():
        if hour in time_range:
            return greeting
    return "Hey"


def get_calendar_events():
    """Get today's calendar events via EventKit bridge."""
    eventkit_path = Path(VAULT_PATH) / "core" / "mcp" / "scripts" / "calendar_eventkit.py"
    if not eventkit_path.exists():
        return []

    try:
        result = subprocess.run(
            [sys.executable, str(eventkit_path), "events", CALENDAR_NAME, "0", "1"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "error" in data:
                return []
            return data if isinstance(data, list) else []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return []


def parse_priorities():
    """Extract weekly priorities from Week_Priorities.md."""
    priorities_path = Path(VAULT_PATH) / "02-Week_Priorities" / "Week_Priorities.md"
    if not priorities_path.exists():
        return []

    content = priorities_path.read_text()
    priorities = []

    # Look for priority items (numbered or bulleted under relevant sections)
    in_priorities = False
    for line in content.splitlines():
        line = line.strip()
        if "Top" in line and ("Week" in line or "Prior" in line):
            in_priorities = True
            continue
        if in_priorities:
            if line.startswith("## ") or line.startswith("---"):
                in_priorities = False
                continue
            # Match numbered or bulleted priority items
            prio_match = re.match(r"^[\d\-\*]+\.?\s*\*?\*?(.+?)\*?\*?\s*$", line)
            if prio_match and len(prio_match.group(1).strip()) > 3:
                priorities.append(prio_match.group(1).strip())

    return priorities[:5]


def parse_commitments():
    """Check for commitments due today from person pages and meeting notes."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    commitments = []

    # Scan recent meeting notes for action items mentioning today
    inbox_path = Path(VAULT_PATH) / "00-Inbox" / "Meetings"
    if inbox_path.exists():
        for note in sorted(inbox_path.glob("*.md"), reverse=True)[:10]:
            content = note.read_text()
            for line in content.splitlines():
                if today_str in line and ("follow" in line.lower() or "action" in line.lower() or "send" in line.lower()):
                    clean = re.sub(r"[#\-\*\[\]>]", "", line).strip()
                    if len(clean) > 10:
                        commitments.append(clean[:120])

    return commitments[:5]


def build_slack_blocks(events, tasks, priorities, commitments):
    """Build Slack Block Kit message."""
    greeting = get_greeting()
    today = datetime.now()
    day_name = f"{today.strftime('%A, %B')} {today.day}"

    # Load user name from profile
    user_name = "there"
    try:
        import yaml
        profile_path = Path(VAULT_PATH) / "System" / "user-profile.yaml"
        if profile_path.exists():
            with open(profile_path) as f:
                profile = yaml.safe_load(f)
                user_name = profile.get("name", "there")
    except Exception:
        pass

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"☀️ {greeting}, {user_name}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"📅 *{day_name}* | Amp Morning Brief"}]
        },
        {"type": "divider"},
    ]

    # Today's meetings
    if events:
        # Filter out all-day events and sort by start time
        timed_events = [e for e in events if not e.get("all_day", False)]
        all_day_events = [e for e in events if e.get("all_day", False)]

        meeting_lines = []
        for e in timed_events[:10]:
            time_str = format_event_time(e.get("start", ""))
            title = e.get("title", "Untitled")
            attendee_count = len(e.get("attendees", []))
            attendee_str = f" ({attendee_count} attendees)" if attendee_count > 0 else ""
            meeting_lines.append(f"• *{time_str}* - {title}{attendee_str}")

        if all_day_events:
            for e in all_day_events:
                meeting_lines.append(f"• 📌 _{e.get('title', 'All day event')}_ (all day)")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📅 Today's Meetings ({len(events)})*\n" + "\n".join(meeting_lines)}
        })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*📅 Today's Meetings*\nNo meetings today. Deep work day! 🎉"}
        })

    blocks.append({"type": "divider"})

    # Weekly priorities
    if priorities:
        prio_lines = [f"{i+1}. {p}" for i, p in enumerate(priorities)]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🎯 This Week's Priorities*\n" + "\n".join(prio_lines)}
        })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🎯 This Week's Priorities*\n_No priorities set. Run `/week-plan` to set them._"}
        })

    # Open tasks (top 8)
    all_open = tasks.get("started", []) + tasks["open"]
    open_tasks = all_open[:8]
    if open_tasks:
        task_lines = []
        for t in open_tasks:
            started = "🔄 " if t.get("started") else ""
            prio = f"[{t['priority']}] " if t.get("priority") else ""
            task_lines.append(f"• {started}{prio}{t['title']}")

        remaining = len(all_open) - len(open_tasks)
        if remaining > 0:
            task_lines.append(f"_...and {remaining} more_")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*✅ Open Tasks ({len(all_open)})*\n" + "\n".join(task_lines)}
        })

    # Blocked tasks
    if tasks["blocked"]:
        blocked_lines = [f"• 🚫 {t['title']}" for t in tasks["blocked"][:3]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*⚠️ Blocked*\n" + "\n".join(blocked_lines)}
        })

    # Commitments due
    if commitments:
        commit_lines = [f"• {c}" for c in commitments]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🤝 Commitments Due*\n" + "\n".join(commit_lines)}
        })

    # Yesterday's completions
    if tasks["done_today"]:
        done_lines = [f"• ✅ {t['title']}" for t in tasks["done_today"][:5]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🏆 Completed Today*\n" + "\n".join(done_lines)}
        })

    # Footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"_Amp Morning Brief | Generated {today.hour % 12 or 12}:{today.strftime('%M %p')}_"}]
    })

    return blocks


def send_test():
    """Send a test message to verify webhook works."""
    now = datetime.now()
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🧪 Amp Test Message", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "Webhook is working! Your morning briefs will appear here."}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"_Sent {now.strftime('%Y-%m-%d')} {now.hour % 12 or 12}:{now.strftime('%M %p')}_"}]}
    ]
    return post_to_slack(blocks, WEBHOOK_URL)


def main():
    global WEBHOOK_URL
    load_env(VAULT_PATH)
    WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", WEBHOOK_URL)

    if "--test" in sys.argv:
        success = send_test()
        sys.exit(0 if success else 1)

    dry_run = "--dry-run" in sys.argv

    print("Gathering morning brief data...")
    events = get_calendar_events()
    tasks = parse_tasks(VAULT_PATH)
    priorities = parse_priorities()
    commitments = parse_commitments()

    all_open = tasks.get("started", []) + tasks["open"]
    print(f"  Calendar: {len(events)} events")
    print(f"  Tasks: {len(all_open)} open, {len(tasks['blocked'])} blocked")
    print(f"  Priorities: {len(priorities)}")
    print(f"  Commitments: {len(commitments)}")

    blocks = build_slack_blocks(events, tasks, priorities, commitments)
    if dry_run:
        print(json.dumps({"blocks": blocks}, indent=2))
        success = True
    else:
        success = post_to_slack(blocks, WEBHOOK_URL)
        if success:
            now = datetime.now()
            print(f"Morning brief posted to Slack at {now.hour % 12 or 12}:{now.strftime('%M %p')}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
