"""Activation policy hash + post-review-pause auto-set (Sprint 7, H5).

Re-stabilization should cover prompts/identity/code, not just weights.
``compute_policy_hash`` is sha256 of:

  - weights.yaml content
  - grounding.yaml content
  - extract.py SYSTEM_PROMPT source
  - draft.py system-prompt-template source
  - identity bundle (5 files concatenated)
  - rubric version

Persists the last-known hash to ``policy-state.yaml`` (gitignored, local
state). When the current hash differs from the persisted one, ``policy_check``
writes ``post-review-pause.yaml`` with ``until: today + 3 days``.

Idempotent: re-running with the same hash is a no-op. ``--acknowledge``
clears the pause early and refreshes the persisted hash.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import yaml


_RUBRIC_VERSION = "v1"  # bump when rubric weighting changes (§9 calibration)
PAUSE_DURATION_DAYS = 3


_IDENTITY_PARTS = (
    ("System", "identity", "amp", "SOUL.md"),
    ("System", "identity", "amp", "STYLE.md"),
    ("System", "identity", "user", "SOUL.md"),
    ("System", "identity", "user", "STYLE.md"),
    ("System", "identity", "README.md"),
)


@dataclass
class PolicyCheckResult:
    current_hash: str
    previous_hash: Optional[str]
    changed: bool
    pause_until: Optional[date]
    notice: str


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _hash_module_constant(module_name: str, attr: str) -> str:
    """Hash a module-level string constant by importing the module."""
    try:
        mod = __import__(module_name, fromlist=[attr])
        v = getattr(mod, attr, "")
        if not isinstance(v, str):
            v = repr(v)
        return v
    except Exception:
        return ""


def compute_policy_hash(vault_root: Path) -> str:
    """sha256 across all policy-relevant files + prompt sources."""
    vr = Path(vault_root)
    parts = [
        ("weights", _read(vr / "System" / "activation" / "weights.yaml")),
        ("grounding", _read(vr / "System" / "activation" / "grounding.yaml")),
        ("extract_prompt", _hash_module_constant("core.activation.extract", "_SYSTEM_PROMPT")),
        ("draft_prompt", _hash_module_constant("core.activation.draft", "_SYSTEM_PROMPT_TEMPLATE")),
        ("rubric_version", _RUBRIC_VERSION),
    ]
    for rel in _IDENTITY_PARTS:
        parts.append((f"identity:{'/'.join(rel)}", _read(vr.joinpath(*rel))))
    h = hashlib.sha256()
    for label, content in parts:
        h.update(label.encode("utf-8"))
        h.update(b"\0")
        h.update(content.encode("utf-8"))
        h.update(b"\n--PART--\n")
    return h.hexdigest()


def read_policy_state(state_path: Path) -> Optional[str]:
    p = Path(state_path)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return None
    v = data.get("policy_hash")
    return v if isinstance(v, str) else None


def write_policy_state(state_path: Path, *, policy_hash: str, now: datetime) -> None:
    p = Path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "policy_hash": policy_hash,
        "updated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(body, f, sort_keys=True)


def write_post_review_pause(pause_path: Path, *, until: date, reason: str) -> None:
    p = Path(pause_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "active": True,
        "until": until.isoformat(),
        "reason": reason,
    }
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(body, f, sort_keys=True)


def clear_post_review_pause(pause_path: Path) -> bool:
    p = Path(pause_path)
    if p.exists():
        try:
            p.unlink()
            return True
        except OSError:
            return False
    return False


def policy_check(
    *,
    vault_root: Path,
    state_path: Path,
    pause_path: Path,
    now: Optional[datetime] = None,
    acknowledge: bool = False,
) -> PolicyCheckResult:
    """Compare current hash vs last-known. Auto-set pause on diff.

    If ``acknowledge`` is True, clear any pause and refresh the persisted
    hash (no pause set even if hash changed).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    current = compute_policy_hash(vault_root)
    previous = read_policy_state(state_path)

    if acknowledge:
        cleared = clear_post_review_pause(pause_path)
        write_policy_state(state_path, policy_hash=current, now=now)
        return PolicyCheckResult(
            current_hash=current,
            previous_hash=previous,
            changed=(previous is not None and previous != current),
            pause_until=None,
            notice=(
                "policy acknowledged; pause cleared"
                if cleared
                else "policy acknowledged; no pause was active"
            ),
        )

    if previous is None:
        # First run — establish baseline, no pause.
        write_policy_state(state_path, policy_hash=current, now=now)
        return PolicyCheckResult(
            current_hash=current,
            previous_hash=None,
            changed=False,
            pause_until=None,
            notice="policy baseline established",
        )

    if previous == current:
        return PolicyCheckResult(
            current_hash=current,
            previous_hash=previous,
            changed=False,
            pause_until=None,
            notice="policy unchanged",
        )

    # Changed → set pause + persist new hash.
    until = now.date() + timedelta(days=PAUSE_DURATION_DAYS)
    write_post_review_pause(pause_path, until=until, reason="policy_change")
    write_policy_state(state_path, policy_hash=current, now=now)
    return PolicyCheckResult(
        current_hash=current,
        previous_hash=previous,
        changed=True,
        pause_until=until,
        notice=(
            f"policy changed (sha {current[:8]} != {previous[:8]}); "
            f"post-review-pause set through {until.isoformat()}. "
            "Run `policy-check --acknowledge` to clear early."
        ),
    )


__all__ = [
    "compute_policy_hash",
    "policy_check",
    "read_policy_state",
    "write_policy_state",
    "write_post_review_pause",
    "clear_post_review_pause",
    "PolicyCheckResult",
    "PAUSE_DURATION_DAYS",
]
