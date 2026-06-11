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


def test_plan_update_force(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    (pkg / "templates/boilerplate/skills/s/SKILL.md").write_text("skill\n")
    (plug / "skills/s/SKILL.md").write_text("skill\n")
    write_manifest(plug, pkg, render_context={"platform": "claude"})

    # user edits on disk only -> normally keep-yours, but force forces apply
    (plug / "skills/s/SKILL.md").write_text("skill EDITED\n")

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg, force=True)}
    assert verdicts["skills/s/SKILL.md"] == "apply"


def test_plan_update_local_missing_policy_by_class(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    (pkg / "templates/boilerplate/skills/s/SKILL.md").write_text("skill\n")
    (plug / "skills/s/SKILL.md").write_text("skill\n")
    (plug / "agents.json").write_text("{}\n")
    write_manifest(plug, pkg, render_context={})

    (plug / "src" / "dispatcher.py").unlink()
    (plug / "skills/s/SKILL.md").unlink()
    (plug / "agents.json").unlink()

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    assert verdicts["src/dispatcher.py"] == "restore-missing"
    assert verdicts["skills/s/SKILL.md"] == "restore-missing"
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


# ---------------------------------------------------------------------------
# Phase 1b: verdicts respect the stack filter (C4 fix)
# ---------------------------------------------------------------------------

def _mk_with_packs(pkg: Path, plug: Path) -> None:
    """Extend _mk with rules/packs layout for pack-filter tests."""
    _mk(pkg, plug)
    # Create upstream pack dirs in the package tree
    (pkg / "templates" / "boilerplate" / "rules" / "packs" / "python").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "rules" / "packs" / "golang").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "rules" / "packs" / "common").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "rules" / "packs" / "python" / "python.md").write_text("# python rules\n")
    (pkg / "templates" / "boilerplate" / "rules" / "packs" / "golang" / "golang.md").write_text("# golang rules\n")
    (pkg / "templates" / "boilerplate" / "rules" / "packs" / "common" / "base.md").write_text("# common\n")


def test_golang_pack_not_proposed_for_python_only_manifest(tmp_path):
    """C4 fix: golang pack files are NOT new-file proposed when manifest says python-only."""
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk_with_packs(pkg, plug)

    # Mint with python-only filter in render_context
    write_manifest(plug, pkg, render_context={
        "platform": "claude",
        "rules_packs": {"selected": ["python"], "enabled": True},
    })

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    # golang pack file must NOT be proposed
    assert "rules/packs/golang/golang.md" not in verdicts


def test_python_pack_updated_content_still_delivered(tmp_path):
    """Python pack files with new upstream content are still proposed when python is selected."""
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk_with_packs(pkg, plug)

    # Deploy python pack file and write manifest
    (plug / "rules" / "packs" / "python").mkdir(parents=True)
    (plug / "rules" / "packs" / "python" / "python.md").write_text("# python rules\n")
    write_manifest(plug, pkg, render_context={
        "platform": "claude",
        "rules_packs": {"selected": ["python"], "enabled": True},
    })

    # Upstream python pack changes
    (pkg / "templates" / "boilerplate" / "rules" / "packs" / "python" / "python.md").write_text("# python rules v2\n")

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    # python pack should be proposed (apply or new-file)
    assert "rules/packs/python/python.md" in verdicts
    assert verdicts["rules/packs/python/python.md"] in ("apply", "new-file")


def test_empty_selected_fails_open_like_null(tmp_path):
    """Empty selected list (unknown stack at mint) must fail-open, not exclude everything.

    A first mint without domain.json records selected=[] because the stack is
    unknown.  That empty list must be treated the same as None (fail-open) so
    the repo can still receive language packs on update.
    """
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk_with_packs(pkg, plug)

    # Manifest written with empty selected — simulates first mint without domain.json
    write_manifest(plug, pkg, render_context={
        "platform": "claude",
        "rules_packs": {"selected": [], "enabled": True},
    })

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    # python pack MUST be proposed (fail-open: unknown stack ≠ no languages wanted)
    assert "rules/packs/python/python.md" in verdicts, (
        f"python pack not proposed with empty selected — got: {list(verdicts)}"
    )


def test_pack_files_excluded_when_rules_packs_disabled(tmp_path):
    """When rules_packs.enabled=False, NO pack files are proposed."""
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk_with_packs(pkg, plug)

    write_manifest(plug, pkg, render_context={
        "platform": "claude",
        "rules_packs": {"selected": [], "enabled": False},
    })

    verdicts = {v.relpath: v.verdict for v in plan_update(plug, pkg)}
    pack_verdicts = {k: v for k, v in verdicts.items() if k.startswith("rules/packs/")}
    assert len(pack_verdicts) == 0, f"Expected no pack verdicts, got: {pack_verdicts}"


# ---------------------------------------------------------------------------
# Phase 1b: mirror regeneration + features recompile on apply_update
# ---------------------------------------------------------------------------

def _mk_pack_plugin(pkg: Path, plug: Path, project: Path) -> None:
    """Set up a minimal project with a deployed plugin that has rules packs."""
    _mk_with_packs(pkg, plug)

    # Deploy the python pack into the plugin dir (simulates a previously-installed plugin)
    (plug / "rules" / "packs" / "python").mkdir(parents=True)
    (plug / "rules" / "packs" / "python" / "python.md").write_text("OLD python rules\n")

    # Deploy common pack too (always present)
    (plug / "rules" / "packs" / "common").mkdir(parents=True)
    (plug / "rules" / "packs" / "common" / "base.md").write_text("# common\n")

    # Simulate an existing mirror install with an OLD file plus an operator edit
    mirror_dir = project / ".claude" / "rules" / "harness" / "python"
    mirror_dir.mkdir(parents=True)
    (mirror_dir / "python.md").write_text("OLD python rules\nOperator-added line\n")

    # common mirror also pre-exists
    common_mirror = project / ".claude" / "rules" / "harness" / "common"
    common_mirror.mkdir(parents=True)
    (common_mirror / "base.md").write_text("# common old\n")

    # domain.json in the location install_rules_packs reads:
    # <project>/.claude/harness-wf-plugin/domain/domain.json
    domain_dir = project / ".claude" / "harness-wf-plugin" / "domain"
    domain_dir.mkdir(parents=True)
    (domain_dir / "domain.json").write_text('{"stack": ["Python"]}\n')

    # features.json enabling rules_packs
    (plug / "features.json").write_text('{"rules_packs": {"enabled": true}}\n')

    # pyproject.toml
    (pkg.parent / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')


def test_post_apply_hooks_regenerates_mirror_with_new_content(tmp_path):
    """Real-FS: _post_apply_hooks regenerates the mirror from the NEW pack content.

    The operator-edited line in the OLD mirror must be gone; the NEW upstream
    content (from the package template) must be present; common/ must also be
    installed.
    """
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    project = tmp_path / "project"
    _mk_pack_plugin(pkg, plug, project)

    # Write manifest with python-only selection
    write_manifest(plug, pkg, render_context={
        "platform": "claude",
        "rules_packs": {"selected": ["python"], "enabled": True},
    })

    # Simulate upstream NEW content in the package template
    (pkg / "templates" / "boilerplate" / "rules" / "packs" / "python" / "python.md").write_text(
        "NEW python rules v2\n"
    )
    # Also update the deployed plugin pack to reflect what an apply would do
    (plug / "rules" / "packs" / "python" / "python.md").write_text("NEW python rules v2\n")

    from harness.update.updater import _post_apply_hooks
    _post_apply_hooks(plug, project)

    mirror_file = project / ".claude" / "rules" / "harness" / "python" / "python.md"
    assert mirror_file.exists(), "mirror file must be regenerated"
    content = mirror_file.read_text(encoding="utf-8")
    assert content == "NEW python rules v2\n", (
        f"Mirror must have NEW content, got: {content!r}"
    )
    assert "Operator-added line" not in content, "Operator-added line must be erased"

    # common/ must be present in the mirror
    common_mirror = project / ".claude" / "rules" / "harness" / "common" / "base.md"
    assert common_mirror.exists(), "common/ must be present in mirror"


def test_apply_update_calls_install_rules_packs_and_compile_features(tmp_path):
    """After apply_update with a project_root, install_rules_packs and compile_features are called."""
    import unittest.mock as mock
    from harness.update.updater import apply_update

    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    harness_d = tmp_path / "harness"
    project = tmp_path / "project"
    _mk(pkg, plug)
    harness_d.mkdir()
    project.mkdir()

    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    (pkg.parent / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    write_manifest(plug, pkg, render_context={"platform": "claude"})

    # Make an upstream change so apply has something to do
    (pkg / "runtime" / "dispatcher.py").write_text("v2\n")

    with mock.patch("harness.update.updater.install_rules_packs") as mock_irp, \
         mock.patch("harness.update.updater.compile_features") as mock_cf:
        mock_cf.return_value = None
        apply_update(
            plug, pkg,
            harness_dir=harness_d,
            headless=True,
            project_root=project,
        )
        mock_irp.assert_called_once()
        mock_cf.assert_called_once()
