"""Stage 4 — Draft offers. §4.4 of design doc.

Mirrors the Sprint 3 extract handshake: Python never calls the LLM. The CLI
emits a handshake dict (`build_draft_prompt`), the agent runs the LLM, and
`apply_draft_response` validates the response and writes the artifact.

Voice is loaded from `System/identity/` (amp/SOUL.md, amp/STYLE.md,
user/SOUL.md, user/STYLE.md, README.md). Missing files degrade to empty
strings with a stderr warning rather than crashing — activation must survive
an incomplete identity vault.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .schemas import Candidate, Draft, Offer, SchemaError, Signal


# Per-offer-type length caps (in words). Meeting recaps and drafts get more
# room; everything else stays tight to respect §4.4's "concrete artifact,
# not a meta-suggestion" rule.
LENGTH_CAPS_WORDS: Dict[str, int] = {
    "meeting_followup": 150,
    "draft_request": 300,
    "commitment_reminder": 100,
    "risk_flag": 100,
    "person_reconnect": 100,
    "prep_draft": 100,
    "contradiction": 100,
}
_DEFAULT_CAP_WORDS = 100


# Closed set of top-level keys the LLM may emit. Anything else is treated
# as prompt-injection / hallucination and rejected.
_RESPONSE_KEYS: frozenset = frozenset({"draft_text", "citations", "confidence", "warnings"})


# Light sanitization: forbid shell-escape / control characters that would
# let an LLM response smuggle a command through a pasted draft. We do not
# attempt heavyweight HTML/markdown sanitization — drafts are markdown, that
# is the point.
_FORBIDDEN_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# --------------------------------------------------------------------------
# Identity loader
# --------------------------------------------------------------------------


_IDENTITY_FILES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("amp_soul", ("System", "identity", "amp", "SOUL.md")),
    ("amp_style", ("System", "identity", "amp", "STYLE.md")),
    ("user_soul", ("System", "identity", "user", "SOUL.md")),
    ("user_style", ("System", "identity", "user", "STYLE.md")),
    ("overview", ("System", "identity", "README.md")),
)


def load_identity(vault_root: Path) -> Dict[str, str]:
    """Read the identity bundle. Missing files → '' + stderr warning."""
    vault_root = Path(vault_root)
    out: Dict[str, str] = {}
    for key, parts in _IDENTITY_FILES:
        p = vault_root.joinpath(*parts)
        if not p.exists():
            print(
                f"warn: identity file not found: {p} (continuing with empty {key})",
                file=sys.stderr,
            )
            out[key] = ""
            continue
        try:
            out[key] = p.read_text(encoding="utf-8")
        except OSError as e:
            print(f"warn: failed to read {p}: {e}", file=sys.stderr)
            out[key] = ""
    return out


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------


_SYSTEM_PROMPT_TEMPLATE = """You are Amp, drafting a short artifact for the user. Your voice is \
established by the identity bundle below. Read it, then draft the artifact \
described in the user prompt.

HARD RULES (violations must be treated as a failed draft):
1. Cite only signals listed in `cited_signals`. Never invent a signal id, \
a meeting, a date, a quote, a commitment, or a fact that is not explicitly \
present in the cited signal excerpts.
2. Do not write in first person as the user unless a cited signal directly \
supplies the user's own words. Amp drafts for the user, not as the user.
3. Respect the length cap for this offer type. Going over is a rejection, \
not a stylistic choice.
4. Output a single JSON object matching the schema. No prose, no markdown \
fences, no commentary outside the JSON. If you cannot draft responsibly, \
return confidence=0.0 and an empty draft_text with warnings explaining why.

OUTPUT SCHEMA:
{{
  "draft_text": "<the artifact body>",
  "citations": ["<signal_id>", ...],  // subset of provided cited_signals
  "confidence": 0.0-1.0,
  "warnings": ["<human-readable warning>", ...]
}}

IDENTITY — Amp SOUL:
{amp_soul}

IDENTITY — Amp STYLE:
{amp_style}

IDENTITY — the user SOUL (read-only; informs tone, do not speak as the user):
{user_soul}

IDENTITY — the user STYLE (read-only; informs tone, do not speak as the user):
{user_style}

IDENTITY — Overview:
{overview}
"""


def _render_system_prompt(identity: Dict[str, str]) -> str:
    safe = {k: (identity.get(k) or "(not provided)") for k, _ in _IDENTITY_FILES}
    return _SYSTEM_PROMPT_TEMPLATE.format(**safe)


def _render_user_prompt(
    offer: Offer,
    candidate: Candidate,
    cited_signals: List[Signal],
    cap_words: int,
) -> str:
    lines: List[str] = []
    lines.append(f"Offer id: {offer.offer_id}")
    lines.append(f"Offer type: {offer.type}")
    lines.append(f"Action verb: {candidate.action_verb}")
    lines.append(f"Summary: {offer.summary}")
    lines.append(f"Ritual: {offer.ritual}")
    lines.append("")
    lines.append(f"Length cap: {cap_words} words. Exceeding this is a rejection.")
    lines.append("")
    lines.append("Cited signals (the ONLY facts you may use):")
    if not cited_signals:
        lines.append("  (no signals attached — you must return confidence=0.0)")
    for s in cited_signals:
        excerpt = s.excerpt.replace("\n", " ").strip()
        if len(excerpt) > 600:
            excerpt = excerpt[:597] + "..."
        lines.append(
            f"  - signal_id={s.signal_id} source={s.source} "
            f"timestamp={s.timestamp} path={s.path}"
        )
        lines.append(f"    excerpt: {excerpt}")
    lines.append("")
    lines.append(
        "Draft the artifact. Return a single JSON object per the schema. "
        "Cite at least one signal_id unless you are returning an empty draft."
    )
    return "\n".join(lines)


def _response_schema_hint() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["draft_text", "citations", "confidence", "warnings"],
        "properties": {
            "draft_text": {"type": "string"},
            "citations": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
    }


def build_draft_prompt(
    offer: Offer,
    candidate: Candidate,
    cited_signals: List[Signal],
    identity: Dict[str, str],
) -> Dict[str, Any]:
    """Return the handshake dict for one offer. The CLI prints this to stdout."""
    cap = LENGTH_CAPS_WORDS.get(offer.type, _DEFAULT_CAP_WORDS)
    return {
        "offer_id": offer.offer_id,
        "system_prompt": _render_system_prompt(identity),
        "user_prompt": _render_user_prompt(offer, candidate, cited_signals, cap),
        "offer": offer.to_dict(),
        "candidate": candidate.to_dict(),
        "cited_signals": [s.to_dict() for s in cited_signals],
        "identity": dict(identity),
        "length_cap_words": cap,
        "schema": _response_schema_hint(),
    }


# --------------------------------------------------------------------------
# Response validation
# --------------------------------------------------------------------------


def _word_count(text: str) -> int:
    return len(text.split())


def apply_draft_response(
    response: Dict[str, Any],
    offer: Offer,
    batch_cited_ids: Set[str],
    *,
    excerpt_by_id: Optional[Dict[str, str]] = None,
    grounding_yaml_path: Optional[Any] = None,
    enable_grounding_gate: bool = True,
) -> Tuple[Optional[Draft], List[str]]:
    """Validate an LLM draft response.

    Returns ``(draft, warnings)`` on success or ``(None, rejection_reasons)``
    on failure. ``batch_cited_ids`` is the set of signal ids that were
    actually passed to the LLM for this offer; any citation outside that
    set is treated as a hallucination.

    Sprint 7 (C2): if ``excerpt_by_id`` is supplied, the draft text is
    additionally checked against the online grounding gate (overlap +
    anchored-token thresholds from ``grounding.yaml``). Pre-Sprint-7 callers
    that don't pass excerpts skip the gate (back-compat).
    """
    if not isinstance(response, dict):
        return None, [f"response_not_object: got {type(response).__name__}"]

    extras = set(response.keys()) - _RESPONSE_KEYS
    if extras:
        return None, [f"unknown_field: {sorted(extras)}"]

    missing = _RESPONSE_KEYS - set(response.keys())
    if missing:
        return None, [f"missing_field: {sorted(missing)}"]

    draft_text = response["draft_text"]
    citations = response["citations"]
    confidence = response["confidence"]
    warnings = response["warnings"]

    if not isinstance(draft_text, str):
        return None, ["draft_text_not_string"]
    if not isinstance(citations, list) or any(not isinstance(c, str) for c in citations):
        return None, ["citations_not_list_of_str"]
    if not isinstance(warnings, list) or any(not isinstance(w, str) for w in warnings):
        return None, ["warnings_not_list_of_str"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None, ["confidence_not_number"]
    if not (0.0 <= float(confidence) <= 1.0):
        return None, ["confidence_out_of_range"]

    # Hallucination gate.
    bad = [c for c in citations if c not in batch_cited_ids]
    if bad:
        return None, [f"hallucinated_citation: {bad}"]

    # Non-empty draft must cite at least one signal.
    if draft_text.strip() and not citations:
        return None, ["draft_text_without_citation"]

    # Forbidden control characters (shell-escape prophylaxis).
    if _FORBIDDEN_CHAR_RE.search(draft_text):
        return None, ["forbidden_control_character"]

    # Length cap.
    cap = LENGTH_CAPS_WORDS.get(offer.type, _DEFAULT_CAP_WORDS)
    wc = _word_count(draft_text)
    if wc > cap:
        return None, [f"over_length: {wc} words > cap {cap} for type {offer.type!r}"]

    # Sprint 7 C2 — online grounding gate.
    if enable_grounding_gate and excerpt_by_id is not None and draft_text.strip():
        from .grounding import check_grounding, thresholds_for

        min_overlap, min_anchored = thresholds_for("draft", grounding_yaml_path)
        cited_excerpts = [excerpt_by_id.get(cid, "") for cid in citations]
        gr = check_grounding(
            draft_text,
            cited_excerpts,
            min_overlap=min_overlap,
            min_anchored_tokens=min_anchored,
        )
        if not gr.passed:
            return None, [
                (
                    f"ungrounded: overlap_ratio={gr.overlap_ratio:.3f} "
                    f"anchored={gr.anchored_tokens}/{gr.total_tokens} "
                    f"unanchored={gr.unanchored_tokens[:8]}"
                )
            ]

    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rel_path = f"System/activation/drafts/{offer.offer_id}.md"
    draft = Draft(
        offer_id=offer.offer_id,
        draft_text=draft_text,
        citations=list(citations),
        confidence=float(confidence),
        warnings=list(warnings),
        created_at=now_iso,
        path=rel_path,
    )
    return draft, list(warnings)


# --------------------------------------------------------------------------
# Disk write
# --------------------------------------------------------------------------


def _yaml_escape(value: Any) -> str:
    """Quote-escape a YAML scalar. Sufficient for our closed input set."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def write_draft_file(draft: Draft, offer: Offer, drafts_dir: Path) -> Path:
    """Write the draft markdown file with YAML frontmatter. Returns the path."""
    drafts_dir = Path(drafts_dir)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    target = drafts_dir / f"{offer.offer_id}.md"

    citations_yaml = "[" + ", ".join(_yaml_escape(c) for c in draft.citations) + "]"
    warnings_yaml = "[" + ", ".join(_yaml_escape(w) for w in draft.warnings) + "]"

    fm = (
        "---\n"
        f"offer_id: {_yaml_escape(offer.offer_id)}\n"
        f"offer_type: {_yaml_escape(offer.type)}\n"
        f"created_at: {_yaml_escape(draft.created_at)}\n"
        f"citations: {citations_yaml}\n"
        f"confidence: {draft.confidence}\n"
        f"warnings: {warnings_yaml}\n"
        "---\n\n"
    )
    target.write_text(fm + draft.draft_text.rstrip() + "\n", encoding="utf-8")
    return target


__all__ = [
    "LENGTH_CAPS_WORDS",
    "load_identity",
    "build_draft_prompt",
    "apply_draft_response",
    "write_draft_file",
]
