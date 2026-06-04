"""Tests for ``core.activation.extract.build_extract_prompt``."""

from __future__ import annotations

from datetime import date

from core.activation.extract import (
    batch_signals,
    build_extract_prompt,
    make_batch_id,
)
from core.activation.schemas import Signal


def _sig(i: int) -> Signal:
    return Signal(
        signal_id=f"sig_{i:04d}",
        source="meeting_notes",
        path=f"04-Projects/X/meetings/2026-04-{(i % 28) + 1:02d}.md",
        timestamp="2026-04-13T10:00:00Z",
        excerpt=f"excerpt number {i}",
    )


def test_batch_grouping_stable_and_bounded():
    signals = [_sig(i) for i in range(123)]
    # Shuffle to prove stability depends on signal_id, not input order.
    import random
    random.Random(42).shuffle(signals)

    batches = batch_signals(signals, max_size=50)
    assert [len(b) for b in batches] == [50, 50, 23]

    # Stable ordering: each batch's IDs ascend, and cross-batch is monotonic.
    flat = [s.signal_id for b in batches for s in b]
    assert flat == sorted(flat)

    # Re-batching after another shuffle returns the same result.
    signals2 = list(signals)
    random.Random(7).shuffle(signals2)
    batches2 = batch_signals(signals2, max_size=50)
    assert [[s.signal_id for s in b] for b in batches] == [
        [s.signal_id for s in b] for b in batches2
    ]


def test_batch_id_format():
    assert make_batch_id(date(2026, 4, 17), 0) == "batch-20260417-00"
    assert make_batch_id(date(2026, 12, 31), 7) == "batch-20261231-07"
    assert make_batch_id(date(2026, 1, 1), 42) == "batch-20260101-42"


def test_prompt_contains_schema_and_citation_rule():
    signals = [_sig(i) for i in range(3)]
    handshake = build_extract_prompt(signals, "batch-20260417-00")

    assert handshake["batch_id"] == "batch-20260417-00"
    assert "system_prompt" in handshake
    assert "user_prompt" in handshake
    assert "schema" in handshake

    # Schema describes Candidate
    schema = handshake["schema"]
    assert "cited_signals" in schema["items"]["properties"]
    assert schema["items"]["properties"]["cited_signals"]["minItems"] == 1
    assert schema["items"]["additionalProperties"] is False
    props = set(schema["items"]["required"])
    assert props == {
        "candidate_id",
        "type",
        "summary",
        "cited_signals",
        "confidence",
        "staleness_days",
        "action_verb",
    }

    # User prompt must tell the model to cite, not invent, and to emit JSON.
    up = handshake["user_prompt"]
    assert "cited_signals" in up
    assert "batch-20260417-00" in up
    for s in signals:
        assert s.signal_id in up

    # System prompt must mention citation grounding + JSON-only.
    sp = handshake["system_prompt"]
    assert "cite" in sp.lower()
    assert "json" in sp.lower()


def test_prompt_signal_payload_matches_input():
    signals = [_sig(i) for i in range(2)]
    handshake = build_extract_prompt(signals, "batch-20260417-00")
    assert handshake["signals"] == [s.to_dict() for s in signals]


def test_batch_signals_rejects_nonpositive_max():
    import pytest
    with pytest.raises(ValueError):
        batch_signals([_sig(1)], max_size=0)
