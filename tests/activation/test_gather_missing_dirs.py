"""Gather must tolerate missing source dirs without raising."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.activation.gather import gather

from vault_fixture import build_vault


FROZEN_NOW = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


def test_missing_dirs_do_not_raise(tmp_path, monkeypatch):
    # Empty vault (no People dir, no Session_Learnings, no Tasks, no projects).
    build_vault(tmp_path / "vault")
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    assert signals == []


def test_missing_people_dir_emits_zero_person_signals(tmp_path, monkeypatch):
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            (
                "04-Projects/X/meeting.md",
                "body",
                FROZEN_NOW,
            )
        ],
    )
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    assert all(s.source != "person_pages" for s in signals)
    # Other sources still work.
    assert any(s.source == "meeting_notes" for s in signals)
