"""
Timezone utilities for Amp.

Reads the user's configured timezone from System/user-profile.yaml
and provides timezone-aware datetime helpers.
"""

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

_DEFAULT_TZ = "America/New_York"
_user_tz = None
_user_tz_loaded_at: float = 0
_TZ_CACHE_TTL = 300  # 5 minutes
_TZ_ALIASES = {
    "EDT": "America/New_York",
    "EST": "America/New_York",
    "CDT": "America/Chicago",
    "CST": "America/Chicago",
    "MDT": "America/Denver",
    "MST": "America/Denver",
    "PDT": "America/Los_Angeles",
    "PST": "America/Los_Angeles",
}


def normalize_timezone_name(tz_name: str | None) -> str:
    """Return a usable IANA timezone name."""
    if not tz_name:
        return _DEFAULT_TZ

    cleaned = str(tz_name).strip()
    if not cleaned:
        return _DEFAULT_TZ

    alias = _TZ_ALIASES.get(cleaned.upper())
    if alias:
        return alias

    return cleaned


def resolve_timezone(tz_name: str | None) -> ZoneInfo:
    """Resolve a timezone name safely, falling back to the default when needed."""
    normalized = normalize_timezone_name(tz_name)
    try:
        return ZoneInfo(normalized)
    except Exception:
        return ZoneInfo(_DEFAULT_TZ)


def detect_system_timezone() -> str:
    """Best-effort detection of the system timezone name.

    Returns the system's IANA timezone name when possible; otherwise
    falls back to the default timezone used by this module.
    """
    try:
        # Let Python determine the local timezone, then extract a usable name.
        local_tz = datetime.now().astimezone().tzinfo
        if hasattr(local_tz, "key"):
            # `zoneinfo.ZoneInfo` instances expose the IANA key via `.key`.
            return getattr(local_tz, "key")  # type: ignore[attr-defined]
        if local_tz is not None:
            name = str(local_tz)
            if name and name.lower() != "local":
                return normalize_timezone_name(name)
    except Exception:
        # If anything goes wrong, fall back to the module default.
        pass

    return _DEFAULT_TZ


def _get_user_timezone() -> ZoneInfo:
    """Load the user's timezone from user-profile.yaml (cached with 5-min TTL)."""
    global _user_tz, _user_tz_loaded_at
    import time as _time
    if _user_tz is not None and (_time.time() - _user_tz_loaded_at) < _TZ_CACHE_TTL:
        return _user_tz

    tz_name = _DEFAULT_TZ

    # Walk up from this file to find the vault root (where System/ lives)
    search = Path(__file__).resolve().parent
    for _ in range(10):
        profile = search / "System" / "user-profile.yaml"
        if profile.exists():
            try:
                with open(profile) as f:
                    data = yaml.safe_load(f)
                if data and data.get("timezone"):
                    tz_name = normalize_timezone_name(data["timezone"])
            except Exception:
                pass
            break
        search = search.parent

    _user_tz = resolve_timezone(tz_name)
    _user_tz_loaded_at = _time.time()
    return _user_tz


def now() -> datetime:
    """Return the current time in the user's configured timezone."""
    return datetime.now(_get_user_timezone())


def today():
    """Return today's date in the user's configured timezone."""
    return now().date()


def convert_utc_to_user(dt_str: str) -> str:
    """Convert a UTC datetime string from EventKit to the user's local time string.

    Handles formats like:
      '2026-03-16 18:30:00 +0000'
      '2026-03-16T18:30:00+00:00'
    Returns:
      '2026-03-16 14:30:00' (if user tz is America/New_York during EDT)
    """
    cleaned = dt_str.strip()

    # Format from NSDate str(): '2026-03-16 18:30:00 +0000'
    if "+0000" in cleaned:
        naive_str = cleaned.replace(" +0000", "")
        utc_dt = datetime.fromisoformat(naive_str).replace(tzinfo=timezone.utc)
    elif cleaned.endswith("Z"):
        utc_dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    else:
        # Try parsing as-is (may already have offset)
        try:
            utc_dt = datetime.fromisoformat(cleaned)
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return dt_str  # Can't parse, return as-is

    local_dt = utc_dt.astimezone(_get_user_timezone())
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")
