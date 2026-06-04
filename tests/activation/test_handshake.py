"""Sprint 7 C1 — handshake artifact persistence."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.activation.handshake import (
    SCHEMA_VERSION,
    gc_handshakes,
    hash_identity,
    hash_weights,
    read_handshake,
    write_handshake,
)


def test_write_then_read_roundtrip(tmp_path: Path):
    target = write_handshake(
        tmp_path,
        stage="extract",
        handshake_id="batch-20260417-00",
        prompt_text="hello",
        payload={"signals_snapshot": [{"signal_id": "sig_1"}]},
        weights_hash="abc",
        identity_hash="def",
    )
    assert target.exists()
    assert target.name == "extract-batch-20260417-00.json"
    h = read_handshake(tmp_path, stage="extract", handshake_id="batch-20260417-00")
    assert h is not None
    assert h["handshake_id"] == "batch-20260417-00"
    assert h["stage"] == "extract"
    assert h["schema_version"] == SCHEMA_VERSION
    assert h["weights_hash"] == "abc"
    assert h["payload"]["signals_snapshot"][0]["signal_id"] == "sig_1"


def test_read_missing_returns_none(tmp_path: Path):
    assert read_handshake(tmp_path, stage="extract", handshake_id="nope") is None


def test_read_corrupt_returns_none(tmp_path: Path):
    p = tmp_path / "extract-bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert read_handshake(tmp_path, stage="extract", handshake_id="bad") is None


def test_gc_removes_old_files(tmp_path: Path):
    write_handshake(tmp_path, stage="extract", handshake_id="old",
                    prompt_text="x", payload={})
    write_handshake(tmp_path, stage="extract", handshake_id="new",
                    prompt_text="y", payload={})
    old_path = tmp_path / "extract-old.json"
    # Backdate the "old" file by 14 days.
    old_ts = (datetime.now(timezone.utc) - timedelta(days=14)).timestamp()
    os.utime(old_path, (old_ts, old_ts))
    deleted = gc_handshakes(tmp_path, older_than_days=7)
    assert old_path in deleted
    assert (tmp_path / "extract-new.json").exists()


def test_gc_no_dir(tmp_path: Path):
    assert gc_handshakes(tmp_path / "missing", older_than_days=7) == []


def test_hash_weights_stable(tmp_path: Path):
    p = tmp_path / "w.yaml"
    p.write_text("w1: 1.0\n")
    h1 = hash_weights(p)
    h2 = hash_weights(p)
    assert h1 == h2
    p.write_text("w1: 2.0\n")
    assert hash_weights(p) != h1


def test_hash_identity_stable(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("alpha")
    b.write_text("beta")
    h1 = hash_identity([a, b])
    h2 = hash_identity([a, b])
    assert h1 == h2
    a.write_text("ALPHA")
    assert hash_identity([a, b]) != h1


def test_hash_weights_missing_path_returns_stable_value():
    # Hashes "" — should be deterministic.
    h1 = hash_weights(None)
    h2 = hash_weights(None)
    assert h1 == h2
