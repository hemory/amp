"""Signal-ID determinism across two gather() calls on the same fixture vault."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.activation.gather import gather

from vault_fixture import build_vault


FROZEN_NOW = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


def _fixture_vault(tmp_path: Path) -> Path:
    build_vault(
        tmp_path / "vault",
        meeting_notes=[
            (
                "04-Projects/Foo/01-planning/meeting-notes.md",
                "# Weekly sync\n\nAction: draft roadmap by Friday.\n",
                FROZEN_NOW - timedelta(days=1),
            ),
        ],
        project_docs=[
            (
                "04-Projects/Foo/design-doc.md",
                "# Design\n\nWe plan to ship.\n",
                FROZEN_NOW - timedelta(days=2),
            ),
        ],
        learnings=[
            ("2026-04-15", "- Shipped activation scaffolding\n"),
        ],
        tasks_md=(
            "# Tasks\n\n## P0 - Urgent\n\n"
            "- [ ] **Write gather tests** - due today ^task-0001\n"
            "- [s] **Implement gather** - in progress ^task-0002\n"
            "- [b] **Calendar bridge** - blocked on perms ^task-0003\n"
        ),
    )
    return tmp_path / "vault"


def test_gather_signal_ids_stable_across_calls(tmp_path, monkeypatch):
    vault = _fixture_vault(tmp_path)
    # Disable calendar source deterministically: monkeypatch its helper.
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    s1 = gather(now=FROZEN_NOW, vault_root=vault)
    s2 = gather(now=FROZEN_NOW, vault_root=vault)

    assert len(s1) == len(s2) > 0
    ids1 = sorted(s.signal_id for s in s1)
    ids2 = sorted(s.signal_id for s in s2)
    assert ids1 == ids2

    # And IDs are unique within a run.
    assert len(set(ids1)) == len(ids1)


def test_gather_emits_all_expected_sources(tmp_path, monkeypatch):
    vault = _fixture_vault(tmp_path)
    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=vault)
    by_source = {s.source for s in signals}
    assert "meeting_notes" in by_source
    assert "project_docs" in by_source
    assert "tasks" in by_source
    assert "session_learnings" in by_source
    # person_pages dir missing — must be absent, not an error.
    assert "person_pages" not in by_source
