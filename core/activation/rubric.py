"""Deterministic rubric for scoring activation offers (Sprint 5).

Per design doc §9 (testing & validation plan) and §10 locked decision #4
("the user grades first 30 offers, Amp self-applies rubric after calibration"),
this module is the *reference-based* quality scoring function. It ships no
network calls, no LLM, no learned weights. Every score is a pure function of
the offer, its cited signals, its (optional) draft, and its (optional) human
grade.

Six dimensions (all 0..1):

    grounding            — every substantive token in summary + draft_text
                           must appear in some cited signal excerpt.
    specificity          — presence of a concrete action verb + a concrete
                           noun (proper name or date-shape token).
    staleness            — max(0, 1 - staleness_days / 14). 0 at ≥14.
    novelty              — 0 if a recent offer shares ≥50% of cited_signals
                           AND the same offer_type; else 1.
    length_discipline    — 1 if within the per-type cap (§4.4 of draft.py);
                           otherwise 1 - overage_ratio, clamped to [0,1].
    citation_discipline  — 1 if cited_signals non-empty AND every citation
                           resolves to a signal in the provided universe;
                           else 0.

    overall              — equal-weighted arithmetic mean of the six. v1
                           weights are deliberately uniform so the
                           calibration phase can surface which dimensions
                           the user actually cares about.

All helpers are intentionally simple and stdlib-only. This is the
calibration instrument; being legible matters more than being clever.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from .draft import LENGTH_CAPS_WORDS, _DEFAULT_CAP_WORDS  # type: ignore[attr-defined]
from .schemas import ACTION_VERBS, Candidate, Draft, Grade, Offer, Signal


_NOVELTY_WINDOW_DAYS = 7
_NOVELTY_OVERLAP_THRESHOLD = 0.5
_STALENESS_HORIZON_DAYS = 14

_DIMENSIONS: Sequence[str] = (
    "grounding",
    "specificity",
    "staleness",
    "novelty",
    "length_discipline",
    "citation_discipline",
)


# --------------------------------------------------------------------------
# Dataclasses
# --------------------------------------------------------------------------


@dataclass
class RubricScore:
    offer_id: str
    grounding: float
    specificity: float
    staleness: float
    novelty: float
    length_discipline: float
    citation_discipline: float
    overall: float
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FixtureScorecard:
    fixture_id: str
    scores: List[RubricScore]
    means: Dict[str, float]
    n_offers: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "n_offers": self.n_offers,
            "means": dict(self.means),
            "scores": [s.to_dict() for s in self.scores],
        }


@dataclass
class RubricCalibration:
    """Pearson correlation between rubric.overall and human.human_score.

    ``r`` is None when fewer than two overlapping grades exist or when either
    series has zero variance (undefined correlation).
    """

    n: int
    pearson_r: Optional[float]
    paired: List[Dict[str, Any]]  # [{offer_id, rubric, human, delta}]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# Helpers — token extraction
# --------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]{1,}")
_DATE_SHAPED_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|"
    r"(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"today|tomorrow|yesterday|tonight|[0-9]{1,2}(?:am|pm))\b",
    re.IGNORECASE,
)


_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "for", "nor", "on", "at", "to",
        "from", "by", "with", "as", "of", "in", "is", "are", "was", "were",
        "be", "been", "being", "it", "its", "this", "that", "these", "those",
        "i", "me", "my", "mine", "you", "your", "yours", "he", "him", "his",
        "she", "her", "hers", "we", "us", "our", "ours", "they", "them",
        "their", "theirs", "do", "does", "did", "has", "have", "had", "will",
        "would", "can", "could", "should", "may", "might", "must", "shall",
        "not", "no", "yes", "so", "if", "then", "than", "when", "where",
        "what", "who", "whom", "which", "how", "why", "about", "some", "any",
        "all", "each", "every", "here", "there", "also", "just", "one",
        "two", "into", "over", "per", "up", "down", "off", "out",
    }
)


def _light_stem(t: str) -> str:
    """Very light suffix stripper for tolerant grounding comparison."""
    t = t.lower()
    for suf in ("ings", "ing", "ed", "es", "s", "'s"):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def _meaningful_tokens(text: str) -> List[str]:
    """Return a list of light-stemmed, stopworded tokens worth grounding."""
    if not text:
        return []
    out: List[str] = []
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        low = tok.lower()
        if low in _STOPWORDS:
            continue
        if len(low) < 3:
            continue
        out.append(_light_stem(tok))
    return out


def _corpus_tokens(signals: Sequence[Signal]) -> set[str]:
    bag: set[str] = set()
    for s in signals:
        for tok in _meaningful_tokens(s.excerpt or ""):
            bag.add(tok)
        # Also consider path basename — "D.Lin 1-1.md" is a legitimate anchor.
        for tok in _meaningful_tokens(s.path or ""):
            bag.add(tok)
    return bag


# --------------------------------------------------------------------------
# Per-dimension scoring
# --------------------------------------------------------------------------


def _score_grounding(
    offer: Offer, draft: Optional[Draft], cited_signals: Sequence[Signal]
) -> tuple[float, str]:
    claim_text = offer.summary or ""
    if draft and draft.draft_text:
        claim_text = claim_text + " " + draft.draft_text
    claim_toks = _meaningful_tokens(claim_text)
    if not claim_toks:
        return 1.0, "no_claim_tokens"
    corpus = _corpus_tokens(cited_signals)
    if not corpus:
        return 0.0, "no_cited_corpus"
    present = sum(1 for t in claim_toks if t in corpus)
    frac = present / len(claim_toks)
    return max(0.0, min(1.0, frac)), f"grounded={present}/{len(claim_toks)}"


_CAPITALIZED_RE = re.compile(r"\b[A-Z][A-Za-z0-9\.\-]{2,}\b")


def _score_specificity(offer: Offer, draft: Optional[Draft]) -> tuple[float, str]:
    text = offer.summary or ""
    if draft and draft.draft_text:
        text = text + " " + draft.draft_text
    lowered = text.lower()
    has_verb = any(v in lowered.split() or v in lowered for v in ACTION_VERBS)
    # Concrete noun: capitalized multi-char token (not sentence-start only) OR
    # a date-shaped token.
    has_proper = bool(_CAPITALIZED_RE.search(text.strip()[1:])) or bool(
        _DATE_SHAPED_RE.search(text)
    )
    if has_verb and has_proper:
        return 1.0, "verb+proper"
    if has_verb or has_proper:
        return 0.5, "verb_only" if has_verb else "proper_only"
    return 0.0, "neither"


def _score_staleness(candidate: Optional[Candidate]) -> tuple[float, str]:
    if candidate is None:
        return 0.0, "no_candidate"
    days = max(0, int(candidate.staleness_days))
    if days >= _STALENESS_HORIZON_DAYS:
        return 0.0, f"stale_{days}d"
    return 1.0 - (days / _STALENESS_HORIZON_DAYS), f"stale_{days}d"


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


def _score_novelty(
    offer: Offer, prior_offers: Sequence[Offer], now: datetime
) -> tuple[float, str]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=_NOVELTY_WINDOW_DAYS)
    cand_cited = set(offer.cited_signals)
    if not cand_cited:
        return 1.0, "no_cited_to_compare"
    for o in prior_offers:
        if o.offer_id == offer.offer_id:
            continue
        if o.type != offer.type:
            continue
        created = _parse_iso(o.created_at)
        if created is None or created < cutoff or created > now:
            continue
        other = set(o.cited_signals)
        if not other:
            continue
        overlap = len(cand_cited & other) / len(cand_cited)
        if overlap >= _NOVELTY_OVERLAP_THRESHOLD:
            return 0.0, f"overlaps_{o.offer_id}"
    return 1.0, "novel"


def _score_length(offer: Offer, draft: Optional[Draft]) -> tuple[float, str]:
    if draft is None or not draft.draft_text:
        return 1.0, "no_draft"
    cap = LENGTH_CAPS_WORDS.get(offer.type, _DEFAULT_CAP_WORDS)
    wc = len(draft.draft_text.split())
    if wc <= cap:
        return 1.0, f"within_cap_{wc}/{cap}"
    overage = (wc - cap) / cap
    return max(0.0, min(1.0, 1.0 - overage)), f"over_cap_{wc}/{cap}"


def _score_citation(
    offer: Offer, signal_universe_ids: set[str]
) -> tuple[float, str]:
    if not offer.cited_signals:
        return 0.0, "no_citations"
    bad = [c for c in offer.cited_signals if c not in signal_universe_ids]
    if bad:
        return 0.0, f"invalid_citations={bad}"
    return 1.0, "ok"


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def score_offer(
    offer: Offer,
    candidate: Optional[Candidate],
    cited_signals: Sequence[Signal],
    draft: Optional[Draft] = None,
    *,
    prior_offers: Sequence[Offer] = (),
    signal_universe_ids: Optional[set[str]] = None,
    now: Optional[datetime] = None,
    grade: Optional[Grade] = None,  # accepted for API symmetry; not used in score
) -> RubricScore:
    """Score a single offer on the six rubric dimensions. See module docstring."""
    if now is None:
        now = datetime.now(timezone.utc)
    if signal_universe_ids is None:
        signal_universe_ids = {s.signal_id for s in cited_signals}

    notes: List[str] = []
    g, n_g = _score_grounding(offer, draft, cited_signals)
    sp, n_sp = _score_specificity(offer, draft)
    st, n_st = _score_staleness(candidate)
    nv, n_nv = _score_novelty(offer, prior_offers, now)
    ld, n_ld = _score_length(offer, draft)
    cd, n_cd = _score_citation(offer, signal_universe_ids)
    notes.extend(
        [
            f"grounding={n_g}",
            f"specificity={n_sp}",
            f"staleness={n_st}",
            f"novelty={n_nv}",
            f"length={n_ld}",
            f"citation={n_cd}",
        ]
    )
    if grade is not None:
        notes.append(f"human_score={grade.human_score:.3f} grader={grade.grader}")

    values = (g, sp, st, nv, ld, cd)
    overall = sum(values) / len(values)

    return RubricScore(
        offer_id=offer.offer_id,
        grounding=round(g, 6),
        specificity=round(sp, 6),
        staleness=round(st, 6),
        novelty=round(nv, 6),
        length_discipline=round(ld, 6),
        citation_discipline=round(cd, 6),
        overall=round(overall, 6),
        notes=notes,
    )


def score_fixture(
    result: "ReplayResult",  # noqa: F821 — avoid circular import
    fixture: "Fixture",  # noqa: F821
) -> FixtureScorecard:
    """Score every offer in a ReplayResult. Aggregates per-dimension means."""
    scores: List[RubricScore] = []
    cand_by_id = {c.candidate_id: c for c in result.candidates}
    sig_by_id = {s.signal_id: s for s in fixture.signals}
    draft_by_offer = {d.offer_id: d for d in result.drafts}
    universe = set(sig_by_id)

    prior_offers = list(fixture.prior_offers) + list(result.offers)
    now = fixture.now()

    for offer in result.offers:
        cited = [sig_by_id[sid] for sid in offer.cited_signals if sid in sig_by_id]
        cand = cand_by_id.get(offer.candidate_id) if offer.candidate_id else None
        draft = draft_by_offer.get(offer.offer_id)
        s = score_offer(
            offer,
            cand,
            cited,
            draft,
            prior_offers=prior_offers,
            signal_universe_ids=universe,
            now=now,
        )
        scores.append(s)

    means: Dict[str, float] = {}
    if scores:
        for dim in _DIMENSIONS:
            means[dim] = round(
                sum(getattr(s, dim) for s in scores) / len(scores), 6
            )
        means["overall"] = round(
            sum(s.overall for s in scores) / len(scores), 6
        )
    else:
        for dim in _DIMENSIONS:
            means[dim] = 0.0
        means["overall"] = 0.0

    return FixtureScorecard(
        fixture_id=result.fixture_id,
        scores=scores,
        means=means,
        n_offers=len(scores),
    )


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0.0 or deny == 0.0:
        return None
    return num / (denx * deny)


def compare_with_grades(
    scorecard: FixtureScorecard, grades: Sequence[Grade]
) -> RubricCalibration:
    """Pair rubric.overall with human.human_score per offer_id; Pearson r."""
    grade_by_id = {g.offer_id: g for g in grades}
    paired: List[Dict[str, Any]] = []
    xs: List[float] = []
    ys: List[float] = []
    for s in scorecard.scores:
        g = grade_by_id.get(s.offer_id)
        if g is None:
            continue
        paired.append(
            {
                "offer_id": s.offer_id,
                "rubric": s.overall,
                "human": g.human_score,
                "delta": round(s.overall - g.human_score, 6),
                "grader": g.grader,
            }
        )
        xs.append(s.overall)
        ys.append(g.human_score)

    r = _pearson(xs, ys)
    return RubricCalibration(
        n=len(paired),
        pearson_r=(round(r, 6) if r is not None else None),
        paired=paired,
    )


__all__ = [
    "RubricScore",
    "FixtureScorecard",
    "RubricCalibration",
    "score_offer",
    "score_fixture",
    "compare_with_grades",
]
