"""Stage 1 — Gather signals. §4.1 of design doc.

Pure-function walker across configured sources; produces a
`list[Signal]`. No LLM, no ranking, no extraction. The CLI
(:mod:`core.activation.__main__`) is responsible for writing
`signals.jsonl`.

Meeting-note detection (``is_meeting_note``):
    A file qualifies as a meeting note iff **one** of the following holds:

    * Its path is under ``00-Inbox/Meetings/`` (literal inbox rule).
    * Its path contains a directory segment literally named ``meetings``
      (case-insensitive) — e.g. ``04-Projects/X/meetings/foo.md``.
    * Its filename/path matches the *hard* tokens ``meeting`` or
      ``meetings`` as a word-boundary regex match. These are explicit
      enough that no content check is required.
    * Its filename/path matches the *soft* tokens ``1-1``, ``1on1``,
      ``standup``, or ``sync`` AND the first ~2000 chars of the file
      contain a line starting (case-insensitively, after optional
      whitespace) with ``Attendees:`` or ``Attendees :``.

    Notably ``planning`` is **not** a keyword (Sprint 2.5 retro:
    ``/01-planning/``-style subdirs produced ~13 false positives out
    of 14 backfill proposals). ``1-on-1`` is also dropped in favour
    of the stricter ``1-1`` / ``1on1`` forms.

Sources (per §3.1, with reality-adjustments documented in
the session audit file):

- Meeting-like notes under ``04-Projects/**`` and ``05-Areas/**``
  (window: 7 days, cap: 200).
- Person pages under ``06-Resources/People/**`` (window: 30 days;
  returns ``[]`` if dir missing).
- Tasks via :func:`core.utils.vault.parse_tasks` (open + started + blocked).
- Project docs under ``04-Projects/**`` (window: 14 days) excluding
  files already captured as meeting notes.
- Session learnings ``System/Session_Learnings/*.md`` (window: 14 days
  by filename date).
- Calendar via ``core.mcp.calendar_server._fetch_events`` (±3 days,
  fail-open on any error).

Global cap: 500 signals, truncated by recency. Tombstones filtered
via a minimal substring match on ``"{source}|{path}"``.
"""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import re
import sys
import time
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from . import paths
from .io_jsonl import read_jsonl
from .schemas import Signal

# --- constants ---------------------------------------------------------

# Hard tokens: path signal alone is sufficient to classify as a meeting.
MEETING_HARD_TOKENS: Tuple[str, ...] = ("meeting", "meetings")
# Soft tokens: need confirmation via an ``Attendees:`` content line
# before classifying as a meeting.
MEETING_SOFT_TOKENS: Tuple[str, ...] = ("1-1", "1on1", "standup", "sync")
# Back-compat tuple (previously exported). Reflects the union of tokens
# the detector looks at, with ``planning`` / ``1-on-1`` removed per the
# Sprint 2.5 retro. External callers should prefer ``is_meeting_note``.
MEETING_KEYWORDS: Tuple[str, ...] = MEETING_HARD_TOKENS + MEETING_SOFT_TOKENS

_MEETING_HARD_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in MEETING_HARD_TOKENS) + r")\b",
    flags=re.IGNORECASE,
)
_MEETING_SOFT_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in MEETING_SOFT_TOKENS) + r")\b",
    flags=re.IGNORECASE,
)
_MEETINGS_DIR_RE = re.compile(r"(?:^|/)meetings(?:/|$)", flags=re.IGNORECASE)
_INBOX_MEETINGS_RE = re.compile(r"(?:^|/)00-Inbox/Meetings(?:/|$)", flags=re.IGNORECASE)
_ATTENDEES_LINE_RE = re.compile(r"(?im)^[ \t]*attendees[ \t]*:")

MEETING_CONTENT_SCAN_CHARS = 2000
MEETING_WINDOW_DAYS = 14  # widened from 7 in Sprint 2.5; content-date scan
                          # gives recall, keyword filter gives precision.
PEOPLE_WINDOW_DAYS = 30
PROJECT_DOC_WINDOW_DAYS = 14
LEARNING_WINDOW_DAYS = 14
CALENDAR_WINDOW_DAYS = 3

MEETING_CAP = 200
GLOBAL_CAP = 500
EXCERPT_CHARS = 300
# Larger window used when scanning meeting-note body text for dates;
# covers frontmatter + first paragraph without pulling entire file.
MEETING_DATE_SCAN_CHARS = 1000
ID_HASH_LEN = 16


# --- date scanning -----------------------------------------------------

_MONTHS: Dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

_MONTH_ALT = (
    "Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|"
    "Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December"
)
_US_LONG_DATE_RE = re.compile(
    rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b",
    flags=re.IGNORECASE,
)

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def extract_latest_content_date(
    text: str, now: Optional[datetime] = None
) -> Optional[datetime]:
    """Return the latest date mentioned in ``text`` that is ``<= now``.

    Recognises ISO (``2026-04-12``), US-long (``Feb 6, 2026``, ``April 2 2026``),
    and month-day short forms (``Feb 6``). Short forms inherit their year from
    the positionally-closest year-bearing date; if none exists, they fall back
    to ``now.year``. Future dates are ignored. Returns a UTC-tz datetime at
    noon on the winning date, or ``None`` if no usable date was found.
    """
    if not text:
        return None
    if now is None:
        now = datetime.now(timezone.utc)
    today = now.date()

    # (position, date) tuples from fully-qualified date mentions.
    dated: List[Tuple[int, date]] = []
    # (position, month, day) tuples from month-day mentions lacking a year.
    undated: List[Tuple[int, int, int]] = []

    for m in _ISO_DATE_RE.finditer(text):
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        dated.append((m.start(), d))

    for m in _US_LONG_DATE_RE.finditer(text):
        month_key = m.group(1).lower().rstrip(".")
        month = _MONTHS.get(month_key)
        if not month:
            continue
        try:
            day = int(m.group(2))
        except ValueError:
            continue
        year_raw = m.group(3)
        if year_raw:
            try:
                dated.append((m.start(), date(int(year_raw), month, day)))
            except ValueError:
                continue
        else:
            undated.append((m.start(), month, day))

    resolved: List[date] = [d for _, d in dated]
    for pos, month, day in undated:
        if dated:
            _, closest = min(dated, key=lambda item: abs(item[0] - pos))
            year = closest.year
        else:
            year = today.year
        try:
            resolved.append(date(year, month, day))
        except ValueError:
            continue

    resolved = [d for d in resolved if d <= today]
    if not resolved:
        return None
    latest = max(resolved)
    return datetime.combine(latest, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)


# Private alias retained for readers used to the `_`-prefixed name.
_extract_latest_content_date = extract_latest_content_date


def _parse_frontmatter(text: str) -> Optional[Dict[str, Any]]:
    """Return the YAML frontmatter as a dict, or None if absent / unparseable."""
    if not text:
        return None
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        loaded = yaml.safe_load(m.group(1))
    except Exception:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _fm_date_to_datetime(value: Any) -> Optional[datetime]:
    """Coerce a YAML frontmatter ``meeting_date`` value to a UTC datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            try:
                d = date.fromisoformat(raw)
                return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _extract_meeting_structured(fm: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pull the subset of frontmatter keys the activation pipeline cares about."""
    if not fm:
        return None
    out: Dict[str, Any] = {}
    if "calendar_event_id" in fm:
        ceid = fm.get("calendar_event_id")
        if isinstance(ceid, str):
            out["calendar_event_id"] = ceid
        elif ceid is None:
            out["calendar_event_id"] = ""
        else:
            out["calendar_event_id"] = str(ceid)
    if "attendees" in fm:
        att = fm.get("attendees")
        if isinstance(att, list):
            out["attendees"] = [str(a) for a in att]
    if "meeting_date" in fm:
        md = fm.get("meeting_date")
        if isinstance(md, (date, datetime)):
            out["meeting_date"] = md.isoformat()
        elif md is not None:
            out["meeting_date"] = str(md)
    return out or None


# --- low-level helpers -------------------------------------------------


def _now(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _root(vault_root: Optional[Path]) -> Path:
    return Path(vault_root) if vault_root is not None else paths.VAULT_ROOT


def _make_signal_id(source: str, rel_path: str, timestamp_iso: str, excerpt: str) -> str:
    payload = f"{source}|{rel_path}|{timestamp_iso}|{excerpt[:200]}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:ID_HASH_LEN]


def _build_signal(
    source: str,
    rel_path: str,
    ts: datetime,
    excerpt: str,
    structured: Optional[Dict[str, Any]] = None,
) -> Signal:
    # Normalise to UTC ISO-8601 so IDs are stable regardless of caller tz.
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    iso = ts.isoformat()
    sid = _make_signal_id(source, rel_path, iso, excerpt)
    return Signal(
        signal_id=sid,
        source=source,
        path=rel_path,
        timestamp=iso,
        excerpt=excerpt,
        structured=structured,
    )


def _rel(root: Path, p: Path) -> str:
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _read_first_chars(p: Path, n: int = EXCERPT_CHARS) -> str:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    # Collapse interior whitespace for compactness but keep linebreaks intact
    # up to the char limit — readers can still eyeball.
    return text[:n]


def _mtime(p: Path) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def is_meeting_note(path: Path, content_head: Optional[str] = None) -> bool:
    """Return True iff the file at ``path`` is a meeting note.

    See the module docstring for the full rule set. ``content_head`` is
    the first ~2000 chars of the file; if ``None`` and the soft-token
    path rule needs confirmation, the function reads the file itself.
    A ``path`` may be absolute or vault-relative — matching operates on
    its posix form as a string, so either works.

    Exported so the backfill script can share exactly this heuristic.
    """
    rel = path.as_posix()

    # Inbox rule: 00-Inbox/Meetings/ is literally the meeting inbox.
    if _INBOX_MEETINGS_RE.search(rel):
        return True
    # Any parent directory literally named "meetings".
    if _MEETINGS_DIR_RE.search(rel):
        return True
    # Hard tokens (meeting / meetings) as a word-boundary match.
    if _MEETING_HARD_RE.search(rel):
        return True
    # Soft tokens require an ``Attendees:`` line in the file head.
    if _MEETING_SOFT_RE.search(rel):
        head = content_head
        if head is None:
            try:
                head = path.read_text(encoding="utf-8", errors="replace")[
                    :MEETING_CONTENT_SCAN_CHARS
                ]
            except OSError:
                return False
        else:
            head = head[:MEETING_CONTENT_SCAN_CHARS]
        return bool(_ATTENDEES_LINE_RE.search(head))
    return False


def _is_meeting_like(rel_path: str, content_head: Optional[str] = None) -> bool:
    """Internal wrapper — treats ``rel_path`` as a posix string path."""
    return is_meeting_note(Path(rel_path), content_head=content_head)


# --- source handlers ---------------------------------------------------


def _read_head(p: Path, n: int) -> str:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[:n]


def _gather_meeting_notes(now: datetime, vault_root: Path) -> List[Signal]:
    # Window compared by DATE (not instant): a file dated 14 days ago is kept.
    cutoff_date = (now - timedelta(days=MEETING_WINDOW_DAYS)).date()
    today = now.date()
    out: List[Signal] = []
    for base in ("04-Projects", "05-Areas"):
        bp = vault_root / base
        if not bp.is_dir():
            continue
        for p in bp.rglob("*.md"):
            if not p.is_file():
                continue
            rel = _rel(vault_root, p)
            # Read head once — reused for content-date scan, frontmatter,
            # and the soft-token attendees check.
            head = _read_head(p, max(MEETING_DATE_SCAN_CHARS, MEETING_CONTENT_SCAN_CHARS))
            if not _is_meeting_like(rel, content_head=head):
                continue
            mt = _mtime(p)

            # Frontmatter is authoritative when present.
            fm = _parse_frontmatter(head)
            structured = _extract_meeting_structured(fm)
            fm_dt = _fm_date_to_datetime(fm.get("meeting_date")) if fm else None

            # Content-date scan (first 1000 chars). Skip frontmatter region
            # so a `meeting_date: 2026-04-10` doesn't double-count as content.
            body_for_scan = head
            if fm is not None:
                m = _FRONTMATTER_RE.match(head)
                if m:
                    body_for_scan = head[m.end():]
            content_dt = extract_latest_content_date(body_for_scan, now=now)

            if fm_dt is not None:
                effective = fm_dt
            elif content_dt is not None and mt is not None:
                effective = max(mt, content_dt)
            elif content_dt is not None:
                effective = content_dt
            else:
                effective = mt

            if effective is None:
                continue
            eff_date = effective.date()
            if eff_date < cutoff_date or eff_date > today:
                continue

            excerpt = head[:EXCERPT_CHARS]
            out.append(
                _build_signal("meeting_notes", rel, effective, excerpt, structured=structured)
            )
    # Cap at 200 most-recent.
    out.sort(key=lambda s: s.timestamp, reverse=True)
    if len(out) > MEETING_CAP:
        out = out[:MEETING_CAP]
    return out


def _gather_person_pages(now: datetime, vault_root: Path) -> List[Signal]:
    people_dir = vault_root / "06-Resources" / "People"
    if not people_dir.is_dir():
        return []
    cutoff = now - timedelta(days=PEOPLE_WINDOW_DAYS)
    out: List[Signal] = []
    for p in people_dir.rglob("*.md"):
        if not p.is_file():
            continue
        mt = _mtime(p)
        if mt is None or mt < cutoff or mt > now:
            continue
        rel = _rel(vault_root, p)
        out.append(_build_signal("person_pages", rel, mt, _person_excerpt(p)))
    return out


def _person_excerpt(p: Path) -> str:
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    pieces: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            pieces.append(stripped)
            break
    # Look for a "Last contact:" line.
    for line in lines:
        if re.search(r"last\s*contact", line, flags=re.IGNORECASE):
            pieces.append(line.strip())
            break
    joined = "\n".join(pieces)
    return joined[:EXCERPT_CHARS]


def _gather_tasks(now: datetime, vault_root: Path) -> List[Signal]:
    try:
        from core.utils.vault import parse_tasks
    except Exception as e:  # pragma: no cover — imports should succeed
        print(f"[gather] tasks import failed: {e}", file=sys.stderr)
        return []
    try:
        parsed = parse_tasks(str(vault_root))
    except Exception as e:
        print(f"[gather] parse_tasks failed: {e}", file=sys.stderr)
        return []
    rel = "03-Tasks/Tasks.md"
    out: List[Signal] = []
    buckets = (
        ("open", parsed.get("open") or []),
        ("started", parsed.get("started") or []),
        ("blocked", parsed.get("blocked") or []),
    )
    for bucket, items in buckets:
        for t in items:
            title = (t.get("title") or "").strip()
            if not title:
                continue
            section = (t.get("section") or "").strip()
            priority = (t.get("priority") or "").strip()
            parts = [f"[{bucket}]", title]
            if priority:
                parts.append(f"(prio={priority})")
            if section:
                parts.append(f"<{section}>")
            excerpt = " ".join(parts)[:EXCERPT_CHARS]
            out.append(_build_signal("tasks", rel, now, excerpt))
    return out


def _gather_project_docs(now: datetime, vault_root: Path) -> List[Signal]:
    bp = vault_root / "04-Projects"
    if not bp.is_dir():
        return []
    cutoff = now - timedelta(days=PROJECT_DOC_WINDOW_DAYS)
    out: List[Signal] = []
    for p in bp.rglob("*.md"):
        if not p.is_file():
            continue
        rel = _rel(vault_root, p)
        if _is_meeting_like(rel, content_head=_read_head(p, MEETING_CONTENT_SCAN_CHARS)):
            continue  # handled by meeting-notes source
        mt = _mtime(p)
        if mt is None or mt < cutoff or mt > now:
            continue
        out.append(_build_signal("project_docs", rel, mt, _read_first_chars(p)))
    return out


_DATE_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def _gather_session_learnings(now: datetime, vault_root: Path) -> List[Signal]:
    sl_dir = vault_root / "System" / "Session_Learnings"
    if not sl_dir.is_dir():
        return []
    cutoff_date = (now - timedelta(days=LEARNING_WINDOW_DAYS)).date()
    today = now.date()
    out: List[Signal] = []
    for p in sorted(sl_dir.glob("*.md")):
        m = _DATE_NAME_RE.match(p.name)
        if not m:
            continue
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d < cutoff_date or d > today:
            continue
        # Timestamp: noon UTC on the named date — avoids tz boundary flakiness.
        ts = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
        rel = _rel(vault_root, p)
        out.append(_build_signal("session_learnings", rel, ts, _read_first_chars(p)))
    return out


def _calendar_fetcher() -> Optional[Callable[[str, str], dict]]:
    """Return a sync callable ``f(start, end) -> result dict`` or None if unavailable.

    Wraps the async ``_fetch_events`` from :mod:`core.mcp.calendar_server`.
    """
    try:
        from core.mcp.calendar_server import _fetch_events  # type: ignore
    except Exception as e:
        print(f"[gather] calendar import unavailable: {e}", file=sys.stderr)
        return None

    def _call(start: str, end: str) -> dict:
        return asyncio.run(_fetch_events(start_date=start, end_date=end))

    return _call


def _gather_calendar(now: datetime, vault_root: Path) -> List[Signal]:
    fetcher = _calendar_fetcher()
    if fetcher is None:
        return []
    start = (now.date() - timedelta(days=CALENDAR_WINDOW_DAYS)).isoformat()
    end = (now.date() + timedelta(days=CALENDAR_WINDOW_DAYS + 1)).isoformat()
    try:
        result = fetcher(start, end)
    except Exception as e:
        print(f"[gather] calendar fetch failed: {e}", file=sys.stderr)
        return []
    if not isinstance(result, dict) or not result.get("success"):
        print(f"[gather] calendar returned error: {result!r}"[:200], file=sys.stderr)
        return []
    events = result.get("events") or []
    out: List[Signal] = []
    for ev in events:
        title = (ev.get("title") or ev.get("summary") or "(untitled)").strip()
        start_s = (ev.get("start") or "").strip()
        end_s = (ev.get("end") or "").strip()
        location = (ev.get("location") or "").strip()
        attendees = ev.get("attendees") or []
        try:
            ts = datetime.fromisoformat(start_s) if start_s else now
        except ValueError:
            ts = now
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rel_path = f"calendar://{start_s or title}"
        pieces = [title]
        if start_s:
            pieces.append(f"start={start_s}")
        if end_s:
            pieces.append(f"end={end_s}")
        if location:
            pieces.append(f"loc={location}")
        if attendees:
            names = [
                (a.get("name") or a.get("email") or "") if isinstance(a, dict) else str(a)
                for a in attendees
            ]
            names = [n for n in names if n]
            if names:
                pieces.append("attendees=" + ", ".join(names[:10]))
        excerpt = " | ".join(pieces)[:EXCERPT_CHARS]
        out.append(_build_signal("calendar", rel_path, ts, excerpt))
    return out


# --- tombstones --------------------------------------------------------


def _load_tombstone_patterns(vault_root: Path) -> List[str]:
    path = vault_root / "System" / "activation" / "tombstones.jsonl"
    try:
        rows = read_jsonl(path)
    except Exception as e:
        print(f"[gather] tombstone read failed: {e}", file=sys.stderr)
        return []
    patterns: List[str] = []
    for row in rows:
        pat = row.get("pattern") if isinstance(row, dict) else None
        if isinstance(pat, str) and pat.strip():
            patterns.append(pat.strip())
    return patterns


def _filter_tombstones(signals: List[Signal], patterns: List[str]) -> List[Signal]:
    if not patterns:
        return signals
    out: List[Signal] = []
    for s in signals:
        key = f"{s.source}|{s.path}"
        if any(_matches(pat, key) for pat in patterns):
            continue
        out.append(s)
    return out


def _matches(pattern: str, key: str) -> bool:
    # Glob-style if pattern has glob chars; otherwise substring (case-sensitive
    # on path, which matches file system).
    if any(ch in pattern for ch in "*?[]"):
        return fnmatch.fnmatchcase(key, pattern)
    return pattern in key


# --- entrypoint --------------------------------------------------------


def gather(
    now: Optional[datetime] = None,
    vault_root: Optional[Path] = None,
) -> List[Signal]:
    """Walk configured sources and produce Signal rows.

    Pure function. ``now`` defaults to :func:`datetime.now` in UTC.
    ``vault_root`` defaults to :data:`core.activation.paths.VAULT_ROOT`.
    """
    started = time.monotonic()
    n = _now(now)
    root = _root(vault_root)

    sources: Iterable[Tuple[str, Callable[[datetime, Path], List[Signal]]]] = (
        ("meeting_notes", _gather_meeting_notes),
        ("person_pages", _gather_person_pages),
        ("tasks", _gather_tasks),
        ("project_docs", _gather_project_docs),
        ("session_learnings", _gather_session_learnings),
        ("calendar", _gather_calendar),
    )

    all_signals: List[Signal] = []
    for name, fn in sources:
        try:
            rows = fn(n, root)
        except Exception as e:
            print(f"[gather] source {name!r} failed: {e}", file=sys.stderr)
            continue
        all_signals.extend(rows)

    # Tombstone filter.
    patterns = _load_tombstone_patterns(root)
    all_signals = _filter_tombstones(all_signals, patterns)

    # Global cap: keep the most-recent by ISO timestamp.
    total_before = len(all_signals)
    if total_before > GLOBAL_CAP:
        all_signals.sort(key=lambda s: s.timestamp, reverse=True)
        all_signals = all_signals[:GLOBAL_CAP]
        print(
            f"[gather] truncated: kept {len(all_signals)} of {total_before} signals",
            file=sys.stderr,
        )

    elapsed = time.monotonic() - started
    print(
        f"[gather] completed in {elapsed:.1f}s, {len(all_signals)} signals",
        file=sys.stderr,
    )
    return all_signals


# --- legacy alias ------------------------------------------------------


def gather_signals() -> List[Signal]:  # pragma: no cover — back-compat shim
    return gather()


__all__ = [
    "gather",
    "gather_signals",
    "extract_latest_content_date",
    "is_meeting_note",
    "MEETING_KEYWORDS",
    "MEETING_HARD_TOKENS",
    "MEETING_SOFT_TOKENS",
]
