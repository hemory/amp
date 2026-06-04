"""Stage 3 — Rank & budget. §4.3 of design doc.

Deterministic Python. No LLM. Pure function of inputs (candidates, offers log,
tombstones, weights, clock, acceptance rate, install age).

Scoring (per candidate):

    score = w1·confidence
          + w2·recency            # newest cited signal, in [0, 1]
          + w3·commitment_strength
          + w4·user_priority
          - w5·recent_offer_penalty
          - w6·rejection_penalty

Pipeline:
  1. Tombstone filter — drop any candidate matching an active tombstone.
  2. Score the survivors.
  3. Duplicate suppression — for identical (offer_type, primary entity) keep
     the higher-scored candidate (ties broken by candidate_id).
  4. Dynamic budget — pick top N. Ghost mode (install<7d or forced) sets N=0
     but still materializes Offer objects with ``status='ghost'``.
"""

from __future__ import annotations

import uuid
from dataclasses import fields as dc_fields
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .schemas import Candidate, Offer, Tombstone

# Forward-typed import to avoid circular surface coupling — ghost.py imports
# nothing from rank, so this is safe.
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .ghost import GhostState


# --- tunables (not user-facing; weights.yaml governs scoring weights) -------

RECENT_OFFER_WINDOW_DAYS = 7
REJECTION_WINDOW_DAYS = 14
RECENCY_HORIZON_DAYS = 14  # age (in days) at which recency boost decays to 0
TOMBSTONE_DEFAULT_TTL_DAYS = 3650  # effectively forever if not specified


_BUDGET_TIERS: Sequence[Tuple[float, int]] = (
    (0.60, 5),
    (0.40, 3),
    (0.20, 2),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp, tolerating the trailing 'Z'."""
    if not isinstance(ts, str) or not ts:
        return None
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _primary_entity(cand: Candidate) -> str:
    """Derive a stable 'primary entity' key for a candidate.

    The design doc refers to entity-level dedup but the Candidate schema does
    not carry a first-class entity field. We use the first cited_signal_id
    (cited_signals are stored in the order emitted) as a stable proxy.
    """
    return cand.cited_signals[0] if cand.cited_signals else cand.candidate_id


def _cited_timestamps(
    cand: Candidate, sig_index: Mapping[str, datetime]
) -> List[datetime]:
    return [sig_index[s] for s in cand.cited_signals if s in sig_index]


def _recency_score(newest: Optional[datetime], now: datetime) -> float:
    """Linear decay over ``RECENCY_HORIZON_DAYS``. Returns a value in [0, 1]."""
    if newest is None:
        return 0.0
    age_days = (now - newest).total_seconds() / 86400.0
    if age_days <= 0:
        return 1.0
    if age_days >= RECENCY_HORIZON_DAYS:
        return 0.0
    return 1.0 - (age_days / RECENCY_HORIZON_DAYS)


def _commitment_strength(cand: Candidate) -> float:
    """Cheap heuristic: meeting_followup / commitment_reminder / risk_flag
    read as 'external commitments' and score 1.0; others score 0.5.
    """
    strong = {"meeting_followup", "commitment_reminder", "risk_flag", "contradiction"}
    return 1.0 if cand.type in strong else 0.5


def _user_priority(cand: Candidate) -> float:
    """Type-based priority floor (Sprint 7 M1).

    Replaces the Sprint-1 placeholder that just echoed confidence (which made
    w4 redundant with w1). The new mapping is documented in weights.yaml:

      risk_flag             → 0.9
      meeting_followup      → 0.7
      commitment_reminder   → P-tier from summary marker:
                                "[P1]"/"P1:" → 1.0
                                "[P2]"/"P2:" → 0.6
                                "[P3]"/"P3:" → 0.3
                                else          → 0.5
      everything else       → 0.5
    """
    t = cand.type
    if t == "risk_flag":
        return 0.9
    if t == "meeting_followup":
        return 0.7
    if t == "commitment_reminder":
        s = (cand.summary or "")
        for marker, val in (
            ("[P1]", 1.0), ("P1:", 1.0), ("(P1)", 1.0),
            ("[P2]", 0.6), ("P2:", 0.6), ("(P2)", 0.6),
            ("[P3]", 0.3), ("P3:", 0.3), ("(P3)", 0.3),
        ):
            if marker in s:
                return val
        return 0.5
    return 0.5


def _pattern_overlap_ratio(a: Sequence[str], b: Sequence[str]) -> float:
    """Symmetric Jaccard on cited_signal sets — used by H1 hard suppression."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(len(sa), len(sb))


def _patterns_match(cand: Candidate, offer: Offer) -> bool:
    """Sprint 7 H1: same offer_type AND (≥50% cited overlap OR same primary entity).

    "Primary entity" maps to the first cited_signal in both records.
    """
    if cand.type != offer.type:
        return False
    if _pattern_overlap_ratio(cand.cited_signals, offer.cited_signals) >= 0.5:
        return True
    cand_primary = cand.cited_signals[0] if cand.cited_signals else None
    offer_primary = offer.cited_signals[0] if offer.cited_signals else None
    return bool(cand_primary and offer_primary and cand_primary == offer_primary)


def _hard_suppress(
    cand: Candidate,
    offers_log: List[Offer],
    now: datetime,
    *,
    rejection_suppress_days: int,
) -> Optional[str]:
    """Sprint 7 H1: drop candidates matching ever-accepted or recently-rejected
    patterns. Returns a reason string when suppressed, else None.
    """
    cutoff = now - timedelta(days=rejection_suppress_days)
    for o in offers_log:
        if not _patterns_match(cand, o):
            continue
        resp = o.user_response
        if resp in ("accepted", "accepted_with_edits"):
            return f"already_accepted:{o.offer_id}"
        if resp == "never_again":
            # never_again is permanent — also covered by Tombstone but we
            # belt-and-brace it here so the suppression layer alone is enough.
            return f"never_again:{o.offer_id}"
        if resp == "rejected":
            created = _parse_ts(o.created_at)
            if created is None:
                continue
            if created >= cutoff:
                return f"recently_rejected:{o.offer_id}"
    return None


def _tombstone_active(t: Dict[str, Any], now: datetime) -> bool:
    """A tombstone is active unless its TTL has elapsed."""
    ts = _parse_ts(t.get("created_at", ""))
    if ts is None:
        return True  # unknown creation → assume active (safer)
    ttl_days = t.get("ttl_days", TOMBSTONE_DEFAULT_TTL_DAYS)
    try:
        ttl_days = int(ttl_days)
    except (TypeError, ValueError):
        ttl_days = TOMBSTONE_DEFAULT_TTL_DAYS
    return now <= ts + timedelta(days=ttl_days)


def _tombstone_matches(cand: Candidate, t: Dict[str, Any]) -> bool:
    """Tombstone matches if same type AND pattern is in cited_signals or
    appears (case-insensitive substring) in the summary.
    """
    if t.get("type") != cand.type:
        return False
    pattern = t.get("pattern") or ""
    if not pattern:
        return False
    if pattern in cand.cited_signals:
        return True
    return pattern.lower() in cand.summary.lower()


def _filter_tombstones(
    candidates: List[Candidate],
    tombstones: List[Tombstone],
    now: datetime,
) -> List[Candidate]:
    active: List[Dict[str, Any]] = []
    for t in tombstones:
        d = t.to_dict() if isinstance(t, Tombstone) else dict(t)
        if _tombstone_active(d, now):
            active.append(d)
    if not active:
        return list(candidates)
    return [c for c in candidates if not any(_tombstone_matches(c, t) for t in active)]


def _recent_offer_penalty(
    cand: Candidate, offers_log: List[Offer], now: datetime
) -> float:
    """1.0 if a similar offer was surfaced in the last 7 days.

    "Similar" = same offer_type AND at least one shared cited_signal. The
    design doc also mentions 'same person/project entity'; we operationalize
    entity-overlap as 'shared cited signals' because signals map one-to-one
    to vault files (a stable surrogate for project/person pages).
    """
    cutoff = now - timedelta(days=RECENT_OFFER_WINDOW_DAYS)
    cand_cited = set(cand.cited_signals)
    for o in offers_log:
        if o.type != cand.type:
            continue
        if not o.shown:
            continue
        created = _parse_ts(o.created_at)
        if created is None or created < cutoff:
            continue
        if cand_cited & set(o.cited_signals):
            return 1.0
    return 0.0


def _rejection_penalty(
    cand: Candidate, offers_log: List[Offer], now: datetime
) -> float:
    """1.0 if a past offer with the same entity + offer_type was rejected in
    the last 14 days. Tombstones drop candidates outright earlier, so this
    term catches the softer 'rejected but not tombstoned' history.
    """
    cutoff = now - timedelta(days=REJECTION_WINDOW_DAYS)
    cand_cited = set(cand.cited_signals)
    for o in offers_log:
        if o.type != cand.type:
            continue
        if o.user_response != "rejected":
            continue
        created = _parse_ts(o.created_at)
        if created is None or created < cutoff:
            continue
        if cand_cited & set(o.cited_signals):
            return 1.0
    return 0.0


def _budget_from_acceptance(rate: Optional[float]) -> int:
    if rate is None:
        return 1
    for threshold, n in _BUDGET_TIERS:
        if rate >= threshold:
            return n
    return 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def rank(
    candidates: List[Candidate],
    *,
    now: datetime,
    offers_log: List[Offer],
    tombstones: List[Tombstone],
    weights: Dict[str, float],
    recent_acceptance_rate: Optional[float],
    days_since_install: int,
    ghost_override: bool = False,
    run_id: Optional[str] = None,
    ritual: str = "daily-plan",
    signal_index: Optional[Dict[str, str]] = None,
    ghost_state: Optional["GhostState"] = None,
    enable_hard_suppression: bool = True,
    rejection_suppress_days: int = 14,
    throttle_cap: Optional[int] = None,
    throttle_reason: Optional[str] = None,
) -> List[Offer]:
    """Score candidates and produce Offer rows.

    Sprint 7 additions:
      * H1 hard suppression — candidates whose pattern matches an
        ever-accepted offer or a rejected offer inside ``rejection_suppress_days``
        are dropped before scoring (suppressed_offers are NOT emitted; the
        decision is recorded only in the run summary).
      * O1 throttle — when ``throttle_cap`` is supplied (computed from
        response-events upstream), the budget is capped to that value and
        ``throttle_reason`` becomes the offer's hold_reason for the
        throttled tail. ``throttle_cap=0`` means produce only ghost'd offers.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    sig_index: Dict[str, datetime] = {}
    if signal_index:
        for sid, ts in signal_index.items():
            parsed = _parse_ts(ts)
            if parsed is not None:
                sig_index[sid] = parsed

    # 1. Tombstone filter
    survivors = _filter_tombstones(candidates, tombstones, now)

    # 1b. Sprint 7 H1 — hard suppression. Independent of tombstones because
    # acceptance/rejection state lives on the offer log, not in tombstones
    # (rejected no longer creates a tombstone after H2).
    if enable_hard_suppression:
        kept: List[Candidate] = []
        for cand in survivors:
            if _hard_suppress(
                cand, offers_log, now,
                rejection_suppress_days=rejection_suppress_days,
            ) is None:
                kept.append(cand)
        survivors = kept

    # 2. Score
    w1 = float(weights.get("w1_confidence", 1.0))
    w2 = float(weights.get("w2_recency", 0.6))
    w3 = float(weights.get("w3_commitment", 1.2))
    w4 = float(weights.get("w4_user_priority", 0.8))
    w5 = float(weights.get("w5_recent_offer_penalty", 0.5))
    w6 = float(weights.get("w6_rejection_penalty", 0.7))

    scored: List[Tuple[Candidate, float, Dict[str, float]]] = []
    for cand in survivors:
        ts_list = _cited_timestamps(cand, sig_index)
        newest = max(ts_list) if ts_list else None
        recency = _recency_score(newest, now)
        commitment = _commitment_strength(cand)
        priority = _user_priority(cand)
        recent_pen = _recent_offer_penalty(cand, offers_log, now)
        rej_pen = _rejection_penalty(cand, offers_log, now)

        score = (
            w1 * float(cand.confidence)
            + w2 * recency
            + w3 * commitment
            + w4 * priority
            - w5 * recent_pen
            - w6 * rej_pen
        )
        components = {
            "confidence": float(cand.confidence),
            "recency": recency,
            "commitment": commitment,
            "user_priority": priority,
            "recent_offer_penalty": recent_pen,
            "rejection_penalty": rej_pen,
        }
        scored.append((cand, score, components))

    # 3. Duplicate suppression by (offer_type, primary_entity)
    best_by_key: Dict[Tuple[str, str], Tuple[Candidate, float, Dict[str, float]]] = {}
    for cand, score, comp in scored:
        key = (cand.type, _primary_entity(cand))
        prev = best_by_key.get(key)
        if prev is None:
            best_by_key[key] = (cand, score, comp)
            continue
        prev_cand, prev_score, _prev_comp = prev
        if score > prev_score or (
            score == prev_score and cand.candidate_id < prev_cand.candidate_id
        ):
            best_by_key[key] = (cand, score, comp)

    deduped = list(best_by_key.values())
    # Stable sort: score desc, candidate_id asc for ties
    deduped.sort(key=lambda t: (-t[1], t[0].candidate_id))

    # 4. Budget
    if ghost_state is not None:
        ghost = ghost_state.active
        ghost_hold_reason = (
            f"ghost:{ghost_state.reason}" if ghost and ghost_state.reason else "ghost"
        )
    else:
        ghost = ghost_override or days_since_install < 7
        ghost_hold_reason = "ghost"
    budget = 0 if ghost else _budget_from_acceptance(recent_acceptance_rate)
    # Sprint 7 O1 — throttle cap (computed by CLI from response-events).
    throttled = False
    if not ghost and throttle_cap is not None and throttle_cap < budget:
        budget = max(0, int(throttle_cap))
        throttled = True

    now_iso = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    offers: List[Offer] = []
    for rank_idx, (cand, score, components) in enumerate(deduped):
        shown = (not ghost) and rank_idx < budget
        if ghost:
            hold_reason = ghost_hold_reason
        elif not shown:
            hold_reason = throttle_reason if throttled else "budget"
        else:
            hold_reason = None
        offers.append(
            Offer(
                offer_id=_mint_offer_id(run_id, rank_idx),
                created_at=now_iso,
                ritual=ritual,
                type=cand.type,
                shown=shown,
                summary=cand.summary,
                cited_signals=list(cand.cited_signals),
                score=round(score, 6),
                candidate_id=cand.candidate_id,
                hold_reason=hold_reason,
                score_components={k: round(v, 6) for k, v in components.items()},
                notes=f"run_id={run_id}",
            )
        )

    return offers


def _mint_offer_id(run_id: str, idx: int) -> str:
    return f"o-{run_id}-{idx:03d}"


__all__ = ["rank"]
