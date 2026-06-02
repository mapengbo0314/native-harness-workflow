"""Phase C apply/recovery tests for `harness-wf update`."""
import json
from pathlib import Path

import pytest

from harness.update.conflict import ConflictResolutionAborted
from harness.update.manifest import read_manifest, write_base_sidecar, write_manifest
from harness.update.updater import (
    JOURNAL_FILENAME,
    _commit_staged_files,
    apply_update,
    recover_journal,
    UpdateRequiresHuman,
)


def _mk(pkg: Path, plug: Path):
    (pkg / "runtime").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "agents").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "skills" / "s").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "scripts").mkdir(parents=True)
    (pkg.parent / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    (plug / "src").mkdir(parents=True)
    (plug / "agents").mkdir(parents=True)
    (plug / "skills" / "s").mkdir(parents=True)


def _stamp(plug: Path, pkg: Path):
    manifest = write_manifest(
        plug,
        pkg,
        render_context={"platform": "claude", "harness_dir_name": ".claude", "selected_agents": []},
    )
    write_base_sidecar(plug, manifest)
    return manifest


def test_apply_update_refreshes_generated_file_and_stamps_manifest(tmp_path):
    pkg = tmp_path / "pkg"
    harness_dir = tmp_path / ".claude"
    plug = harness_dir / "harness-wf-plugin"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    _stamp(plug, pkg)

    (pkg / "runtime" / "dispatcher.py").write_text("v2\n")

    apply_update(plug, pkg, harness_dir=harness_dir)

    assert (plug / "src" / "dispatcher.py").read_text() == "v2\n"
    assert not (plug / JOURNAL_FILENAME).exists()
    manifest = read_manifest(plug)
    assert manifest["owned"]["src/dispatcher.py"]["rendered_hash"]


def test_apply_update_stamps_manifest_with_installed_package_version(tmp_path):
    pkg = tmp_path / "pkg"
    harness_dir = tmp_path / ".claude"
    plug = harness_dir / "harness-wf-plugin"
    _mk(pkg, plug)
    (pkg.parent / "pyproject.toml").write_text('[project]\nversion = "1.2.0"\n')
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    manifest = _stamp(plug, pkg)
    manifest["harness_version"] = "1.1.0"
    (plug / ".harness-meta.json").write_text(json.dumps(manifest, indent=2) + "\n")

    (pkg / "runtime" / "dispatcher.py").write_text("v2\n")

    apply_update(plug, pkg, harness_dir=harness_dir)

    assert read_manifest(plug)["harness_version"] == "1.2.0"


def test_apply_update_headless_requires_human_leaves_disk_unchanged(tmp_path):
    pkg = tmp_path / "pkg"
    harness_dir = tmp_path / ".claude"
    plug = harness_dir / "harness-wf-plugin"
    _mk(pkg, plug)
    (pkg / "templates" / "boilerplate" / "skills" / "s" / "SKILL.md").write_text("skill\n")
    skill = plug / "skills" / "s" / "SKILL.md"
    skill.write_text("skill\n")
    _stamp(plug, pkg)
    skill.unlink()

    with pytest.raises(UpdateRequiresHuman):
        apply_update(plug, pkg, harness_dir=harness_dir, headless=True)

    assert not skill.exists()
    assert not (plug / JOURNAL_FILENAME).exists()


def test_apply_update_resolves_conflict_before_live_writes(tmp_path):
    pkg = tmp_path / "pkg"
    harness_dir = tmp_path / ".claude"
    plug = harness_dir / "harness-wf-plugin"
    _mk(pkg, plug)
    source = pkg / "templates" / "boilerplate" / "agents" / "a.md"
    deployed = plug / "agents" / "a.md"
    source.write_text("base\n")
    deployed.write_text("base\n")
    _stamp(plug, pkg)

    source.write_text("theirs\n")
    deployed.write_text("ours\n")

    with pytest.raises(ConflictResolutionAborted):
        apply_update(plug, pkg, harness_dir=harness_dir, input_fn=lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    assert deployed.read_text() == "ours\n"
    assert not (plug / JOURNAL_FILENAME).exists()


def test_apply_update_regenerates_derived_from_staged_markdown(tmp_path):
    pkg = tmp_path / "pkg"
    harness_dir = tmp_path / ".claude"
    plug = harness_dir / "harness-wf-plugin"
    _mk(pkg, plug)
    source = pkg / "templates" / "boilerplate" / "agents" / "a.md"
    deployed = plug / "agents" / "a.md"
    source.write_text("# Agent A\nbase")
    deployed.write_text("# Agent A\nbase")
    (plug / "agents.json").write_text("{}\n")
    _stamp(plug, pkg)

    source.write_text("# Agent A\nnew upstream")

    apply_update(plug, pkg, harness_dir=harness_dir)

    data = json.loads((plug / "agents.json").read_text())
    assert data["agents"]["a"]["source"] == "# Agent A\nnew upstream"


def test_recover_journal_restores_backups_and_removes_new_files(tmp_path):
    plug = tmp_path / "plug"
    plug.mkdir()
    target = plug / "src" / "dispatcher.py"
    backup = plug / ".harness-meta" / "update-backups" / "tx" / "src" / "dispatcher.py"
    new_target = plug / "scripts" / "new.sh"
    target.parent.mkdir()
    target.write_text("new\n")
    backup.parent.mkdir(parents=True)
    backup.write_text("old\n")
    new_target.parent.mkdir()
    new_target.write_text("created\n")
    (plug / JOURNAL_FILENAME).write_text(json.dumps({
        "id": "tx",
        "entries": [
            {"target": str(target), "backup": str(backup), "existed": True},
            {"target": str(new_target), "backup": str(plug / ".harness-meta" / "update-backups" / "tx" / "scripts" / "new.sh"), "existed": False},
        ],
    }))

    recover_journal(plug)

    assert target.read_text() == "old\n"
    assert not new_target.exists()
    assert not (plug / JOURNAL_FILENAME).exists()


def test_apply_update_updates_marketplace_harness_entry_preserving_others(tmp_path):
    pkg = tmp_path / "pkg"
    harness_dir = tmp_path / ".claude"
    plug = harness_dir / "harness-wf-plugin"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    market = harness_dir / ".claude-plugin" / "marketplace.json"
    market.parent.mkdir(parents=True)
    market.write_text(json.dumps({
        "name": "local",
        "version": "market-owned",
        "plugins": [
            {"name": "other-plugin", "source": "./other", "custom": True},
            {"name": "orchestrator-plugin", "source": "./old", "custom": "keep"},
        ],
    }))
    _stamp(plug, pkg)
    (pkg / "runtime" / "dispatcher.py").write_text("v2\n")

    apply_update(plug, pkg, harness_dir=harness_dir)

    data = json.loads(market.read_text())
    assert data["plugins"][0] == {"name": "other-plugin", "source": "./other", "custom": True}
    assert data["version"] == "market-owned"
    harness_entry = data["plugins"][1]
    assert harness_entry["name"] == "orchestrator-plugin"
    assert harness_entry["source"] == "./harness-wf-plugin"
    assert harness_entry["custom"] == "keep"


def test_apply_update_preserves_unrelated_plugin_json_fields(tmp_path):
    pkg = tmp_path / "pkg"
    harness_dir = tmp_path / ".claude"
    plug = harness_dir / "harness-wf-plugin"
    _mk(pkg, plug)
    (plug / ".claude-plugin").mkdir(parents=True)
    (plug / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "orchestrator-plugin",
        "version": "old",
        "description": "project-specific description",
        "author": {"name": "Project Author"},
        "x-claude-managed": {"keep": True},
    }))
    _stamp(plug, pkg)

    apply_update(plug, pkg, harness_dir=harness_dir)

    data = json.loads((plug / ".claude-plugin" / "plugin.json").read_text())
    assert data["version"] == "1.0.0"
    assert data["description"] == "project-specific description"
    assert data["author"] == {"name": "Project Author"}
    assert data["x-claude-managed"] == {"keep": True}


def test_apply_update_formats_readme_template_with_project_name(tmp_path):
    pkg = tmp_path / "pkg"
    harness_dir = tmp_path / "demo-project" / ".claude"
    plug = harness_dir / "harness-wf-plugin"
    _mk(pkg, plug)
    source = pkg / "templates" / "boilerplate" / "README.md.template"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# {project_name}\n")
    (plug / "README.md").write_text("# old\n")
    manifest = write_manifest(
        plug,
        pkg,
        render_context={
            "platform": "claude",
            "harness_dir_name": ".claude",
            "selected_agents": [],
            "project_name": "demo-project",
        },
    )
    manifest["owned"]["README.md"]["source_hash"] = "old-source"
    (plug / ".harness-meta.json").write_text(json.dumps(manifest, indent=2) + "\n")

    apply_update(plug, pkg, harness_dir=harness_dir)

    assert (plug / "README.md").read_text() == "# demo-project\n"


def test_recover_journal_restores_manifest_if_crash_after_manifest_commit(tmp_path):
    plug = tmp_path / "plug"
    staged = tmp_path / "staged"
    plug.mkdir()
    staged.mkdir()
    (plug / ".harness-meta.json").write_text('{"old": true}\n')
    (staged / ".harness-meta.json").write_text('{"new": true}\n')

    _commit_staged_files(plug, staged, [".harness-meta.json"])
    assert json.loads((plug / ".harness-meta.json").read_text()) == {"new": True}

    recover_journal(plug)

    assert json.loads((plug / ".harness-meta.json").read_text()) == {"old": True}
