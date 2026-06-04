#!/usr/bin/env python3
"""
Amp End-of-Day Digest - Push evening summary to Slack.

Summarizes what was completed today, what's still open, blocked items,
and tomorrow's first meeting. Complements the morning brief.

Usage:
    python3 scripts/eod_digest.py              # Post digest
    python3 scripts/eod_digest.py --dry-run    # Preview without posting
    python3 scripts/eod_digest.py --test       # Send test message

Scheduling (macOS LaunchAgent):
    See ~/Library/LaunchAgents/com.amp.eod-digest.plist
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


def get_tomorrow_events():
    """Get tomorrow's calendar events."""
    eventkit_path = Path(VAULT_PATH) / "core" / "mcp" / "scripts" / "calendar_eventkit.py"
    if not eventkit_path.exists():
        return []

    try:
        result = subprocess.run(
            [sys.executable, str(eventkit_path), "events", CALENDAR_NAME, "1", "2"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data, list):
                return [e for e in data if not e.get("all_day", False)]
    except Exception:
        pass
    return []


def check_inbox():
    """Count unprocessed items in inbox folders."""
    inbox_path = Path(VAULT_PATH) / "00-Inbox"
    count = 0
    for subfolder in ["Meetings", "Ideas", "Slack"]:
        folder = inbox_path / subfolder
        if folder.exists():
            today_str = datetime.now().strftime("%Y-%m-%d")
            for f in folder.glob("*.md"):
                if today_str in f.name:
                    content = f.read_text()
                    count += len(re.findall(r"^- \[ \]", content, re.MULTILINE))
    return count


def build_blocks(tasks, tomorrow_events, inbox_count):
    """Build Slack blocks for EOD digest."""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    tomorrow_name = f"{tomorrow.strftime('%A, %B')} {tomorrow.day}"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🌙 End of Day Wrap-Up", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"📅 {now.strftime('%A, %B')} {now.day} | {now.hour % 12 or 12}:{now.strftime('%M %p')}"}]
        },
        {"type": "divider"},
    ]

    # Completed today
    if tasks["done_today"]:
        done_lines = [f"• ✅ {t['title']}" for t in tasks["done_today"]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🏆 Completed Today ({len(tasks['done_today'])})*\n" + "\n".join(done_lines)}
        })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🏆 Completed Today*\nNo tasks marked done today."}
        })

    # In progress
    if tasks["started"]:
        started_lines = [f"• 🔄 {t['title']}" for t in tasks["started"][:5]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🔄 Still In Progress*\n" + "\n".join(started_lines)}
        })

    # Blocked
    if tasks["blocked"]:
        blocked_lines = [f"• 🚫 {t['title']}" for t in tasks["blocked"][:3]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*⚠️ Blocked*\n" + "\n".join(blocked_lines)}
        })

    blocks.append({"type": "divider"})

    # Stats bar
    open_count = len(tasks["open"]) + len(tasks["started"])
    stats = f"📊 *Today's Stats:* {len(tasks['done_today'])} completed | {open_count} still open | {len(tasks['blocked'])} blocked"
    if inbox_count > 0:
        stats += f" | {inbox_count} inbox items to triage"
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": stats}
    })

    blocks.append({"type": "divider"})

    # Tomorrow preview
    if tomorrow_events:
        first_meeting = tomorrow_events[0]
        time_str = format_event_time(first_meeting.get("start", ""))
        title = first_meeting.get("title", "Meeting")
        attendee_count = len(first_meeting.get("attendees", []))

        tomorrow_text = f"*📅 Tomorrow ({tomorrow_name})*\n"
        tomorrow_text += f"First meeting: *{time_str}* - {title}"
        if attendee_count > 0:
            tomorrow_text += f" ({attendee_count} attendees)"
        tomorrow_text += f"\n{len(tomorrow_events)} meeting(s) total"

        # Top open tasks for tomorrow
        top_tasks = tasks["started"][:2] + [t for t in tasks["open"] if t.get("priority") in ["P0", "🎯"]][:2]
        if top_tasks:
            tomorrow_text += "\n\n*Focus for tomorrow:*"
            for t in top_tasks[:3]:
                prio = f"[{t['priority']}] " if t.get("priority") else ""
                tomorrow_text += f"\n• {prio}{t['title']}"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": tomorrow_text}
        })
    else:
        # No meetings tomorrow
        top_tasks = tasks["started"][:2] + [t for t in tasks["open"] if t.get("priority") in ["P0", "🎯"]][:3]
        tomorrow_text = f"*📅 Tomorrow ({tomorrow_name})*\nNo meetings. Deep work day! 🎉"
        if top_tasks:
            tomorrow_text += "\n\n*Focus for tomorrow:*"
            for t in top_tasks[:3]:
                prio = f"[{t['priority']}] " if t.get("priority") else ""
                tomorrow_text += f"\n• {prio}{t['title']}"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": tomorrow_text}
        })

    # Footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"_Amp EOD Digest | {now.hour % 12 or 12}:{now.strftime('%M %p')} | Run `/daily-review` in Amp for full daily review_"}]
    })

    return blocks


def send_test():
    now = datetime.now()
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🧪 EOD Digest Test", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "EOD digest is working! You'll see your wrap-up here at 5 PM."}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"_Sent {now.strftime('%Y-%m-%d')} {now.hour % 12 or 12}:{now.strftime('%M %p')}_"}]}
    ]
    return post_to_slack(blocks, WEBHOOK_URL)


def main():
    global WEBHOOK_URL
    load_env(VAULT_PATH)
    WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", WEBHOOK_URL)

    if "--test" in sys.argv:
        sys.exit(0 if send_test() else 1)

    dry_run = "--dry-run" in sys.argv

    print("Gathering end-of-day data...")
    tasks = parse_tasks(VAULT_PATH)
    tomorrow_events = get_tomorrow_events()
    inbox_count = check_inbox()

    print(f"  Completed today: {len(tasks['done_today'])}")
    print(f"  Still open: {len(tasks['open'])}")
    print(f"  In progress: {len(tasks['started'])}")
    print(f"  Blocked: {len(tasks['blocked'])}")
    print(f"  Tomorrow's meetings: {len(tomorrow_events)}")
    print(f"  Inbox items: {inbox_count}")

    blocks = build_blocks(tasks, tomorrow_events, inbox_count)
    if dry_run:
        print(json.dumps({"blocks": blocks}, indent=2))
        success = True
    else:
        success = post_to_slack(blocks, WEBHOOK_URL)
        if success:
            now = datetime.now()
            print(f"EOD digest posted at {now.hour % 12 or 12}:{now.strftime('%M %p')}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
