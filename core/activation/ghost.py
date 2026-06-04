"""Sprint 6 — Ghost mode as a first-class state.

Ghost mode is the §7 / §10 #2 safeguard: the engine runs the full pipeline
but does not surface offers. Sprint 6 promotes it from a CLI flag the
ranker reads to a programmatic state shared across log, surface, and the
ghost-exit ritual.

Stdlib only — yaml read/write goes through ``core.activation.config`` for
parsing but write side stays here so we don't reach across modules.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


GHOST_INSTALL_WINDOW_DAYS = 7  # §10 locked decision #2
GHOST_REVIEW_LOOKBACK_DAYS = 7  # used by ghost-exit eligibility check


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

GHOST_REASONS = ("install_window", "manual", "post_review_pause")


@dataclass
class GhostState:
    """The canonical ghost-mode state at a point in time.

    ``reason`` is one of ``GHOST_REASONS`` when ``active`` is True, else "".
    ``expected_end`` is None for open-ended manual ghost.
    ``review_completed_at`` is the timestamp of the most recent ghost-review
    marker found in ghost-log.md (None if there isn't one).
    """

    active: bool
    reason: str
    started_at: datetime
    expected_end: Optional[datetime] = None
    review_completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "reason": self.reason,
            "started_at": _iso(self.started_at),
            "expected_end": _iso(self.expected_end) if self.expected_end else None,
            "review_completed_at": (
                _iso(self.review_completed_at) if self.review_completed_at else None
            ),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _date_to_dt(d: date) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=timezone.utc)


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# install.yaml (bootstrap)
# ---------------------------------------------------------------------------

def read_install_date(state_path: Path) -> date:
    """Read the install date from ``install.yaml``.

    If the file does not exist, this function **bootstraps it** by writing
    today's UTC date and returning it. Installation date is a one-shot
    marker — once written it never changes (this is what makes the 7-day
    install window deterministic).

    Sprint 7 M2: if the file is missing but the activation directory shows
    signs of prior life (ghost-log.md exists, offers.jsonl non-empty, etc.),
    we suspect file loss / vault drift. In that case we still bootstrap a
    fresh date (so the system keeps working) BUT also write a sidecar at
    ``install.yaml.recovered.{ts}`` and emit a stderr WARNING so the user can
    investigate. If the file exists but contains an unparseable
    ``install_date``, we abort instead of silently overwriting — corrupted
    files are a louder failure than missing ones.
    """
    p = Path(state_path)
    if p.exists():
        # Read directly so YAML errors surface as SystemExit (don't trust
        # _read_yaml here — it swallows errors for non-critical callers).
        try:
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:  # corrupted YAML
            raise SystemExit(
                f"install.yaml is unreadable ({e!r}); refusing to overwrite. "
                "Inspect the file or move it aside, then re-run."
            )
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise SystemExit(
                f"install.yaml has unexpected top-level type {type(data).__name__}; "
                "expected a mapping. Inspect the file or move it aside, then re-run."
            )
        raw = data.get("install_date")
        d = _coerce_date(raw)
        if d is not None:
            return d
        if raw is not None:
            # File exists with a non-empty but unparseable install_date —
            # never silently overwrite. Force the operator to look.
            raise SystemExit(
                f"install.yaml has install_date={raw!r} which is not a valid date. "
                "Fix or remove the field manually, then re-run."
            )
        # File exists but install_date is missing — heal it (no data loss risk).

    # Bootstrap path. Detect "drift" — file is missing but the vault
    # shows prior activation activity → noisy recovery sidecar.
    drift = False
    try:
        act_dir = p.parent
        if act_dir.exists():
            for sentinel in ("ghost-log.md", "offers.jsonl", "candidates.jsonl"):
                sp = act_dir / sentinel
                if sp.exists() and sp.stat().st_size > 0:
                    drift = True
                    break
    except OSError:
        pass

    today = datetime.now(timezone.utc).date()
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_yaml(p) if p.exists() else {}
    existing["install_date"] = today.isoformat()
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, sort_keys=True)

    if drift:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sidecar = p.with_suffix(p.suffix + f".recovered.{ts}")
        try:
            with sidecar.open("w", encoding="utf-8") as f:
                yaml.safe_dump(
                    {
                        "recovered_at": _iso(datetime.now(timezone.utc)),
                        "bootstrapped_install_date": today.isoformat(),
                        "note": (
                            "install.yaml was missing but the activation "
                            "directory contained prior state. A fresh "
                            "install_date was written; the previous true "
                            "install date is unknown. Investigate vault "
                            "history if this is unexpected."
                        ),
                    },
                    f,
                    sort_keys=True,
                )
            print(
                f"WARNING: install.yaml was missing; bootstrapped to {today.isoformat()} "
                f"and wrote sidecar {sidecar.name} (Sprint 7 M2).",
                file=sys.stderr,
            )
        except OSError:
            pass

    return today


def write_install_field(state_path: Path, key: str, value: Any) -> None:
    """Update or set ``key`` in install.yaml. Creates the file if missing."""
    p = Path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = _read_yaml(p) if p.exists() else {}
    data[key] = value
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=True)


# ---------------------------------------------------------------------------
# ghost-log review markers
# ---------------------------------------------------------------------------

# Structured marker line written by mark_ghost_review_complete. The JSON
# payload is on the same line so ghost-log.md remains readable.
_REVIEW_MARKER_PREFIX = "<!-- ghost-review "
_REVIEW_MARKER_SUFFIX = " -->"


def mark_ghost_review_complete(
    log_path: Path,
    *,
    now: datetime,
    decisions: List[Dict[str, Any]],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a structured ghost-review entry to ghost-log.md.

    ``decisions`` is a list of dicts like
    ``{"offer_id": "o-...", "user_response": "accepted", "reason": ...}``.
    Returns the marker payload (also embedded in the file as a HTML comment
    so ghost-log.md stays human-readable).
    """
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    accepts = sum(
        1 for d in decisions
        if d.get("user_response") in ("accepted", "accepted_with_edits")
    )
    rejects = sum(1 for d in decisions if d.get("user_response") == "rejected")
    others = len(decisions) - accepts - rejects

    # Sprint 7 H4 — explicit count of decisions that are "real responses"
    # (accepted variants + rejected + never_again). Snoozed/ignored/viewed
    # do not count toward exit eligibility.
    decided_offer_count = sum(
        1 for d in decisions
        if d.get("user_response") in (
            "accepted", "accepted_with_edits", "rejected", "never_again",
        )
    )

    payload = {
        "kind": "ghost_review_complete",
        "completed_at": _iso(now),
        "n_offers_reviewed": len(decisions),
        "accepts": accepts,
        "rejects": rejects,
        "other": others,
        "decided_offer_count": decided_offer_count,
        "notes": notes or "",
    }

    header = (
        f"\n## Ghost review — {_iso(now)}\n"
        f"- offers reviewed: {len(decisions)}\n"
        f"- accept/reject/other: {accepts}/{rejects}/{others}\n"
    )
    if notes:
        header += f"- notes: {notes}\n"
    if decisions:
        header += "- decisions:\n"
        for d in decisions:
            oid = d.get("offer_id", "?")
            resp = d.get("user_response", "?")
            r = d.get("reason")
            tail = f" ({r})" if r else ""
            header += f"  - {oid}: {resp}{tail}\n"

    marker = (
        _REVIEW_MARKER_PREFIX
        + json.dumps(payload, sort_keys=True)
        + _REVIEW_MARKER_SUFFIX
        + "\n"
    )
    with p.open("a", encoding="utf-8") as f:
        f.write(header)
        f.write(marker)
    return payload


def find_recent_ghost_reviews(
    log_path: Path, *, now: datetime, window_days: int = GHOST_REVIEW_LOOKBACK_DAYS
) -> List[Dict[str, Any]]:
    """Return ghost-review marker payloads completed within ``window_days``."""
    p = Path(log_path)
    if not p.exists():
        return []
    cutoff = now - timedelta(days=window_days)
    out: List[Dict[str, Any]] = []
    pattern = re.compile(
        re.escape(_REVIEW_MARKER_PREFIX) + r"(\{.*?\})" + re.escape(_REVIEW_MARKER_SUFFIX)
    )
    for m in pattern.finditer(p.read_text(encoding="utf-8")):
        try:
            payload = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        ts = _parse_iso(payload.get("completed_at", ""))
        if ts is None or ts < cutoff:
            continue
        out.append(payload)
    return out


# ---------------------------------------------------------------------------
# State computation
# ---------------------------------------------------------------------------

def compute_ghost_state(
    *,
    install_date: date,
    now: datetime,
    manual_yaml_path: Path,
    ghost_review_log_path: Path,
    post_review_pause_path: Optional[Path] = None,
) -> GhostState:
    """Return the canonical GhostState. §7 of design doc.

    Precedence (first match wins):
      1. Install window: now < install_date + 7 days.
      2. Manual: ``ghost-mode.yaml`` exists with ``active: true``. Honors
         optional ``until: YYYY-MM-DD``.
      3. Post-review pause: marker file ``post-review-pause.yaml`` exists
         (Sprint 7 will populate this; Sprint 6 only honors it as a flag).
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    install_dt = _date_to_dt(install_date)
    window_end = install_dt + timedelta(days=GHOST_INSTALL_WINDOW_DAYS)

    review_payloads = find_recent_ghost_reviews(
        Path(ghost_review_log_path), now=now, window_days=GHOST_REVIEW_LOOKBACK_DAYS
    )
    last_review_ts: Optional[datetime] = None
    if review_payloads:
        candidates = [
            _parse_iso(p.get("completed_at", "")) for p in review_payloads
        ]
        candidates = [c for c in candidates if c is not None]
        if candidates:
            last_review_ts = max(candidates)

    # 1. Install window
    if now < window_end:
        return GhostState(
            active=True,
            reason="install_window",
            started_at=install_dt,
            expected_end=window_end,
            review_completed_at=last_review_ts,
        )

    # 2. Manual ghost-mode.yaml
    manual = _read_yaml(Path(manual_yaml_path))
    if manual.get("active") is True:
        until = _coerce_date(manual.get("until"))
        expected_end: Optional[datetime] = None
        if until is not None:
            # active through end of `until` day → expected_end is start of next day
            expected_end = _date_to_dt(until + timedelta(days=1))
            if now >= expected_end:
                # expired; fall through to next gate
                pass
            else:
                return GhostState(
                    active=True,
                    reason="manual",
                    started_at=now,
                    expected_end=expected_end,
                    review_completed_at=last_review_ts,
                )
        else:
            # open-ended manual ghost
            return GhostState(
                active=True,
                reason="manual",
                started_at=now,
                expected_end=None,
                review_completed_at=last_review_ts,
            )

    # 3. Post-review pause marker
    if post_review_pause_path is not None and Path(post_review_pause_path).exists():
        prp = _read_yaml(Path(post_review_pause_path))
        if prp.get("active", True):
            until = _coerce_date(prp.get("until"))
            expected_end = (
                _date_to_dt(until + timedelta(days=1)) if until else None
            )
            if expected_end is None or now < expected_end:
                return GhostState(
                    active=True,
                    reason="post_review_pause",
                    started_at=now,
                    expected_end=expected_end,
                    review_completed_at=last_review_ts,
                )

    # Inactive
    return GhostState(
        active=False,
        reason="",
        started_at=install_dt,
        expected_end=None,
        review_completed_at=last_review_ts,
    )


# ---------------------------------------------------------------------------
# Sprint 7 H4 — Ghost-exit readiness predicates
# ---------------------------------------------------------------------------


def check_ghost_exit_ready(
    *,
    install_date: date,
    now: datetime,
    manual_yaml_path: Path,
    ghost_review_log_path: Path,
    post_review_pause_path: Optional[Path] = None,
    install_yaml_path: Optional[Path] = None,
    response_events_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Sprint 7 H4 — multi-predicate ghost-exit readiness.

    Returns a dict with a per-predicate breakdown plus an overall
    ``ready: bool``. Predicates that must all pass:

      P1: install window has elapsed (now ≥ install_date + 7 days).
      P2: ghost-mode.yaml is not active (no manual hold).
      P3: post-review-pause is not active (no policy-hash hold).
      P4: ≥3 distinct calendar days carry ghost-review markers in the
          last 7 days.
      P5: ≥5 total decided offers (accepted/accepted_with_edits/rejected/
          never_again) across those reviews.
      P6: Sprint 7 O2 — if a prior ghost_exited_at is set on install.yaml
          AND ≥7 days have elapsed since that prior exit, the day-7
          acceptance rate (computed from response-events) must be ≥0.50.
          First exit (no prior ghost_exited_at) → P6 is N/A and passes.

    Caller is expected to render this dict for the operator. The flag
    ``ready`` is the AND of all predicates.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    install_dt = _date_to_dt(install_date)
    window_end = install_dt + timedelta(days=GHOST_INSTALL_WINDOW_DAYS)
    p1 = now >= window_end

    manual = _read_yaml(Path(manual_yaml_path))
    p2 = not (manual.get("active") is True)

    p3 = True
    if post_review_pause_path is not None and Path(post_review_pause_path).exists():
        prp = _read_yaml(Path(post_review_pause_path))
        if prp.get("active", True):
            until = _coerce_date(prp.get("until"))
            if until is None:
                p3 = False
            else:
                end = _date_to_dt(until + timedelta(days=1))
                if now < end:
                    p3 = False

    reviews = find_recent_ghost_reviews(
        Path(ghost_review_log_path), now=now, window_days=GHOST_REVIEW_LOOKBACK_DAYS
    )
    distinct_days = set()
    decided_total = 0
    for r in reviews:
        ts = _parse_iso(r.get("completed_at", ""))
        if ts is None:
            continue
        distinct_days.add(ts.date())
        # Older markers may not carry decided_offset_count — fall back to
        # accepts+rejects as the closest legacy approximation.
        decided_total += int(
            r.get("decided_offer_count")
            if r.get("decided_offer_count") is not None
            else (r.get("accepts", 0) + r.get("rejects", 0))
        )
    p4 = len(distinct_days) >= 3
    p5 = decided_total >= 5

    # P6 — Sprint 7 O2 day-7 acceptance gate (only after a prior exit).
    p6 = True
    p6_reason = "n/a (first exit)"
    day7_rate: Optional[float] = None
    prior_exit: Optional[datetime] = None
    if install_yaml_path is not None and Path(install_yaml_path).exists():
        data = _read_yaml(Path(install_yaml_path))
        prior_exit = _parse_iso(data.get("ghost_exited_at", "") or "")
    if prior_exit is not None:
        if now < prior_exit + timedelta(days=7):
            # Still inside the evaluation grace period — gate is not yet
            # enforceable. Treat as N/A so re-exits during the live phase
            # remain idempotent.
            p6_reason = "live phase <7 days old; gate not yet enforceable"
        elif response_events_path is not None:
            from .metrics import day7_acceptance_rate
            from .io_jsonl import read_jsonl as _read_jsonl
            from .schemas import Offer as _Offer
            offers_path = Path(install_yaml_path).parent / "offers.jsonl"
            try:
                offers = [_Offer.from_dict(r) for r in _read_jsonl(offers_path)]
            except Exception:
                offers = []
            day7_rate = day7_acceptance_rate(
                Path(response_events_path),
                offers,
                live_start=prior_exit,
                now=now,
            )
            if day7_rate is None:
                p6_reason = "insufficient day-7 data"
                p6 = False
            elif day7_rate < 0.50:
                p6_reason = f"day-7 acceptance {day7_rate:.2f} < 0.50"
                p6 = False
            else:
                p6_reason = f"day-7 acceptance {day7_rate:.2f} ≥ 0.50"

    return {
        "ready": all([p1, p2, p3, p4, p5, p6]),
        "predicates": {
            "P1_install_window_elapsed": p1,
            "P2_no_manual_ghost": p2,
            "P3_no_post_review_pause": p3,
            "P4_distinct_review_days_ge_3": p4,
            "P5_decided_offers_ge_5": p5,
            "P6_day7_acceptance_ok": p6,
        },
        "details": {
            "now": _iso(now),
            "install_window_end": _iso(window_end),
            "distinct_review_days": sorted(d.isoformat() for d in distinct_days),
            "decided_offer_count": decided_total,
            "prior_exit_at": _iso(prior_exit) if prior_exit else None,
            "day7_acceptance_rate": day7_rate,
            "p6_reason": p6_reason,
        },
    }


__all__ = [
    "GHOST_INSTALL_WINDOW_DAYS",
    "GHOST_REVIEW_LOOKBACK_DAYS",
    "GHOST_REASONS",
    "GhostState",
    "compute_ghost_state",
    "read_install_date",
    "write_install_field",
    "mark_ghost_review_complete",
    "find_recent_ghost_reviews",
    "check_ghost_exit_ready",
]
