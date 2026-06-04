"""Sprint 6 — SKILL.md must contain the ghost-mode flow section."""

from __future__ import annotations

from pathlib import Path


SKILL_PATH = (
    Path(__file__).resolve().parents[2]
    / ".claude" / "skills" / "activation-review" / "SKILL.md"
)


def test_skill_has_ghost_mode_flow_section():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "## Ghost-mode flow" in text
    for cmd in ("ghost-status", "ghost-review", "ghost-exit"):
        assert cmd in text, f"SKILL.md missing reference to {cmd}"


def test_skill_still_says_daily_plan_untouched():
    text = SKILL_PATH.read_text(encoding="utf-8").lower()
    assert "does not modify /daily-plan" in text or "untouched" in text


def test_skill_mentions_ghost_exit_acknowledge():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "--acknowledge" in text


def test_skill_documents_ghost_state_reasons():
    text = SKILL_PATH.read_text(encoding="utf-8")
    for reason in ("install_window", "manual", "post_review_pause"):
        assert reason in text, f"SKILL.md missing ghost reason: {reason}"
