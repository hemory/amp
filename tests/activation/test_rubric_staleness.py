from core.activation.rubric import score_offer
from rubric_helpers import mk_candidate, mk_offer, mk_signal


def test_staleness_linear_decay():
    sig = mk_signal("sig_a", "Alex Reel timeline")
    offer = mk_offer()
    s0 = score_offer(offer, mk_candidate(staleness=0), [sig])
    assert s0.staleness == 1.0
    s7 = score_offer(offer, mk_candidate(staleness=7), [sig])
    assert abs(s7.staleness - 0.5) < 1e-6
    s14 = score_offer(offer, mk_candidate(staleness=14), [sig])
    assert s14.staleness == 0.0
    s20 = score_offer(offer, mk_candidate(staleness=20), [sig])
    assert s20.staleness == 0.0
