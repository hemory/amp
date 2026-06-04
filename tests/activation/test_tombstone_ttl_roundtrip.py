"""Tombstone ttl_days round-trip: dataclass ↔ dict ↔ rank internals."""

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


def test_ttl_days_present_round_trip():
    data = {
        "tombstone_id": "t1",
        "created_at": "2026-04-10T00:00:00Z",
        "type": "meeting_followup",
        "pattern": "sig_a",
        "source_offer_id": None,
        "notes": None,
        "ttl_days": 7,
    }
    t = Tombstone.from_dict(data)
    assert t.ttl_days == 7
    assert t.to_dict() == data


def test_ttl_days_absent_round_trip_stays_compact():
    data = {
        "tombstone_id": "t2",
        "created_at": "2026-04-10T00:00:00Z",
        "type": "meeting_followup",
        "pattern": "sig_a",
        "source_offer_id": None,
        "notes": None,
    }
    t = Tombstone.from_dict(data)
    assert t.ttl_days is None
    out = t.to_dict()
    assert "ttl_days" not in out
    assert out == data


def test_ttl_days_none_explicit_round_trip():
    data = {
        "tombstone_id": "t3",
        "created_at": "2026-04-10T00:00:00Z",
        "type": "meeting_followup",
        "pattern": "sig_a",
        "ttl_days": None,
    }
    t = Tombstone.from_dict(data)
    assert t.ttl_days is None
    # None gets stripped on the way out.
    assert "ttl_days" not in t.to_dict()


def test_rank_honors_expired_ttl():
    """A tombstone with ttl_days=3 created 10 days ago is inactive — the
    candidate should survive."""
    expired = Tombstone(
        tombstone_id="t_exp",
        created_at="2026-04-07T00:00:00Z",  # 10 days before NOW
        type="meeting_followup",
        pattern="sig_a",
        ttl_days=3,
    )
    cand = Candidate(
        candidate_id="c1",
        type="meeting_followup",
        summary="x",
        cited_signals=["sig_a"],
        confidence=0.8,
        staleness_days=1,
        action_verb="send",
    )
    offers = rank(
        [cand],
        now=NOW,
        offers_log=[],
        tombstones=[expired],
        weights=WEIGHTS,
        recent_acceptance_rate=0.7,
        days_since_install=30,
    )
    assert len(offers) == 1


def test_rank_active_ttl_still_drops():
    active = Tombstone(
        tombstone_id="t_active",
        created_at="2026-04-16T00:00:00Z",  # 1 day before NOW
        type="meeting_followup",
        pattern="sig_a",
        ttl_days=7,
    )
    cand = Candidate(
        candidate_id="c1",
        type="meeting_followup",
        summary="x",
        cited_signals=["sig_a"],
        confidence=0.8,
        staleness_days=1,
        action_verb="send",
    )
    offers = rank(
        [cand],
        now=NOW,
        offers_log=[],
        tombstones=[active],
        weights=WEIGHTS,
        recent_acceptance_rate=0.7,
        days_since_install=30,
    )
    assert offers == []
