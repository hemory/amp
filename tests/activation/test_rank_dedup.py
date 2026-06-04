"""Dedup: within a run, identical (type, primary entity) keep higher-scored."""

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


def _c(cid, conf):
    return Candidate(
        candidate_id=cid,
        type="meeting_followup",
        summary="Send recap",
        cited_signals=["sig_shared"],  # same primary entity
        confidence=conf,
        staleness_days=1,
        action_verb="send",
    )


def test_dedup_keeps_higher_score():
    low = _c("c_low", 0.3)
    high = _c("c_high", 0.9)
    offers = rank(
        [low, high],
        now=NOW,
        offers_log=[],
        tombstones=[],
        weights=WEIGHTS,
        recent_acceptance_rate=0.7,
        days_since_install=30,
    )
    assert len(offers) == 1
    assert offers[0].candidate_id == "c_high"
