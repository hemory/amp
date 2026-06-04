"""Shared rubric test helpers — factories for Offer/Signal/Candidate/Draft."""

from __future__ import annotations

from core.activation.schemas import Candidate, Draft, Offer, Signal


def mk_offer(
    *,
    offer_id: str = "o1",
    type: str = "meeting_followup",
    summary: str = "Schedule 30 min with Alex on Reel #3 timeline",
    cited: list[str] | None = None,
    created_at: str = "2026-04-19T09:00:00Z",
    shown: bool = True,
) -> Offer:
    return Offer(
        offer_id=offer_id,
        created_at=created_at,
        ritual="daily-plan",
        type=type,
        shown=shown,
        summary=summary,
        cited_signals=cited if cited is not None else ["sig_a"],
        score=1.0,
    )


def mk_signal(sid: str, excerpt: str) -> Signal:
    return Signal(
        signal_id=sid,
        source="meeting_notes",
        path=f"04-Projects/X/{sid}.md",
        timestamp="2026-04-18T10:00:00Z",
        excerpt=excerpt,
    )


def mk_candidate(staleness: int = 0) -> Candidate:
    return Candidate(
        candidate_id="c1",
        type="meeting_followup",
        summary="Schedule 30 min with Alex on Reel #3 timeline",
        cited_signals=["sig_a"],
        confidence=0.9,
        staleness_days=staleness,
        action_verb="schedule",
    )


def mk_draft(text: str = "Hi Alex — schedule 30 min to finalize Reel #3.") -> Draft:
    return Draft(
        offer_id="o1",
        draft_text=text,
        citations=["sig_a"],
        confidence=0.9,
        warnings=[],
        created_at="2026-04-19T09:00:00Z",
        path="x.md",
    )
