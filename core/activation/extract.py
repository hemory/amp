"""Stage 2 — Extract candidates. §4.2 of design doc.

The LLM is executed by the agent, not by Python. Sprint 3 ships a two-step
handshake; Sprint 7 (C1) persists a snapshot artifact under
``System/activation/handshakes/`` so apply-time validation runs against the
frozen world the prompt was built from, not against live ``signals.jsonl``.

Sprint 7 (C2) also adds the online grounding gate: even with valid
citations, candidate.summary must overlap meaningfully with the cited
excerpts.
"""

from __future__ import annotations

from dataclasses import fields as dc_fields
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .grounding import check_grounding, thresholds_for
from .schemas import ACTION_VERBS, OFFER_TYPES, Candidate, SchemaError, Signal


# Closed set of Candidate top-level keys (excluding lineage fields the LLM
# never sees). Anything else in the LLM response is treated as a
# hallucination / prompt-injection and rejected.
_LLM_CANDIDATE_KEYS = frozenset(
    {
        "candidate_id",
        "type",
        "summary",
        "cited_signals",
        "confidence",
        "staleness_days",
        "action_verb",
    }
)


_SYSTEM_PROMPT = (
    "You are Amp's activation extractor. Your job is to read a bounded batch "
    "of raw vault signals and propose a small set of candidate offers that "
    "the user could act on. Every candidate must be grounded in the cited "
    "signals — if you cannot cite, you must not propose. Never invent facts, "
    "names, dates, or commitments that are not explicitly present in the "
    "cited signals. Output valid JSON only; no prose, no markdown, no "
    "commentary. Be conservative: it is better to return zero candidates "
    "than to fabricate."
)


def _user_prompt(signals: List[Signal], batch_id: str) -> str:
    """Build the user-side prompt describing the batch and output contract."""
    lines: List[str] = []
    lines.append(f"Batch: {batch_id}")
    lines.append(f"Signals in this batch: {len(signals)}")
    lines.append("")
    lines.append("Allowed offer types (closed enum):")
    lines.append("  " + ", ".join(OFFER_TYPES))
    lines.append("Allowed action verbs (closed enum):")
    lines.append("  " + ", ".join(ACTION_VERBS))
    lines.append("")
    lines.append("Output contract:")
    lines.append(
        "  Return a JSON array (top-level) of candidate objects. Each "
        "candidate MUST match the provided schema exactly and include only "
        "the listed keys. No extra keys."
    )
    lines.append("  Every candidate MUST include at least one signal_id from")
    lines.append("  this batch in its 'cited_signals' list. A candidate with")
    lines.append("  zero citations MUST NOT be emitted.")
    lines.append("  Do not invent signal_ids. Do not invent dates. Do not")
    lines.append("  paraphrase a signal into a commitment it does not state.")
    lines.append("  If no candidates are warranted, return [].")
    lines.append("")
    lines.append("Signals:")
    for s in signals:
        excerpt = s.excerpt.replace("\n", " ").strip()
        if len(excerpt) > 500:
            excerpt = excerpt[:497] + "..."
        lines.append(
            f"  - signal_id={s.signal_id} source={s.source} "
            f"timestamp={s.timestamp} path={s.path}"
        )
        lines.append(f"    excerpt: {excerpt}")
    return "\n".join(lines)


def _candidate_schema_hint() -> Dict[str, Any]:
    """Minimal JSON-Schema-ish description for the LLM's output contract."""
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "candidate_id",
                "type",
                "summary",
                "cited_signals",
                "confidence",
                "staleness_days",
                "action_verb",
            ],
            "properties": {
                "candidate_id": {"type": "string"},
                "type": {"type": "string", "enum": list(OFFER_TYPES)},
                "summary": {"type": "string"},
                "cited_signals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "staleness_days": {"type": "integer", "minimum": 0},
                "action_verb": {"type": "string", "enum": list(ACTION_VERBS)},
            },
        },
    }


def batch_signals(signals: List[Signal], max_size: int = 50) -> List[List[Signal]]:
    """Stable grouping of signals into batches of size ≤ max_size.

    Ordering is by ``signal_id`` ascending so the same input produces the
    same batches across runs.
    """
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    ordered = sorted(signals, key=lambda s: s.signal_id)
    return [ordered[i : i + max_size] for i in range(0, len(ordered), max_size)]


def make_batch_id(day: date, n: int) -> str:
    """Format a batch id as ``batch-YYYYMMDD-nn`` (nn zero-padded, ≥2)."""
    return f"batch-{day.strftime('%Y%m%d')}-{n:02d}"


def build_extract_prompt(
    signals: List[Signal],
    batch_id: str,
) -> Dict[str, Any]:
    """Return the handshake dict the CLI prints to stdout.

    The caller (agent/skill) is responsible for invoking the LLM with
    ``system_prompt`` + ``user_prompt`` and capturing a JSON response.

    The returned dict contains the raw signal rows so that the response can
    be re-validated later without re-reading state.
    """
    return {
        "batch_id": batch_id,
        "system_prompt": _SYSTEM_PROMPT,
        "user_prompt": _user_prompt(signals, batch_id),
        "signals": [s.to_dict() for s in signals],
        "schema": _candidate_schema_hint(),
    }


def _reject(
    rejected: List[Dict[str, Any]],
    raw: Any,
    reason: str,
    detail: Optional[str] = None,
) -> None:
    row: Dict[str, Any] = {"reason": reason, "raw": raw}
    if detail:
        row["detail"] = detail
    rejected.append(row)


def apply_extract_response(
    response: List[Dict[str, Any]],
    batch: List[Signal],
    batch_id: str,
    *,
    run_id: Optional[str] = None,
    now: Optional[datetime] = None,
    grounding_yaml_path: Optional[Any] = None,
    enable_grounding_gate: bool = True,
) -> Tuple[List[Candidate], List[Dict[str, Any]]]:
    """Validate an LLM response. Returns ``(accepted, rejected)``.

    Validation order per candidate:
      1. Must be a mapping.
      2. No extra/unknown keys (hallucination canary).
      3. Must have ``cited_signals`` non-empty.
      4. Every cited signal_id must exist in this batch.
      5. Candidate.from_dict — schema valid.
      6. Online grounding gate (Sprint 7 C2): summary tokens must overlap
         with cited excerpts.

    Sprint 7 (C3): every accepted Candidate is stamped with ``run_id``,
    ``batch_id``, ``created_at`` (defaulted from inputs).
    """
    if not isinstance(response, list):
        return [], [
            {
                "reason": "response_not_list",
                "detail": f"expected list at top level, got {type(response).__name__}",
                "raw": response,
            }
        ]

    batch_ids = {s.signal_id for s in batch}
    excerpt_by_id = {s.signal_id: s.excerpt for s in batch}
    accepted: List[Candidate] = []
    rejected: List[Dict[str, Any]] = []

    if now is None:
        now = datetime.now(timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    run_id = run_id or f"run-{batch_id}"

    min_overlap, min_anchored = thresholds_for("extract", grounding_yaml_path)

    for idx, raw in enumerate(response):
        if not isinstance(raw, dict):
            _reject(
                rejected,
                raw,
                "not_a_mapping",
                f"item[{idx}] expected object, got {type(raw).__name__}",
            )
            continue

        extras = set(raw.keys()) - _LLM_CANDIDATE_KEYS
        if extras:
            _reject(
                rejected,
                raw,
                "unknown_field",
                f"unexpected keys: {sorted(extras)}",
            )
            continue

        cited = raw.get("cited_signals")
        if not isinstance(cited, list) or len(cited) == 0:
            _reject(
                rejected,
                raw,
                "missing_cited_signals",
                "cited_signals must be a non-empty list",
            )
            continue

        bad = [c for c in cited if not isinstance(c, str) or c not in batch_ids]
        if bad:
            _reject(
                rejected,
                raw,
                "hallucinated_signal_id",
                f"cited_signals not in batch {batch_id}: {bad}",
            )
            continue

        try:
            cand = Candidate.from_dict(raw)
        except SchemaError as e:
            _reject(rejected, raw, "schema_error", str(e))
            continue

        if cand.type not in OFFER_TYPES:
            _reject(rejected, raw, "bad_offer_type", f"type={cand.type!r}")
            continue
        if cand.action_verb not in ACTION_VERBS:
            _reject(rejected, raw, "bad_action_verb", f"action_verb={cand.action_verb!r}")
            continue

        # Sprint 7 C2: online grounding gate.
        if enable_grounding_gate:
            cited_excerpts = [excerpt_by_id.get(sid, "") for sid in cand.cited_signals]
            gr = check_grounding(
                cand.summary,
                cited_excerpts,
                min_overlap=min_overlap,
                min_anchored_tokens=min_anchored,
            )
            if not gr.passed:
                _reject(
                    rejected,
                    raw,
                    "ungrounded",
                    (
                        f"grounding overlap_ratio={gr.overlap_ratio:.3f} "
                        f"anchored={gr.anchored_tokens}/{gr.total_tokens} "
                        f"unanchored={gr.unanchored_tokens[:8]}"
                    ),
                )
                continue

        # Sprint 7 C3: stamp lineage on accepted candidates.
        cand.run_id = run_id
        cand.batch_id = batch_id
        cand.created_at = created_at
        accepted.append(cand)

    return accepted, rejected


__all__ = [
    "build_extract_prompt",
    "apply_extract_response",
    "batch_signals",
    "make_batch_id",
]
