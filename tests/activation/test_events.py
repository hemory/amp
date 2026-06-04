"""Sprint 7 H3 — append-only event log."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.activation.events import append_event, iter_events


def test_append_then_iter_roundtrip(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    append_event(path, offer_id="o-1", response="accepted", mode="live", now=now)
    append_event(path, offer_id="o-1", response="rejected", mode="live",
                 now=now + timedelta(hours=1), reason="changed mind")

    rows = list(iter_events(path))
    assert len(rows) == 2
    assert rows[0].offer_id == "o-1"
    assert rows[0].response == "accepted"
    assert rows[1].response == "rejected"
    assert rows[1].reason == "changed mind"


def test_iter_window_filters(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    base = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        append_event(path, offer_id=f"o-{i}", response="accepted", mode="live",
                     now=base + timedelta(days=i))
    rows = list(iter_events(
        path,
        since=base + timedelta(days=1),
        until=base + timedelta(days=3),
    ))
    # since inclusive, until exclusive
    assert {r.offer_id for r in rows} == {"o-1", "o-2"}


def test_malformed_lines_skipped(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"not": "an event"}\n'
        + 'this is not json\n'
        + '\n',
        encoding="utf-8",
    )
    # Append a valid one
    append_event(path, offer_id="o-1", response="accepted", mode="live",
                 now=datetime.now(timezone.utc))
    rows = list(iter_events(path))
    assert len(rows) == 1
    assert rows[0].offer_id == "o-1"


def test_iter_missing_file_empty(tmp_path: Path):
    rows = list(iter_events(tmp_path / "nope.jsonl"))
    assert rows == []
