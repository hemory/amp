"""Subprocess tests for `python -m core.activation gather`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    (act / "drafts").mkdir(parents=True)
    for n in ("signals.jsonl", "candidates.jsonl", "offers.jsonl", "tombstones.jsonl"):
        (act / n).touch()
    (act / "kill.yaml").write_text("disabled: false\n", encoding="utf-8")
    (act / "weights.yaml").write_text("w1_confidence: 1.0\n", encoding="utf-8")
    # A single meeting note so summary is non-empty.
    mn = vault / "04-Projects" / "Demo" / "meeting-notes.md"
    mn.parent.mkdir(parents=True, exist_ok=True)
    mn.write_text("# demo\nAction: ship it.\n", encoding="utf-8")
    return vault


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


def test_gather_dry_run_exits_zero_prints_summary(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "gather", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "gather summary" in result.stdout
    assert "total_signals" in result.stdout
    assert "by_source" in result.stdout
    assert "wrote_file:    False" in result.stdout
    # signals.jsonl must stay empty (dry-run).
    assert (vault / "System" / "activation" / "signals.jsonl").stat().st_size == 0


def test_gather_real_run_writes_signals_file(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "gather")
    assert result.returncode == 0, result.stderr
    assert "wrote_file:    True" in result.stdout
    sig_path = vault / "System" / "activation" / "signals.jsonl"
    contents = sig_path.read_text(encoding="utf-8")
    assert contents.strip(), "signals.jsonl should contain at least one row"


def test_gather_kill_switch_short_circuits(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "System" / "activation" / "kill.yaml").write_text(
        "disabled: true\nreason: debugging\n", encoding="utf-8"
    )
    result = _run(vault, "gather")
    assert result.returncode == 0, result.stderr
    assert "kill-switch engaged" in result.stdout
    assert "gather summary" not in result.stdout


def test_gather_quiet_mode_short_circuits(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "System" / "activation" / "quiet-mode.yaml").write_text(
        "until: 2099-12-31\nreason: long vacation\n", encoding="utf-8"
    )
    result = _run(vault, "gather")
    assert result.returncode == 0, result.stderr
    assert "quiet mode until 2099-12-31" in result.stdout
    assert "gather summary" not in result.stdout
