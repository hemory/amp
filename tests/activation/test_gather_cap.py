"""Cap enforcement: 200 per meeting source and 500 global."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.activation.gather import gather
from core.activation.gather import MEETING_CAP, GLOBAL_CAP

from vault_fixture import build_vault, set_mtime


FROZEN_NOW = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


def test_meeting_cap_at_200_and_global_cap_at_500_keeps_most_recent(tmp_path, monkeypatch):
    # 600 meeting notes, mtime = now - i hours. i=0 is newest.
    vault = tmp_path / "vault"
    build_vault(vault)
    base = vault / "04-Projects" / "Stress"
    base.mkdir(parents=True, exist_ok=True)
    for i in range(600):
        p = base / f"meeting-{i:04d}.md"
        p.write_text(f"# note {i}\n", encoding="utf-8")
        set_mtime(p, FROZEN_NOW - timedelta(minutes=i))

    import core.activation.gather as g

    monkeypatch.setattr(g, "_calendar_fetcher", lambda: None)

    signals = gather(now=FROZEN_NOW, vault_root=vault)

    meeting = [s for s in signals if s.source == "meeting_notes"]
    assert len(meeting) <= MEETING_CAP
    assert len(signals) <= GLOBAL_CAP

    # Newest kept: meeting-0000 must be present, meeting-0599 must not.
    kept = {s.path for s in meeting}
    assert any(p.endswith("meeting-0000.md") for p in kept)
    assert not any(p.endswith("meeting-0599.md") for p in kept)
