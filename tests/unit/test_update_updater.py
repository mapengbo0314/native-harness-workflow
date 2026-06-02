"""A4 — the two-hash verdict engine (R1).

`verdict()` is the pure truth table.  `plan_update()` maps it over a manifest
by reading on-disk + upstream hashes (reads only, never writes).
"""
from pathlib import Path

import pytest

from harness.update.updater import verdict, plan_update
from harness.update.manifest import write_manifest, read_manifest, hash_file


@pytest.mark.parametrize("we_changed,user_edited,expected", [
    (False, False, "current"),
    (True, False, "apply"),
    (False, True, "keep-yours"),
    (True, True, "conflict"),
])
def test_verdict_truth_table(we_changed, user_edited, expected):
    assert verdict(we_changed, user_edited) == expected


# --- plan_update over a fixture ---------------------------------------------

def _mk(pkg: Path, plug: Path):
    (pkg / "runtime").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "skills" / "s").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "agents").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "scripts").mkdir(parents=True)
    (pkg.parent / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    (plug / "src").mkdir(parents=True)
    (plug / "skills" / "s").mkdir(parents=True)
    (plug / "agents").mkdir(parents=True)


def test_plan_update_covers_all_buckets(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)

    # Seed upstream + deployed identical, then write the baseline manifest.
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    (pkg / "templates/boilerplate/skills/s/SKILL.md").write_text("skill\n")
    (plug / "skills/s/SKILL.md").write_text("skill\n")
    (pkg / "templates/boilerplate/agents/a.md").write_text("agent\n")
    (plug / "agents/a.md").write_text("agent\n")
    (plug / "agents.json").write_text("{}\n")
    write_manifest(plug, pkg, render_context={"platform": "claude"})

    # Now diverge:
    #  dispatcher: upstream changes (we changed) -> apply
    (pkg / "runtime" / "dispatcher.py").write_text("v2\n")
    #  SKILL.md: user edits on disk only -> keep-yours
    (plug / "skills/s/SKILL.md").write_text("skill EDITED\n")
    #  a.md: both change -> conflict
    (pkg / "templates/boilerplate/agents/a.md").write_text("agent v2\n")
    (plug / "agents/a.md").write_text("agent EDITED\n")

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["src/dispatcher.py"] == "apply"
    assert verdicts["skills/s/SKILL.md"] == "keep-yours"
    assert verdicts["agents/a.md"] == "conflict"
    assert verdicts["agents.json"] == "derived"


def test_plan_update_unchanged_is_current(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    write_manifest(plug, pkg, render_context={})
    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["src/dispatcher.py"] == "current"


def test_plan_update_user_deleted_file_is_flagged(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    write_manifest(plug, pkg, render_context={})
    (plug / "src" / "dispatcher.py").unlink()  # user deleted
    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["src/dispatcher.py"] == "restore-missing"


def test_plan_update_discovers_new_upstream_producer_paths(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    write_manifest(plug, pkg, render_context={})

    (pkg / "templates" / "boilerplate" / "scripts" / "refresh.sh").write_text("new\n")

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["scripts/refresh.sh"] == "new-file"


def test_plan_update_still_detects_removed_upstream_from_old_manifest(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    source = pkg / "runtime" / "dispatcher.py"
    source.write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    write_manifest(plug, pkg, render_context={})

    source.unlink()

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["src/dispatcher.py"] == "removed-upstream"


def test_removed_upstream_wins_over_local_missing(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    source = pkg / "runtime" / "dispatcher.py"
    source.write_text("v1\n")
    deployed = plug / "src" / "dispatcher.py"
    deployed.write_text("v1\n")
    write_manifest(plug, pkg, render_context={})

    source.unlink()
    deployed.unlink()

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["src/dispatcher.py"] == "removed-upstream"


def test_plan_update_local_missing_policy_by_class(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    (pkg / "templates" / "boilerplate" / "skills" / "s" / "SKILL.md").write_text("skill\n")
    (plug / "skills" / "s" / "SKILL.md").write_text("skill\n")
    (plug / "agents.json").write_text("{}\n")
    write_manifest(plug, pkg, render_context={})

    (plug / "src" / "dispatcher.py").unlink()
    (plug / "skills" / "s" / "SKILL.md").unlink()
    (plug / "agents.json").unlink()

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["src/dispatcher.py"] == "restore-missing"
    assert verdicts["skills/s/SKILL.md"] == "requires-human"
    assert verdicts["agents.json"] == "regenerate-missing"


def test_new_upstream_producer_collision_requires_human(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    write_manifest(plug, pkg, render_context={})

    (pkg / "templates" / "boilerplate" / "scripts" / "refresh.sh").write_text("new upstream\n")
    (plug / "scripts").mkdir()
    (plug / "scripts" / "refresh.sh").write_text("local user file\n")

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["scripts/refresh.sh"] == "requires-human"


def test_plan_update_ignores_local_files_outside_producer_paths(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    write_manifest(plug, pkg, render_context={})

    (plug / "notes.md").write_text("user file\n")

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert "notes.md" not in verdicts


def test_plan_update_owned_path_replaced_by_directory_requires_human(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    deployed = plug / "src" / "dispatcher.py"
    deployed.write_text("v1\n")
    write_manifest(plug, pkg, render_context={})

    deployed.unlink()
    deployed.mkdir()

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["src/dispatcher.py"] == "requires-human"
