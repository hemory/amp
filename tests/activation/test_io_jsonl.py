"""JSONL I/O tests, including atomic-rewrite crash simulation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.activation import io_jsonl


def test_append_then_read_roundtrip(tmp_path: Path):
    p = tmp_path / "sub" / "rows.jsonl"
    io_jsonl.append_jsonl(p, {"a": 1, "b": "x"})
    io_jsonl.append_jsonl(p, {"a": 2, "b": "y"})
    rows = io_jsonl.read_jsonl(p)
    assert rows == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]


def test_read_missing_file_returns_empty(tmp_path: Path):
    assert io_jsonl.read_jsonl(tmp_path / "nope.jsonl") == []


def test_read_skips_blank_lines(tmp_path: Path):
    p = tmp_path / "r.jsonl"
    p.write_text('{"a":1}\n\n   \n{"a":2}\n', encoding="utf-8")
    assert io_jsonl.read_jsonl(p) == [{"a": 1}, {"a": 2}]


def test_read_bad_json_raises(tmp_path: Path):
    p = tmp_path / "bad.jsonl"
    p.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        io_jsonl.read_jsonl(p)


def test_rewrite_replaces_contents(tmp_path: Path):
    p = tmp_path / "r.jsonl"
    io_jsonl.append_jsonl(p, {"a": 1})
    io_jsonl.append_jsonl(p, {"a": 2})
    io_jsonl.rewrite_jsonl(p, [{"a": 3}])
    assert io_jsonl.read_jsonl(p) == [{"a": 3}]


def test_rewrite_crash_preserves_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Simulate a crash mid-rewrite and confirm the original file is intact."""
    p = tmp_path / "r.jsonl"
    original_rows = [{"a": 1, "msg": "keep"}, {"a": 2, "msg": "me"}]
    for row in original_rows:
        io_jsonl.append_jsonl(p, row)
    original_bytes = p.read_bytes()

    def exploding_iter():
        yield {"a": 99}
        raise RuntimeError("simulated crash mid-write")

    with pytest.raises(RuntimeError, match="simulated crash"):
        io_jsonl.rewrite_jsonl(p, exploding_iter())

    # Original file untouched.
    assert p.read_bytes() == original_bytes
    assert io_jsonl.read_jsonl(p) == original_rows

    # And no leftover temp files in the dir.
    leftovers = [
        x.name for x in p.parent.iterdir()
        if x.name.startswith(f".{p.name}.") and x.name.endswith(".tmp")
    ]
    assert leftovers == []


def test_rewrite_creates_parent_dirs(tmp_path: Path):
    p = tmp_path / "deep" / "nest" / "r.jsonl"
    io_jsonl.rewrite_jsonl(p, [{"a": 1}])
    assert io_jsonl.read_jsonl(p) == [{"a": 1}]


def test_append_sorts_keys_deterministically(tmp_path: Path):
    p = tmp_path / "r.jsonl"
    io_jsonl.append_jsonl(p, {"b": 2, "a": 1})
    line = p.read_text(encoding="utf-8").strip()
    # keys sorted → a comes before b
    assert line == json.dumps({"a": 1, "b": 2}, sort_keys=True)
