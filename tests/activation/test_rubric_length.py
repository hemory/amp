from core.activation.rubric import score_offer
from rubric_helpers import mk_candidate, mk_draft, mk_offer, mk_signal


def test_length_within_cap_is_one():
    offer = mk_offer(type="meeting_followup")  # cap = 150 words
    draft = mk_draft(text="one two three " * 10)  # 30 words
    s = score_offer(offer, mk_candidate(), [mk_signal("sig_a", "one two three")], draft)
    assert s.length_discipline == 1.0


def test_length_twenty_pct_over_is_0_8():
    offer = mk_offer(type="commitment_reminder")  # cap = 100 words
    draft = mk_draft(text=" ".join(["word"] * 120))  # 20% over
    s = score_offer(offer, mk_candidate(), [mk_signal("sig_a", "word")], draft)
    assert abs(s.length_discipline - 0.8) < 1e-6


def test_length_no_draft_is_one():
    offer = mk_offer()
    s = score_offer(offer, mk_candidate(), [mk_signal("sig_a", "x")], draft=None)
    assert s.length_discipline == 1.0
