"""Sprint 7 M2 — install.yaml hardening (corrupt abort, drift sidecar)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from core.activation.ghost import read_install_date


def test_corrupt_yaml_aborts(tmp_path: Path):
    p = tmp_path / "install.yaml"
    p.write_text("install_date: : : :\n  - bad\n[broken", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        read_install_date(p)
    assert "install.yaml" in str(exc.value)


def test_unparseable_install_date_aborts(tmp_path: Path):
    p = tmp_path / "install.yaml"
    p.write_text("install_date: not-a-date\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        read_install_date(p)


def test_missing_file_bootstraps_quietly(tmp_path: Path, capsys):
    act = tmp_path / "System" / "activation"
    act.mkdir(parents=True)
    p = act / "install.yaml"
    today = read_install_date(p)
    assert today == datetime.now(timezone.utc).date()
    assert p.exists()
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err  # no drift sidecar


def test_missing_file_with_drift_writes_sidecar(tmp_path: Path, capsys):
    act = tmp_path / "System" / "activation"
    act.mkdir(parents=True)
    (act / "ghost-log.md").write_text("prior activity here\n", encoding="utf-8")
    p = act / "install.yaml"
    read_install_date(p)
    sidecars = list(act.glob("install.yaml.recovered.*"))
    assert len(sidecars) == 1
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "Sprint 7 M2" in captured.err


def test_missing_install_date_field_heals_silently(tmp_path: Path):
    p = tmp_path / "install.yaml"
    p.write_text(yaml.safe_dump({"other_key": "value"}), encoding="utf-8")
    today = read_install_date(p)
    assert today == datetime.now(timezone.utc).date()
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert data["install_date"] == today.isoformat()
    assert data["other_key"] == "value"
