"""Unit tests for harness.domain.seed — detect stack + scaffold domain.json
(manual slots empty, stack filled, references suggested) and the
.claude/docs/reference/ docs dir. Never clobbers an existing manifest."""
from __future__ import annotations

import json

from harness.domain import seed
from harness.domain.model import OpsManifest


def _init(tmp_path, **kw):
    return seed.run_domain_init(
        tmp_path,
        manifest_path=tmp_path / "plugin" / "domain" / "domain.json",
        reference_dir=tmp_path / ".claude" / "docs" / "reference",
        detect_stack_fn=kw.pop("detect_stack_fn", lambda p: ["Python", "fastapi"]),
        **kw,
    )


def test_creates_manifest_with_detected_stack_and_empty_slots(tmp_path):
    path = _init(tmp_path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["schema_version"] == 1
    assert data["stack"] == ["Python", "fastapi"]
    # manual slots are present but empty — engineers fill them later
    for slot in ("environments", "test", "deploy", "infra"):
        assert data[slot] == {}
    # loadable by the model
    assert OpsManifest.load(path).stack == ("Python", "fastapi")


def test_scaffolds_reference_dir_with_readme(tmp_path):
    _init(tmp_path)
    readme = tmp_path / ".claude" / "docs" / "reference" / "README.md"
    assert readme.exists()
    assert "domain-compile" in readme.read_text()


def test_suggests_references_from_doc_h1(tmp_path):
    (tmp_path / "README.md").write_text("# Acme Service\n\nbody\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "RELEASING.md").write_text("intro\n# How to release\n")
    path = _init(tmp_path)
    refs = json.loads(path.read_text())["references"]
    assert refs["README.md"] == "Acme Service"
    assert refs["docs/RELEASING.md"] == "How to release"


def test_does_not_clobber_existing_manifest(tmp_path):
    mp = tmp_path / "plugin" / "domain" / "domain.json"
    mp.parent.mkdir(parents=True)
    mp.write_text(json.dumps({"schema_version": 1, "stack": ["Go"], "deploy": {"command": "./ship"}}))
    seed.run_domain_init(
        tmp_path, manifest_path=mp,
        reference_dir=tmp_path / ".claude" / "docs" / "reference",
        detect_stack_fn=lambda p: ["Python"],
    )
    data = json.loads(mp.read_text())
    assert data["stack"] == ["Go"]                  # preserved, not overwritten
    assert data["deploy"] == {"command": "./ship"}  # authored content intact


def test_creates_parent_dirs(tmp_path):
    path = _init(tmp_path)
    assert path.parent.name == "domain"
    assert path.parent.exists()


# --- domain-refresh: re-detect stack, merge it, preserve authored fields ----

def test_refresh_updates_only_stack_preserving_authored_fields(tmp_path):
    mp = tmp_path / "plugin" / "domain" / "domain.json"
    mp.parent.mkdir(parents=True)
    mp.write_text(json.dumps({
        "schema_version": 1,
        "stack": ["Go"],
        "deploy": {"command": "./ship"},
        "business": {"direction": "grow"},
    }))
    seed.run_domain_refresh(
        tmp_path, manifest_path=mp, detect_stack_fn=lambda p: ["Python", "fastapi"],
    )
    data = json.loads(mp.read_text())
    assert data["stack"] == ["Python", "fastapi"]      # re-detected
    assert data["deploy"] == {"command": "./ship"}     # authored, preserved
    assert data["business"] == {"direction": "grow"}   # compiled, preserved


def test_refresh_is_noop_with_hint_when_manifest_missing(tmp_path):
    mp = tmp_path / "plugin" / "domain" / "domain.json"
    msgs = []
    seed.run_domain_refresh(
        tmp_path, manifest_path=mp,
        detect_stack_fn=lambda p: ["Python"], output_fn=msgs.append,
    )
    assert not mp.exists()                             # nothing created
    assert any("domain-init" in m for m in msgs)      # tells you what to run
