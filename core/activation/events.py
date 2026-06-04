"""Append-only response event log (Sprint 7, H3).

The Offer row carries the latest user_response for fast lookups; this log
carries the *history*. Every call to ``record_response`` appends one Event.
Metrics (acceptance rate, day-7 gate, weekly review) read from here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .io_jsonl import append_jsonl, iter_jsonl
from .schemas import Event


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def append_event(
    path: Path,
    *,
    offer_id: str,
    response: str,
    mode: str,
    now: datetime,
    reason: Optional[str] = None,
) -> Event:
    ev = Event(
        event_id=f"ev-{uuid.uuid4().hex[:12]}",
        offer_id=offer_id,
        response=response,
        timestamp=_to_iso(now),
        mode=mode,
        reason=reason,
    )
    append_jsonl(Path(path), ev.to_dict())
    return ev


def iter_events(
    path: Path,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Iterator[Event]:
    """Yield Events from ``path``, optionally bounded by [since, until).

    Robust to corrupted/partial lines — bad rows are silently skipped so a
    single bad write can't poison the whole event stream.
    """
    import json as _json

    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s:
                continue
            try:
                row = _json.loads(s)
            except _json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            try:
                ev = Event.from_dict(row)
            except (TypeError, ValueError, KeyError):
                continue
            if since is not None or until is not None:
                ts = _parse_iso(ev.timestamp)
                if ts is None:
                    continue
                if since is not None and ts < since:
                    continue
                if until is not None and ts >= until:
                    continue
            yield ev


__all__ = ["append_event", "iter_events"]
