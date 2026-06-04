"""Sprint 6 — render_ghost_digest output shape."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.activation.ghost import GhostState
from core.activation.schemas import Draft, Offer, Signal
from core.activation.surface import render_ghost_digest


NOW = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)


def _state(active: bool, reason: str = "install_window"):
    return GhostState(
        active=active,
        reason=reason if active else "",
        started_at=NOW - timedelta(days=2),
        expected_end=NOW + timedelta(days=5) if active else None,
    )


def _offer(idx: int, hold: str = "ghost:install_window") -> Offer:
    return Offer(
        offer_id=f"o-{idx:03d}",
        created_at="2026-04-20T11:00:00Z",
        ritual="daily-plan",
        type="meeting_followup",
        shown=False,
        summary=f"send recap {idx}",
        cited_signals=[f"sig_{idx}"],
        score=0.7,
        candidate_id=f"c-{idx:03d}",
        hold_reason=hold,
    )


def test_digest_renders_held_offers():
    offers = [_offer(0), _offer(1)]
    drafts = {
        "o-001": Draft(
            offer_id="o-001",
            draft_text="Hi D.Lin,\nThanks for the chat.",
            citations=["sig_1"],
            confidence=0.8,
            warnings=[],
            created_at="2026-04-20T11:30:00Z",
            path="System/activation/drafts/o-001.md",
        ),
    }
    sigs = {
        "sig_0": Signal(
            signal_id="sig_0",
            source="meeting_notes",
            path="04-Projects/X/m.md",
            timestamp="2026-04-19T10:00:00Z",
            excerpt="x",
        ),
    }
    out = render_ghost_digest(
        offers=offers, drafts=drafts, cited_signals_lookup=sigs,
        ghost_state=_state(True), now=NOW,
    )
    assert "ghost mode active (install_window)" in out
    assert "Held offers in this digest:** 2" in out
    assert "send recap 0" in out
    assert "send recap 1" in out
    assert "ghost:install_window" in out
    assert "04-Projects/X/m.md" in out  # cited signal link
    assert "Hi D.Lin," in out  # draft body


def test_digest_empty_state_message():
    out = render_ghost_digest(
        offers=[], drafts={}, cited_signals_lookup={},
        ghost_state=_state(True), now=NOW,
    )
    assert "No offers were held in ghost mode" in out
    assert "ghost-exit --acknowledge" in out


def test_digest_inactive_status():
    out = render_ghost_digest(
        offers=[_offer(0)], drafts={}, cited_signals_lookup={},
        ghost_state=_state(False), now=NOW,
    )
    assert "ghost mode inactive" in out


def test_digest_filters_non_ghost_offers():
    held = _offer(0, hold="ghost")
    not_held = _offer(1, hold=None)
    out = render_ghost_digest(
        offers=[held, not_held], drafts={}, cited_signals_lookup={},
        ghost_state=_state(True), now=NOW,
    )
    assert "Held offers in this digest:** 1" in out
    assert "send recap 0" in out
    assert "send recap 1" not in out
