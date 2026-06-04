"""Sprint 7 C3 — run lineage filter (CLI behavior).

The actual filter happens in __main__._cmd_rank, but rank() preserves
candidate order so we test the lineage-stamping side effect end-to-end.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.activation.extract import apply_extract_response
from core.activation.schemas import Signal


NOW = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _sig(sid="sig_1", excerpt="Schedule with Alex to finalize Reel timeline"):
    return Signal(
        signal_id=sid, source="meeting_notes", path="People/Alex.md",
        timestamp=NOW.isoformat().replace("+00:00", "Z"),
        excerpt=excerpt,
    )


def _llm_payload(cid="c-1"):
    return [{
        "candidate_id": cid,
        "type": "meeting_followup",
        "summary": "Schedule with Alex",
        "cited_signals": ["sig_1"],
        "confidence": 0.8,
        "staleness_days": 0,
        "action_verb": "schedule",
    }]


def test_extract_apply_stamps_run_id_and_batch_id():
    accepted, rejected = apply_extract_response(
        _llm_payload(),
        batch=[_sig()],
        batch_id="b-001",
        run_id="run-abc",
        now=NOW,
        enable_grounding_gate=False,
    )
    assert len(accepted) == 1
    assert accepted[0].run_id == "run-abc"
    assert accepted[0].batch_id == "b-001"
    assert accepted[0].created_at  # stamped


def test_extract_apply_legacy_call_uses_sentinels():
    accepted, _ = apply_extract_response(
        _llm_payload(),
        batch=[_sig()],
        batch_id="b-001",
        now=NOW,
        enable_grounding_gate=False,
    )
    # No run_id passed → derived from batch_id.
    assert accepted[0].run_id  # auto-stamped a run_id
    assert accepted[0].batch_id == "b-001"


def test_extract_grounding_gate_drops_ungrounded():
    payload = _llm_payload()
    payload[0]["summary"] = "Order new espresso machine for office"
    accepted, rejected = apply_extract_response(
        payload, batch=[_sig()], batch_id="b-y",
        run_id="run-x", now=NOW,
        enable_grounding_gate=True,
    )
    assert accepted == []
    assert any("ground" in (r.get("reason") or "") for r in rejected)
