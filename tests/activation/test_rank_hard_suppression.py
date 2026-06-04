"""Sprint 7 H1 — hard suppression of repeats."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.activation.rank import _hard_suppress, rank
from core.activation.schemas import Candidate, Offer


NOW = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
WEIGHTS = {
    "w1_confidence": 1.0, "w2_recency": 0.6, "w3_commitment": 1.2,
    "w4_user_priority": 0.8, "w5_recent_offer_penalty": 0.5,
    "w6_rejection_penalty": 0.7,
}


def _c(cid="c-1", t="meeting_followup", cited=("sig_alex", "sig_q2"), conf=0.7):
    return Candidate(
        candidate_id=cid, type=t,
        summary="Schedule with Alex", cited_signals=list(cited),
        confidence=conf, staleness_days=1, action_verb="schedule",
    )


def _o(oid, *, response, t="meeting_followup", cited=("sig_alex", "sig_q2"),
       created=NOW - timedelta(days=2)):
    return Offer(
        offer_id=oid, created_at=created.isoformat().replace("+00:00", "Z"),
        ritual="daily-plan", type=t, shown=True, summary="x",
        cited_signals=list(cited), score=0.5, candidate_id="c-old",
        user_response=response,
    )


def test_accepted_offer_suppresses_same_pattern():
    cand = _c()
    accepted = _o("o-acc", response="accepted")
    assert _hard_suppress(cand, [accepted], NOW, rejection_suppress_days=14) is not None


def test_rejected_offer_inside_window_suppresses():
    cand = _c()
    rejected = _o("o-rej", response="rejected", created=NOW - timedelta(days=5))
    assert _hard_suppress(cand, [rejected], NOW, rejection_suppress_days=14) is not None


def test_rejected_offer_outside_window_does_not_suppress():
    cand = _c()
    rejected = _o("o-rej", response="rejected", created=NOW - timedelta(days=30))
    assert _hard_suppress(cand, [rejected], NOW, rejection_suppress_days=14) is None


def test_never_again_suppresses_regardless_of_window():
    cand = _c()
    nac = _o("o-na", response="never_again", created=NOW - timedelta(days=400))
    assert _hard_suppress(cand, [nac], NOW, rejection_suppress_days=14) is not None


def test_different_type_does_not_suppress():
    cand = _c(t="meeting_followup")
    accepted = _o("o-acc", response="accepted", t="commitment_reminder")
    assert _hard_suppress(cand, [accepted], NOW, rejection_suppress_days=14) is None


def test_low_overlap_does_not_suppress():
    cand = _c(cited=("sig_alice", "sig_other"))
    accepted = _o("o-acc", response="accepted",
                  cited=("sig_alex", "sig_q2", "sig_third", "sig_fourth"))
    # Jaccard 0/6 = 0; primary entity differs (sig_alice vs sig_alex)
    assert _hard_suppress(cand, [accepted], NOW, rejection_suppress_days=14) is None


def test_rank_drops_suppressed_before_scoring():
    cand = _c()
    accepted = _o("o-acc", response="accepted")
    offers = rank(
        [cand], now=NOW, offers_log=[accepted], tombstones=[],
        weights=WEIGHTS, recent_acceptance_rate=0.7, days_since_install=30,
        signal_index={"sig_alex": NOW.isoformat(), "sig_q2": NOW.isoformat()},
    )
    # Hard suppression — candidate dropped, no offer emitted.
    assert offers == []


def test_rank_can_disable_hard_suppression():
    cand = _c()
    accepted = _o("o-acc", response="accepted")
    offers = rank(
        [cand], now=NOW, offers_log=[accepted], tombstones=[],
        weights=WEIGHTS, recent_acceptance_rate=0.7, days_since_install=30,
        enable_hard_suppression=False,
        signal_index={"sig_alex": NOW.isoformat(), "sig_q2": NOW.isoformat()},
    )
    assert len(offers) >= 1
