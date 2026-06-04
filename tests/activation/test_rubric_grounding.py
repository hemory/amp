from core.activation.rubric import score_offer
from rubric_helpers import mk_candidate, mk_offer, mk_signal


def test_grounding_full_when_all_tokens_cited():
    offer = mk_offer(summary="Reel timeline")
    sig = mk_signal("sig_a", "Reel timeline finalize with Alex")
    s = score_offer(offer, mk_candidate(), [sig])
    assert s.grounding == 1.0


def test_grounding_drops_when_ungrounded_claim():
    offer = mk_offer(
        summary="Send quarterly forecast unicorn centaur velociraptor aquamarine"
    )
    sig = mk_signal("sig_a", "Reel timeline finalize with Alex")
    s = score_offer(offer, mk_candidate(), [sig])
    assert s.grounding < 1.0
    assert s.grounding <= 0.5
