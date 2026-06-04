"""Sprint 7 — CLI smoke for new subcommands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    act = v / "System" / "activation"
    act.mkdir(parents=True)
    (act / "kill.yaml").write_text("disabled: false\n", encoding="utf-8")
    # Identity
    idd = v / "System" / "identity"
    (idd / "amp").mkdir(parents=True)
    (idd / "user").mkdir(parents=True)
    (idd / "amp" / "SOUL.md").write_text("amp soul", encoding="utf-8")
    (idd / "amp" / "STYLE.md").write_text("amp style", encoding="utf-8")
    (idd / "user" / "SOUL.md").write_text("user soul", encoding="utf-8")
    (idd / "user" / "STYLE.md").write_text("user style", encoding="utf-8")
    (idd / "README.md").write_text("overview", encoding="utf-8")
    (act / "weights.yaml").write_text("w1_confidence: 1.0\n", encoding="utf-8")
    (act / "grounding.yaml").write_text(
        "extract:\n  min_overlap: 0.4\n  min_anchored_tokens: 2\n",
        encoding="utf-8",
    )
    return v


def _run(vault: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        "AMP_VAULT_ROOT": str(vault),
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(_REPO_ROOT),
    }
    return subprocess.run(
        [sys.executable, "-m", "core.activation", *args],
        cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True,
        timeout=30,
    )


def test_handshake_gc_no_dir(tmp_path):
    v = _vault(tmp_path)
    r = _run(v, "handshake-gc", "--older-than-days", "7")
    assert r.returncode == 0, r.stderr


def test_handshake_gc_removes_old(tmp_path):
    v = _vault(tmp_path)
    hs = v / "System" / "activation" / "handshakes"
    hs.mkdir()
    old = hs / "extract-old.json"
    old.write_text("{}", encoding="utf-8")
    import os
    import time
    backdated = time.time() - 14 * 86400
    os.utime(old, (backdated, backdated))
    r = _run(v, "handshake-gc", "--older-than-days", "7")
    assert r.returncode == 0, r.stderr
    assert not old.exists()


def test_policy_check_first_run(tmp_path):
    v = _vault(tmp_path)
    r = _run(v, "policy-check")
    assert r.returncode == 0, r.stderr
    state = v / "System" / "activation" / "policy-state.yaml"
    assert state.exists()


def test_policy_check_detects_change(tmp_path):
    v = _vault(tmp_path)
    _run(v, "policy-check")
    (v / "System" / "activation" / "weights.yaml").write_text(
        "w1_confidence: 99.0\n", encoding="utf-8",
    )
    r = _run(v, "policy-check")
    assert r.returncode == 0, r.stderr
    pause = v / "System" / "activation" / "post-review-pause.yaml"
    assert pause.exists()
    # Acknowledge clears.
    r2 = _run(v, "policy-check", "--acknowledge")
    assert r2.returncode == 0, r2.stderr
    assert not pause.exists()


def test_weekly_metrics_empty_vault(tmp_path):
    v = _vault(tmp_path)
    r = _run(v, "weekly-metrics", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "offers_proposed" in data
    assert data["offers_proposed"] == 0


def test_ghost_status_check_exit_ready_outputs_predicates(tmp_path):
    v = _vault(tmp_path)
    # Bootstrap install first via ghost-status.
    _run(v, "ghost-status")
    r = _run(v, "ghost-status", "--check-exit-ready")
    assert r.returncode == 0, r.stderr
    assert "P1" in r.stdout or "P1" in r.stderr


def test_log_never_again_creates_tombstone(tmp_path):
    v = _vault(tmp_path)
    act = v / "System" / "activation"
    offer = {
        "offer_id": "o-1", "created_at": "2026-04-17T07:00:00Z",
        "ritual": "daily-plan", "type": "meeting_followup", "shown": True,
        "summary": "Send recap", "cited_signals": ["sig_0"], "score": 0.8,
        "candidate_id": "c_001", "hold_reason": None,
        "draft_artifact_path": None, "score_components": {},
        "user_response": None, "response_timestamp": None,
        "time_to_response_s": None, "edit_distance_if_accepted": None,
        "notes": None,
    }
    (act / "offers.jsonl").write_text(
        json.dumps(offer, sort_keys=True) + "\n", encoding="utf-8",
    )
    r = _run(v, "log", "--offer-id", "o-1", "--response", "never_again")
    assert r.returncode == 0, r.stderr
    tombs = (act / "tombstones.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(tombs) == 1
    assert "never_again" in (act / "response-events.jsonl").read_text(encoding="utf-8")
