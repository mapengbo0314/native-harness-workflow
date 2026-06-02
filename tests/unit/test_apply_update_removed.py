import pytest
import shutil
from pathlib import Path
from harness.update.updater import apply_update, UpdateRequiresHuman
from harness.update.manifest import write_manifest

def _mk(pkg: Path, plug: Path):
    (pkg / "runtime").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "skills" / "s").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "agents").mkdir(parents=True)
    (pkg / "templates" / "boilerplate" / "scripts").mkdir(parents=True)
    # The pyproject.toml is expected at pkg.parent
    (pkg.parent / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    (plug / "src").mkdir(parents=True)
    (plug / "skills" / "s").mkdir(parents=True)
    (plug / "agents").mkdir(parents=True)

def test_apply_update_removed_generated_does_not_block(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    
    (pkg / "runtime" / "dispatcher.py").write_text("v1\n")
    (plug / "src" / "dispatcher.py").write_text("v1\n")
    
    write_manifest(plug, pkg, render_context={"platform": "claude", "harness_dir_name": ".claude"})
    
    # Remove it upstream
    (pkg / "runtime" / "dispatcher.py").unlink()
    
    # In same-major update, a removed generated file should NOT raise an exception.
    # It should just apply the removal.
    apply_update(plug, pkg, harness_dir=tmp_path / "harness")
    assert not (plug / "src" / "dispatcher.py").exists()

def test_apply_update_removed_customizable_blocks_without_force(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    
    (pkg / "templates" / "boilerplate" / "skills" / "s" / "SKILL.md").write_text("skill\n")
    (plug / "skills" / "s" / "SKILL.md").write_text("skill\n")
    
    write_manifest(plug, pkg, render_context={"platform": "claude", "harness_dir_name": ".claude"})
    
    # Remove it upstream
    (pkg / "templates" / "boilerplate" / "skills" / "s" / "SKILL.md").unlink()
    
    # It should block because it's customizable
    with pytest.raises(UpdateRequiresHuman, match="removed-upstream:skills/s/SKILL.md"):
        apply_update(plug, pkg, harness_dir=tmp_path / "harness")

def test_apply_update_removed_customizable_succeeds_with_force(tmp_path):
    pkg = tmp_path / "pkg"
    plug = tmp_path / "plug"
    _mk(pkg, plug)
    
    (pkg / "templates" / "boilerplate" / "skills" / "s" / "SKILL.md").write_text("skill\n")
    (plug / "skills" / "s" / "SKILL.md").write_text("skill\n")
    
    write_manifest(plug, pkg, render_context={"platform": "claude", "harness_dir_name": ".claude"})
    
    # Remove it upstream
    (pkg / "templates" / "boilerplate" / "skills" / "s" / "SKILL.md").unlink()
    
    # With force, it should not block and should be removed
    apply_update(plug, pkg, harness_dir=tmp_path / "harness", force=True)
    assert not (plug / "skills" / "s" / "SKILL.md").exists()
