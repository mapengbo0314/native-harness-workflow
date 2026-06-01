"""A6 — gzipped base sidecar for customizable files (the 3-way merge base)."""
from pathlib import Path

from harness.update.manifest import write_manifest, write_base_sidecar, read_base


def _fixture(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    (pkg / "templates" / "boilerplate" / "agents").mkdir(parents=True)
    (pkg.parent / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    (pkg / "templates/boilerplate/agents/a.md").write_text("agent base\n")
    (plug / "agents").mkdir(parents=True)
    (plug / "agents" / "a.md").write_text("agent base\n")
    (plug / "src").mkdir(parents=True)
    (plug / "src" / "dispatcher.py").write_text("v1\n")  # generated: no sidecar
    return pkg, plug


def test_sidecar_written_only_for_customizable(tmp_path):
    pkg, plug = _fixture(tmp_path)
    meta = write_manifest(plug, pkg, render_context={})
    write_base_sidecar(plug, meta)

    base_dir = plug / ".harness-meta" / "base"
    assert (base_dir / "agents" / "a.md.gz").exists()      # customizable
    assert not (base_dir / "src" / "dispatcher.py.gz").exists()  # generated


def test_read_base_round_trips(tmp_path):
    pkg, plug = _fixture(tmp_path)
    meta = write_manifest(plug, pkg, render_context={})
    write_base_sidecar(plug, meta)
    assert read_base(plug, "agents/a.md") == "agent base\n"


def test_read_base_missing_returns_none(tmp_path):
    pkg, plug = _fixture(tmp_path)
    write_manifest(plug, pkg, render_context={})
    assert read_base(plug, "agents/a.md") is None
