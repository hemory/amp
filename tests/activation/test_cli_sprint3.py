"""End-to-end subprocess smoke tests for Sprint 3 CLI subcommands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    act = vault / "System" / "activation"
    (act / "drafts").mkdir(parents=True)
    for n in ("signals.jsonl", "candidates.jsonl", "offers.jsonl", "tombstones.jsonl"):
        (act / n).touch()
    (act / "kill.yaml").write_text("disabled: false\n", encoding="utf-8")
    (act / "weights.yaml").write_text(
        "w1_confidence: 1.0\nw2_recency: 0.6\nw3_commitment: 1.2\n"
        "w4_user_priority: 0.8\nw5_recent_offer_penalty: 0.5\n"
        "w6_rejection_penalty: 0.7\n",
        encoding="utf-8",
    )
    # Pre-populate signals.jsonl with three rows.
    signals_path = act / "signals.jsonl"
    rows = [
        {
            "signal_id": f"sig_{i}",
            "source": "meeting_notes",
            "path": f"04-Projects/X/meetings/2026-04-{10+i:02d}.md",
            "timestamp": "2026-04-13T10:00:00Z",
            "excerpt": f"hello {i}",
        }
        for i in range(3)
    ]
    with signals_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    return vault


def _run(vault: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        "AMP_VAULT_ROOT": str(vault),
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(_REPO_ROOT),
    }
    return subprocess.run(
        [sys.executable, "-m", "core.activation", *args],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_extract_prompt_emits_handshake_json(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "extract-prompt")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["batch_id"].startswith("batch-")
    assert data["batch_id"].endswith("-00")
    assert len(data["signals"]) == 3
    assert "schema" in data
    assert "cited_signals" in data["user_prompt"]


def test_extract_apply_happy_path_appends_candidates(tmp_path):
    vault = _make_vault(tmp_path)
    # Step 1: get the batch_id from extract-prompt.
    ep = _run(vault, "extract-prompt")
    assert ep.returncode == 0, ep.stderr
    batch_id = json.loads(ep.stdout)["batch_id"]

    # Step 2: simulate an LLM response file.
    resp = [
        {
            "candidate_id": "c_001",
            "type": "meeting_followup",
            "summary": "Send recap",
            "cited_signals": ["sig_0"],
            "confidence": 0.8,
            "staleness_days": 1,
            "action_verb": "send",
        },
        {
            # Hallucinated signal_id — should be rejected.
            "candidate_id": "c_002",
            "type": "meeting_followup",
            "summary": "Made-up",
            "cited_signals": ["sig_FAKE"],
            "confidence": 0.8,
            "staleness_days": 1,
            "action_verb": "send",
        },
    ]
    resp_path = tmp_path / "resp.json"
    resp_path.write_text(json.dumps(resp), encoding="utf-8")

    ea = _run(vault, "extract-apply", "--input", str(resp_path), "--batch-id", batch_id, "--no-grounding-gate")
    assert ea.returncode == 0, ea.stderr
    assert "accepted=1" in ea.stderr
    assert "rejected=1" in ea.stderr

    candidates_path = vault / "System" / "activation" / "candidates.jsonl"
    lines = [l for l in candidates_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["candidate_id"] == "c_001"


def test_rank_writes_offers_and_prints_summary(tmp_path):
    vault = _make_vault(tmp_path)
    # Seed candidates.jsonl directly.
    cand_path = vault / "System" / "activation" / "candidates.jsonl"
    cands = [
        {
            "candidate_id": f"c_{i:03d}",
            "type": "meeting_followup",
            "summary": f"s {i}",
            "cited_signals": [f"sig_{i}"],
            "confidence": 0.5 + (i * 0.1),
            "staleness_days": 1,
            "action_verb": "send",
        }
        for i in range(3)
    ]
    with cand_path.open("w", encoding="utf-8") as f:
        for c in cands:
            f.write(json.dumps(c, sort_keys=True) + "\n")

    # Live mode (not ghost): expect some surfaced.
    rk = _run(
        vault,
        "rank",
        "--days-since-install",
        "30",
        "--acceptance-rate",
        "0.7",
    )
    assert rk.returncode == 0, rk.stderr
    assert "surfaced=" in rk.stdout
    assert "ghost=" in rk.stdout

    offers_path = vault / "System" / "activation" / "offers.jsonl"
    lines = [l for l in offers_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 3


def test_rank_ghost_mode_for_new_install(tmp_path):
    vault = _make_vault(tmp_path)
    cand_path = vault / "System" / "activation" / "candidates.jsonl"
    cand_path.write_text(
        json.dumps(
            {
                "candidate_id": "c_001",
                "type": "meeting_followup",
                "summary": "s",
                "cited_signals": ["sig_0"],
                "confidence": 0.8,
                "staleness_days": 1,
                "action_verb": "send",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    rk = _run(vault, "rank", "--days-since-install", "3")
    assert rk.returncode == 0, rk.stderr
    assert "surfaced=0" in rk.stdout
    assert "ghost=1" in rk.stdout


def test_extract_prompt_empty_signals(tmp_path):
    vault = _make_vault(tmp_path)
    # Empty signals.jsonl
    (vault / "System" / "activation" / "signals.jsonl").write_text("", encoding="utf-8")
    result = _run(vault, "extract-prompt")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["signals"] == []
