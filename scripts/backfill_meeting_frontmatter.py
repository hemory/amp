#!/usr/bin/env python3
"""Backfill YAML frontmatter onto existing meeting notes.

Part of Sprint 2.5 of the B-1 Activation Engine. Scans
``04-Projects/**/*.md`` and ``05-Areas/**/*.md`` for files that look like
meeting notes (keyword heuristic shared with
``core.activation.gather``), and proposes a frontmatter block for each.

Behavior:
  - Files that already have a frontmatter block are skipped.
  - Meeting date is inferred via the same content-date scan used by
    gather (``extract_latest_content_date``) — falls back to mtime.
  - Attendees are parsed from the first line starting with ``Attendees:``.
    Both comma-separated names and ``[[Wiki_Link]]`` forms are supported.
  - Calendar event match is attempted via
    ``core.mcp.calendar_server._fetch_events`` for date ±1 day. Pick the
    event whose title has the closest case-insensitive substring overlap
    with the file's H1 or filename stem.
  - Default is ``--dry-run``: nothing is written; proposed frontmatter is
    printed to stdout. Pass ``--write`` to actually modify files.
  - Refuses to touch files outside ``04-Projects/`` + ``05-Areas/``.

Usage::

    python3 scripts/backfill_meeting_frontmatter.py [--dry-run] [--write] \\
        [--limit N] [--since YYYY-MM-DD] [--vault PATH]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---- bootstrap: add repo root to sys.path so `core.*` imports work. ---
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.activation.gather import (  # noqa: E402
    extract_latest_content_date,
    is_meeting_note,
)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover — yaml is required
    print("error: pyyaml not available; cannot run backfill", file=sys.stderr)
    raise


# ---- helpers ----------------------------------------------------------


ALLOWED_ROOTS: Tuple[str, ...] = ("04-Projects", "05-Areas")
FORBIDDEN_ROOTS: Tuple[str, ...] = ("00-Inbox", "System", ".claude", "06-Resources")
FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|$)", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")


def _already_has_frontmatter(text: str) -> bool:
    return bool(FRONTMATTER_RE.match(text))


def _infer_meeting_date(
    text: str, mtime: Optional[datetime], now: datetime
) -> Optional[date]:
    dt = extract_latest_content_date(text, now=now)
    if dt is not None:
        return dt.date()
    if mtime is not None:
        return mtime.astimezone(timezone.utc).date()
    return None


def _parse_attendees(text: str) -> List[str]:
    """Extract attendees from the first ``Attendees:`` line in the body."""
    for raw_line in text.splitlines()[:50]:
        line = raw_line.strip()
        low = line.lower()
        if low.startswith("attendees:") or low.startswith("attendees :"):
            _, _, rest = line.partition(":")
            rest = rest.strip()
            if not rest:
                return []
            # Prefer wiki links when present, else split on commas.
            wikis = WIKI_LINK_RE.findall(rest)
            if wikis:
                names = [_normalize_name(n) for n in wikis]
            else:
                names = [_normalize_name(p) for p in rest.split(",")]
            return [n for n in names if n]
    return []


def _normalize_name(raw: str) -> str:
    """Mirror of :func:`core.mcp.calendar_server.normalize_name_for_filename`.

    Kept local to avoid importing the full MCP module (which loads macOS
    bridges). Update both if the convention changes.
    """
    clean = re.sub(r"[^\w\s-]", "", raw)
    return re.sub(r"\s+", "_", clean.strip())


def _file_h1_or_stem(text: str, p: Path) -> str:
    m = H1_RE.search(text)
    if m:
        return m.group(1).strip()
    # Strip leading date prefix like "2026-03-30 - Title" if present.
    stem = p.stem
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}\s*-\s*", "", stem)
    return stem.strip()


def _match_calendar_event(
    title_hint: str, meeting_date: date
) -> Tuple[str, Optional[str]]:
    """Return (event_id, matched_title) or ("", None) on no-match / error.

    Uses ``core.mcp.calendar_server._fetch_events`` over a ±1-day window.
    Fail-open: any exception → empty event id.
    """
    try:
        import asyncio

        from core.mcp.calendar_server import _fetch_events  # type: ignore
    except Exception:
        return "", None

    start = (meeting_date - timedelta(days=1)).isoformat()
    end = (meeting_date + timedelta(days=2)).isoformat()
    try:
        result = asyncio.run(_fetch_events(start_date=start, end_date=end))
    except Exception:
        return "", None
    if not isinstance(result, dict) or not result.get("success"):
        return "", None
    events = result.get("events") or []
    if not events:
        return "", None

    hint = title_hint.lower()
    best: Optional[Tuple[int, dict]] = None
    for ev in events:
        ev_title = (ev.get("title") or ev.get("summary") or "").lower()
        if not ev_title:
            continue
        if hint and (hint in ev_title or ev_title in hint):
            # Score by length of the shorter side — rough overlap proxy.
            score = min(len(ev_title), len(hint))
            if best is None or score > best[0]:
                best = (score, ev)
    if best is None:
        return "", None
    ev = best[1]
    ev_id = (
        ev.get("id")
        or ev.get("event_id")
        or ev.get("uid")
        or ""
    )
    return str(ev_id), (ev.get("title") or ev.get("summary"))


def _build_frontmatter(fm: Dict[str, Any]) -> str:
    """Render the frontmatter dict as a YAML block with `---` fences."""
    body = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return f"---\n{body}---\n\n"


def _safe_relative_path(vault: Path, p: Path) -> str:
    try:
        return p.resolve().relative_to(vault.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _is_allowed_path(vault: Path, p: Path) -> bool:
    rel = _safe_relative_path(vault, p)
    top = rel.split("/", 1)[0] if "/" in rel else rel
    if top in FORBIDDEN_ROOTS:
        return False
    return top in ALLOWED_ROOTS


# ---- core walk --------------------------------------------------------


@dataclass
class Proposal:
    path: Path
    rel: str
    frontmatter: Dict[str, Any]
    block: str


def _iter_candidates(vault: Path, since: Optional[date]) -> List[Path]:
    out: List[Path] = []
    for base in ALLOWED_ROOTS:
        bp = vault / base
        if not bp.is_dir():
            continue
        for p in bp.rglob("*.md"):
            if not p.is_file():
                continue
            rel = _safe_relative_path(vault, p)
            # Read head once for the soft-token ``Attendees:`` check.
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                continue
            if not is_meeting_note(Path(rel), content_head=head):
                continue
            if since is not None:
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
                if mtime.date() < since:
                    continue
            out.append(p)
    out.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return out


# Public alias (used by tests and any external reuse).
find_candidates = _iter_candidates


def _propose(vault: Path, p: Path, now: datetime) -> Tuple[str, Optional[Proposal]]:
    """Return (status, proposal). status ∈ {write, skip:*, error:*}."""
    if not _is_allowed_path(vault, p):
        return "skip:out_of_scope", None

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"error:read:{e}", None

    if _already_has_frontmatter(text):
        return "skip:has_frontmatter", None

    try:
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    except OSError:
        mtime = None

    md = _infer_meeting_date(text, mtime, now)
    if md is None:
        return "skip:no_date", None

    title_hint = _file_h1_or_stem(text, p)
    attendees = _parse_attendees(text)
    event_id, _match_title = _match_calendar_event(title_hint, md)

    rel = _safe_relative_path(vault, p)
    fm: Dict[str, Any] = {
        "calendar_event_id": event_id or "",
        "meeting_date": md.isoformat(),
        "attendees": attendees,
        "source_inbox_file": "",
        "processed_at": now.isoformat(),
    }
    block = _build_frontmatter(fm)
    return "write", Proposal(path=p, rel=rel, frontmatter=fm, block=block)


def _atomic_prepend(p: Path, block: str, original: str) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        tmp.write_text(block + original, encoding="utf-8")
        os.replace(tmp, p)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# ---- cli --------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="backfill_meeting_frontmatter",
        description=(
            "Propose or write YAML frontmatter for existing meeting notes "
            "under 04-Projects/ and 05-Areas/."
        ),
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="(default) print proposals; do not modify files")
    mode.add_argument("--write", action="store_true",
                      help="actually write frontmatter into files (atomic)")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N files")
    ap.add_argument("--since", type=str, default=None,
                    help="only consider files with mtime on/after YYYY-MM-DD")
    ap.add_argument("--vault", type=str, default=None,
                    help="vault root (defaults to repo root)")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    vault = Path(args.vault).resolve() if args.vault else _REPO_ROOT
    since: Optional[date] = None
    if args.since:
        try:
            since = date.fromisoformat(args.since)
        except ValueError:
            print(f"error: --since must be YYYY-MM-DD (got {args.since!r})", file=sys.stderr)
            return 2

    now = datetime.now(timezone.utc)
    write_mode = bool(args.write)  # dry_run is default; explicit --write flips

    stats = {
        "scanned": 0,
        "skipped_has_frontmatter": 0,
        "skipped_no_date": 0,
        "skipped_out_of_scope": 0,
        "would_write": 0,
        "wrote": 0,
        "errors": 0,
    }

    candidates = _iter_candidates(vault, since)
    for p in candidates:
        if args.limit is not None and stats["would_write"] + stats["wrote"] >= args.limit:
            break
        stats["scanned"] += 1

        status, proposal = _propose(vault, p, now)

        if status == "skip:has_frontmatter":
            stats["skipped_has_frontmatter"] += 1
            continue
        if status == "skip:no_date":
            stats["skipped_no_date"] += 1
            print(f"SKIP  {_safe_relative_path(vault, p)}  (no inferable date)")
            continue
        if status == "skip:out_of_scope":
            stats["skipped_out_of_scope"] += 1
            continue
        if status.startswith("error:"):
            stats["errors"] += 1
            print(f"ERROR {_safe_relative_path(vault, p)}  ({status})", file=sys.stderr)
            continue
        assert status == "write" and proposal is not None

        if write_mode:
            try:
                original = p.read_text(encoding="utf-8", errors="replace")
                _atomic_prepend(p, proposal.block, original)
                stats["wrote"] += 1
                print(f"WROTE {proposal.rel}  meeting_date={proposal.frontmatter['meeting_date']}")
            except OSError as e:
                stats["errors"] += 1
                print(f"ERROR {proposal.rel}  ({e})", file=sys.stderr)
        else:
            stats["would_write"] += 1
            print(f"PROPOSE {proposal.rel}")
            print("--- proposed frontmatter ---")
            sys.stdout.write(proposal.block)
            print("---")

    print()
    print("Summary:")
    for k in (
        "scanned",
        "skipped_has_frontmatter",
        "skipped_no_date",
        "skipped_out_of_scope",
        "would_write",
        "wrote",
        "errors",
    ):
        print(f"  {k}: {stats[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
