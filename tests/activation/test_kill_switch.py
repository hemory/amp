"""Kill-switch tests."""

from __future__ import annotations

import pytest

from core.activation.kill_switch import KillSwitchEngaged, is_killed, kill_status, raise_if_killed


def test_kill_off_by_default(activation_dir):
    kill_path = activation_dir / "kill.yaml"
    kill_path.write_text('disabled: false\nreason: ""\n', encoding="utf-8")
    assert is_killed() is False
    raise_if_killed()  # should not raise


def test_kill_on_raises(activation_dir):
    kill_path = activation_dir / "kill.yaml"
    kill_path.write_text('disabled: true\nreason: "debug"\n', encoding="utf-8")
    assert is_killed() is True
    killed, reason = kill_status()
    assert killed is True
    assert reason == "debug"
    with pytest.raises(KillSwitchEngaged) as ei:
        raise_if_killed()
    assert "debug" in str(ei.value)


def test_kill_missing_file_treated_as_off(activation_dir):
    kill_path = activation_dir / "kill.yaml"
    if kill_path.exists():
        kill_path.unlink()
    assert is_killed() is False
    raise_if_killed()


def test_kill_on_without_reason(activation_dir):
    kill_path = activation_dir / "kill.yaml"
    kill_path.write_text("disabled: true\n", encoding="utf-8")
    killed, reason = kill_status()
    assert killed is True
    assert reason is None
