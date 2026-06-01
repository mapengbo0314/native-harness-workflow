"""A2/A3 — normalize+hash helper and the ownership manifest writer/reader.

write_manifest is tested standalone against a fixture tree (it is wired into
the real mint flow in Phase C).  No mutation of any real .claude/ here.
"""
import json
from pathlib import Path

import pytest

from harness.update.manifest import (
    normalize_and_hash,
    hash_file,
    write_manifest,
    read_manifest,
)


# --- A2: normalization is line-ending / trailing-whitespace insensitive -----

def test_crlf_and_lf_hash_identically():
    assert normalize_and_hash("a\r\nb\r\n") == normalize_and_hash("a\nb\n")


def test_trailing_whitespace_and_final_newlines_ignored():
    assert normalize_and_hash("a\nb") == normalize_and_hash("a   \nb\n\n\n")


def test_different_content_differs():
    assert normalize_and_hash("a\nb") != normalize_and_hash("a\nc")


def test_hash_file_reads_and_normalizes(tmp_path):
    f = tmp_path / "x.txt"
    f.write_bytes(b"hello\r\nworld\r\n")
    assert hash_file(f) == normalize_and_hash("hello\nworld")


# --- A3: manifest writer over a fixture plugin tree -------------------------

@pytest.fixture
def fake_package(tmp_path) -> Path:
    """A stand-in for src/harness/ with the upstream sources update compares against."""
    pkg = tmp_path / "pkg"
    (pkg / "runtime").mkdir(parents=True)
    (pkg / "runtime" / "dispatcher.py").write_text("print('dispatch v1')\n")
    (pkg / "templates" / "boilerplate" / "skills" / "diagnose").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "skills" / "diagnose" / "SKILL.md").write_text("# diagnose\n")
    # pyproject for version stamping
    (pkg.parent / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n')
    return pkg


@pytest.fixture
def fake_plugin(tmp_path) -> Path:
    """A stand-in deployed plugin dir (.claude/harness-wf-plugin/)."""
    plug = tmp_path / "harness-wf-plugin"
    (plug / "src").mkdir(parents=True)
    (plug / "src" / "dispatcher.py").write_text("print('dispatch v1')\n")
    (plug / "skills" / "diagnose").mkdir(parents=True)
    (plug / "skills" / "diagnose" / "SKILL.md").write_text("# diagnose\n")
    (plug / "agents.json").write_text('{"agents": []}\n')
    # pollution + secrets that must be excluded
    (plug / "state").mkdir()
    (plug / "state" / "campaign.json").write_text("{}")
    (plug / ".env.telemetry-harness").write_text("KEY=secret\n")
    (plug / "src" / "__pycache__").mkdir()
    (plug / "src" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    return plug


def test_write_manifest_owns_and_hashes_correctly(fake_plugin, fake_package):
    meta = write_manifest(fake_plugin, fake_package, render_context={"harness_dir_name": ".claude", "platform": "claude"})
    owned = meta["owned"]

    # runtime file: source resolved + hashed, matches upstream
    disp = owned["src/dispatcher.py"]
    assert disp["class"] == "generated"
    assert disp["producer"] == "runtime_copy"
    assert disp["source_path"] == "runtime/dispatcher.py"
    assert disp["source_hash"] == hash_file(fake_package / "runtime" / "dispatcher.py")
    assert disp["rendered_hash"] == hash_file(fake_plugin / "src" / "dispatcher.py")

    # customizable skill
    assert owned["skills/diagnose/SKILL.md"]["class"] == "customizable"

    # derived projection: no source
    assert owned["agents.json"]["class"] == "derived"
    assert owned["agents.json"]["source_hash"] is None


def test_write_manifest_excludes_pollution_and_secrets(fake_plugin, fake_package):
    meta = write_manifest(fake_plugin, fake_package, render_context={})
    owned = meta["owned"]
    assert not any(k.startswith("state") for k in owned)
    assert ".env.telemetry-harness" not in owned
    assert not any("__pycache__" in k for k in owned)
    assert ".harness-meta.json" not in owned


def test_write_manifest_stamps_version_and_context(fake_plugin, fake_package):
    meta = write_manifest(fake_plugin, fake_package, render_context={"platform": "claude"})
    assert meta["harness_version"] == "9.9.9"
    assert meta["render_context"]["platform"] == "claude"
    assert "built_at" in meta


def test_round_trip_read_manifest(fake_plugin, fake_package):
    write_manifest(fake_plugin, fake_package, render_context={"platform": "claude"})
    loaded = read_manifest(fake_plugin)
    assert loaded["render_context"]["platform"] == "claude"
    assert "src/dispatcher.py" in loaded["owned"]
