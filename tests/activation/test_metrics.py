"""Sprint 7 O4 — weekly metrics + acceptance computation."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.activation.events import append_event
from core.activation.io_jsonl import append_jsonl
from core.activation.metrics import (
    acceptance_rate_from_events,
    day7_acceptance_rate,
    weekly_metrics,
)
from core.activation.schemas import Offer


def _vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    (v / "System" / "activation").mkdir(parents=True)
    return v


def _offer(
    *,
    offer_id: str,
    created_at: datetime,
    shown: bool = True,
    user_response=None,
    cited_signals=("sig_1",),
    grounding_score=0.6,
    hold_reason=None,
    draft=False,
    time_to_response=None,
) -> dict:
    o = Offer(
        offer_id=offer_id,
        created_at=created_at.isoformat().replace("+00:00", "Z"),
        ritual="daily-plan",
        type="commitment_reminder",
        shown=shown,
        summary="Schedule with Alex",
        cited_signals=list(cited_signals),
        score=0.5,
        candidate_id="c-1",
        hold_reason=hold_reason,
        draft_artifact_path="drafts/x.json" if draft else None,
        user_response=user_response,
        time_to_response_s=time_to_response,
        grounding_score=grounding_score,
    )
    return o.to_dict()


def test_weekly_metrics_counts(tmp_path):
    vault = _vault(tmp_path)
    act = vault / "System" / "activation"
    week_end = date(2026, 5, 7)
    base = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)

    # 3 in-window offers (different responses), 1 outside.
    append_jsonl(act / "offers.jsonl", _offer(
        offer_id="o-1", created_at=base, user_response="accepted", draft=True,
        time_to_response=120,
    ))
    append_jsonl(act / "offers.jsonl", _offer(
        offer_id="o-2", created_at=base + timedelta(hours=1),
        user_response="rejected", grounding_score=0.2,
    ))
    append_jsonl(act / "offers.jsonl", _offer(
        offer_id="o-3", created_at=base + timedelta(hours=2),
        user_response=None, hold_reason="ghost:install_window",
    ))
    append_jsonl(act / "offers.jsonl", _offer(
        offer_id="o-old", created_at=base - timedelta(days=20),
        user_response="accepted",
    ))

    append_event(act / "response-events.jsonl",
                 offer_id="o-1", response="accepted", mode="live",
                 now=base + timedelta(minutes=2))
    append_event(act / "response-events.jsonl",
                 offer_id="o-2", response="rejected", mode="live",
                 now=base + timedelta(hours=1, minutes=2))

    m = weekly_metrics(vault_root=vault, week_ending=week_end)
    assert m.offers_proposed == 3
    assert m.offers_surfaced == 3
    assert m.accepted == 1
    assert m.rejected == 1
    assert m.draft_count == 1
    assert m.draft_adopted_count == 1
    assert m.offers_held_ghost == 1
    assert m.median_response_seconds == 120.0
    assert m.grounding_pass_rate is not None
    # 2 of 3 offers (0.6, 0.2, 0.6) >= 0.4 → 2/3
    assert abs(m.grounding_pass_rate - 2 / 3) < 1e-6


def test_acceptance_rate_returns_none_below_minimum(tmp_path):
    p = tmp_path / "events.jsonl"
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)
    for i in range(3):
        append_event(p, offer_id=f"o-{i}", response="accepted", mode="live",
                     now=now - timedelta(days=1))
    assert acceptance_rate_from_events(p, now=now, min_decided=5) is None


def test_acceptance_rate_latest_event_wins(tmp_path):
    p = tmp_path / "events.jsonl"
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)
    for i in range(5):
        append_event(p, offer_id=f"o-{i}", response="accepted", mode="live",
                     now=now - timedelta(days=2))
    # Two of them get rejected later (regret).
    append_event(p, offer_id="o-0", response="rejected", mode="live",
                 now=now - timedelta(days=1))
    append_event(p, offer_id="o-1", response="rejected", mode="live",
                 now=now - timedelta(days=1))
    rate = acceptance_rate_from_events(p, now=now, min_decided=5)
    assert rate is not None
    assert abs(rate - 0.6) < 1e-6  # 3 accepted / 5 decided


def test_day7_returns_none_before_window_elapses(tmp_path):
    live_start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    now = live_start + timedelta(days=4)
    rate = day7_acceptance_rate(
        tmp_path / "missing.jsonl", offers=[],
        live_start=live_start, now=now,
    )
    assert rate is None


def test_day7_computes_after_window(tmp_path):
    live_start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    now = live_start + timedelta(days=8)
    events = tmp_path / "events.jsonl"
    offers = []
    for i in range(4):
        ts = live_start + timedelta(days=1, hours=i)
        offers.append(Offer.from_dict(_offer(
            offer_id=f"o-{i}", created_at=ts, shown=True,
        )))
        append_event(
            events, offer_id=f"o-{i}",
            response="accepted" if i < 3 else "rejected",
            mode="live", now=ts + timedelta(minutes=5),
        )
    rate = day7_acceptance_rate(events, offers=offers,
                                live_start=live_start, now=now)
    assert rate is not None
    assert abs(rate - 0.75) < 1e-6
