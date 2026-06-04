"""Sprint 7 C2 — online grounding gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.activation.grounding import (
    GroundingResult,
    check_grounding,
    load_thresholds,
    thresholds_for,
)


def test_passes_when_summary_overlaps_excerpt():
    r = check_grounding(
        "Schedule 30 min with Alex to finalize the Reel timeline.",
        ["Action: the user to schedule 30 min with Alex to finalize Reel #3 timeline by Friday."],
    )
    assert r.passed
    assert r.overlap_ratio >= 0.4


def test_fails_when_summary_introduces_new_concepts():
    r = check_grounding(
        "I can pull yesterday's pillar notes and session learnings into the skeleton.",
        ["Q2 narrative due 2026-04-20. No progress in five days."],
    )
    assert not r.passed
    assert any("pillar" in t for t in r.unanchored_tokens) or r.overlap_ratio < 0.4


def test_passes_vacuously_when_no_claim_tokens():
    r = check_grounding("ok ok ok", ["any excerpt"])
    assert r.passed


def test_date_tokens_use_substring_fallback():
    r = check_grounding(
        "Send recap by 2026-04-20.",
        ["due 2026-04-20"],
    )
    assert r.passed


def test_thresholds_for_extract_default():
    overlap, anchored = thresholds_for("extract", None)
    assert 0.0 < overlap <= 1.0
    assert anchored >= 1


def test_thresholds_for_draft_default():
    overlap, anchored = thresholds_for("draft", None)
    assert anchored >= 1


def test_thresholds_loaded_from_file(tmp_path: Path):
    p = tmp_path / "grounding.yaml"
    p.write_text(
        "extract:\n  min_overlap: 0.55\n  min_anchored_tokens: 4\n"
        "draft:\n  min_overlap: 0.65\n  min_anchored_tokens: 5\n",
        encoding="utf-8",
    )
    overlap, anchored = thresholds_for("extract", p)
    assert overlap == 0.55
    assert anchored == 4
    overlap, anchored = thresholds_for("draft", p)
    assert overlap == 0.65
    assert anchored == 5


def test_no_citations_fails():
    r = check_grounding("Send recap to Alex today.", [])
    # No corpus → cannot anchor anything.
    assert not r.passed


def test_load_thresholds_returns_dict_default():
    d = load_thresholds(None)
    assert "extract" in d and "draft" in d
