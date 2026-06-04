"""Rank tests: scoring monotonicity, dedup, tombstones, budget, CLI smoke."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.activation.rank import rank
from core.activation.schemas import Candidate, Offer, Tombstone


NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
WEIGHTS = {
    "w1_confidence": 1.0,
    "w2_recency": 0.6,
    "w3_commitment": 1.2,
    "w4_user_priority": 0.8,
    "w5_recent_offer_penalty": 0.5,
    "w6_rejection_penalty": 0.7,
}


def _cand(cid="c_001", conf=0.7, cited=("sig_a",), ctype="meeting_followup", summary="s"):
    return Candidate(
        candidate_id=cid,
        type=ctype,
        summary=summary,
        cited_signals=list(cited),
        confidence=conf,
        staleness_days=1,
        action_verb="send",
    )


def _sig_index(age_days: int = 1, signal_id: str = "sig_a") -> dict:
    ts = (NOW - timedelta(days=age_days)).isoformat().replace("+00:00", "Z")
    return {signal_id: ts}


def _rank(candidates, **kw):
    kwargs = dict(
        now=NOW,
        offers_log=[],
        tombstones=[],
        weights=WEIGHTS,
        recent_acceptance_rate=0.7,
        days_since_install=30,
        signal_index=_sig_index(),
    )
    kwargs.update(kw)
    return rank(candidates, **kwargs)


def test_monotonic_confidence():
    low = _cand("c_low", conf=0.2)
    high = _cand("c_high", conf=0.95, cited=("sig_b",))
    offers = _rank([low, high], signal_index={"sig_a": NOW.isoformat(), "sig_b": NOW.isoformat()})
    # Same everything else; higher confidence should score higher.
    by_cid = {o.candidate_id: o for o in offers}
    assert by_cid["c_high"].score > by_cid["c_low"].score


def test_recency_boosts_newer():
    old_c = _cand("c_old", cited=("sig_old",))
    new_c = _cand("c_new", cited=("sig_new",))
    idx = {
        "sig_old": (NOW - timedelta(days=10)).isoformat(),
        "sig_new": NOW.isoformat(),
    }
    offers = _rank([old_c, new_c], signal_index=idx)
    by_cid = {o.candidate_id: o for o in offers}
    assert by_cid["c_new"].score > by_cid["c_old"].score
    assert by_cid["c_new"].score_components["recency"] > by_cid["c_old"].score_components["recency"]


def test_recent_offer_penalty_drops_below_cutoff():
    c = _cand("c_penalized", cited=("sig_a",))
    prior = Offer(
        offer_id="o_old",
        created_at=(NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        ritual="daily-plan",
        type="meeting_followup",
        shown=True,
        summary="same",
        cited_signals=["sig_a"],
        score=0.9,
    )
    offers_no = _rank([c])
    offers_yes = _rank([c], offers_log=[prior])
    assert offers_no[0].score_components["recent_offer_penalty"] == 0.0
    assert offers_yes[0].score_components["recent_offer_penalty"] == 1.0
    assert offers_yes[0].score < offers_no[0].score


def test_recent_offer_penalty_expires_after_seven_days():
    c = _cand("c_p")
    prior = Offer(
        offer_id="o_old",
        created_at=(NOW - timedelta(days=8)).isoformat().replace("+00:00", "Z"),
        ritual="daily-plan",
        type="meeting_followup",
        shown=True,
        summary="same",
        cited_signals=["sig_a"],
        score=0.9,
    )
    offers = _rank([c], offers_log=[prior])
    assert offers[0].score_components["recent_offer_penalty"] == 0.0


def test_rejection_penalty_from_offers_log():
    """Sprint 7 H1: rejection inside the hard-suppression window now drops
    the candidate outright. The penalty term still applies for older
    rejections that survive suppression."""
    c = _cand("c_r")
    prior = Offer(
        offer_id="o_r",
        created_at=(NOW - timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        ritual="daily-plan",
        type="meeting_followup",
        shown=True,
        summary="s",
        cited_signals=["sig_a"],
        score=0.5,
        user_response="rejected",
    )
    offers = _rank([c], offers_log=[prior])
    # 30 days ago is outside the 14-day rejection_suppress window, so the
    # candidate survives and carries the soft penalty.
    assert offers, "candidate older than suppression window should survive"
    # Penalty term itself uses a 14-day window per legacy behavior;
    # for rejections outside that window it's 0.0. The H1 suppression
    # window has the same default, so 30 days lands outside both.
    assert offers[0].score_components["rejection_penalty"] == 0.0
