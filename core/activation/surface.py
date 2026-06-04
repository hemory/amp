"""Stage 5 — Surface offers. §4.5 of design doc.

Sprint 4 deliverable. Renders the "Proposed Actions" markdown block for
inclusion at the top of /daily-plan output.

Sprint 6 added the ghost-review digest renderer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from .schemas import Draft, Offer, Signal

if TYPE_CHECKING:  # pragma: no cover
    from .ghost import GhostState


def surface_offers(offers: List[Offer]) -> str:
    raise NotImplementedError("Sprint 4 — see B1_Activation_Engine_Design.md §4.5")


# ---------------------------------------------------------------------------
# Sprint 6 — ghost-review digest
# ---------------------------------------------------------------------------

def _days_remaining(state: "GhostState", now: datetime) -> Optional[int]:
    if state.expected_end is None:
        return None
    delta = state.expected_end - now
    days = int(delta.total_seconds() // 86400)
    return max(0, days + (1 if delta.total_seconds() % 86400 else 0))


def _is_ghost(offer: Offer) -> bool:
    hr = offer.hold_reason or ""
    return hr == "ghost" or hr.startswith("ghost:")


def render_ghost_digest(
    *,
    offers: List[Offer],
    drafts: Dict[str, Draft],
    cited_signals_lookup: Dict[str, Signal],
    ghost_state: "GhostState",
    now: datetime,
) -> str:
    """Render the markdown digest of held-in-ghost offers.

    Pure function, no I/O. ``offers`` may be the entire offers log; only
    held-in-ghost rows are surfaced. ``drafts`` maps offer_id → Draft (may
    be empty). ``cited_signals_lookup`` maps signal_id → Signal so we can
    print path links without re-reading signals.jsonl.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    held = [o for o in offers if _is_ghost(o)]

    lines: List[str] = []
    lines.append("# Ghost-mode review digest")
    lines.append("")
    if ghost_state.active:
        reason = ghost_state.reason or "unspecified"
        lines.append(f"- **Status:** 👻 ghost mode active ({reason})")
        days = _days_remaining(ghost_state, now)
        if days is not None:
            lines.append(f"- **Days remaining (expected):** {days}")
        elif ghost_state.reason == "manual":
            lines.append("- **Days remaining:** open-ended (manual)")
    else:
        lines.append("- **Status:** ghost mode inactive (showing prior held offers)")
    lines.append(f"- **Held offers in this digest:** {len(held)}")
    lines.append(f"- **Generated at:** {now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')}")
    lines.append("")

    if not held:
        lines.append("_No offers were held in ghost mode for this window._")
        lines.append("")
    else:
        lines.append("## Proposed actions Amp WOULD have surfaced (held in ghost):")
        lines.append("")
        for idx, offer in enumerate(held, start=1):
            verb = ""
            cand_id = offer.candidate_id or ""
            lines.append(f"### {idx}. [{offer.type}] {offer.summary}")
            lines.append("")
            lines.append(f"- **offer_id:** `{offer.offer_id}`")
            if cand_id:
                lines.append(f"- **candidate_id:** `{cand_id}`")
            lines.append(f"- **hold_reason:** `{offer.hold_reason}`")
            if offer.cited_signals:
                lines.append("- **citations:**")
                for sid in offer.cited_signals:
                    sig = cited_signals_lookup.get(sid)
                    if sig is not None:
                        lines.append(f"  - `{sid}` → [{sig.path}]({sig.path})")
                    else:
                        lines.append(f"  - `{sid}`")
            draft = drafts.get(offer.offer_id)
            if draft is not None:
                lines.append("- **draft:**")
                lines.append("")
                for dl in draft.draft_text.splitlines():
                    lines.append(f"  > {dl}")
                lines.append("")
            else:
                lines.append("- _no draft attached_")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "To exit ghost mode: run `python -m core.activation ghost-exit "
        "--acknowledge` after reviewing."
    )
    lines.append("")
    return "\n".join(lines)


def write_ghost_digest(content: str, path: Path) -> None:
    """Write the digest markdown to ``path`` (parents auto-created)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


__all__ = ["surface_offers", "render_ghost_digest", "write_ghost_digest"]
