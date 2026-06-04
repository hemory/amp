"""Quiet-mode check. §6.5 of design doc.

`System/activation/quiet-mode.yaml` may contain:
    until: 2026-04-25      # ISO date; engine is quiet until *end* of this day
    reason: "out of office"

Missing file → not quiet.
Malformed yaml or missing `until:` → not quiet (fail-open; we never want the
quiet-mode file itself to crash the daily-plan ritual).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple

from .config import load_quiet


def _coerce_until(value: object) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s).date()
        except ValueError:
            try:
                return date.fromisoformat(s)
            except ValueError:
                return None
    return None


def quiet_status(
    path: Path | None = None, today: Optional[date] = None
) -> Tuple[bool, Optional[str], Optional[date]]:
    """Return (is_quiet, reason, until_date).

    Quiet iff `until` is a valid date and today <= until.
    """
    try:
        data = load_quiet(path)
    except Exception:
        # Malformed YAML — fail-open per module docstring.
        return False, None, None

    if not isinstance(data, dict) or not data:
        return False, None, None

    until = _coerce_until(data.get("until"))
    if until is None:
        return False, None, None

    today = today or date.today()
    if today > until:
        return False, None, until

    reason = data.get("reason")
    if isinstance(reason, str):
        reason = reason.strip() or None
    else:
        reason = None
    return True, reason, until


def is_quiet(
    path: Path | None = None, today: Optional[date] = None
) -> Tuple[bool, Optional[str]]:
    """Return (is_quiet, reason)."""
    quiet, reason, _ = quiet_status(path, today)
    return quiet, reason


__all__ = ["is_quiet", "quiet_status"]
