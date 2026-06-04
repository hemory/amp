"""Replay must never mutate the live System/activation/*.jsonl files."""

from __future__ import annotations

import json
from pathlib import Path

from core.activation.replay import load_fixture, run_replay


def _fixture_dir(tmp_vault: Path) -> Path:
    d = tmp_vault / "fx"
    d.mkdir()
    (d / "meta.yaml").write_text(
        "id: iso01\n"
        "description: isolation test\n"
        "created_at: '2026-04-19T00:00:00Z'\n"
        "now: '2026-04-19T09:00:00Z'\n"
        "days_since_install: 30\n"
        "acceptance_rate: 0.6\n"
        "ghost: false\n",
        encoding="utf-8",
    )
    sig = {
        "signal_id": "sig_x",
        "source": "meeting_notes",
        "path": "04-Projects/Z/m.md",
        "timestamp": "2026-04-18T10:00:00Z",
        "excerpt": "Schedule review with J.Park on 2026-04-20.",
    }
    (d / "signals.jsonl").write_text(
        json.dumps(sig, sort_keys=True) + "\n", encoding="utf-8"
    )
    cand = [
        {
            "candidate_id": "c1",
            "type": "meeting_followup",
            "summary": "Schedule review with J.Park on 2026-04-20.",
            "cited_signals": ["sig_x"],
            "confidence": 0.8,
            "staleness_days": 1,
            "action_verb": "schedule",
        }
    ]
    (d / "extract_response.json").write_text(json.dumps(cand), encoding="utf-8")
    return d


def test_replay_without_write_run_does_not_touch_vault(activation_dir, tmp_path):
    vault = activation_dir.parent.parent  # <tmp>/vault
    # Seed the live files with sentinel content.
    live_offers = activation_dir / "offers.jsonl"
    sentinel = '{"sentinel": "do not touch"}\n'
    live_offers.write_text(sentinel, encoding="utf-8")
    live_signals = activation_dir / "signals.jsonl"
    live_signals.write_text(sentinel, encoding="utf-8")
    live_candidates = activation_dir / "candidates.jsonl"
    live_candidates.write_text(sentinel, encoding="utf-8")
    live_tombs = activation_dir / "tombstones.jsonl"
    live_tombs.write_text(sentinel, encoding="utf-8")

    fx = load_fixture(_fixture_dir(tmp_path))
    result = run_replay(fx, vault_root=vault, write_run=False)
    assert result.run_dir is None
    assert len(result.offers) == 1

    # Every live file must still be bit-identical to the sentinel content.
    assert live_offers.read_text(encoding="utf-8") == sentinel
    assert live_signals.read_text(encoding="utf-8") == sentinel
    assert live_candidates.read_text(encoding="utf-8") == sentinel
    assert live_tombs.read_text(encoding="utf-8") == sentinel
    # No replay/runs/ directory exists yet.
    assert not (activation_dir / "replay" / "runs").exists()


def test_replay_with_write_run_writes_only_under_replay_runs(activation_dir, tmp_path):
    vault = activation_dir.parent.parent
    sentinel = '{"sentinel": "do not touch"}\n'
    live_offers = activation_dir / "offers.jsonl"
    live_offers.write_text(sentinel, encoding="utf-8")

    fx = load_fixture(_fixture_dir(tmp_path))
    result = run_replay(fx, vault_root=vault, write_run=True)
    assert result.run_dir is not None
    assert result.run_dir.exists()
    # Path is scoped under replay/runs/<fixture_id>/<stamp>/
    parts = result.run_dir.parts
    assert "replay" in parts
    assert "runs" in parts
    assert "iso01" in parts
    # Outputs are written inside run_dir, NOT in the live activation dir.
    assert (result.run_dir / "offers.jsonl").exists()
    assert live_offers.read_text(encoding="utf-8") == sentinel
