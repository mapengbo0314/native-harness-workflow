import json
from pathlib import Path
from unittest.mock import patch

import harness
from harness.update.updater import _migrate_b0_paths
from harness.update.manifest import hash_file

def test_migrate_b0_paths_moves_and_injects_into_manifest(tmp_path):
    harness_dir = tmp_path / ".claude"
    harness_dir.mkdir()
    plugin_dir = harness_dir / "harness-wf-plugin"
    plugin_dir.mkdir()
    package_root = Path(harness.__file__).parent
    
    # Create old B0 paths
    rules_dir = harness_dir / "rules"
    rules_dir.mkdir()
    (rules_dir / "core_mandates.md").write_text("old mandates")
    
    (harness_dir / "agent.json").write_text('{"old": "agent"}')
    (harness_dir / "skills.json").write_text('{"old": "skills"}')
    
    manifest = {"owned": {}}
    
    _migrate_b0_paths(manifest, harness_dir, plugin_dir, package_root, dry_run=False)
    
    # Check physical move
    assert not (harness_dir / "rules").exists()
    assert not (harness_dir / "agent.json").exists()
    assert not (harness_dir / "skills.json").exists()
    
    assert (plugin_dir / "rules" / "core_mandates.md").exists()
    assert (plugin_dir / "agent.json").exists()
    assert (plugin_dir / "skills.json").exists()
    
    # Check manifest injection
    assert "rules/core_mandates.md" in manifest["owned"]
    assert "agent.json" in manifest["owned"]
    assert "skills.json" in manifest["owned"]
    
    assert manifest["owned"]["agent.json"]["class"] == "generated"
    assert manifest["owned"]["agent.json"]["source_hash"] == hash_file(package_root / "templates" / "boilerplate" / "agent.json")
    assert manifest["owned"]["agent.json"]["rendered_hash"] == hash_file(plugin_dir / "agent.json")

def test_migrate_b0_paths_dry_run(tmp_path):
    harness_dir = tmp_path / ".claude"
    harness_dir.mkdir()
    plugin_dir = harness_dir / "harness-wf-plugin"
    plugin_dir.mkdir()
    package_root = Path(harness.__file__).parent
    
    # Create old B0 paths
    (harness_dir / "agent.json").write_text('{"old": "agent"}')
    
    manifest = {"owned": {}}
    
    _migrate_b0_paths(manifest, harness_dir, plugin_dir, package_root, dry_run=True)
    
    # Physical file should NOT have moved
    assert (harness_dir / "agent.json").exists()
    assert not (plugin_dir / "agent.json").exists()
    
    # But it should be injected in the manifest with rendered hash of the original physical file
    assert "agent.json" in manifest["owned"]
    assert manifest["owned"]["agent.json"]["rendered_hash"] == hash_file(harness_dir / "agent.json")
