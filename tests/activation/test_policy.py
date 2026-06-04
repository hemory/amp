"""Sprint 7 — policy hash + auto post-review-pause."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from core.activation.policy import compute_policy_hash, policy_check


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    act.mkdir(parents=True)
    (act / "weights.yaml").write_text("w1_confidence: 1.0\n", encoding="utf-8")
    (act / "grounding.yaml").write_text(
        "extract:\n  min_overlap: 0.4\n  min_anchored_tokens: 2\n",
        encoding="utf-8",
    )
    # Identity bundle (5 files referenced by policy._IDENTITY_PARTS).
    idroot = vault / "System" / "identity"
    (idroot / "amp").mkdir(parents=True)
    (idroot / "user").mkdir(parents=True)
    (idroot / "amp" / "SOUL.md").write_text("amp soul", encoding="utf-8")
    (idroot / "amp" / "STYLE.md").write_text("amp style", encoding="utf-8")
    (idroot / "user" / "SOUL.md").write_text("user soul", encoding="utf-8")
    (idroot / "user" / "STYLE.md").write_text("user style", encoding="utf-8")
    (idroot / "README.md").write_text("identity readme", encoding="utf-8")
    return vault


def test_compute_policy_hash_stable(tmp_path):
    vault = _make_vault(tmp_path)
    h1 = compute_policy_hash(vault)
    h2 = compute_policy_hash(vault)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_identity_change_changes_hash(tmp_path):
    vault = _make_vault(tmp_path)
    h1 = compute_policy_hash(vault)
    (vault / "System" / "identity" / "amp" / "SOUL.md").write_text("AMP SOUL v2",
                                                                    encoding="utf-8")
    h2 = compute_policy_hash(vault)
    assert h1 != h2


def test_first_check_establishes_baseline(tmp_path):
    vault = _make_vault(tmp_path)
    state = vault / "System" / "activation" / "policy-state.yaml"
    pause = vault / "System" / "activation" / "post-review-pause.yaml"
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    result = policy_check(
        vault_root=vault, state_path=state, pause_path=pause,
        now=now, acknowledge=False,
    )
    assert state.exists()
    assert not pause.exists()  # no change to react to
    assert not result.changed
    assert result.pause_until is None


def test_policy_change_writes_pause(tmp_path):
    vault = _make_vault(tmp_path)
    state = vault / "System" / "activation" / "policy-state.yaml"
    pause = vault / "System" / "activation" / "post-review-pause.yaml"
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    # Establish baseline.
    policy_check(vault_root=vault, state_path=state, pause_path=pause, now=now)
    # Tweak weights.
    (vault / "System" / "activation" / "weights.yaml").write_text(
        "w1_confidence: 2.0\n", encoding="utf-8",
    )
    result = policy_check(vault_root=vault, state_path=state, pause_path=pause,
                          now=now)
    assert result.changed
    assert result.pause_until is not None
    assert pause.exists()
    data = yaml.safe_load(pause.read_text(encoding="utf-8"))
    assert data.get("active") is True


def test_acknowledge_clears_pause_and_refreshes(tmp_path):
    vault = _make_vault(tmp_path)
    state = vault / "System" / "activation" / "policy-state.yaml"
    pause = vault / "System" / "activation" / "post-review-pause.yaml"
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    policy_check(vault_root=vault, state_path=state, pause_path=pause, now=now)
    (vault / "System" / "activation" / "weights.yaml").write_text(
        "w1_confidence: 2.0\n", encoding="utf-8",
    )
    policy_check(vault_root=vault, state_path=state, pause_path=pause, now=now)
    assert pause.exists()
    # Acknowledge — clears pause and rebaselines.
    result = policy_check(vault_root=vault, state_path=state, pause_path=pause,
                          now=now, acknowledge=True)
    assert "acknowledged" in result.notice
    assert not pause.exists()
    # Subsequent check sees no change.
    r2 = policy_check(vault_root=vault, state_path=state, pause_path=pause,
                      now=now, acknowledge=False)
    assert not r2.changed
