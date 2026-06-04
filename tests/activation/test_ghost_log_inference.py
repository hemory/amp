"""Sprint 6 — log.record_response infers ghost vs live from offer.hold_reason."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.activation.log import record_response
from core.activation.schemas import Offer


NOW = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _seed(tmp_path: Path, hold_reason):
    op = tmp_path / "offers.jsonl"
    tp = tmp_path / "tombstones.jsonl"
    gp = tmp_path / "ghost-log.md"
    o = Offer(
        offer_id="o-x",
        created_at="2026-05-01T11:00:00Z",
        ritual="daily-plan",
        type="meeting_followup",
        shown=False,
        summary="x",
        cited_signals=["sig_a"],
        score=0.5,
        hold_reason=hold_reason,
    )
    op.write_text(json.dumps(o.to_dict(), sort_keys=True) + "\n")
    return op, tp, gp


def test_inferred_ghost_when_hold_reason_is_ghost(tmp_path):
    op, tp, gp = _seed(tmp_path, "ghost")
    record_response(
        "o-x", "accepted", now=NOW,
        offers_path=op, tombstones_path=tp, ghost_log_path=gp,
    )
    assert "mode=ghost" in gp.read_text()


def test_inferred_ghost_when_hold_reason_is_subtype(tmp_path):
    op, tp, gp = _seed(tmp_path, "ghost:install_window")
    record_response(
        "o-x", "viewed", now=NOW,
        offers_path=op, tombstones_path=tp, ghost_log_path=gp,
    )
    assert "mode=ghost" in gp.read_text()


def test_inferred_live_when_hold_reason_is_none(tmp_path):
    op, tp, gp = _seed(tmp_path, None)
    record_response(
        "o-x", "accepted", now=NOW,
        offers_path=op, tombstones_path=tp, ghost_log_path=gp,
    )
    assert "mode=live" in gp.read_text()


def test_explicit_kwarg_wins_over_inference(tmp_path):
    op, tp, gp = _seed(tmp_path, "ghost")
    # Pass ghost_mode=False explicitly even though offer is held in ghost.
    record_response(
        "o-x", "accepted", now=NOW,
        offers_path=op, tombstones_path=tp, ghost_log_path=gp,
        ghost_mode=False,
    )
    text = gp.read_text()
    assert "mode=live" in text
    assert "mode=ghost" not in text
