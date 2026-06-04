"""Sprint 2.5 — content-date scanning for meeting notes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.activation.gather import (
    extract_latest_content_date,
    gather,
)

from vault_fixture import build_vault, set_mtime


FROZEN_NOW = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_calendar(monkeypatch):
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)


# ---------- extract_latest_content_date ----------


def test_extract_latest_prefers_latest_past_date():
    text = "Feb 6, 2026 kickoff\n\nFollowup on 2026-04-12 with Lin."
    got = extract_latest_content_date(text, now=FROZEN_NOW)
    assert got is not None
    assert got.date().isoformat() == "2026-04-12"


def test_extract_latest_ignores_future_dates():
    text = "We'll meet on May 30, 2026 to review."  # future
    got = extract_latest_content_date(text, now=FROZEN_NOW)
    assert got is None


def test_extract_latest_resolves_short_form_from_nearby_year():
    text = "Kickoff in 2026.\n\nFeb 6 — agenda."
    got = extract_latest_content_date(text, now=FROZEN_NOW)
    assert got is not None
    assert got.date().isoformat() == "2026-02-06"


def test_extract_latest_returns_none_for_empty():
    assert extract_latest_content_date("", now=FROZEN_NOW) is None
    assert extract_latest_content_date("no dates here at all", now=FROZEN_NOW) is None


# ---------- _gather_meeting_notes with content-date scan ----------


def _meeting(body: str, rel: str, mtime: datetime):
    return (rel, body, mtime)


def test_content_date_scan_picks_latest(tmp_path):
    """File mtime 30 days ago; content mentions 2026-04-12 — included."""
    body = "Feb 6, 2026 kickoff.\n\nFollowup notes from 2026-04-12."
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            _meeting(body, "04-Projects/Foo/meeting-notes.md", FROZEN_NOW - timedelta(days=30)),
        ],
    )
    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    meetings = [s for s in signals if s.source == "meeting_notes"]
    assert len(meetings) == 1
    # Effective timestamp is the content date (2026-04-12), not mtime.
    assert meetings[0].timestamp.startswith("2026-04-12")


def test_content_date_fallback_to_mtime(tmp_path):
    body = "No dates in this meeting planning note."
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            _meeting(body, "04-Projects/Foo/meeting-followup.md", FROZEN_NOW - timedelta(days=5)),
        ],
    )
    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    meetings = [s for s in signals if s.source == "meeting_notes"]
    assert len(meetings) == 1
    # Timestamp is derived from mtime (approximately 5 days ago).
    ts = datetime.fromisoformat(meetings[0].timestamp)
    assert abs((ts - (FROZEN_NOW - timedelta(days=5))).total_seconds()) < 5


def test_frontmatter_meeting_date_wins(tmp_path):
    """Frontmatter meeting_date trumps both content scan and mtime."""
    body = (
        "---\n"
        "meeting_date: 2026-04-10\n"
        "attendees: [Alex_Rivera, the user]\n"
        "calendar_event_id: \"evt-abc-123\"\n"
        "---\n\n"
        "Discussion from Feb 6, 2026 and 2026-03-01 follow-ups.\n"
    )
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            _meeting(body, "04-Projects/Foo/meeting-notes.md", FROZEN_NOW - timedelta(days=30)),
        ],
    )
    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    meetings = [s for s in signals if s.source == "meeting_notes"]
    assert len(meetings) == 1
    assert meetings[0].timestamp.startswith("2026-04-10")
    # Structured payload surfaces the frontmatter for Sprint 3 matching.
    assert meetings[0].structured is not None
    assert meetings[0].structured["calendar_event_id"] == "evt-abc-123"
    assert meetings[0].structured["attendees"] == ["Alex_Rivera", "the user"]
    assert meetings[0].structured["meeting_date"] == "2026-04-10"


def test_content_date_ignores_future_dates(tmp_path):
    """File mentions future May 30, 2026 — ignored; falls back to mtime."""
    body = "Upcoming: May 30, 2026 strategy session."
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            _meeting(body, "04-Projects/Foo/meeting-preview.md", FROZEN_NOW - timedelta(days=2)),
        ],
    )
    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    meetings = [s for s in signals if s.source == "meeting_notes"]
    assert len(meetings) == 1
    ts = datetime.fromisoformat(meetings[0].timestamp)
    # Should use mtime (~2 days ago), NOT the future date.
    assert ts < FROZEN_NOW
    assert ts > FROZEN_NOW - timedelta(days=3)


def test_meeting_window_now_14_days(tmp_path):
    """A meeting 10 days old by content-date is kept (would have been out under 7d)."""
    body = "Planning note dated 2026-04-07."  # 10 days before FROZEN_NOW
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            _meeting(body, "04-Projects/Foo/meeting-recap.md", FROZEN_NOW - timedelta(days=60)),
        ],
    )
    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    meetings = [s for s in signals if s.source == "meeting_notes"]
    assert len(meetings) == 1
    assert meetings[0].timestamp.startswith("2026-04-07")


def test_meeting_outside_14_day_window_excluded(tmp_path):
    body = "Notes from 2026-03-01 — well outside window."
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            _meeting(body, "04-Projects/Foo/meeting-archive.md", FROZEN_NOW - timedelta(days=60)),
        ],
    )
    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    meetings = [s for s in signals if s.source == "meeting_notes"]
    assert meetings == []
