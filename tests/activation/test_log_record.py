"""record_response: accept/reject/snooze/ignore, ghost log, tombstone, atomic write."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.activation.log import record_response
from core.activation.schemas import Offer


NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)


def _seed(tmp_path: Path, *, offers: int = 1):
    offers_path = tmp_path / "offers.jsonl"
    tombs_path = tmp_path / "tombstones.jsonl"
    ghost_path = tmp_path / "ghost-log.md"
    rows = []
    for i in range(offers):
        o = Offer(
            offer_id=f"o_test_{i:03d}",
            created_at="2026-04-17T07:00:00Z",
            ritual="daily-plan",
            type="meeting_followup",
            shown=True,
            summary=f"test offer {i}",
            cited_signals=[f"sig_{i}"],
            score=0.5,
        )
        rows.append(o.to_dict())
    with offers_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    return offers_path, tombs_path, ghost_path


def _kwargs(offers_path, tombs_path, ghost_path, **over):
    base = dict(
        now=NOW,
        offers_path=offers_path,
        tombstones_path=tombs_path,
        ghost_log_path=ghost_path,
        ghost_mode=False,
    )
    base.update(over)
    return base


def test_accepted_sets_fields_and_leaves_no_tombstone(tmp_path):
    op, tp, gp = _seed(tmp_path)
    o = record_response("o_test_000", "accepted", **_kwargs(op, tp, gp))
    assert o.user_response == "accepted"
    assert o.response_timestamp is not None
    assert o.time_to_response_s is not None
    assert not tp.exists() or tp.read_text() == ""


def test_rejected_appends_event_no_tombstone(tmp_path):
    """Sprint 7 H2: rejected no longer creates a tombstone (only never_again does)."""
    op, tp, gp = _seed(tmp_path)
    o = record_response(
        "o_test_000", "rejected",
        **_kwargs(op, tp, gp, reason="too noisy"),
    )
    assert o.user_response == "rejected"
    assert o.response_reason == "too noisy"
    assert not tp.exists() or tp.read_text() == ""


def test_never_again_appends_tombstone(tmp_path):
    """Sprint 7 H2: ``never_again`` is the new permanent suppression."""
    op, tp, gp = _seed(tmp_path)
    o = record_response(
        "o_test_000", "never_again",
        **_kwargs(op, tp, gp, reason="not relevant"),
    )
    assert o.user_response == "never_again"
    lines = [l for l in tp.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["type"] == "meeting_followup"
    assert row["pattern"] == "sig_0"
    assert row["source_offer_id"] == "o_test_000"
    assert row["notes"] == "not relevant"


def test_snoozed_and_ignored_do_not_tombstone(tmp_path):
    for resp in ("snoozed", "ignored"):
        sub = tmp_path / resp
        sub.mkdir()
        op, tp, gp = _seed(sub)
        record_response("o_test_000", resp, **_kwargs(op, tp, gp))
        assert not tp.exists() or tp.read_text() == ""


def test_ghost_mode_writes_ghost_log(tmp_path):
    op, tp, gp = _seed(tmp_path)
    record_response(
        "o_test_000", "accepted",
        **_kwargs(op, tp, gp, ghost_mode=True),
    )
    assert gp.exists()
    content = gp.read_text(encoding="utf-8")
    assert "mode=ghost" in content
    assert "o_test_000" in content
    assert "response=accepted" in content


def test_live_mode_also_writes_ghost_log_tagged_live(tmp_path):
    op, tp, gp = _seed(tmp_path)
    record_response("o_test_000", "accepted", **_kwargs(op, tp, gp))
    assert gp.exists()
    assert "mode=live" in gp.read_text(encoding="utf-8")


def test_offer_id_not_found_raises(tmp_path):
    op, tp, gp = _seed(tmp_path)
    with pytest.raises(ValueError, match="offer_id not found"):
        record_response("NOPE", "accepted", **_kwargs(op, tp, gp))


def test_invalid_response_raises(tmp_path):
    op, tp, gp = _seed(tmp_path)
    with pytest.raises(ValueError, match="not in"):
        record_response("o_test_000", "totally_bogus", **_kwargs(op, tp, gp))


def test_atomic_write_preserves_other_rows(tmp_path):
    """Rewriting one row must not drop neighbors."""
    op, tp, gp = _seed(tmp_path, offers=3)
    record_response("o_test_001", "accepted", **_kwargs(op, tp, gp))
    lines = [l for l in op.read_text().splitlines() if l.strip()]
    assert len(lines) == 3
    rows = [json.loads(l) for l in lines]
    by_id = {r["offer_id"]: r for r in rows}
    assert by_id["o_test_000"].get("user_response") is None
    assert by_id["o_test_001"]["user_response"] == "accepted"
    assert by_id["o_test_002"].get("user_response") is None


def test_never_again_with_empty_cited_signals_uses_offer_id_as_pattern(tmp_path):
    """Edge: pattern falls back to offer_id if no cited signals (H2: never_again)."""
    op = tmp_path / "offers.jsonl"
    tp = tmp_path / "tombstones.jsonl"
    gp = tmp_path / "ghost-log.md"
    o = Offer(
        offer_id="o_nocite",
        created_at="2026-04-17T07:00:00Z",
        ritual="daily-plan",
        type="meeting_followup",
        shown=True,
        summary="",
        cited_signals=[],
        score=0.0,
    )
    with op.open("w", encoding="utf-8") as f:
        f.write(json.dumps(o.to_dict(), sort_keys=True) + "\n")
    record_response("o_nocite", "never_again", **_kwargs(op, tp, gp))
    row = json.loads(tp.read_text().splitlines()[0])
    assert row["pattern"] == "o_nocite"
