"""Sprint 6 — rank.rank() honors explicit GhostState; CLI auto-passes one."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.activation.ghost import GhostState
from core.activation.rank import rank
from core.activation.schemas import Candidate


_REPO_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _candidate(i: int) -> Candidate:
    return Candidate(
        candidate_id=f"c{i:03d}",
        type="meeting_followup",
        summary=f"do thing {i}",
        cited_signals=[f"sig_{i}"],
        confidence=0.8,
        staleness_days=0,
        action_verb="send",
    )


def test_explicit_ghost_state_overrides_days_since_install():
    cands = [_candidate(0)]
    state = GhostState(
        active=True, reason="install_window",
        started_at=NOW - timedelta(days=2),
        expected_end=NOW + timedelta(days=5),
    )
    offers = rank(
        cands, now=NOW, offers_log=[], tombstones=[], weights={},
        recent_acceptance_rate=None,
        days_since_install=999,  # well past install window
        ghost_state=state,
    )
    assert offers[0].hold_reason == "ghost:install_window"
    assert offers[0].shown is False


def test_explicit_inactive_ghost_state_unblocks():
    cands = [_candidate(0)]
    state = GhostState(active=False, reason="", started_at=NOW)
    offers = rank(
        cands, now=NOW, offers_log=[], tombstones=[], weights={},
        recent_acceptance_rate=0.7,  # high enough for nonzero budget
        days_since_install=0,  # would normally trigger ghost
        ghost_state=state,
    )
    assert offers[0].shown is True
    assert offers[0].hold_reason is None


def test_legacy_no_ghost_state_keeps_plain_ghost_label():
    cands = [_candidate(0)]
    offers = rank(
        cands, now=NOW, offers_log=[], tombstones=[], weights={},
        recent_acceptance_rate=None, days_since_install=0,
    )
    assert offers[0].hold_reason == "ghost"


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    (act / "drafts").mkdir(parents=True)
    for n in ("signals.jsonl", "candidates.jsonl", "offers.jsonl", "tombstones.jsonl"):
        (act / n).touch()
    (act / "kill.yaml").write_text("disabled: false\n")
    cand = _candidate(0)
    (act / "candidates.jsonl").write_text(
        json.dumps(cand.to_dict(), sort_keys=True) + "\n"
    )
    return vault


def _run(vault: Path, *args):
    env = {"AMP_VAULT_ROOT": str(vault), "PATH": "/usr/bin:/bin", "PYTHONPATH": str(_REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "core.activation", *args],
        cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True, timeout=30,
    )


def test_cli_rank_auto_passes_install_window_state(tmp_path):
    """Fresh vault: install.yaml is bootstrapped to today → install_window ghost."""
    vault = _make_vault(tmp_path)
    r = _run(vault, "rank", "--days-since-install", "0")
    assert r.returncode == 0, r.stderr
    rows = [
        json.loads(l)
        for l in (vault / "System" / "activation" / "offers.jsonl").read_text().splitlines()
        if l.strip()
    ]
    assert rows
    assert rows[0]["hold_reason"] == "ghost:install_window"
