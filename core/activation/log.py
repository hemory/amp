"""Stage 6 — Record user response on an offer. §4.5 of design doc.

Deterministic Python, no LLM. Reads offers.jsonl, updates the matching row,
atomically rewrites, appends an Event to response-events.jsonl (Sprint 7 H3),
and (only on ``never_again``) appends a Tombstone. Ghost mode gets a
human-readable one-liner in ghost-log.md instead of a live-surfacing log.

Sprint 7 H2 split: ``rejected`` no longer creates a Tombstone (rank's
short-term suppression handles "not now"); ``never_again`` is the new
permanent suppression. Existing tombstones from Sprint 4–6 ``rejected``
calls remain valid; we don't retro-delete.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from .events import append_event
from .io_jsonl import append_jsonl, read_jsonl, rewrite_jsonl
from .schemas import Offer, Tombstone, USER_RESPONSES


# User responses recorded via record_response. Sprint 7 added ``never_again``.
_ALLOWED_RESPONSES = tuple(r for r in USER_RESPONSES if r is not None)


def _now_iso(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(s: str) -> Optional[datetime]:
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


def record_response(
    offer_id: str,
    response: str,
    *,
    now: datetime,
    offers_path: Path,
    tombstones_path: Path,
    ghost_log_path: Path,
    ghost_mode: Optional[bool] = None,
    reason: Optional[str] = None,
    events_path: Optional[Path] = None,
) -> Offer:
    """Update an offer with the user's response.

    Atomically rewrites offers.jsonl. Appends an Event to ``events_path``
    (if provided). Only ``never_again`` creates a Tombstone (Sprint 7 H2).
    The ghost-log line is tagged ``mode=ghost`` when the offer was held in
    ghost mode, else ``mode=live``.

    ``ghost_mode``: if not passed (None), the mode is **inferred** from the
    target offer's ``hold_reason`` (``"ghost"`` or any ``"ghost:*"`` subtype
    → ghost). Pass an explicit bool to override.

    Raises:
      ValueError: if ``response`` is outside USER_RESPONSES or ``offer_id``
        is not found in offers.jsonl.
    """
    if response not in _ALLOWED_RESPONSES:
        raise ValueError(
            f"response {response!r} not in {list(_ALLOWED_RESPONSES)}"
        )

    rows = read_jsonl(Path(offers_path))
    found_idx: Optional[int] = None
    for i, row in enumerate(rows):
        if row.get("offer_id") == offer_id:
            found_idx = i
            break
    if found_idx is None:
        raise ValueError(f"offer_id not found: {offer_id}")

    row = rows[found_idx]
    offer = Offer.from_dict(row)

    created = _parse_iso(offer.created_at)
    now_tz = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    ttr: Optional[int] = None
    if created is not None:
        ttr = int((now_tz - created).total_seconds())
        if ttr < 0:
            ttr = 0

    offer.user_response = response
    offer.response_timestamp = _now_iso(now)
    offer.time_to_response_s = ttr
    offer.response_reason = reason

    rows[found_idx] = offer.to_dict()

    # Atomic rewrite — on failure, offers.jsonl is untouched.
    rewrite_jsonl(Path(offers_path), rows)

    # Resolve ghost_mode: explicit kwarg wins; otherwise infer from offer.
    if ghost_mode is None:
        hr = offer.hold_reason or ""
        ghost_mode = (hr == "ghost") or hr.startswith("ghost:")

    # Tombstone only on `never_again` (Sprint 7 H2). `rejected` is "not
    # now" — rank.py's hard-suppression window handles short-term
    # suppression automatically.
    if response == "never_again":
        pattern = (
            offer.cited_signals[0]
            if offer.cited_signals
            else offer.offer_id
        )
        tomb = Tombstone(
            tombstone_id=f"t-{uuid.uuid4().hex[:12]}",
            created_at=_now_iso(now),
            type=offer.type,
            pattern=pattern,
            source_offer_id=offer.offer_id,
            notes=reason,
        )
        append_jsonl(Path(tombstones_path), tomb.to_dict())

    # Append an event row (Sprint 7 H3).
    if events_path is not None:
        append_event(
            Path(events_path),
            offer_id=offer.offer_id,
            response=response,
            mode=("ghost" if ghost_mode else "live"),
            now=now,
            reason=reason,
        )

    # Ghost-log note (in both ghost mode and live mode — the design doc
    # keeps ghost-log.md as a human-readable diary). We keep it minimal:
    # one line per response, prefixed with the mode.
    _append_ghost_log(
        Path(ghost_log_path),
        offer=offer,
        response=response,
        reason=reason,
        ghost_mode=ghost_mode,
    )

    return offer


def _append_ghost_log(
    path: Path,
    *,
    offer: Offer,
    response: str,
    reason: Optional[str],
    ghost_mode: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "ghost" if ghost_mode else "live"
    reason_tail = f" reason={reason!r}" if reason else ""
    line = (
        f"- [{offer.response_timestamp}] mode={mode} "
        f"offer_id={offer.offer_id} type={offer.type} "
        f"response={response}{reason_tail}\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def compute_acceptance_rate(
    offers: List[Offer],
    *,
    window_days: int = 14,
    now: Optional[datetime] = None,
) -> Optional[float]:
    """Trailing-``window_days`` acceptance rate. Returns None if <5 decided.

    Decided = offer with ``user_response`` in
    {accepted, accepted_with_edits, rejected}. Acceptance counts the first
    two; rejection counts rejected. snoozed/ignored/viewed are not decided.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=window_days)

    decided = 0
    accepted = 0
    for o in offers:
        if o.user_response not in ("accepted", "accepted_with_edits", "rejected"):
            continue
        ts = _parse_iso(o.response_timestamp or "")
        if ts is None or ts < cutoff:
            continue
        decided += 1
        if o.user_response in ("accepted", "accepted_with_edits"):
            accepted += 1

    if decided < 5:
        return None
    return accepted / decided


__all__ = ["record_response", "compute_acceptance_rate"]
