"""Shared fixture-vault builder for Sprint 2 gather tests."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def set_mtime(p: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(p, (ts, ts))


def build_vault(
    root: Path,
    *,
    meeting_notes: Iterable[tuple[str, str, datetime]] = (),
    project_docs: Iterable[tuple[str, str, datetime]] = (),
    people: Iterable[tuple[str, str, datetime]] = (),
    learnings: Iterable[tuple[str, str]] = (),  # (date_str, body)
    tasks_md: str | None = None,
    tombstones_jsonl: str | None = None,
) -> Path:
    """Lay out a tmp vault with the given sources. Returns vault root.

    All file paths are relative to ``root``. ``mtime`` is applied explicitly.
    """
    root.mkdir(parents=True, exist_ok=True)
    # Activation dir (tests that call CLI need it too).
    act = root / "System" / "activation"
    (act / "drafts").mkdir(parents=True, exist_ok=True)
    for name in ("signals.jsonl", "candidates.jsonl", "offers.jsonl"):
        (act / name).touch()
    if tombstones_jsonl is None:
        (act / "tombstones.jsonl").touch()
    else:
        (act / "tombstones.jsonl").write_text(tombstones_jsonl, encoding="utf-8")
    (act / "kill.yaml").write_text("disabled: false\n", encoding="utf-8")
    (act / "weights.yaml").write_text("w1_confidence: 1.0\n", encoding="utf-8")

    def _write(rel: str, body: str, mtime: datetime) -> Path:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        set_mtime(p, mtime)
        return p

    for rel, body, mtime in meeting_notes:
        _write(rel, body, mtime)
    for rel, body, mtime in project_docs:
        _write(rel, body, mtime)
    for rel, body, mtime in people:
        _write(rel, body, mtime)
    for date_str, body in learnings:
        _write(f"System/Session_Learnings/{date_str}.md", body, datetime.now(timezone.utc))
    if tasks_md is not None:
        (root / "03-Tasks").mkdir(parents=True, exist_ok=True)
        (root / "03-Tasks" / "Tasks.md").write_text(tasks_md, encoding="utf-8")
    return root
