"""Sprint 6/7 — ghost-exit refusal & success paths via subprocess.

Sprint 7 H4 hardened the predicates: ≥3 distinct review days AND ≥5 total
decided offers (accepted/accepted_with_edits/rejected/never_again). The
single-marker tests have been updated to seed enough markers to satisfy
the new gate; the refusal tests target individual predicate failures.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from core.activation.ghost import mark_ghost_review_complete


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _vault(tmp_path: Path, *, install_days_ago: int = 30, manual_active: bool = False) -> Path:
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    (act / "drafts").mkdir(parents=True)
    for n in ("signals.jsonl", "candidates.jsonl", "offers.jsonl", "tombstones.jsonl"):
        (act / n).touch()
    (act / "kill.yaml").write_text("disabled: false\n")
    install_date = (datetime.now(timezone.utc).date() - timedelta(days=install_days_ago))
    (act / "install.yaml").write_text(f"install_date: {install_date.isoformat()}\n")
    if manual_active:
        (act / "ghost-mode.yaml").write_text("active: true\n")
    return vault


def _run(vault: Path, *args):
    env = {"AMP_VAULT_ROOT": str(vault), "PATH": "/usr/bin:/bin", "PYTHONPATH": str(_REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "core.activation", *args],
        cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True, timeout=30,
    )


def _add_review_marker(vault: Path, days_ago: int = 0, decisions=None):
    log = vault / "System" / "activation" / "ghost-log.md"
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    mark_ghost_review_complete(
        log, now=when,
        decisions=decisions or [{"offer_id": "o-x", "user_response": "accepted"}],
    )


def _seed_h4_satisfied(vault: Path):
    """Seed 3 distinct calendar days × 2 decided offers each = 6 decided.
    Satisfies P4 (≥3 days) and P5 (≥5 decided)."""
    _add_review_marker(vault, days_ago=0, decisions=[
        {"offer_id": "o-a", "user_response": "accepted"},
        {"offer_id": "o-b", "user_response": "rejected"},
    ])
    _add_review_marker(vault, days_ago=2, decisions=[
        {"offer_id": "o-c", "user_response": "accepted"},
        {"offer_id": "o-d", "user_response": "rejected"},
    ])
    _add_review_marker(vault, days_ago=4, decisions=[
        {"offer_id": "o-e", "user_response": "accepted"},
        {"offer_id": "o-f", "user_response": "never_again"},
    ])


def test_refuses_without_acknowledge(tmp_path):
    vault = _vault(tmp_path)
    _seed_h4_satisfied(vault)
    r = _run(vault, "ghost-exit")
    assert r.returncode == 1
    assert "--acknowledge" in r.stderr


def test_refuses_without_prior_review(tmp_path):
    vault = _vault(tmp_path)
    r = _run(vault, "ghost-exit", "--acknowledge")
    assert r.returncode == 1
    # H4: P4 (distinct review days) fails when no markers exist.
    assert "P4_distinct_review_days_ge_3" in r.stderr
    assert "FAIL" in r.stderr


def test_refuses_when_install_window_not_elapsed(tmp_path):
    vault = _vault(tmp_path, install_days_ago=2)
    _seed_h4_satisfied(vault)
    r = _run(vault, "ghost-exit", "--acknowledge")
    assert r.returncode == 1
    assert "P1_install_window_elapsed" in r.stderr


def test_refuses_when_manual_ghost_set(tmp_path):
    vault = _vault(tmp_path, manual_active=True)
    _seed_h4_satisfied(vault)
    r = _run(vault, "ghost-exit", "--acknowledge")
    assert r.returncode == 1
    assert "P2_no_manual_ghost" in r.stderr


def test_succeeds_when_criteria_met(tmp_path):
    vault = _vault(tmp_path)
    _seed_h4_satisfied(vault)
    r = _run(vault, "ghost-exit", "--acknowledge")
    assert r.returncode == 0, r.stderr
    install = yaml.safe_load((vault / "System" / "activation" / "install.yaml").read_text())
    assert "ghost_exited_at" in install


def test_idempotent(tmp_path):
    vault = _vault(tmp_path)
    _seed_h4_satisfied(vault)
    r1 = _run(vault, "ghost-exit", "--acknowledge")
    assert r1.returncode == 0
    r2 = _run(vault, "ghost-exit", "--acknowledge")
    assert r2.returncode == 0


def test_force_bypasses_predicate_gate(tmp_path):
    """Sprint 7 H4: --force lets operator override after manual audit."""
    vault = _vault(tmp_path)
    # No review markers — would normally fail P4/P5.
    r = _run(vault, "ghost-exit", "--acknowledge", "--force")
    assert r.returncode == 0, r.stderr
