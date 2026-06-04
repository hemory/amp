"""Kill switch for the Activation Engine. §9.4 of design doc.

`System/activation/kill.yaml` with `disabled: true` disables the entire
engine. Missing file is treated as OFF (engine enabled).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from .config import load_kill


class KillSwitchEngaged(RuntimeError):
    """Raised by raise_if_killed() when the kill switch is set."""

    def __init__(self, reason: Optional[str] = None):
        self.reason = reason or ""
        super().__init__(f"kill-switch engaged: {self.reason}" if self.reason else "kill-switch engaged")


def kill_status(path: Path | None = None) -> Tuple[bool, Optional[str]]:
    """Return (is_killed, reason)."""
    data = load_kill(path)
    disabled = bool(data.get("disabled", False))
    reason = data.get("reason") or None
    if isinstance(reason, str) and not reason.strip():
        reason = None
    return disabled, reason


def is_killed(path: Path | None = None) -> bool:
    """True if the engine is disabled via kill.yaml."""
    killed, _ = kill_status(path)
    return killed


def raise_if_killed(path: Path | None = None) -> None:
    """Raise KillSwitchEngaged if disabled."""
    killed, reason = kill_status(path)
    if killed:
        raise KillSwitchEngaged(reason)


__all__ = ["is_killed", "raise_if_killed", "kill_status", "KillSwitchEngaged"]
