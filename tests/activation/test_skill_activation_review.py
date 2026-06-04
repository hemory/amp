"""Lightweight sanity tests for the activation-review SKILL.md."""

from __future__ import annotations

from pathlib import Path


SKILL_PATH = (
    Path(__file__).resolve().parents[2]
    / ".claude" / "skills" / "activation-review" / "SKILL.md"
)


def test_skill_file_exists():
    assert SKILL_PATH.exists(), f"missing: {SKILL_PATH}"


def test_skill_has_frontmatter():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    assert "name: activation-review" in text
    assert "description:" in text


def test_skill_mentions_required_subcommands():
    text = SKILL_PATH.read_text(encoding="utf-8")
    for sub in (
        "gather",
        "extract-prompt",
        "extract-apply",
        "rank",
        "draft-prompt",
        "draft-apply",
        "log",
        "acceptance-rate",
    ):
        assert sub in text, f"SKILL.md missing subcommand reference: {sub}"


def test_skill_mentions_safety_paths():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "System/activation/kill.yaml" in text
    assert "System/activation/quiet-mode.yaml" in text


def test_skill_has_required_section_headers():
    text = SKILL_PATH.read_text(encoding="utf-8")
    # Minimal structural expectations.
    for header in ("## Purpose", "## Process", "## Safety notes", "## Frontmatter / config"):
        assert header in text, f"missing header: {header}"


def test_skill_does_not_rewrite_daily_plan():
    text = SKILL_PATH.read_text(encoding="utf-8").lower()
    # Guardrail: the skill must not claim to modify /daily-plan.
    assert "does not modify /daily-plan" in text or "untouched" in text
