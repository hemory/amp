"""Budget / ghost mode tests."""

from __future__ import annotations

from datetime import datetime, timezone

from core.activation.rank import rank
from core.activation.schemas import Candidate


NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
WEIGHTS = {
    "w1_confidence": 1.0,
    "w2_recency": 0.6,
    "w3_commitment": 1.2,
    "w4_user_priority": 0.8,
    "w5_recent_offer_penalty": 0.5,
    "w6_rejection_penalty": 0.7,
}


def _candidates(n: int):
    out = []
    for i in range(n):
        out.append(
            Candidate(
                candidate_id=f"c_{i:03d}",
                type="meeting_followup",
                summary=f"summary {i}",
                cited_signals=[f"sig_{i}"],
                confidence=0.5 + (i * 0.01),
                staleness_days=1,
                action_verb="send",
            )
        )
    return out


def _rank(cands, **kw):
    defaults = dict(
        now=NOW,
        offers_log=[],
        tombstones=[],
        weights=WEIGHTS,
        recent_acceptance_rate=0.7,
        days_since_install=30,
    )
    defaults.update(kw)
    return rank(cands, **defaults)


def test_ghost_mode_first_week_budget_zero():
    offers = _rank(_candidates(6), days_since_install=3)
    assert len(offers) == 6
    assert all(not o.shown for o in offers)
    assert all(o.hold_reason == "ghost" for o in offers)


def test_acceptance_high_gives_budget_five():
    offers = _rank(_candidates(10), recent_acceptance_rate=0.7)
    shown = [o for o in offers if o.shown]
    held = [o for o in offers if not o.shown]
    assert len(shown) == 5
    assert len(held) == 5
    assert all(o.hold_reason == "budget" for o in held)


def test_acceptance_medium_gives_budget_three():
    offers = _rank(_candidates(10), recent_acceptance_rate=0.45)
    assert sum(1 for o in offers if o.shown) == 3


def test_acceptance_low_gives_budget_two():
    offers = _rank(_candidates(10), recent_acceptance_rate=0.25)
    assert sum(1 for o in offers if o.shown) == 2


def test_acceptance_very_low_gives_budget_one():
    offers = _rank(_candidates(10), recent_acceptance_rate=0.1)
    assert sum(1 for o in offers if o.shown) == 1


def test_acceptance_none_defaults_to_one():
    offers = _rank(_candidates(10), recent_acceptance_rate=None)
    assert sum(1 for o in offers if o.shown) == 1


def test_ghost_override_forces_budget_zero_regardless_of_rate():
    offers = _rank(
        _candidates(5),
        recent_acceptance_rate=0.9,
        days_since_install=365,
        ghost_override=True,
    )
    assert all(not o.shown for o in offers)
    assert all(o.hold_reason == "ghost" for o in offers)


def test_determinism_same_inputs_same_outputs():
    cands = _candidates(5)
    a = _rank(cands, run_id="fixed")
    b = _rank(cands, run_id="fixed")
    assert [o.to_dict() for o in a] == [o.to_dict() for o in b]
