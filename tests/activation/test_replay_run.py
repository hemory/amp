"""End-to-end replay on the sample-01 fixture."""

from __future__ import annotations

from pathlib import Path

from core.activation.replay import load_fixture, run_replay


_SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "System" / "activation" / "replay" / "fixtures" / "sample-01"
)


def test_sample_replay_catches_hallucinated_citation():
    fx = load_fixture(_SAMPLE)
    result = run_replay(fx)
    # 4 candidates in extract_response; 1 rejected for hallucinated signal.
    assert len(result.candidates) == 3
    assert len(result.rejections) == 1
    first = result.rejections[0]
    assert first["reason"] == "hallucinated_signal_id"
    assert "sig_hallucinated_summit" in first["detail"]


def test_sample_replay_offer_and_draft_counts():
    fx = load_fixture(_SAMPLE)
    result = run_replay(fx)
    # 3 surviving candidates → 3 offers. Non-ghost, high-acceptance-rate
    # fixture → all 3 surfaced.
    assert len(result.offers) == 3
    assert all(o.shown for o in result.offers)
    # Two draft_responses recorded → two drafts materialized.
    assert len(result.drafts) == 2
    assert len(result.draft_rejections) == 0


def test_sample_replay_offer_ids_are_deterministic():
    fx = load_fixture(_SAMPLE)
    r1 = run_replay(fx)
    r2 = run_replay(fx)
    assert [o.offer_id for o in r1.offers] == [o.offer_id for o in r2.offers]
    # Convention: o-replay-<fixture_id>-<idx>
    for o in r1.offers:
        assert o.offer_id.startswith("o-replay-sample-01-")
