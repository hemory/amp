from core.activation.rubric import score_offer
from rubric_helpers import mk_candidate, mk_offer, mk_signal


def test_specificity_vague_is_low():
    offer = mk_offer(summary="follow up with the person about the thing")
    s = score_offer(offer, mk_candidate(), [mk_signal("sig_a", "follow up")])
    assert s.specificity == 0.0


def test_specificity_concrete_is_high():
    offer = mk_offer(
        summary="Schedule 30 min with Alex on Reel #3 timeline by 2026-04-17"
    )
    s = score_offer(
        offer, mk_candidate(), [mk_signal("sig_a", "Alex Reel timeline")]
    )
    assert s.specificity == 1.0


def test_specificity_partial_is_half():
    offer = mk_offer(summary="schedule a meeting and review the notes")
    s = score_offer(offer, mk_candidate(), [mk_signal("sig_a", "schedule notes")])
    assert s.specificity == 0.5
