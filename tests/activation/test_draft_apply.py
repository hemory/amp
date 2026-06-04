"""apply_draft_response: happy, hallucination, over-length, file write."""

from __future__ import annotations

from pathlib import Path

from core.activation.draft import apply_draft_response, write_draft_file
from core.activation.schemas import Offer


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
    )


def test_apply_draft_happy_path():
    resp = {
        "draft_text": "Hi D — quick recap: three decisions.",
        "citations": ["sig_abc"],
        "confidence": 0.8,
        "warnings": [],
    }
    draft, warnings = apply_draft_response(resp, _offer(), {"sig_abc"})
    assert draft is not None
    assert draft.draft_text == resp["draft_text"]
    assert draft.citations == ["sig_abc"]
    assert draft.confidence == 0.8
    assert draft.path == "System/activation/drafts/o_test_001.md"
    assert warnings == []


def test_apply_draft_rejects_hallucinated_citation():
    resp = {
        "draft_text": "Hi D — recap.",
        "citations": ["sig_NOTREAL"],
        "confidence": 0.5,
        "warnings": [],
    }
    draft, notes = apply_draft_response(resp, _offer(), {"sig_abc"})
    assert draft is None
    assert any("hallucinated_citation" in n for n in notes)


def test_apply_draft_rejects_over_length_for_type():
    # 101 words — over the 100-word cap for risk_flag.
    text = " ".join(["word"] * 101)
    resp = {
        "draft_text": text,
        "citations": ["sig_abc"],
        "confidence": 0.8,
        "warnings": [],
    }
    draft, notes = apply_draft_response(resp, _offer("risk_flag"), {"sig_abc"})
    assert draft is None
    assert any("over_length" in n for n in notes)


def test_apply_draft_accepts_at_length_cap():
    # meeting_followup cap = 150; exactly 150 words passes.
    text = " ".join(["w"] * 150)
    resp = {
        "draft_text": text,
        "citations": ["sig_abc"],
        "confidence": 0.8,
        "warnings": [],
    }
    draft, _ = apply_draft_response(resp, _offer("meeting_followup"), {"sig_abc"})
    assert draft is not None


def test_apply_draft_rejects_unknown_field():
    resp = {
        "draft_text": "ok",
        "citations": ["sig_abc"],
        "confidence": 0.8,
        "warnings": [],
        "extra": "nope",
    }
    draft, notes = apply_draft_response(resp, _offer(), {"sig_abc"})
    assert draft is None
    assert any("unknown_field" in n for n in notes)


def test_apply_draft_rejects_forbidden_control_char():
    resp = {
        "draft_text": "bad\x00text",
        "citations": ["sig_abc"],
        "confidence": 0.5,
        "warnings": [],
    }
    draft, notes = apply_draft_response(resp, _offer(), {"sig_abc"})
    assert draft is None
    assert any("forbidden_control_character" in n for n in notes)


def test_apply_draft_rejects_nonempty_without_citation():
    resp = {
        "draft_text": "something",
        "citations": [],
        "confidence": 0.5,
        "warnings": [],
    }
    draft, notes = apply_draft_response(resp, _offer(), {"sig_abc"})
    assert draft is None
    assert any("draft_text_without_citation" in n for n in notes)


def test_write_draft_file_writes_frontmatter_and_body(tmp_path: Path):
    resp = {
        "draft_text": "Hi D — recap.",
        "citations": ["sig_abc"],
        "confidence": 0.77,
        "warnings": ["generic_voice"],
    }
    offer = _offer()
    draft, _ = apply_draft_response(resp, offer, {"sig_abc"})
    assert draft is not None
    target = write_draft_file(draft, offer, tmp_path)

    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert 'offer_id: "o_test_001"' in content
    assert 'offer_type: "meeting_followup"' in content
    assert 'citations: ["sig_abc"]' in content
    assert "confidence: 0.77" in content
    assert 'warnings: ["generic_voice"]' in content
    assert "Hi D — recap." in content
