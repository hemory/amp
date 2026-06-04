"""Path resolution for the Activation Engine.

Resolves the vault root by looking for a `System/` sibling starting from the
package directory and walking upward. Can be overridden with the
`AMP_VAULT_ROOT` environment variable (primarily for tests).

All paths are computed as module-level constants from a single `VAULT_ROOT`.
Injecting paths during tests is done by setting `AMP_VAULT_ROOT` and
reloading this module (see `tests/activation/conftest.py`).
"""

from __future__ import annotations

import os
from pathlib import Path


def _resolve_vault_root() -> Path:
    env = os.environ.get("AMP_VAULT_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    # Walk upward from this file looking for a sibling `System/` directory.
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "System").is_dir():
            return parent
    # Fallback: two levels up from core/activation/paths.py
    return here.parents[2]


VAULT_ROOT: Path = _resolve_vault_root()
ACTIVATION_DIR: Path = VAULT_ROOT / "System" / "activation"

SIGNALS_PATH: Path = ACTIVATION_DIR / "signals.jsonl"
CANDIDATES_PATH: Path = ACTIVATION_DIR / "candidates.jsonl"
OFFERS_PATH: Path = ACTIVATION_DIR / "offers.jsonl"
TOMBSTONES_PATH: Path = ACTIVATION_DIR / "tombstones.jsonl"
WEIGHTS_PATH: Path = ACTIVATION_DIR / "weights.yaml"
KILL_PATH: Path = ACTIVATION_DIR / "kill.yaml"
QUIET_PATH: Path = ACTIVATION_DIR / "quiet-mode.yaml"
GHOST_LOG_PATH: Path = ACTIVATION_DIR / "ghost-log.md"
INSTALL_PATH: Path = ACTIVATION_DIR / "install.yaml"
GHOST_MODE_PATH: Path = ACTIVATION_DIR / "ghost-mode.yaml"
POST_REVIEW_PAUSE_PATH: Path = ACTIVATION_DIR / "post-review-pause.yaml"
DRAFTS_DIR: Path = ACTIVATION_DIR / "drafts"
HANDSHAKES_DIR: Path = ACTIVATION_DIR / "handshakes"
RESPONSE_EVENTS_PATH: Path = ACTIVATION_DIR / "response-events.jsonl"
GROUNDING_PATH: Path = ACTIVATION_DIR / "grounding.yaml"
POLICY_STATE_PATH: Path = ACTIVATION_DIR / "policy-state.yaml"
BEHAVIORAL_MODEL_STUB_PATH: Path = VAULT_ROOT / "System" / "behavioral-model-stub.md"


__all__ = [
    "VAULT_ROOT",
    "ACTIVATION_DIR",
    "SIGNALS_PATH",
    "CANDIDATES_PATH",
    "OFFERS_PATH",
    "TOMBSTONES_PATH",
    "WEIGHTS_PATH",
    "KILL_PATH",
    "QUIET_PATH",
    "GHOST_LOG_PATH",
    "INSTALL_PATH",
    "GHOST_MODE_PATH",
    "POST_REVIEW_PAUSE_PATH",
    "DRAFTS_DIR",
    "HANDSHAKES_DIR",
    "RESPONSE_EVENTS_PATH",
    "GROUNDING_PATH",
    "POLICY_STATE_PATH",
    "BEHAVIORAL_MODEL_STUB_PATH",
]
