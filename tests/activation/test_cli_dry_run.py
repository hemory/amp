"""CLI subprocess tests for `python -m core.activation run`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_tmp_vault(tmp_path: Path, *, kill_disabled: bool = False) -> Path:
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    (act / "drafts").mkdir(parents=True)
    (act / "kill.yaml").write_text(
        f"disabled: {'true' if kill_disabled else 'false'}\nreason: {'debug-test' if kill_disabled else ''}\n",
        encoding="utf-8",
    )
    (act / "weights.yaml").write_text(
        "w1_confidence: 1.0\nw2_recency: 0.6\nw3_commitment: 1.2\n"
        "w4_user_priority: 0.8\nw5_recent_offer_penalty: 0.5\nw6_rejection_penalty: 0.7\n",
        encoding="utf-8",
    )
    return vault


def _run_cli(vault: Path, *args: str) -> subprocess.CompletedProcess:
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


def test_cli_dry_run_exits_zero_and_prints_summary(tmp_path: Path):
    vault = _make_tmp_vault(tmp_path)
    result = _run_cli(vault, "run", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "dry-run config snapshot" in result.stdout
    assert "w1_confidence" in result.stdout
    assert str(vault) in result.stdout
    assert "kill" in result.stdout
    assert "quiet" in result.stdout


def test_cli_run_without_dry_run_prints_skeleton_message(tmp_path: Path):
    vault = _make_tmp_vault(tmp_path)
    result = _run_cli(vault, "run")
    assert result.returncode == 0, result.stderr
    assert "pipeline not yet wired" in result.stdout
    assert "2 of 7" in result.stdout


def test_cli_kill_switch_short_circuits(tmp_path: Path):
    vault = _make_tmp_vault(tmp_path, kill_disabled=True)
    result = _run_cli(vault, "run")
    assert result.returncode == 0, result.stderr
    assert "kill-switch engaged" in result.stdout
    assert "debug-test" in result.stdout
    # Must not have run the regular pipeline message.
    assert "pipeline not yet wired" not in result.stdout


def test_cli_kill_switch_short_circuits_even_with_dry_run(tmp_path: Path):
    vault = _make_tmp_vault(tmp_path, kill_disabled=True)
    result = _run_cli(vault, "run", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "kill-switch engaged" in result.stdout
    assert "dry-run config snapshot" not in result.stdout


def test_cli_quiet_mode_short_circuits(tmp_path: Path):
    vault = _make_tmp_vault(tmp_path)
    (vault / "System" / "activation" / "quiet-mode.yaml").write_text(
        "until: 2099-12-31\nreason: long vacation\n", encoding="utf-8"
    )
    result = _run_cli(vault, "run")
    assert result.returncode == 0, result.stderr
    assert "quiet mode until 2099-12-31" in result.stdout
    assert "long vacation" in result.stdout
