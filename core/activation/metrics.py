"""Weekly review metrics (Sprint 7, O4).

Public API: ``weekly_metrics(*, vault_root, week_ending)`` → WeeklyMetrics.
Reads only on-disk state — response-events.jsonl, offers.jsonl, drafts/.
No live LLM calls. Used by the ``weekly-metrics`` CLI and the activation
review skill's close-out summary.

Definitions:
    week:                       7 days ending on ``week_ending`` (inclusive).
    offers_proposed:            offers created in the window.
    offers_surfaced:            shown=true.
    offers_held_ghost:          hold_reason starts with "ghost".
    accepted/rejected/...:      counted from response-events filtered to
                                events whose offer was created in the window.
    draft_count:                offers in window with draft_artifact_path.
    draft_adopted_count:        drafts whose offer's latest response is
                                accepted/accepted_with_edits.
    median/p95 response_seconds: from offer.time_to_response_s where set.
    grounding_pass_rate:        offers in window with grounding_score≥pass.
    citation_pass_rate:         offers in window with non-empty cited_signals
                                (offer-level discipline; the schema gate
                                already enforces it but this surfaces the rate).
    throttle_active_days:       distinct calendar days in window where any
                                offer carries hold_reason starting "throttle".
    ghost_active_days:          distinct calendar days in window where any
                                offer carries hold_reason starting "ghost".
"""

from __future__ import annotations

import statistics
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from .events import iter_events
from .io_jsonl import read_jsonl
from .schemas import Event, Offer, WeeklyMetrics


_GROUNDING_PASS_THRESHOLD = 0.4  # mirrors grounding.yaml min_overlap default


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not isinstance(s, str) or not s:
        return None
    v = s.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _percentile(values: Sequence[float], pct: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def weekly_metrics(
    *,
    vault_root: Path,
    week_ending: Optional[date] = None,
) -> WeeklyMetrics:
    """Compute weekly metrics ending on ``week_ending`` (inclusive)."""
    if week_ending is None:
        week_ending = datetime.now(timezone.utc).date()
    end_dt = datetime.combine(week_ending + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)
    start_dt = end_dt - timedelta(days=7)

    act = Path(vault_root) / "System" / "activation"

    offers = [Offer.from_dict(r) for r in read_jsonl(act / "offers.jsonl")]
    events = list(iter_events(act / "response-events.jsonl", since=start_dt, until=end_dt))

    in_window: List[Offer] = []
    for o in offers:
        ts = _parse_iso(o.created_at)
        if ts is None:
            continue
        if start_dt <= ts < end_dt:
            in_window.append(o)

    offers_proposed = len(in_window)
    offers_surfaced = sum(1 for o in in_window if o.shown)
    offers_held_ghost = sum(
        1 for o in in_window if (o.hold_reason or "").startswith("ghost")
    )

    in_window_ids = {o.offer_id for o in in_window}
    accepted = rejected = never_again_count = snoozed = ignored = 0
    for ev in events:
        if ev.offer_id not in in_window_ids:
            continue
        r = ev.response
        if r in ("accepted", "accepted_with_edits"):
            accepted += 1
        elif r == "rejected":
            rejected += 1
        elif r == "never_again":
            never_again_count += 1
        elif r == "snoozed":
            snoozed += 1
        elif r == "ignored":
            ignored += 1

    draft_count = sum(1 for o in in_window if o.draft_artifact_path)
    draft_adopted_count = sum(
        1 for o in in_window
        if o.draft_artifact_path
        and o.user_response in ("accepted", "accepted_with_edits")
    )

    rt = [float(o.time_to_response_s) for o in in_window if o.time_to_response_s is not None]
    median_response = float(statistics.median(rt)) if rt else None
    p95_response = _percentile(rt, 0.95) if rt else None

    eds = [float(o.edit_distance_if_accepted) for o in in_window
           if o.edit_distance_if_accepted is not None]
    mean_ed = float(sum(eds) / len(eds)) if eds else None

    gs = [o.grounding_score for o in in_window if o.grounding_score is not None]
    grounding_pass_rate: Optional[float] = None
    if gs:
        grounding_pass_rate = round(
            sum(1 for v in gs if v >= _GROUNDING_PASS_THRESHOLD) / len(gs), 6
        )

    citation_pass_rate: Optional[float] = None
    if in_window:
        citation_pass_rate = round(
            sum(1 for o in in_window if o.cited_signals) / len(in_window), 6
        )

    throttle_days: set = set()
    ghost_days: set = set()
    for o in in_window:
        ts = _parse_iso(o.created_at)
        if ts is None:
            continue
        d = ts.date()
        hr = o.hold_reason or ""
        if hr.startswith("throttle"):
            throttle_days.add(d)
        if hr.startswith("ghost"):
            ghost_days.add(d)

    return WeeklyMetrics(
        week_ending=week_ending.isoformat(),
        offers_proposed=offers_proposed,
        offers_surfaced=offers_surfaced,
        offers_held_ghost=offers_held_ghost,
        accepted=accepted,
        rejected=rejected,
        never_again_count=never_again_count,
        snoozed=snoozed,
        ignored=ignored,
        draft_count=draft_count,
        draft_adopted_count=draft_adopted_count,
        median_response_seconds=median_response,
        p95_response_seconds=p95_response,
        mean_edit_distance=mean_ed,
        grounding_pass_rate=grounding_pass_rate,
        citation_pass_rate=citation_pass_rate,
        throttle_active_days=len(throttle_days),
        ghost_active_days=len(ghost_days),
    )


def acceptance_rate_from_events(
    events_path: Path,
    *,
    window_days: int = 14,
    now: Optional[datetime] = None,
    min_decided: int = 5,
) -> Optional[float]:
    """Trailing acceptance rate computed from events. Returns None if <min_decided.

    Per-offer LATEST event wins (so accept→reject regret is honored).
    Decided = response in {accepted, accepted_with_edits, rejected, never_again}.
    Acceptance counts only the accepted variants.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=window_days)

    latest: dict = {}
    for ev in iter_events(events_path, since=cutoff):
        latest[ev.offer_id] = ev

    decided = 0
    accepted = 0
    for ev in latest.values():
        if ev.response in ("accepted", "accepted_with_edits", "rejected", "never_again"):
            decided += 1
            if ev.response in ("accepted", "accepted_with_edits"):
                accepted += 1

    if decided < min_decided:
        return None
    return accepted / decided


def day7_acceptance_rate(
    events_path: Path,
    offers: List[Offer],
    *,
    live_start: datetime,
    now: datetime,
) -> Optional[float]:
    """Acceptance over offers surfaced in days 1-7 of the live phase.

    Returns None if the 7-day window has not yet fully elapsed (gate is N/A).
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if live_start.tzinfo is None:
        live_start = live_start.replace(tzinfo=timezone.utc)
    end = live_start + timedelta(days=7)
    if now < end:
        return None  # not enough live history yet

    in_window_ids: set = set()
    for o in offers:
        if not o.shown:
            continue
        ts = _parse_iso(o.created_at)
        if ts is None:
            continue
        if live_start <= ts < end:
            in_window_ids.add(o.offer_id)
    if not in_window_ids:
        return None

    latest: dict = {}
    for ev in iter_events(events_path):
        if ev.offer_id in in_window_ids:
            latest[ev.offer_id] = ev

    decided = 0
    accepted = 0
    for oid in in_window_ids:
        ev = latest.get(oid)
        if ev is None:
            continue
        if ev.response in ("accepted", "accepted_with_edits", "rejected", "never_again"):
            decided += 1
            if ev.response in ("accepted", "accepted_with_edits"):
                accepted += 1

    if decided == 0:
        return None
    return accepted / decided


__all__ = [
    "weekly_metrics",
    "acceptance_rate_from_events",
    "day7_acceptance_rate",
]
