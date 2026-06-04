"""Identity loader: happy path, partial files, empty vault."""

from __future__ import annotations

from pathlib import Path

from core.activation.draft import load_identity


def _write_identity(vault: Path, keys: dict) -> None:
    idir = vault / "System" / "identity"
    (idir / "amp").mkdir(parents=True, exist_ok=True)
    (idir / "user").mkdir(parents=True, exist_ok=True)
    for rel, content in keys.items():
        p = idir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def test_load_identity_all_files_present(tmp_path: Path):
    vault = tmp_path / "vault"
    _write_identity(
        vault,
        {
            "amp/SOUL.md": "amp soul",
            "amp/STYLE.md": "amp style",
            "user/SOUL.md": "user soul",
            "user/STYLE.md": "user style",
            "README.md": "overview",
        },
    )
    got = load_identity(vault)
    assert got == {
        "amp_soul": "amp soul",
        "amp_style": "amp style",
        "user_soul": "user soul",
        "user_style": "user style",
        "overview": "overview",
    }


def test_load_identity_missing_files_return_empty(tmp_path: Path, capsys):
    vault = tmp_path / "vault"
    _write_identity(vault, {"amp/SOUL.md": "only soul"})
    got = load_identity(vault)
    assert got["amp_soul"] == "only soul"
    assert got["amp_style"] == ""
    assert got["user_soul"] == ""
    assert got["user_style"] == ""
    assert got["overview"] == ""
    # Warnings went to stderr.
    err = capsys.readouterr().err
    assert "identity file not found" in err


def test_load_identity_empty_vault(tmp_path: Path, capsys):
    vault = tmp_path / "vault"
    vault.mkdir()
    got = load_identity(vault)
    assert set(got.keys()) == {
        "amp_soul", "amp_style", "user_soul", "user_style", "overview"
    }
    assert all(v == "" for v in got.values())
    # Should warn for all 5.
    err = capsys.readouterr().err
    assert err.count("identity file not found") == 5
