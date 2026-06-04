"""Tombstone tests: active tombstones drop candidates outright."""

from __future__ import annotations

from datetime import datetime, timezone

from core.activation.rank import rank
from core.activation.schemas import Candidate, Tombstone


NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
WEIGHTS = {
    "w1_confidence": 1.0,
    "w2_recency": 0.6,
    "w3_commitment": 1.2,
    "w4_user_priority": 0.8,
    "w5_recent_offer_penalty": 0.5,
    "w6_rejection_penalty": 0.7,
}


def _c(cid="c1", summary="Send recap to D.Lin", cited=("sig_a",)):
    return Candidate(
        candidate_id=cid,
        type="meeting_followup",
        summary=summary,
        cited_signals=list(cited),
        confidence=0.8,
        staleness_days=1,
        action_verb="send",
    )


def test_active_tombstone_by_signal_id_drops_candidate():
    tomb = Tombstone(
        tombstone_id="t1",
        created_at="2026-04-10T00:00:00Z",
        type="meeting_followup",
        pattern="sig_a",  # pattern = signal_id match
    )
    offers = rank(
        [_c()],
        now=NOW,
        offers_log=[],
        tombstones=[tomb],
        weights=WEIGHTS,
        recent_acceptance_rate=0.7,
        days_since_install=30,
    )
    assert offers == []


def test_active_tombstone_by_summary_substring_drops_candidate():
    tomb = Tombstone(
        tombstone_id="t2",
        created_at="2026-04-10T00:00:00Z",
        type="meeting_followup",
        pattern="D.Lin",
    )
    offers = rank(
        [_c()],
        now=NOW,
        offers_log=[],
        tombstones=[tomb],
        weights=WEIGHTS,
        recent_acceptance_rate=0.7,
        days_since_install=30,
    )
    assert offers == []


def test_tombstone_wrong_type_does_not_match():
    tomb = Tombstone(
        tombstone_id="t3",
        created_at="2026-04-10T00:00:00Z",
        type="person_reconnect",  # different type
        pattern="sig_a",
    )
    offers = rank(
        [_c()],
        now=NOW,
        offers_log=[],
        tombstones=[tomb],
        weights=WEIGHTS,
        recent_acceptance_rate=0.7,
        days_since_install=30,
    )
    assert len(offers) == 1
