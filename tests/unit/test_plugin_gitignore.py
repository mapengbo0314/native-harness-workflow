"""The minted plugin .gitignore must merge, not clobber, and must cover .venv.

The hooks run via `uv run` with a pyproject.toml in the plugin dir, so uv
materializes .venv/ + uv.lock inside the plugin on first hook execution —
without .venv/ ignored, a target repo whose root .gitignore lacks the pattern
commits ~76MB of venv. And re-minting over an existing plugin must preserve
any entries the user added themselves."""
from __future__ import annotations

from harness.init.plugin_generator import _write_plugin_gitignore

REQUIRED = ("state/", "logs/", ".venv/")


def test_fresh_plugin_gets_all_required_entries(tmp_path):
    _write_plugin_gitignore(tmp_path)
    lines = (tmp_path / ".gitignore").read_text().splitlines()
    for entry in REQUIRED:
        assert entry in lines


def test_existing_user_entries_are_preserved(tmp_path):
    (tmp_path / ".gitignore").write_text("# mine\nmy-scratch/\nlogs/\n")
    _write_plugin_gitignore(tmp_path)
    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert "# mine" in lines
    assert "my-scratch/" in lines
    for entry in REQUIRED:
        assert entry in lines


def test_overlapping_entries_are_not_duplicated(tmp_path):
    (tmp_path / ".gitignore").write_text("state/\nlogs/\n")
    _write_plugin_gitignore(tmp_path)
    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert lines.count("state/") == 1
    assert lines.count("logs/") == 1


def test_idempotent_across_reminting(tmp_path):
    _write_plugin_gitignore(tmp_path)
    first = (tmp_path / ".gitignore").read_text()
    _write_plugin_gitignore(tmp_path)
    assert (tmp_path / ".gitignore").read_text() == first
