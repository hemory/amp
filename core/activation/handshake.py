"""Handshake artifacts (Sprint 7, C1).

A handshake is a snapshot file that pins an LLM call to a frozen world.
Without it the apply step re-derives state from live JSONL files — racy
if ``gather`` (or any other writer) runs in between.

Files live under ``System/activation/handshakes/`` (gitignored — runtime
state). Two stages, two file naming conventions:

    extract-{batch_id}.json       # Stage 2
    draft-{offer_id}.json         # Stage 4

A handshake JSON includes:

  - ``handshake_id``       — stable id (== batch_id or offer_id with a prefix)
  - ``stage``              — "extract" | "draft"
  - ``schema_version``     — bumped when the on-disk shape changes
  - ``created_at``         — ISO-8601
  - ``prompt_text``        — the full system + user prompt the LLM saw
  - ``prompt_hash``        — sha256(prompt_text)
  - ``weights_hash``       — sha256(weights.yaml content) at handshake time
  - ``identity_hash``      — sha256(identity bundle concat) at handshake time
  - ``payload``            — full snapshot of the data the apply step needs
                              (signals for extract; offer + cited_signals
                              + identity for draft).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read(path: Optional[Path]) -> str:
    if path is None or not Path(path).exists():
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def hash_weights(weights_path: Optional[Path]) -> str:
    return _sha256(_read(weights_path))


def hash_identity(identity_files: List[Path]) -> str:
    """Concatenated content hash of the identity bundle."""
    parts = [_read(p) for p in identity_files]
    return _sha256("\n--FILE--\n".join(parts))


def write_handshake(
    handshakes_dir: Path,
    *,
    handshake_id: str,
    stage: str,
    prompt_text: str,
    payload: Dict[str, Any],
    weights_hash: str = "",
    identity_hash: str = "",
) -> Path:
    """Persist a handshake JSON. Returns the file path.

    ``handshake_id`` becomes the filename: ``{stage}-{handshake_id}.json``.
    """
    handshakes_dir = Path(handshakes_dir)
    handshakes_dir.mkdir(parents=True, exist_ok=True)
    name = f"{stage}-{handshake_id}.json"
    target = handshakes_dir / name
    body = {
        "handshake_id": handshake_id,
        "stage": stage,
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_iso(),
        "prompt_text": prompt_text,
        "prompt_hash": _sha256(prompt_text),
        "weights_hash": weights_hash,
        "identity_hash": identity_hash,
        "payload": payload,
    }
    target.write_text(
        json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return target


def read_handshake(
    handshakes_dir: Path, *, stage: str, handshake_id: str
) -> Optional[Dict[str, Any]]:
    """Return the handshake dict, or None if missing/corrupt."""
    p = Path(handshakes_dir) / f"{stage}-{handshake_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def gc_handshakes(
    handshakes_dir: Path, *, older_than_days: int = 7, now: Optional[datetime] = None
) -> List[Path]:
    """Delete handshake files older than ``older_than_days``.

    Returns the list of deleted paths. Robust to missing dir + unreadable
    files (skipped silently).
    """
    p = Path(handshakes_dir)
    if not p.exists():
        return []
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=older_than_days)
    deleted: List[Path] = []
    for f in p.glob("*.json"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                f.unlink()
                deleted.append(f)
            except OSError:
                pass
    return deleted


__all__ = [
    "SCHEMA_VERSION",
    "write_handshake",
    "read_handshake",
    "gc_handshakes",
    "hash_weights",
    "hash_identity",
]
