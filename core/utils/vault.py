"""
Shared vault utilities for Amp scripts.

Canonical implementations of functions previously duplicated across
eod_digest.py, morning_brief.py, and meeting_prep_auto.py.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

from core.constants import TASKS_FILE
from datetime import datetime
from pathlib import Path


def load_env(vault_path: str) -> None:
    """Load environment variables from .env file in the vault root.

    Tries python-dotenv first for robust parsing (quoted values, interpolation).
    Falls back to simple manual parsing if dotenv is not installed.
    """
    env_path = Path(vault_path) / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
    except ImportError:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


def parse_tasks(vault_path: str) -> dict:
    """Parse tasks from Tasks.md into categorised lists.

    Returns a dict with keys:
        open      - list of dicts (title, priority, section)
        started   - list of dicts (title, priority, section, started=True)
        blocked   - list of dicts (title, section)
        done_today - list of dicts (title,)
    """
    tasks_path = Path(vault_path) / TASKS_FILE
    if not tasks_path.exists():
        return {"done_today": [], "open": [], "blocked": [], "started": []}

    content = tasks_path.read_text()
    today_str = datetime.now().strftime("%Y-%m-%d")
    open_tasks: list[dict] = []
    blocked: list[dict] = []
    done_today: list[dict] = []
    started: list[dict] = []
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
        title = title.strip()

        priority = ""
        if "P0" in current_section:
            priority = "P0"
        elif "P1" in current_section:
            priority = "P1"
        elif "This Week" in current_section:
            priority = "\U0001f3af"

        if status == " ":
            open_tasks.append({"title": title, "priority": priority, "section": current_section})
        elif status == "s":
            started.append({"title": title, "priority": priority, "section": current_section, "started": True})
        elif status == "b":
            blocked.append({"title": title, "section": current_section})
        elif status == "x" and today_str in rest:
            done_today.append({"title": title})

    return {"done_today": done_today, "open": open_tasks, "blocked": blocked, "started": started}


def post_to_slack(blocks: list, webhook_url: str, retries: int = 3) -> bool:
    """Post Slack Block Kit message via webhook with exponential-backoff retry.

    Returns True on success, False on failure after all retries.
    Client errors (400, 403, 404) are not retried.
    """
    if not webhook_url:
        print("Error: No Slack webhook URL provided.")
        return False

    payload = json.dumps({"blocks": blocks}).encode("utf-8")

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                print(f"Slack error: {resp.status}")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()
            except Exception:
                pass
            print(f"Slack error: {e.code} - {body}")
            if e.code in (400, 403, 404):
                return False
        except Exception as e:
            print(f"Slack request failed (attempt {attempt + 1}/{retries}): {e}")

        if attempt < retries - 1:
            delay = 2 ** attempt
            time.sleep(delay)

    return False


def format_event_time(start: str, end: str | None = None) -> str:
    """Format event timestamp string(s) for human-readable display.

    Handles ISO-8601 (``2026-01-15T09:00:00``), space-separated
    (``2026-01-15 09:00:00 +0000``), and other common calendar formats.

    If *end* is provided the result is ``"start - end"``.
    """
    def _format_single(ts: str) -> str:
        if not ts:
            return ""
        try:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(ts[:19], fmt)
                    return f"{dt.hour % 12 or 12}:{dt.strftime('%M %p')}"
                except ValueError:
                    continue

            # Manual fallback for partial/other formats
            if "T" in ts:
                time_part = ts.split("T")[1][:5]
            elif " " in ts:
                time_part = ts.split(" ")[1][:5]
            else:
                return ts[:16]

            h, m = int(time_part[:2]), int(time_part[3:5])
            period = "AM" if h < 12 else "PM"
            h = h if h <= 12 else h - 12
            h = 12 if h == 0 else h
            return f"{h}:{m:02d} {period}"
        except Exception:
            return ts[:16]

    result = _format_single(start)
    if end:
        end_str = _format_single(end)
        if end_str:
            result = f"{result} - {end_str}"
    return result
