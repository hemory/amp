"""compute_acceptance_rate: insufficient data, boundary, window trim."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.activation.log import compute_acceptance_rate
from core.activation.schemas import Offer


NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _offer(offset_days: float, response: str | None) -> Offer:
    ts = NOW - timedelta(days=offset_days)
    return Offer(
        offer_id=f"o_{offset_days}",
        created_at=_iso(ts - timedelta(minutes=5)),
        ritual="daily-plan",
        type="meeting_followup",
        shown=True,
        summary="x",
        cited_signals=["s1"],
        score=0.5,
        user_response=response,
        response_timestamp=_iso(ts) if response else None,
    )


def test_insufficient_data_returns_none():
    offers = [_offer(i, "accepted") for i in range(4)]  # only 4 decided
    assert compute_acceptance_rate(offers, now=NOW) is None


def test_boundary_exactly_five_decided():
    offers = [_offer(i, "accepted") for i in range(5)]
    rate = compute_acceptance_rate(offers, now=NOW)
    assert rate == 1.0


def test_mixed_decided_computed():
    offers = (
        [_offer(i, "accepted") for i in range(3)]
        + [_offer(i + 3, "rejected") for i in range(2)]
    )
    rate = compute_acceptance_rate(offers, now=NOW)
    assert rate == 3 / 5


def test_window_excludes_old_decisions():
    # 4 recent + 10 very old → only 4 recent count → insufficient.
    offers = (
        [_offer(i, "accepted") for i in range(4)]
        + [_offer(30 + i, "accepted") for i in range(10)]
    )
    assert compute_acceptance_rate(offers, window_days=14, now=NOW) is None


def test_undecided_responses_do_not_count():
    offers = (
        [_offer(i, "accepted") for i in range(3)]
        + [_offer(3, "snoozed")]
        + [_offer(4, "ignored")]
        + [_offer(5, "viewed")]
    )
    # Only 3 decided → insufficient.
    assert compute_acceptance_rate(offers, now=NOW) is None


def test_accepted_with_edits_counts_as_accepted():
    offers = (
        [_offer(i, "accepted_with_edits") for i in range(5)]
    )
    rate = compute_acceptance_rate(offers, now=NOW)
    assert rate == 1.0
