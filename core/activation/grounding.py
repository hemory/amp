"""Online grounding gate (Sprint 7, C2).

Citation ≠ grounding. The extract / draft handshake already enforces that
``cited_signals`` are real ids; this module enforces that the *content* of
the produced text is actually anchored in the cited excerpts.

Heuristic v1: deterministic, no LLM.

  1. Tokenize ``text`` into "claim tokens": proper nouns (capitalized
     multi-char), dates, numbers, action verbs, key nouns (≥4 chars,
     non-stopword).
  2. For each claim token, check if it appears (case-insensitive, light
     stem) in any cited excerpt.
  3. ``overlap_ratio = anchored / total``.
  4. Pass requires ``overlap_ratio >= min_overlap`` AND
     ``anchored >= min_anchored_tokens``.

Per-stage thresholds live in ``System/activation/grounding.yaml`` (tracked,
this is policy not state).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from .schemas import GroundingResult


_DEFAULTS: Dict[str, Dict[str, float]] = {
    "extract": {"min_overlap": 0.4, "min_anchored_tokens": 2},
    "draft": {"min_overlap": 0.4, "min_anchored_tokens": 3},
}


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]{1,}")
_NUMBER_RE = re.compile(r"\b\d{2,}\b")
_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|"
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?|"
    r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
    r"today|tomorrow|yesterday|tonight|[0-9]{1,2}(?:am|pm))\b",
    re.IGNORECASE,
)
_ACTION_VERBS = ("draft", "send", "schedule", "review", "decide")
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
        "two", "into", "over", "per", "want", "need", "make", "take", "let",
        "get", "got", "see", "say", "way", "now", "yet", "use", "like",
    }
)


def _light_stem(t: str) -> str:
    t = t.lower()
    for suf in ("ings", "ing", "ed", "es", "s", "'s"):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def _claim_tokens(text: str) -> List[str]:
    """Extract claim tokens worth grounding from ``text``."""
    if not text:
        return []
    out: List[str] = []
    seen: set = set()

    def add(tok: str) -> None:
        s = _light_stem(tok)
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    # Dates / day names — keep verbatim (lowercased) as their own anchor.
    for m in _DATE_RE.finditer(text):
        add(m.group(0))

    # Numbers (≥2 digits): treat as their own claim token.
    for m in _NUMBER_RE.finditer(text):
        add(m.group(0))

    # Words.
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        low = tok.lower()
        if low in _STOPWORDS:
            continue
        # Action verb (always a claim) OR proper noun OR ≥4-char noun.
        is_proper = tok[0].isupper() and len(tok) >= 3
        is_long = len(low) >= 4
        is_verb = low in _ACTION_VERBS
        if is_proper or is_long or is_verb:
            add(tok)
    return out


def _corpus(excerpts: Sequence[str]) -> set:
    """Build a stem-set covering all tokens in every cited excerpt."""
    bag: set = set()
    for ex in excerpts:
        if not ex:
            continue
        # Lowercased substring of the whole excerpt — used for date matches.
        whole = ex.lower()
        # Pre-cache full text so we can do substring fallback for dates.
        for m in _TOKEN_RE.finditer(ex):
            bag.add(_light_stem(m.group(0)))
        for m in _NUMBER_RE.finditer(ex):
            bag.add(_light_stem(m.group(0)))
        for m in _DATE_RE.finditer(ex):
            bag.add(_light_stem(m.group(0)))
        bag.add(("__corpus__", whole))  # sentinel, used by _present
    return bag


def _present(token: str, corpus: set) -> bool:
    if token in corpus:
        return True
    # Date/number tokens may appear differently formatted in the excerpt;
    # fall back to substring match against the original lowercased corpus.
    for entry in corpus:
        if isinstance(entry, tuple) and entry and entry[0] == "__corpus__":
            if token in entry[1]:
                return True
    return False


def load_thresholds(path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
    """Read per-stage thresholds from grounding.yaml. Falls back to defaults."""
    if path is None or not Path(path).exists():
        return {k: dict(v) for k, v in _DEFAULTS.items()}
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {k: dict(v) for k, v in _DEFAULTS.items()}
    out: Dict[str, Dict[str, float]] = {}
    for stage, defaults in _DEFAULTS.items():
        merged = dict(defaults)
        if isinstance(data.get(stage), dict):
            for k, v in data[stage].items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    merged[k] = float(v) if k == "min_overlap" else int(v)
        out[stage] = merged
    return out


def check_grounding(
    text: str,
    cited_excerpts: Iterable[str],
    *,
    min_overlap: float = 0.4,
    min_anchored_tokens: int = 2,
) -> GroundingResult:
    """Return a GroundingResult assessing whether ``text`` is anchored."""
    excerpts = [e for e in cited_excerpts if e]
    tokens = _claim_tokens(text or "")
    if not tokens:
        # Degenerate — no claims means nothing to ground; treat as pass.
        return GroundingResult(
            passed=True,
            overlap_ratio=1.0,
            anchored_tokens=0,
            total_tokens=0,
            unanchored_tokens=[],
            reason="no_claim_tokens",
        )
    if not excerpts:
        return GroundingResult(
            passed=False,
            overlap_ratio=0.0,
            anchored_tokens=0,
            total_tokens=len(tokens),
            unanchored_tokens=tokens,
            reason="no_cited_excerpts",
        )
    corpus = _corpus(excerpts)
    anchored = 0
    unanchored: List[str] = []
    for t in tokens:
        if _present(t, corpus):
            anchored += 1
        else:
            unanchored.append(t)
    ratio = anchored / len(tokens)
    passed = ratio >= min_overlap and anchored >= min_anchored_tokens
    reason = None if passed else (
        f"overlap_ratio={ratio:.3f}<{min_overlap} or "
        f"anchored={anchored}<{min_anchored_tokens}"
    )
    return GroundingResult(
        passed=passed,
        overlap_ratio=round(ratio, 6),
        anchored_tokens=anchored,
        total_tokens=len(tokens),
        unanchored_tokens=unanchored,
        reason=reason,
    )


def thresholds_for(stage: str, path: Optional[Path] = None) -> Tuple[float, int]:
    """Convenience: return (min_overlap, min_anchored_tokens) for stage."""
    cfg = load_thresholds(path)
    s = cfg.get(stage, _DEFAULTS.get(stage, {"min_overlap": 0.4, "min_anchored_tokens": 2}))
    return float(s["min_overlap"]), int(s["min_anchored_tokens"])


__all__ = ["check_grounding", "load_thresholds", "thresholds_for"]
