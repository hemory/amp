"""Schema tests — good and bad cases, dict round-trip."""

from __future__ import annotations

import pytest

from core.activation.schemas import (
    Candidate,
    Offer,
    SchemaError,
    Signal,
    Tombstone,
)


# ---------- Signal ----------

def _good_signal_data():
    return {
        "signal_id": "sig_abc123",
        "source": "meeting_notes",
        "path": "04-Projects/X/meetings/2026-04-13.md",
        "timestamp": "2026-04-13T10:00:00Z",
        "excerpt": "the user to send followup to D.Lin by Fri",
    }


def test_signal_happy_path_roundtrip():
    data = _good_signal_data()
    sig = Signal.from_dict(data)
    assert sig.signal_id == "sig_abc123"
    out = sig.to_dict()
    assert out == data  # deterministic


def test_signal_missing_field_raises():
    data = _good_signal_data()
    del data["excerpt"]
    with pytest.raises(SchemaError, match="excerpt"):
        Signal.from_dict(data)


def test_signal_wrong_type_raises():
    data = _good_signal_data()
    data["timestamp"] = 12345
    with pytest.raises(SchemaError, match="timestamp"):
        Signal.from_dict(data)


def test_signal_empty_id_raises():
    data = _good_signal_data()
    data["signal_id"] = ""
    with pytest.raises(SchemaError):
        Signal.from_dict(data)


def test_signal_without_structured_omits_key_on_roundtrip():
    data = _good_signal_data()
    sig = Signal.from_dict(data)
    assert sig.structured is None
    # `structured` not included when None to keep existing rows compact.
    assert "structured" not in sig.to_dict()
    assert sig.to_dict() == data


def test_signal_with_structured_roundtrips():
    data = _good_signal_data()
    data["structured"] = {
        "calendar_event_id": "evt-abc",
        "attendees": ["Alex_Rivera", "the user"],
        "meeting_date": "2026-04-10",
    }
    sig = Signal.from_dict(data)
    assert sig.structured == data["structured"]
    assert sig.to_dict() == data


def test_signal_structured_must_be_dict():
    data = _good_signal_data()
    data["structured"] = "not a dict"
    with pytest.raises(SchemaError, match="structured"):
        Signal.from_dict(data)


# ---------- Candidate ----------

def _good_candidate_data():
    return {
        "candidate_id": "c_2026-04-17_001",
        "type": "meeting_followup",
        "summary": "Send followup to D.Lin",
        "cited_signals": ["sig_abc123"],
        "confidence": 0.82,
        "staleness_days": 2,
        "action_verb": "draft",
    }


def test_candidate_happy_path_roundtrip():
    data = _good_candidate_data()
    c = Candidate.from_dict(data)
    assert c.type == "meeting_followup"
    assert c.to_dict() == data


def test_candidate_bad_type_enum_raises():
    data = _good_candidate_data()
    data["type"] = "random_thought"
    with pytest.raises(SchemaError, match="type"):
        Candidate.from_dict(data)


def test_candidate_bad_action_verb_raises():
    data = _good_candidate_data()
    data["action_verb"] = "ponder"
    with pytest.raises(SchemaError, match="action_verb"):
        Candidate.from_dict(data)


def test_candidate_empty_citations_raises():
    data = _good_candidate_data()
    data["cited_signals"] = []
    with pytest.raises(SchemaError, match="cited_signals"):
        Candidate.from_dict(data)


def test_candidate_confidence_out_of_range_raises():
    data = _good_candidate_data()
    data["confidence"] = 1.5
    with pytest.raises(SchemaError, match="confidence"):
        Candidate.from_dict(data)


def test_candidate_non_str_citation_raises():
    data = _good_candidate_data()
    data["cited_signals"] = ["sig_abc", 42]
    with pytest.raises(SchemaError, match="cited_signals"):
        Candidate.from_dict(data)


# ---------- Offer ----------

def _good_offer_data():
    return {
        "offer_id": "o_2026-04-17_002",
        "created_at": "2026-04-17T07:02:11Z",
        "ritual": "daily-plan",
        "type": "meeting_followup",
        "shown": True,
        "summary": "Send workshop followup to D.Lin",
        "cited_signals": ["sig_abc123"],
        "score": 0.82,
        "candidate_id": "c_2026-04-17_001",
        "hold_reason": None,
        "draft_artifact_path": "System/activation/drafts/o_2026-04-17_002.md",
        "score_components": {"confidence": 0.9, "recency": 0.8},
        "user_response": None,
        "response_timestamp": None,
        "time_to_response_s": None,
        "edit_distance_if_accepted": None,
        "notes": None,
    }


def test_offer_happy_path_roundtrip():
    data = _good_offer_data()
    o = Offer.from_dict(data)
    assert o.offer_id == "o_2026-04-17_002"
    assert o.to_dict() == data


def test_offer_bad_ritual_raises():
    data = _good_offer_data()
    data["ritual"] = "standup"
    with pytest.raises(SchemaError, match="ritual"):
        Offer.from_dict(data)


def test_offer_bad_user_response_raises():
    data = _good_offer_data()
    data["user_response"] = "maybe"
    with pytest.raises(SchemaError, match="user_response"):
        Offer.from_dict(data)


def test_offer_bad_hold_reason_raises():
    data = _good_offer_data()
    data["hold_reason"] = "whatever"
    with pytest.raises(SchemaError, match="hold_reason"):
        Offer.from_dict(data)


def test_offer_shown_must_be_bool():
    data = _good_offer_data()
    data["shown"] = "yes"
    with pytest.raises(SchemaError, match="shown"):
        Offer.from_dict(data)


def test_offer_missing_score_raises():
    data = _good_offer_data()
    del data["score"]
    with pytest.raises(SchemaError, match="score"):
        Offer.from_dict(data)


# ---------- Tombstone ----------

def _good_tombstone_data():
    return {
        "tombstone_id": "t_2026-04-17_001",
        "created_at": "2026-04-17T08:00:00Z",
        "type": "person_reconnect",
        "pattern": "person_reconnect:J.Park",
        "source_offer_id": "o_2026-04-10_003",
        "notes": None,
    }


def test_tombstone_happy_path_roundtrip():
    data = _good_tombstone_data()
    t = Tombstone.from_dict(data)
    assert t.pattern == "person_reconnect:J.Park"
    assert t.to_dict() == data


def test_tombstone_bad_type_raises():
    data = _good_tombstone_data()
    data["type"] = "nope"
    with pytest.raises(SchemaError, match="type"):
        Tombstone.from_dict(data)


def test_tombstone_missing_pattern_raises():
    data = _good_tombstone_data()
    del data["pattern"]
    with pytest.raises(SchemaError, match="pattern"):
        Tombstone.from_dict(data)
