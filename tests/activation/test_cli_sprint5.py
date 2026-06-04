"""Sprint 5 CLI smoke tests: replay, grade, rubric-check."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SAMPLE = _REPO_ROOT / "System" / "activation" / "replay" / "fixtures" / "sample-01"


def _run(vault: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        "AMP_VAULT_ROOT": str(vault),
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(_REPO_ROOT),
    }
    return subprocess.run(
        [sys.executable, "-m", "core.activation", *args],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    (act / "drafts").mkdir(parents=True)
    for n in ("signals.jsonl", "candidates.jsonl", "offers.jsonl", "tombstones.jsonl"):
        (act / n).touch()
    (act / "kill.yaml").write_text("disabled: false\n", encoding="utf-8")
    return vault


def _copy_sample_to_tmp(tmp_path: Path) -> Path:
    dest = tmp_path / "sample-01"
    shutil.copytree(_SAMPLE, dest)
    return dest


def test_replay_sample_fixture_prints_summary(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "replay", "--fixture", str(_SAMPLE))
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "replay fixture=sample-01" in out
    assert "candidates=3" in out
    assert "rejected=1" in out
    assert "offers=3" in out
    # Calibration reported with 3 grades.
    assert "calibration:" in out
    assert "pearson_r=" in out or "undefined" in out


def test_replay_json_mode_parses(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "replay", "--fixture", str(_SAMPLE), "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["fixture_id"] == "sample-01"
    assert data["summary"]["n_offers"] == 3
    assert data["summary"]["n_rejections"] == 1
    assert "scorecard" in data
    assert "calibration" in data
    assert data["calibration"]["n"] == 3


def test_grade_appends_to_fixture_grades(tmp_path):
    vault = _make_vault(tmp_path)
    fixture = _copy_sample_to_tmp(tmp_path)
    before = (fixture / "grades.jsonl").read_text(encoding="utf-8").splitlines()
    result = _run(
        vault,
        "grade",
        "--fixture",
        str(fixture),
        "--offer-id",
        "o-test-0001",
        "--score",
        "0.77",
        "--reason",
        "CLI smoke",
        "--grader",
        "user",
    )
    assert result.returncode == 0, result.stderr
    after = (fixture / "grades.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(after) == len(before) + 1
    row = json.loads(after[-1])
    assert row["offer_id"] == "o-test-0001"
    assert row["human_score"] == 0.77
    assert row["grader"] == "user"


def test_rubric_check_on_live_offer(tmp_path):
    vault = _make_vault(tmp_path)
    act = vault / "System" / "activation"
    # Seed a minimal live offer + signal.
    sig = {
        "signal_id": "sig_live",
        "source": "meeting_notes",
        "path": "04-Projects/X/m.md",
        "timestamp": "2026-04-18T10:00:00Z",
        "excerpt": "Schedule review with J.Park on 2026-04-20.",
    }
    (act / "signals.jsonl").write_text(
        json.dumps(sig, sort_keys=True) + "\n", encoding="utf-8"
    )
    offer = {
        "offer_id": "o_live_001",
        "created_at": "2026-04-19T09:00:00Z",
        "ritual": "daily-plan",
        "type": "meeting_followup",
        "shown": True,
        "summary": "Schedule review with J.Park on 2026-04-20",
        "cited_signals": ["sig_live"],
        "score": 0.9,
        "candidate_id": None,
        "hold_reason": None,
        "draft_artifact_path": None,
        "score_components": {},
        "user_response": None,
        "response_timestamp": None,
        "time_to_response_s": None,
        "edit_distance_if_accepted": None,
        "notes": None,
    }
    (act / "offers.jsonl").write_text(
        json.dumps(offer, sort_keys=True) + "\n", encoding="utf-8"
    )
    result = _run(vault, "rubric-check", "--offer-id", "o_live_001", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["offer_id"] == "o_live_001"
    assert 0.0 <= data["overall"] <= 1.0
    # Well-formed, citation-backed, concrete offer → high overall.
    assert data["citation_discipline"] == 1.0
    assert data["specificity"] == 1.0


def test_rubric_check_unknown_offer_returns_2(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "rubric-check", "--offer-id", "does_not_exist")
    assert result.returncode == 2
    assert "offer not found" in result.stderr


def test_replay_missing_fixture_returns_2(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "replay", "--fixture", str(tmp_path / "nope"))
    assert result.returncode == 2
    assert "error:" in result.stderr


def test_replay_kill_switch_honored(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "System" / "activation" / "kill.yaml").write_text(
        "disabled: true\nreason: test\n", encoding="utf-8"
    )
    result = _run(vault, "replay", "--fixture", str(_SAMPLE))
    assert result.returncode == 0
    assert "kill-switch engaged" in result.stdout
