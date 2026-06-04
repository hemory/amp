"""Calendar failure must not break the pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.activation.gather import gather

from vault_fixture import build_vault


FROZEN_NOW = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


def test_calendar_helper_unavailable_returns_other_sources(tmp_path, monkeypatch, capsys):
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            ("04-Projects/X/meeting.md", "body", FROZEN_NOW - timedelta(hours=1)),
        ],
    )

    import core.activation.gather as g

    # Helper returns None (simulating failed import / no calendar access).
    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    assert any(s.source == "meeting_notes" for s in signals)
    assert all(s.source != "calendar" for s in signals)


def test_calendar_fetch_raises_is_swallowed(tmp_path, monkeypatch, capsys):
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            ("04-Projects/X/meeting.md", "body", FROZEN_NOW - timedelta(hours=1)),
        ],
    )
    import core.activation.gather as g

    def boom(start, end):
        raise RuntimeError("no calendar permission")

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: boom)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    captured = capsys.readouterr()
    assert "calendar fetch failed" in captured.err
    assert any(s.source == "meeting_notes" for s in signals)
    assert all(s.source != "calendar" for s in signals)


def test_calendar_success_emits_signals(tmp_path, monkeypatch):
    build_vault(tmp_path / "vault")
    import core.activation.gather as g

    ev_start = (FROZEN_NOW + timedelta(hours=2)).isoformat()
    ev_end = (FROZEN_NOW + timedelta(hours=3)).isoformat()

    def fake(start, end):
        return {
            "success": True,
            "events": [
                {
                    "title": "1:1 with Alex",
                    "start": ev_start,
                    "end": ev_end,
                    "attendees": [{"name": "Alex"}],
                },
            ],
        }

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: fake)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    cal = [s for s in signals if s.source == "calendar"]
    assert len(cal) == 1
    assert "1:1 with Alex" in cal[0].excerpt
