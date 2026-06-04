"""Tombstone filter: signal matching a tombstone pattern must be dropped."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from core.activation.gather import gather

from vault_fixture import build_vault


FROZEN_NOW = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


def test_tombstone_substring_pattern_filters_signal(tmp_path, monkeypatch):
    tomb_row = {
        "tombstone_id": "tomb0001",
        "created_at": FROZEN_NOW.isoformat(),
        "type": "meeting_followup",
        "pattern": "04-Projects/Foo/meeting.md",
    }
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            ("04-Projects/Foo/meeting.md", "should be tombstoned", FROZEN_NOW - timedelta(hours=1)),
            ("04-Projects/Bar/meeting.md", "should survive", FROZEN_NOW - timedelta(hours=1)),
        ],
        tombstones_jsonl=json.dumps(tomb_row) + "\n",
    )
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    paths = {s.path for s in signals if s.source == "meeting_notes"}
    assert "04-Projects/Foo/meeting.md" not in paths
    assert "04-Projects/Bar/meeting.md" in paths


def test_tombstone_glob_pattern_filters(tmp_path, monkeypatch):
    tomb_row = {
        "tombstone_id": "tomb0002",
        "created_at": FROZEN_NOW.isoformat(),
        "type": "meeting_followup",
        "pattern": "meeting_notes|04-Projects/Foo/*",
    }
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            ("04-Projects/Foo/meeting.md", "x", FROZEN_NOW - timedelta(hours=1)),
            ("04-Projects/Bar/meeting.md", "y", FROZEN_NOW - timedelta(hours=1)),
        ],
        tombstones_jsonl=json.dumps(tomb_row) + "\n",
    )
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=tmp_path / "vault")
    paths = {s.path for s in signals if s.source == "meeting_notes"}
    assert "04-Projects/Foo/meeting.md" not in paths
    assert "04-Projects/Bar/meeting.md" in paths
