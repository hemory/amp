from datetime import datetime, timezone

from core.activation.rubric import score_offer
from rubric_helpers import mk_candidate, mk_offer, mk_signal


def test_novelty_zero_when_overlapping_recent_offer():
    sig = mk_signal("sig_a", "Alex Reel timeline")
    offer = mk_offer(cited=["sig_a"])
    prior = mk_offer(
        offer_id="o_prior",
        cited=["sig_a", "sig_b"],
        created_at="2026-04-18T09:00:00Z",
    )
    s = score_offer(
        offer,
        mk_candidate(),
        [sig],
        prior_offers=[prior],
        now=datetime(2026, 4, 19, 9, tzinfo=timezone.utc),
    )
    assert s.novelty == 0.0


def test_novelty_one_when_no_recent_overlap():
    sig = mk_signal("sig_a", "Alex Reel timeline")
    offer = mk_offer(cited=["sig_a"])
    prior = mk_offer(
        offer_id="o_prior",
        cited=["sig_a"],
        created_at="2026-04-01T09:00:00Z",
    )
    s = score_offer(
        offer,
        mk_candidate(),
        [sig],
        prior_offers=[prior],
        now=datetime(2026, 4, 19, 9, tzinfo=timezone.utc),
    )
    assert s.novelty == 1.0


def test_novelty_one_when_different_type():
    sig = mk_signal("sig_a", "Alex Reel timeline")
    offer = mk_offer(cited=["sig_a"], type="meeting_followup")
    prior = mk_offer(
        offer_id="o_prior",
        cited=["sig_a"],
        type="commitment_reminder",
        created_at="2026-04-18T09:00:00Z",
    )
    s = score_offer(
        offer,
        mk_candidate(),
        [sig],
        prior_offers=[prior],
        now=datetime(2026, 4, 19, 9, tzinfo=timezone.utc),
    )
    assert s.novelty == 1.0
