"""Pure read functions for activation YAML config files.

No side effects. No caching. Callers decide when to reload.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from . import paths


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at top of {path}, got {type(data).__name__}")
    return data


def load_weights(path: Path | None = None) -> Dict[str, float]:
    """Load ranker weights. Returns empty dict if file missing."""
    p = path if path is not None else paths.WEIGHTS_PATH
    data = _read_yaml(p)
    return {k: float(v) for k, v in data.items()}


def load_kill(path: Path | None = None) -> Dict[str, Any]:
    """Load kill-switch config. Returns {} if missing (treated as OFF)."""
    p = path if path is not None else paths.KILL_PATH
    return _read_yaml(p)


def load_quiet(path: Path | None = None) -> Dict[str, Any]:
    """Load quiet-mode config. Returns {} if missing (treated as not-quiet)."""
    p = path if path is not None else paths.QUIET_PATH
    return _read_yaml(p)


def load_config() -> Dict[str, Any]:
    """Load a consolidated snapshot of all config. Pure read."""
    return {
        "vault_root": str(paths.VAULT_ROOT),
        "activation_dir": str(paths.ACTIVATION_DIR),
        "weights": load_weights(),
        "kill": load_kill(),
        "quiet": load_quiet(),
    }


__all__ = ["load_weights", "load_kill", "load_quiet", "load_config"]
