"""Tests for ``core.activation.extract.apply_extract_response``.

Covers the citation-required gate, hallucination canary, schema validation,
and the partial-batch path (good + bad mixed in one response).
"""

from __future__ import annotations

from core.activation.extract import apply_extract_response
from core.activation.schemas import Signal


def _signals():
    return [
        Signal(
            signal_id=f"sig_{i}",
            source="meeting_notes",
            path=f"x/{i}.md",
            timestamp="2026-04-13T10:00:00Z",
            excerpt="e",
        )
        for i in range(3)
    ]


def _good_cand(i: int = 1, cited=("sig_0",)) -> dict:
    return {
        "candidate_id": f"c_{i:03d}",
        "type": "meeting_followup",
        "summary": "Send recap to D.Lin",
        "cited_signals": list(cited),
        "confidence": 0.7,
        "staleness_days": 2,
        "action_verb": "send",
    }


def test_happy_path_all_accepted():
    response = [_good_cand(1), _good_cand(2, cited=("sig_1", "sig_2"))]
    accepted, rejected = apply_extract_response(response, _signals(), "batch-20260417-00", enable_grounding_gate=False)
    assert len(accepted) == 2
    assert not rejected
    assert accepted[0].type == "meeting_followup"


def test_hallucinated_signal_id_rejected():
    cand = _good_cand(cited=("sig_0", "sig_NOT_REAL"))
    accepted, rejected = apply_extract_response([cand], _signals(), "batch-20260417-00", enable_grounding_gate=False)
    assert not accepted
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "hallucinated_signal_id"
    assert "sig_NOT_REAL" in rejected[0]["detail"]


def test_missing_cited_signals_rejected():
    cand = _good_cand()
    cand["cited_signals"] = []
    accepted, rejected = apply_extract_response([cand], _signals(), "batch-20260417-00", enable_grounding_gate=False)
    assert not accepted
    assert rejected[0]["reason"] == "missing_cited_signals"


def test_bad_offer_type_rejected():
    cand = _good_cand()
    cand["type"] = "definitely_not_an_offer_type"
    accepted, rejected = apply_extract_response([cand], _signals(), "batch-20260417-00", enable_grounding_gate=False)
    assert not accepted
    assert rejected[0]["reason"] in ("schema_error", "bad_offer_type")


def test_extra_field_rejected():
    cand = _good_cand()
    cand["sneaky_extra"] = "I am trying to inject a new field"
    accepted, rejected = apply_extract_response([cand], _signals(), "batch-20260417-00", enable_grounding_gate=False)
    assert not accepted
    assert rejected[0]["reason"] == "unknown_field"
    assert "sneaky_extra" in rejected[0]["detail"]


def test_partial_batch_three_good_two_bad():
    good1 = _good_cand(1, cited=("sig_0",))
    good2 = _good_cand(2, cited=("sig_1",))
    good3 = _good_cand(3, cited=("sig_2",))
    bad_halluc = _good_cand(4, cited=("sig_999",))
    bad_extra = _good_cand(5)
    bad_extra["injected"] = "x"

    response = [good1, bad_halluc, good2, bad_extra, good3]
    accepted, rejected = apply_extract_response(response, _signals(), "batch-20260417-00", enable_grounding_gate=False)
    assert len(accepted) == 3
    assert [c.candidate_id for c in accepted] == ["c_001", "c_002", "c_003"]
    assert len(rejected) == 2


def test_response_not_list():
    accepted, rejected = apply_extract_response({"not": "a list"}, _signals(), "b", enable_grounding_gate=False)  # type: ignore[arg-type]
    assert not accepted
    assert rejected[0]["reason"] == "response_not_list"


def test_non_mapping_item_rejected():
    accepted, rejected = apply_extract_response(["plain string"], _signals(), "b", enable_grounding_gate=False)  # type: ignore[list-item]
    assert not accepted
    assert rejected[0]["reason"] == "not_a_mapping"


def test_bad_confidence_range_rejected_as_schema_error():
    cand = _good_cand()
    cand["confidence"] = 1.5
    accepted, rejected = apply_extract_response([cand], _signals(), "b", enable_grounding_gate=False)
    assert not accepted
    assert rejected[0]["reason"] == "schema_error"
