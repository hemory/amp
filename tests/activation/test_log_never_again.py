"""Sprint 7 H2 — never_again creates Tombstone + Event."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.activation.events import iter_events
from core.activation.io_jsonl import append_jsonl, read_jsonl
from core.activation.log import record_response
from core.activation.schemas import Offer


NOW = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _seed(tmp_path: Path) -> dict:
    offers = tmp_path / "offers.jsonl"
    o = Offer(
        offer_id="o-1",
        created_at="2026-05-01T11:00:00Z",
        ritual="daily-plan", type="meeting_followup",
        shown=True, summary="x", cited_signals=["sig_alex"],
        score=0.5, candidate_id="c-1",
    )
    append_jsonl(offers, o.to_dict())
    return {
        "offers": offers,
        "tombs": tmp_path / "tombstones.jsonl",
        "ghost_log": tmp_path / "ghost-log.md",
        "events": tmp_path / "events.jsonl",
    }


def test_never_again_writes_tombstone_and_event(tmp_path):
    p = _seed(tmp_path)
    record_response(
        "o-1", "never_again",
        now=NOW, offers_path=p["offers"], tombstones_path=p["tombs"],
        ghost_log_path=p["ghost_log"], events_path=p["events"],
        reason="not relevant",
    )
    tombs = read_jsonl(p["tombs"])
    assert len(tombs) == 1
    assert tombs[0]["pattern"] == "sig_alex"
    assert tombs[0]["source_offer_id"] == "o-1"
    events = list(iter_events(p["events"]))
    assert len(events) == 1
    assert events[0].response == "never_again"


def test_rejected_writes_event_but_no_tombstone(tmp_path):
    p = _seed(tmp_path)
    record_response(
        "o-1", "rejected",
        now=NOW, offers_path=p["offers"], tombstones_path=p["tombs"],
        ghost_log_path=p["ghost_log"], events_path=p["events"],
    )
    assert not p["tombs"].exists() or read_jsonl(p["tombs"]) == []
    events = list(iter_events(p["events"]))
    assert len(events) == 1
    assert events[0].response == "rejected"


def test_offer_user_response_updated(tmp_path):
    p = _seed(tmp_path)
    record_response(
        "o-1", "accepted",
        now=NOW, offers_path=p["offers"], tombstones_path=p["tombs"],
        ghost_log_path=p["ghost_log"], events_path=p["events"],
    )
    rows = read_jsonl(p["offers"])
    assert rows[0]["user_response"] == "accepted"
    assert rows[0]["time_to_response_s"] >= 0


def test_unknown_response_rejected(tmp_path):
    p = _seed(tmp_path)
    import pytest
    with pytest.raises(ValueError):
        record_response(
            "o-1", "maybe_later",
            now=NOW, offers_path=p["offers"], tombstones_path=p["tombs"],
            ghost_log_path=p["ghost_log"], events_path=p["events"],
        )
