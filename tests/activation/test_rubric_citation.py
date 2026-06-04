from core.activation.rubric import score_offer
from rubric_helpers import mk_candidate, mk_offer, mk_signal


def test_citation_empty_is_zero():
    offer = mk_offer(cited=[])
    s = score_offer(offer, mk_candidate(), [], signal_universe_ids=set())
    assert s.citation_discipline == 0.0


def test_citation_invalid_id_is_zero():
    offer = mk_offer(cited=["sig_fake"])
    sig = mk_signal("sig_a", "Alex Reel timeline")
    s = score_offer(
        offer,
        mk_candidate(),
        [sig],
        signal_universe_ids={"sig_a"},
    )
    assert s.citation_discipline == 0.0


def test_citation_ok_is_one():
    offer = mk_offer(cited=["sig_a"])
    sig = mk_signal("sig_a", "Alex Reel timeline")
    s = score_offer(
        offer,
        mk_candidate(),
        [sig],
        signal_universe_ids={"sig_a"},
    )
    assert s.citation_discipline == 1.0
