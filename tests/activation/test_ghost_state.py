"""Sprint 6 — GhostState computation, install.yaml bootstrap, manual until."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from core.activation.ghost import (
    GHOST_INSTALL_WINDOW_DAYS,
    compute_ghost_state,
    mark_ghost_review_complete,
    read_install_date,
    write_install_field,
)


UTC = timezone.utc


def _paths(tmp_path: Path):
    install = tmp_path / "install.yaml"
    manual = tmp_path / "ghost-mode.yaml"
    log = tmp_path / "ghost-log.md"
    pause = tmp_path / "post-review-pause.yaml"
    return install, manual, log, pause


def test_install_yaml_bootstrap_creates_with_today(tmp_path):
    install, _m, _l, _p = _paths(tmp_path)
    assert not install.exists()
    d = read_install_date(install)
    assert install.exists()
    today = datetime.now(UTC).date()
    assert d == today
    # Read again is idempotent
    d2 = read_install_date(install)
    assert d2 == d


def test_install_window_active_then_inactive(tmp_path):
    install, manual, log, pause = _paths(tmp_path)
    install_date = date(2026, 4, 17)
    install.write_text(f"install_date: {install_date.isoformat()}\n")

    # Day 0
    s = compute_ghost_state(
        install_date=install_date,
        now=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        manual_yaml_path=manual,
        ghost_review_log_path=log,
        post_review_pause_path=pause,
    )
    assert s.active and s.reason == "install_window"
    assert s.expected_end == datetime(2026, 4, 24, 0, 0, tzinfo=UTC)

    # Day 6 (still in window)
    s = compute_ghost_state(
        install_date=install_date,
        now=datetime(2026, 4, 23, 23, 59, tzinfo=UTC),
        manual_yaml_path=manual,
        ghost_review_log_path=log,
        post_review_pause_path=pause,
    )
    assert s.active and s.reason == "install_window"

    # Day 7 — window elapsed, no manual → inactive
    s = compute_ghost_state(
        install_date=install_date,
        now=datetime(2026, 4, 24, 0, 0, tzinfo=UTC),
        manual_yaml_path=manual,
        ghost_review_log_path=log,
        post_review_pause_path=pause,
    )
    assert not s.active and s.reason == ""


def test_manual_ghost_yaml_with_until(tmp_path):
    install, manual, log, pause = _paths(tmp_path)
    install_date = date(2026, 1, 1)  # well past the install window
    manual.write_text("active: true\nuntil: 2026-04-30\n")

    # Inside until
    s = compute_ghost_state(
        install_date=install_date,
        now=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
        manual_yaml_path=manual,
        ghost_review_log_path=log,
        post_review_pause_path=pause,
    )
    assert s.active and s.reason == "manual"
    assert s.expected_end == datetime(2026, 5, 1, 0, 0, tzinfo=UTC)

    # After until → inactive (manual clause expired)
    s = compute_ghost_state(
        install_date=install_date,
        now=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        manual_yaml_path=manual,
        ghost_review_log_path=log,
        post_review_pause_path=pause,
    )
    assert not s.active


def test_manual_ghost_open_ended(tmp_path):
    install, manual, log, pause = _paths(tmp_path)
    install_date = date(2026, 1, 1)
    manual.write_text("active: true\n")
    s = compute_ghost_state(
        install_date=install_date,
        now=datetime(2030, 1, 1, tzinfo=UTC),
        manual_yaml_path=manual,
        ghost_review_log_path=log,
        post_review_pause_path=pause,
    )
    assert s.active and s.reason == "manual"
    assert s.expected_end is None


def test_post_review_pause_marker(tmp_path):
    install, manual, log, pause = _paths(tmp_path)
    install_date = date(2026, 1, 1)
    pause.write_text("active: true\n")
    s = compute_ghost_state(
        install_date=install_date,
        now=datetime(2026, 6, 1, tzinfo=UTC),
        manual_yaml_path=manual,
        ghost_review_log_path=log,
        post_review_pause_path=pause,
    )
    assert s.active and s.reason == "post_review_pause"


def test_inactive_default(tmp_path):
    install, manual, log, pause = _paths(tmp_path)
    install_date = date(2026, 1, 1)
    s = compute_ghost_state(
        install_date=install_date,
        now=datetime(2026, 6, 1, tzinfo=UTC),
        manual_yaml_path=manual,
        ghost_review_log_path=log,
        post_review_pause_path=pause,
    )
    assert not s.active and s.reason == ""


def test_review_marker_roundtrip(tmp_path):
    log = tmp_path / "ghost-log.md"
    payload = mark_ghost_review_complete(
        log,
        now=datetime(2026, 4, 20, tzinfo=UTC),
        decisions=[
            {"offer_id": "o-1", "user_response": "accepted"},
            {"offer_id": "o-2", "user_response": "rejected", "reason": "noisy"},
        ],
        notes="first pass",
    )
    assert payload["accepts"] == 1
    assert payload["rejects"] == 1
    text = log.read_text()
    assert "Ghost review" in text
    assert "ghost_review_complete" in text


def test_write_install_field(tmp_path):
    p = tmp_path / "install.yaml"
    write_install_field(p, "ghost_exited_at", "2026-04-25T12:00:00Z")
    data = yaml.safe_load(p.read_text())
    assert data["ghost_exited_at"] == "2026-04-25T12:00:00Z"
