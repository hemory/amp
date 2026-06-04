"""JSONL read/write helpers with atomic rewrite.

Rewrites use temp-file-and-rename (`os.replace`) to avoid leaving a
partially written file on crash.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    """Append a single row. Creates parent dirs and file as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read all rows. Missing file returns []. Blank lines skipped."""
    path = Path(path)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            s = raw.strip()
            if not s:
                continue
            try:
                out.append(json.loads(s))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}: invalid JSON on line {lineno}: {e}") from e
    return out


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Memory-friendly iterator over rows."""
    path = Path(path)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            s = raw.strip()
            if not s:
                continue
            try:
                yield json.loads(s)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}: invalid JSON on line {lineno}: {e}") from e


def rewrite_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    """Atomically replace `path` with the given rows.

    Writes to a temp file in the same directory, fsyncs, then `os.replace`s
    over the target. If the write fails mid-way the original file is left
    untouched.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up temp file on any failure; leave original intact.
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


__all__ = ["append_jsonl", "read_jsonl", "iter_jsonl", "rewrite_jsonl"]
