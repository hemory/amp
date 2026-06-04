"""Shared fixtures for activation tests.

We isolate each test in a tmp `AMP_VAULT_ROOT` by:
  1. Creating a `System/activation/` tree inside tmp_path.
  2. Setting the env var.
  3. Importlib.reload'ing the `core.activation.paths` + `config` modules so
     the module-level constants pick up the new root.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path for `core.activation` imports when
# pytest is invoked from anywhere.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def activation_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the activation engine at a fresh empty tmp vault."""
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    (act / "drafts").mkdir(parents=True)

    # Touch all expected empty files so tests can operate like on a real vault.
    for name in ("signals.jsonl", "candidates.jsonl", "offers.jsonl", "tombstones.jsonl"):
        (act / name).touch()

    monkeypatch.setenv("AMP_VAULT_ROOT", str(vault))

    # Reload only `paths` — its module-level constants cache the vault root.
    # Everything else reads `paths.X` at call time so picks up the update.
    import core.activation.paths as _paths

    importlib.reload(_paths)

    yield act

    # Best-effort cleanup: reload back to default vault detection.
    monkeypatch.delenv("AMP_VAULT_ROOT", raising=False)
    importlib.reload(_paths)
