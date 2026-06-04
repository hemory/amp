"""Quiet-mode tests."""

from __future__ import annotations

from datetime import date

from core.activation.quiet_mode import is_quiet, quiet_status


def test_quiet_no_file(activation_dir):
    qpath = activation_dir / "quiet-mode.yaml"
    if qpath.exists():
        qpath.unlink()
    quiet, reason = is_quiet()
    assert quiet is False
    assert reason is None


def test_quiet_past_until_is_off(activation_dir):
    (activation_dir / "quiet-mode.yaml").write_text(
        "until: 2020-01-01\nreason: old vacation\n", encoding="utf-8"
    )
    quiet, reason = is_quiet(today=date(2026, 4, 17))
    assert quiet is False


def test_quiet_future_until_is_on(activation_dir):
    (activation_dir / "quiet-mode.yaml").write_text(
        "until: 2099-12-31\nreason: sabbatical\n", encoding="utf-8"
    )
    quiet, reason, until = quiet_status(today=date(2026, 4, 17))
    assert quiet is True
    assert reason == "sabbatical"
    assert until == date(2099, 12, 31)


def test_quiet_today_equals_until_is_on(activation_dir):
    (activation_dir / "quiet-mode.yaml").write_text(
        "until: 2026-04-17\n", encoding="utf-8"
    )
    quiet, _, _ = quiet_status(today=date(2026, 4, 17))
    assert quiet is True


def test_quiet_malformed_yaml_fails_open(activation_dir):
    (activation_dir / "quiet-mode.yaml").write_text(
        "until: [this is: not valid\n:::", encoding="utf-8"
    )
    quiet, reason = is_quiet(today=date(2026, 4, 17))
    assert quiet is False
    assert reason is None


def test_quiet_missing_until_field_is_off(activation_dir):
    (activation_dir / "quiet-mode.yaml").write_text(
        "reason: forgot to set date\n", encoding="utf-8"
    )
    quiet, _ = is_quiet(today=date(2026, 4, 17))
    assert quiet is False
