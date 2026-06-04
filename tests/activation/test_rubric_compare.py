from core.activation.rubric import FixtureScorecard, RubricScore, _pearson, compare_with_grades
from core.activation.schemas import Grade


def _score(oid: str, overall: float) -> RubricScore:
    return RubricScore(
        offer_id=oid,
        grounding=1.0,
        specificity=1.0,
        staleness=1.0,
        novelty=1.0,
        length_discipline=1.0,
        citation_discipline=1.0,
        overall=overall,
    )


def _grade(oid: str, human: float) -> Grade:
    return Grade(
        offer_id=oid,
        human_score=human,
        reason="x",
        graded_at="2026-01-01T00:00:00Z",
        grader="user",
    )


def test_pearson_perfect_correlation():
    r = _pearson([1.0, 2.0, 3.0, 4.0, 5.0], [2.0, 4.0, 6.0, 8.0, 10.0])
    assert r is not None
    assert abs(r - 1.0) < 1e-6


def test_compare_with_grades_positive_correlation_5_points():
    scores = [_score(f"o{i}", 0.2 * i) for i in range(1, 6)]
    card = FixtureScorecard(fixture_id="t", scores=scores, means={}, n_offers=len(scores))
    grades = [_grade(f"o{i}", 0.2 * i) for i in range(1, 6)]
    cal = compare_with_grades(card, grades)
    assert cal.n == 5
    assert cal.pearson_r is not None
    assert abs(cal.pearson_r - 1.0) < 1e-6


def test_compare_with_grades_zero_variance_is_none():
    scores = [_score("o1", 0.5), _score("o2", 0.5)]
    card = FixtureScorecard(fixture_id="t", scores=scores, means={}, n_offers=2)
    grades = [_grade("o1", 0.4), _grade("o2", 0.8)]
    cal = compare_with_grades(card, grades)
    assert cal.pearson_r is None
    assert cal.n == 2


def test_compare_with_grades_no_overlap_is_empty():
    scores = [_score("o1", 0.5)]
    card = FixtureScorecard(fixture_id="t", scores=scores, means={}, n_offers=1)
    grades = [_grade("o_other", 0.5)]
    cal = compare_with_grades(card, grades)
    assert cal.n == 0
    assert cal.pearson_r is None
    assert cal.paired == []
