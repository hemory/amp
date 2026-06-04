"""Tests for the tightened meeting-note heuristic (`is_meeting_note`).

Motivated by the Sprint 2.5 retro: the previous substring-based keyword
match ("planning" among them) produced 13 false positives out of 14
backfill proposals in the real vault. See gather.py module docstring
for the full rule set.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make repo root importable when pytest is invoked from anywhere.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.activation.gather import is_meeting_note  # noqa: E402


# ---------- positive cases --------------------------------------------


def test_filename_meeting_notes_md_matches():
    assert is_meeting_note(
        Path("04-Projects/Retain_Talent/01-planning/meeting-notes.md"),
        content_head="",
    )


def test_inbox_meetings_directory_matches():
    assert is_meeting_note(Path("00-Inbox/Meetings/foo.md"), content_head="")


def test_soft_token_1_1_with_attendees_matches():
    head = "# D.Lin 1-1\n\nAttendees: D.Lin, the user\n\nnotes..."
    assert is_meeting_note(Path("05-Areas/People/D.Lin 1-1.md"), content_head=head)


def test_meetings_subdirectory_matches():
    assert is_meeting_note(
        Path("04-Projects/Foo/meetings/2026-04-13.md"), content_head=""
    )


def test_hard_token_case_insensitive():
    assert is_meeting_note(Path("04-Projects/Foo/Meeting-Notes.md"), content_head="")


# ---------- negative cases (the Sprint 2.5 false positives) ----------


def test_townhall_proposal_with_planning_dir_is_not_meeting():
    assert not is_meeting_note(
        Path("05-Areas/Town_Halls/planning/may-2026-townhall-proposal-v2.md"),
        content_head="# Proposal\n\nbody...",
    )


def test_plt_ownership_proposal_is_not_meeting():
    assert not is_meeting_note(
        Path("05-Areas/Town_Halls/planning/plt-ownership-proposal.md"),
        content_head="",
    )


def test_content_planning_doc_is_not_meeting():
    assert not is_meeting_note(
        Path("04-Projects/Retain_Talent/03-content/2026-03-30 - Next 3 Reels Planning.md"),
        content_head="",
    )


def test_reflection_doc_is_not_meeting():
    assert not is_meeting_note(
        Path("05-Areas/Career/Evidence/2025-11-17-Reflection.md"),
        content_head="",
    )


def test_townhall_pitch_is_not_meeting():
    assert not is_meeting_note(
        Path("05-Areas/Town_Halls/planning/march-townhall-pitch.md"),
        content_head="",
    )


# ---------- soft-token gating ----------------------------------------


def test_soft_token_without_attendees_is_not_meeting():
    # filename matches `1-1` but no Attendees line -> soft tokens
    # require content confirmation, so this must be rejected.
    head = "# Team 1-1 recap\n\nSome notes.\n"
    assert not is_meeting_note(
        Path("04-Projects/Foo/team-1-1-recap.md"), content_head=head
    )


def test_soft_token_sync_without_attendees_is_not_meeting():
    head = "# my sync script\n\nhelper script notes.\n"
    assert not is_meeting_note(
        Path("05-Areas/Tools/my-sync-script.md"), content_head=head
    )


def test_soft_token_standup_with_attendees_matches():
    head = "# Standup\nAttendees : Alice, Bob\n"
    assert is_meeting_note(Path("04-Projects/Foo/daily-standup.md"), content_head=head)


def test_soft_token_1on1_with_attendees_matches():
    head = "  Attendees: Alice, the user"
    assert is_meeting_note(Path("05-Areas/People/alice-1on1.md"), content_head=head)


def test_attendees_match_is_case_insensitive():
    head = "ATTENDEES: Alice, Bob\n"
    assert is_meeting_note(Path("04-Projects/Foo/quick-sync.md"), content_head=head)


# ---------- backfill regression: real meeting vs. proposal doc -------


def _set_mtime(p: Path, when: datetime) -> None:
    ts = when.timestamp()
    os.utime(p, (ts, ts))


def test_backfill_find_candidates_skips_proposal_in_planning_dir(tmp_path: Path):
    """Given a vault with one real meeting note and one proposal doc
    in a ``/planning/`` subdir, ``find_candidates`` must return only
    the meeting note — the proposal's path contains "planning" but
    that is no longer a keyword."""
    # Import the backfill script as a module; add `scripts/` to sys.path.
    scripts_dir = _REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import backfill_meeting_frontmatter as mod  # type: ignore

    vault = tmp_path / "vault"
    real_meeting = vault / "04-Projects" / "Customer_Onboarding" / "01-planning" / "meeting-notes.md"
    proposal = vault / "05-Areas" / "Town_Halls" / "planning" / "may-2026-townhall-proposal-v2.md"
    real_meeting.parent.mkdir(parents=True, exist_ok=True)
    proposal.parent.mkdir(parents=True, exist_ok=True)
    real_meeting.write_text(
        "# Customer Onboarding Planning Meeting\n\n2026-04-12\n\nNotes...\n",
        encoding="utf-8",
    )
    proposal.write_text(
        "# May 2026 Town Hall Proposal v2\n\nA proposal for the townhall.\n",
        encoding="utf-8",
    )
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    _set_mtime(real_meeting, recent)
    _set_mtime(proposal, recent)

    candidates = mod.find_candidates(vault, since=None)
    rel_paths = [p.resolve().relative_to(vault.resolve()).as_posix() for p in candidates]
    assert "04-Projects/Customer_Onboarding/01-planning/meeting-notes.md" in rel_paths
    assert "05-Areas/Town_Halls/planning/may-2026-townhall-proposal-v2.md" not in rel_paths
    assert len(rel_paths) == 1
