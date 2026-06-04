"""Sprint 7 H4 — ghost-exit predicate matrix unit tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from core.activation.ghost import check_ghost_exit_ready


def _vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    (v / "System" / "activation").mkdir(parents=True)
    return v


def _seed_reviews(path: Path, *, days_ago: list[int], decided_each: int = 2) -> None:
    """Write ghost-review markers via the public API across distinct calendar days."""
    from core.activation.ghost import mark_ghost_review_complete
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    for d in days_ago:
        ts = now - timedelta(days=d)
        decisions = [
            {"offer_id": f"o-{d}-{i}", "user_response": "accepted"}
            for i in range(decided_each)
        ]
        mark_ghost_review_complete(path, now=ts, decisions=decisions)


def _all_pass_kwargs(tmp_path: Path) -> dict:
    v = _vault(tmp_path)
    manual = v / "System" / "activation" / "ghost-mode.yaml"
    review = v / "System" / "activation" / "ghost-review-log.md"
    install = v / "System" / "activation" / "install.yaml"
    pause = v / "System" / "activation" / "post-review-pause.yaml"
    events = v / "System" / "activation" / "response-events.jsonl"
    install_date = date(2026, 4, 1)  # >7 days before NOW
    install.write_text(yaml.safe_dump({"install_date": install_date.isoformat()}),
                       encoding="utf-8")
    _seed_reviews(review, days_ago=[1, 2, 3], decided_each=2)
    return dict(
        install_date=install_date,
        now=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        manual_yaml_path=manual,
        ghost_review_log_path=review,
        post_review_pause_path=pause,
        install_yaml_path=install,
        response_events_path=events,
    )


def test_all_predicates_pass_when_satisfied(tmp_path):
    res = check_ghost_exit_ready(**_all_pass_kwargs(tmp_path))
    assert res["ready"] is True
    for k, v in res["predicates"].items():
        assert v is True, f"{k} should be True"


def test_p1_fails_inside_install_window(tmp_path):
    kw = _all_pass_kwargs(tmp_path)
    kw["install_date"] = date(2026, 4, 28)  # only 3 days ago
    res = check_ghost_exit_ready(**kw)
    assert res["predicates"]["P1_install_window_elapsed"] is False
    assert res["ready"] is False


def test_p2_fails_when_manual_ghost_active(tmp_path):
    kw = _all_pass_kwargs(tmp_path)
    kw["manual_yaml_path"].write_text(yaml.safe_dump({"active": True}),
                                       encoding="utf-8")
    res = check_ghost_exit_ready(**kw)
    assert res["predicates"]["P2_no_manual_ghost"] is False


def test_p3_fails_when_post_review_pause_active(tmp_path):
    kw = _all_pass_kwargs(tmp_path)
    kw["post_review_pause_path"].write_text(
        yaml.safe_dump({"active": True, "until": "2026-05-30"}),
        encoding="utf-8",
    )
    res = check_ghost_exit_ready(**kw)
    assert res["predicates"]["P3_no_post_review_pause"] is False


def test_p4_fails_when_too_few_review_days(tmp_path):
    kw = _all_pass_kwargs(tmp_path)
    kw["ghost_review_log_path"].unlink()
    _seed_reviews(kw["ghost_review_log_path"], days_ago=[1, 2], decided_each=3)
    res = check_ghost_exit_ready(**kw)
    assert res["predicates"]["P4_distinct_review_days_ge_3"] is False


def test_p5_fails_when_too_few_decided_offers(tmp_path):
    kw = _all_pass_kwargs(tmp_path)
    kw["ghost_review_log_path"].unlink()
    _seed_reviews(kw["ghost_review_log_path"], days_ago=[1, 2, 3],
                  decided_each=1)  # 3 total < 5
    res = check_ghost_exit_ready(**kw)
    assert res["predicates"]["P5_decided_offers_ge_5"] is False


def test_p6_first_exit_passes(tmp_path):
    """No prior ghost_exited_at on install.yaml → P6 N/A → pass."""
    kw = _all_pass_kwargs(tmp_path)
    res = check_ghost_exit_ready(**kw)
    assert res["predicates"]["P6_day7_acceptance_ok"] is True
    assert "first exit" in res["details"]["p6_reason"]
