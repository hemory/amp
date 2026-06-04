"""Sprint 4 CLI smoke tests via subprocess."""

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
    # Identity
    idd = vault / "System" / "identity"
    (idd / "amp").mkdir(parents=True)
    (idd / "user").mkdir(parents=True)
    (idd / "amp" / "SOUL.md").write_text("amp soul", encoding="utf-8")
    (idd / "amp" / "STYLE.md").write_text("amp style", encoding="utf-8")
    (idd / "user" / "SOUL.md").write_text("user soul", encoding="utf-8")
    (idd / "user" / "STYLE.md").write_text("user style", encoding="utf-8")
    (idd / "README.md").write_text("overview", encoding="utf-8")
    # Seed one signal + one candidate + one offer linked.
    sig = {
        "signal_id": "sig_0",
        "source": "meeting_notes",
        "path": "04-Projects/X/meetings/2026-04-13.md",
        "timestamp": "2026-04-13T10:00:00Z",
        "excerpt": "the user to send followup to D.Lin by Fri",
    }
    (act / "signals.jsonl").write_text(
        json.dumps(sig, sort_keys=True) + "\n", encoding="utf-8"
    )
    cand = {
        "candidate_id": "c_001",
        "type": "meeting_followup",
        "summary": "Send recap",
        "cited_signals": ["sig_0"],
        "confidence": 0.8,
        "staleness_days": 1,
        "action_verb": "send",
    }
    (act / "candidates.jsonl").write_text(
        json.dumps(cand, sort_keys=True) + "\n", encoding="utf-8"
    )
    offer = {
        "offer_id": "o_test_001",
        "created_at": "2026-04-17T07:00:00Z",
        "ritual": "daily-plan",
        "type": "meeting_followup",
        "shown": True,
        "summary": "Send recap",
        "cited_signals": ["sig_0"],
        "score": 0.8,
        "candidate_id": "c_001",
        "hold_reason": None,
        "draft_artifact_path": None,
        "score_components": {},
        "user_response": None,
        "response_timestamp": None,
        "time_to_response_s": None,
        "edit_distance_if_accepted": None,
        "notes": None,
    }
    (act / "offers.jsonl").write_text(
        json.dumps(offer, sort_keys=True) + "\n", encoding="utf-8"
    )
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


def test_draft_prompt_single_offer_emits_handshake(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "draft-prompt", "--offer-id", "o_test_001")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["offer_id"] == "o_test_001"
    assert data["identity"]["amp_soul"] == "amp soul"
    assert len(data["cited_signals"]) == 1
    assert data["length_cap_words"] == 150
    assert "schema" in data


def test_draft_prompt_all_emits_jsonl(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "draft-prompt", "--all")
    assert result.returncode == 0, result.stderr
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["offer_id"] == "o_test_001"


def test_draft_apply_happy_path(tmp_path):
    vault = _make_vault(tmp_path)
    resp = {
        "draft_text": "Hi D — quick recap: three decisions.",
        "citations": ["sig_0"],
        "confidence": 0.8,
        "warnings": [],
    }
    resp_path = tmp_path / "resp.json"
    resp_path.write_text(json.dumps(resp), encoding="utf-8")
    result = _run(
        vault, "draft-apply",
        "--offer-id", "o_test_001",
        "--input", str(resp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "written=1" in result.stdout
    draft_file = vault / "System" / "activation" / "drafts" / "o_test_001.md"
    assert draft_file.exists()
    # Offer should now carry draft_artifact_path.
    offers = vault / "System" / "activation" / "offers.jsonl"
    row = json.loads(offers.read_text().splitlines()[0])
    assert row["draft_artifact_path"] == "System/activation/drafts/o_test_001.md"


def test_draft_apply_rejects_hallucination(tmp_path):
    vault = _make_vault(tmp_path)
    resp = {
        "draft_text": "Hi D",
        "citations": ["sig_NOTREAL"],
        "confidence": 0.8,
        "warnings": [],
    }
    resp_path = tmp_path / "resp.json"
    resp_path.write_text(json.dumps(resp), encoding="utf-8")
    result = _run(
        vault, "draft-apply",
        "--offer-id", "o_test_001",
        "--input", str(resp_path),
    )
    assert result.returncode == 1
    assert "written=0" in result.stdout
    assert "hallucinated_citation" in result.stderr


def test_log_accepted(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(
        vault, "log",
        "--offer-id", "o_test_001",
        "--response", "accepted",
    )
    assert result.returncode == 0, result.stderr
    offers = vault / "System" / "activation" / "offers.jsonl"
    row = json.loads(offers.read_text().splitlines()[0])
    assert row["user_response"] == "accepted"


def test_log_never_again_creates_tombstone(tmp_path):
    """Sprint 7 H2: tombstones now come from never_again, not rejected."""
    vault = _make_vault(tmp_path)
    result = _run(
        vault, "log",
        "--offer-id", "o_test_001",
        "--response", "never_again",
        "--reason", "noisy",
    )
    assert result.returncode == 0, result.stderr
    tombs = vault / "System" / "activation" / "tombstones.jsonl"
    lines = [l for l in tombs.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["pattern"] == "sig_0"
    assert row["notes"] == "noisy"


def test_log_rejected_no_tombstone(tmp_path):
    """Sprint 7 H2: rejected does NOT create a tombstone (only an event)."""
    vault = _make_vault(tmp_path)
    result = _run(
        vault, "log",
        "--offer-id", "o_test_001",
        "--response", "rejected",
        "--reason", "noisy",
    )
    assert result.returncode == 0, result.stderr
    tombs = vault / "System" / "activation" / "tombstones.jsonl"
    assert (not tombs.exists()) or tombs.read_text().strip() == ""


def test_log_unknown_offer_fails(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(
        vault, "log",
        "--offer-id", "NOPE",
        "--response", "accepted",
    )
    assert result.returncode == 2
    assert "offer_id not found" in result.stderr


def test_acceptance_rate_insufficient(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run(vault, "acceptance-rate")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "insufficient_data"
