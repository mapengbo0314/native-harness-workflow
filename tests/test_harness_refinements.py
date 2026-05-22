import os
import json
import pytest
from pathlib import Path
from harness.dispatcher import OrchestratorDispatcher

def test_dispatcher_gatekeeper_enforcement(tmp_path):
    # Setup mock config dir
    config_dir = tmp_path / ".claude" / "plugin-generated" / "config"
    config_dir.mkdir(parents=True)
    
    # Create fake gatekeeper script that fails
    scripts_dir = tmp_path / ".claude" / "plugin-generated" / "scripts"
    scripts_dir.mkdir(parents=True)
    gatekeeper_py = scripts_dir / "gatekeeper.py"
    gatekeeper_py.write_text("import sys; print('Missing plan'); sys.exit(1)")
    
    dispatcher = OrchestratorDispatcher(str(config_dir))
    
    with pytest.raises(PermissionError, match="Gatekeeper Phase 3 failed"):
        dispatcher.validate_against_rules("implementer")
        
    # Test pass
    gatekeeper_py.write_text("import sys; sys.exit(0)")
    assert dispatcher.validate_against_rules("implementer") is True
