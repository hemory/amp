"""Fixture loader tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.activation.replay import FixtureError, load_fixture


_SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "System" / "activation" / "replay" / "fixtures" / "sample-01"
)


def test_sample_fixture_loads():
    fx = load_fixture(_SAMPLE)
    assert fx.fixture_id == "sample-01"
    assert len(fx.signals) == 8
    assert len(fx.extract_response) == 4
    # Two recorded draft responses.
    assert len(fx.draft_responses) == 2
    assert fx.days_since_install == 30
    assert fx.acceptance_rate == 0.65
    assert fx.ghost is False
    assert fx.now().year == 2026
    assert len(fx.grades) == 3


def test_missing_meta_raises(tmp_path: Path):
    d = tmp_path / "fx"
    d.mkdir()
    (d / "signals.jsonl").write_text("", encoding="utf-8")
    (d / "extract_response.json").write_text("[]", encoding="utf-8")
    with pytest.raises(FixtureError, match="missing meta.yaml"):
        load_fixture(d)


def test_malformed_meta_raises(tmp_path: Path):
    d = tmp_path / "fx"
    d.mkdir()
    (d / "meta.yaml").write_text(": not: valid: yaml:\n - [\n", encoding="utf-8")
    (d / "signals.jsonl").write_text("", encoding="utf-8")
    (d / "extract_response.json").write_text("[]", encoding="utf-8")
    with pytest.raises(FixtureError):
        load_fixture(d)


def test_meta_missing_required_key_raises(tmp_path: Path):
    d = tmp_path / "fx"
    d.mkdir()
    (d / "meta.yaml").write_text(
        "id: x\ndescription: x\ncreated_at: '2026-01-01T00:00:00Z'\n",
        encoding="utf-8",
    )
    (d / "signals.jsonl").write_text("", encoding="utf-8")
    (d / "extract_response.json").write_text("[]", encoding="utf-8")
    with pytest.raises(FixtureError, match="missing required key"):
        load_fixture(d)


def test_missing_optional_files_ok(tmp_path: Path):
    d = tmp_path / "fx"
    d.mkdir()
    (d / "meta.yaml").write_text(
        "id: tiny\ndescription: tiny\ncreated_at: '2026-01-01T00:00:00Z'\n"
        "now: '2026-01-01T00:00:00Z'\ndays_since_install: 10\n",
        encoding="utf-8",
    )
    (d / "signals.jsonl").write_text("", encoding="utf-8")
    (d / "extract_response.json").write_text("[]", encoding="utf-8")
    fx = load_fixture(d)
    assert fx.draft_responses == {}
    assert fx.prior_offers == []
    assert fx.prior_tombstones == []
    assert fx.grades == []


def test_missing_signals_file_raises(tmp_path: Path):
    d = tmp_path / "fx"
    d.mkdir()
    (d / "meta.yaml").write_text(
        "id: x\ndescription: x\ncreated_at: '2026-01-01T00:00:00Z'\n"
        "now: '2026-01-01T00:00:00Z'\ndays_since_install: 10\n",
        encoding="utf-8",
    )
    (d / "extract_response.json").write_text("[]", encoding="utf-8")
    with pytest.raises(FixtureError, match="missing signals"):
        load_fixture(d)


def test_not_a_directory_raises(tmp_path: Path):
    f = tmp_path / "not-a-dir"
    f.write_text("", encoding="utf-8")
    with pytest.raises(FixtureError):
        load_fixture(f)
