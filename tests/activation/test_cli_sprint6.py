"""Sprint 6 — CLI smoke tests for ghost-status, ghost-review, ghost-exit."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _vault(tmp_path: Path, *, install_days_ago: int = 30) -> Path:
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    (act / "drafts").mkdir(parents=True)
    for n in ("signals.jsonl", "candidates.jsonl", "offers.jsonl", "tombstones.jsonl"):
        (act / n).touch()
    (act / "kill.yaml").write_text("disabled: false\n")
    install_date = (datetime.now(timezone.utc).date() - timedelta(days=install_days_ago))
    (act / "install.yaml").write_text(f"install_date: {install_date.isoformat()}\n")
    return vault


def _seed_held_offer(vault: Path):
    op = vault / "System" / "activation" / "offers.jsonl"
    row = {
        "offer_id": "o-h-001",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ritual": "daily-plan",
        "type": "meeting_followup",
        "shown": False,
        "summary": "send recap",
        "cited_signals": ["sig_x"],
        "score": 0.5,
        "hold_reason": "ghost:install_window",
    }
    op.write_text(json.dumps(row, sort_keys=True) + "\n")


def _run(vault: Path, *args):
    env = {"AMP_VAULT_ROOT": str(vault), "PATH": "/usr/bin:/bin", "PYTHONPATH": str(_REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "core.activation", *args],
        cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True, timeout=30,
    )


def test_ghost_status_json(tmp_path):
    vault = _vault(tmp_path, install_days_ago=2)
    r = _run(vault, "ghost-status", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["active"] is True
    assert payload["reason"] == "install_window"


def test_ghost_status_inactive(tmp_path):
    vault = _vault(tmp_path, install_days_ago=30)
    r = _run(vault, "ghost-status", "--json")
    assert r.returncode == 0
    assert json.loads(r.stdout)["active"] is False


def test_ghost_review_renders_and_archives(tmp_path):
    vault = _vault(tmp_path, install_days_ago=2)
    _seed_held_offer(vault)
    r = _run(vault, "ghost-review", "--window-days", "7")
    assert r.returncode == 0, r.stderr
    assert "Ghost-mode review digest" in r.stdout
    assert "send recap" in r.stdout
    archives = list((vault / "System" / "activation").glob("ghost-review-*.md"))
    assert len(archives) == 1


def test_ghost_review_no_write(tmp_path):
    vault = _vault(tmp_path, install_days_ago=2)
    _seed_held_offer(vault)
    r = _run(vault, "ghost-review", "--no-write")
    assert r.returncode == 0
    archives = list((vault / "System" / "activation").glob("ghost-review-*.md"))
    assert len(archives) == 0


def test_ghost_review_mark_complete_appends_marker(tmp_path):
    vault = _vault(tmp_path, install_days_ago=2)
    _seed_held_offer(vault)
    r = _run(vault, "ghost-review", "--mark-complete", "--notes", "first pass")
    assert r.returncode == 0
    log = (vault / "System" / "activation" / "ghost-log.md").read_text()
    assert "ghost_review_complete" in log
    assert "first pass" in log


def test_ghost_exit_without_acknowledge_exits_1(tmp_path):
    vault = _vault(tmp_path)
    r = _run(vault, "ghost-exit")
    assert r.returncode == 1
