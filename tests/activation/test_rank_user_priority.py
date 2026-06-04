"""Sprint 7 M1 — type-based user_priority floor."""

from __future__ import annotations

from core.activation.rank import _user_priority
from core.activation.schemas import Candidate


def _c(t: str, summary: str = "x") -> Candidate:
    return Candidate(
        candidate_id="c-1", type=t, summary=summary,
        cited_signals=["sig_1"], confidence=0.5,
        staleness_days=1, action_verb="schedule",
    )


def test_risk_flag_priority():
    assert _user_priority(_c("risk_flag")) == 0.9


def test_meeting_followup_priority():
    assert _user_priority(_c("meeting_followup")) == 0.7


def test_commitment_default_priority():
    assert _user_priority(_c("commitment_reminder", "do the thing")) == 0.5


def test_commitment_p1_marker():
    assert _user_priority(_c("commitment_reminder", "[P1] urgent")) == 1.0
    assert _user_priority(_c("commitment_reminder", "P1: urgent")) == 1.0
    assert _user_priority(_c("commitment_reminder", "(P1) urgent")) == 1.0


def test_commitment_p2_marker():
    assert _user_priority(_c("commitment_reminder", "[P2] medium")) == 0.6


def test_commitment_p3_marker():
    assert _user_priority(_c("commitment_reminder", "[P3] low")) == 0.3


def test_other_types_default():
    assert _user_priority(_c("contradiction")) == 0.5
    assert _user_priority(_c("self_undercut")) == 0.5
