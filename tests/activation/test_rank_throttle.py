"""Sprint 7 O1 — throttle when acceptance is low."""

from __future__ import annotations

from datetime import datetime, timezone

from core.activation.rank import rank
from core.activation.schemas import Candidate


NOW = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
WEIGHTS = {
    "w1_confidence": 1.0, "w2_recency": 0.6, "w3_commitment": 1.2,
    "w4_user_priority": 0.8, "w5_recent_offer_penalty": 0.5,
    "w6_rejection_penalty": 0.7,
}


def _cands(n: int):
    out = []
    for i in range(n):
        out.append(Candidate(
            candidate_id=f"c-{i}", type="meeting_followup",
            summary=f"summary {i}", cited_signals=[f"sig_{i}"],
            confidence=0.7 + 0.01 * i, staleness_days=1,
            action_verb="schedule",
        ))
    return out


def _sig_index_for(cands):
    return {c.cited_signals[0]: NOW.isoformat() for c in cands}


def test_throttle_cap_zero_holds_all():
    cands = _cands(3)
    offers = rank(
        cands, now=NOW, offers_log=[], tombstones=[], weights=WEIGHTS,
        recent_acceptance_rate=0.05, days_since_install=30,
        signal_index=_sig_index_for(cands),
        throttle_cap=0, throttle_reason="throttle:very_low_acceptance",
    )
    # All offers are produced but none shown.
    assert len(offers) == 3
    assert all(not o.shown for o in offers)
    assert all(o.hold_reason == "throttle:very_low_acceptance" for o in offers)


def test_throttle_cap_one_shows_only_top():
    cands = _cands(4)
    offers = rank(
        cands, now=NOW, offers_log=[], tombstones=[], weights=WEIGHTS,
        recent_acceptance_rate=0.7, days_since_install=30,
        signal_index=_sig_index_for(cands),
        throttle_cap=1, throttle_reason="throttle:low_acceptance",
    )
    shown = [o for o in offers if o.shown]
    assert len(shown) == 1
    held = [o for o in offers if not o.shown]
    # At least one held offer is throttled.
    assert any(o.hold_reason == "throttle:low_acceptance" for o in held)


def test_no_throttle_uses_default_budget():
    cands = _cands(2)
    offers = rank(
        cands, now=NOW, offers_log=[], tombstones=[], weights=WEIGHTS,
        recent_acceptance_rate=0.7, days_since_install=30,
        signal_index=_sig_index_for(cands),
    )
    shown = [o for o in offers if o.shown]
    assert len(shown) >= 1
