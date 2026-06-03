import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import harness
from harness.init.cli import run_update, parse_args
from harness.update.manifest import read_manifest

def test_adopt_mode_synthesizes_manifest(tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_dir = project_path / ".claude"
    config_dir.mkdir()
    plugin_dir = config_dir / "harness-wf-plugin"
    plugin_dir.mkdir()
    
    with patch("sys.argv", ["harness-wf", "update", "--project-path", str(project_path), "--adopt", "--check"]):
        args = parse_args()
    
    # Just run update with adopt
    run_update(args)
    
    # Manifest should have been synthesized
    manifest_path = plugin_dir / ".harness-meta.json"
    assert manifest_path.exists()
    
    # It should have basic fields set from write_manifest
    manifest = json.loads(manifest_path.read_text())
    assert manifest["render_context"]["harness_dir_name"] == ".claude"
    assert manifest["render_context"]["platform"] == "claude"
    assert manifest["render_context"]["selected_agents"] == []
