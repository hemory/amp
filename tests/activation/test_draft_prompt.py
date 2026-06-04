"""build_draft_prompt: handshake structure, identity, cited signals, length cap."""

from __future__ import annotations

from core.activation.draft import LENGTH_CAPS_WORDS, build_draft_prompt
from core.activation.schemas import Candidate, Offer, Signal


def _offer(offer_type: str = "meeting_followup") -> Offer:
    return Offer(
        offer_id="o_test_001",
        created_at="2026-04-17T07:00:00Z",
        ritual="daily-plan",
        type=offer_type,
        shown=True,
        summary="Send workshop followup to D.Lin",
        cited_signals=["sig_abc"],
        score=0.82,
        candidate_id="c_test_001",
    )


def _candidate(offer_type: str = "meeting_followup") -> Candidate:
    return Candidate(
        candidate_id="c_test_001",
        type=offer_type,
        summary="Send workshop followup to D.Lin",
        cited_signals=["sig_abc"],
        confidence=0.8,
        staleness_days=1,
        action_verb="send",
    )


def _signal(sid: str = "sig_abc") -> Signal:
    return Signal(
        signal_id=sid,
        source="meeting_notes",
        path="04-Projects/X/meetings/2026-04-13.md",
        timestamp="2026-04-13T10:00:00Z",
        excerpt="the user to send followup to D.Lin by Fri",
    )


_IDENT = {
    "amp_soul": "AMP_SOUL_MARKER",
    "amp_style": "AMP_STYLE_MARKER",
    "user_soul": "USER_SOUL_MARKER",
    "user_style": "USER_STYLE_MARKER",
    "overview": "OVERVIEW_MARKER",
}


def test_handshake_top_level_keys():
    hs = build_draft_prompt(_offer(), _candidate(), [_signal()], _IDENT)
    for k in (
        "offer_id", "system_prompt", "user_prompt",
        "offer", "candidate", "cited_signals", "identity",
        "length_cap_words", "schema",
    ):
        assert k in hs, f"missing key: {k}"
    assert hs["offer_id"] == "o_test_001"


def test_handshake_includes_identity_markers_in_system_prompt():
    hs = build_draft_prompt(_offer(), _candidate(), [_signal()], _IDENT)
    sp = hs["system_prompt"]
    for marker in _IDENT.values():
        assert marker in sp


def test_handshake_includes_cited_signals_excerpt_in_user_prompt():
    hs = build_draft_prompt(_offer(), _candidate(), [_signal()], _IDENT)
    up = hs["user_prompt"]
    assert "sig_abc" in up
    assert "D.Lin by Fri" in up


def test_handshake_length_cap_per_type():
    hs_mf = build_draft_prompt(
        _offer("meeting_followup"), _candidate("meeting_followup"),
        [_signal()], _IDENT,
    )
    assert hs_mf["length_cap_words"] == LENGTH_CAPS_WORDS["meeting_followup"] == 150

    hs_dr = build_draft_prompt(
        _offer("draft_request"), _candidate("draft_request"),
        [_signal()], _IDENT,
    )
    assert hs_dr["length_cap_words"] == LENGTH_CAPS_WORDS["draft_request"] == 300

    hs_rf = build_draft_prompt(
        _offer("risk_flag"), _candidate("risk_flag"),
        [_signal()], _IDENT,
    )
    assert hs_rf["length_cap_words"] == 100


def test_handshake_forbids_first_person_as_user():
    hs = build_draft_prompt(_offer(), _candidate(), [_signal()], _IDENT)
    sp = hs["system_prompt"].lower()
    assert "not in first person" in sp or "not as user" in sp or "drafts for the user, not as the user" in sp


def test_handshake_requires_citation_in_system_prompt():
    hs = build_draft_prompt(_offer(), _candidate(), [_signal()], _IDENT)
    sp = hs["system_prompt"].lower()
    assert "cite only signals" in sp
    assert "never invent" in sp
