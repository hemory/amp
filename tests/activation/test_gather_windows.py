"""Time-window enforcement per §3.1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.activation.gather import gather

from vault_fixture import build_vault


FROZEN_NOW = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


def test_meeting_notes_window_excludes_old_files(tmp_path, monkeypatch):
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            (
                "04-Projects/Foo/meeting-recent.md",
                "recent",
                FROZEN_NOW - timedelta(days=3),
            ),
            (
                "04-Projects/Foo/meeting-old.md",
                "old",
                FROZEN_NOW - timedelta(days=30),
            ),
        ],
    )
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    meeting_paths = {s.path for s in signals if s.source == "meeting_notes"}
    assert "04-Projects/Foo/meeting-recent.md" in meeting_paths
    assert "04-Projects/Foo/meeting-old.md" not in meeting_paths


def test_project_docs_window_is_14_days(tmp_path, monkeypatch):
    build_vault(
        tmp_path / "vault",
        project_docs=[
            (
                "04-Projects/Foo/design-recent.md",
                "recent",
                FROZEN_NOW - timedelta(days=10),
            ),
            (
                "04-Projects/Foo/design-stale.md",
                "stale",
                FROZEN_NOW - timedelta(days=20),
            ),
        ],
    )
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    doc_paths = {s.path for s in signals if s.source == "project_docs"}
    assert "04-Projects/Foo/design-recent.md" in doc_paths
    assert "04-Projects/Foo/design-stale.md" not in doc_paths


def test_session_learnings_14_day_window(tmp_path, monkeypatch):
    build_vault(
        tmp_path / "vault",
        learnings=[
            ("2026-04-15", "in window"),
            ("2026-04-01", "out of window"),
        ],
    )
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    learnings = [s for s in signals if s.source == "session_learnings"]
    names = {Path(s.path).name for s in learnings}
    assert "2026-04-15.md" in names
    assert "2026-04-01.md" not in names
