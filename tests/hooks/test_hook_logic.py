import os
import shutil
import tempfile
import subprocess
import json
import sys
import shlex
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to sys.path to allow importing harness modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from harness.init.cli import main

@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_project_path = Path(tmp_dir)
        # Copy boilerplate
        src_path = Path("tests/fixtures/boilerplates/sample-py-app")
        shutil.copytree(src_path, tmp_project_path, dirs_exist_ok=True)
        
        # Init git as it might be needed by some tools
        subprocess.run(["git", "init"], cwd=tmp_dir, check=True, capture_output=True)
        
        yield tmp_project_path

def run_harness_init(project_path, platform_choice, llm="gemini", include_plugin=False, mock_should_gen_plugin=None):
    # Mock LLM response for discovery
    with patch('harness.init.discovery_engine.query_llm') as mock_query_llm, \
         patch('subprocess.run') as mock_run, \
         patch('urllib.request.urlopen') as mock_urlopen, \
         patch('harness.init.cli.parse_args') as mock_parse_args, \
         patch('sys.exit'):
        
        # Mock LLM response
        skills = []
        if include_plugin:
            skills.append({"name": "orchestrator-plugin", "url": "https://github.com/example/plugin", "type": "extension"})
        
        mock_query_llm.return_value = json.dumps({
            "sme_name": "test-sme", 
            "core_domain_value": "test value", 
            "invariants": ["inv1"], 
            "glossary": {"term": "def"}, 
            "domain_events": ["event1"], 
            "skills": skills, 
            "mcps": []
        })
        
        # Mock subprocess.run for codegraph init
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock urlopen for skill downloads (empty response)
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b""

        args = MagicMock()
        args.command = "init"
        args.project_path = str(project_path)
        args.llm = llm
        args.model = None
        args.bundle = None
        mock_parse_args.return_value = args

        env = {
            "HARNESS_HEADLESS": "1",
            "HARNESS_PLATFORM": platform_choice,
            "GEMINI_API_KEY": "fake-key",
            "ANTHROPIC_API_KEY": "fake-key",
            "OPENAI_API_KEY": "fake-key",
            "PATH": os.environ.get("PATH", "")
        }
        
        with patch.dict(os.environ, env):
            try:
                main()
            except SystemExit:
                pass

def test_registered_hook_commands_execute(temp_project):
    run_harness_init(temp_project, "2", llm="anthropic", include_plugin=True, mock_should_gen_plugin=True)
    
    plugin_dir = temp_project / ".claude" / "plugin-generated"
    assert not (plugin_dir / "src" / "hooks").exists()
    assert not (plugin_dir / "src" / "hook_validator.py").exists()

    state_dir = plugin_dir / "state"
    state_dir.mkdir(exist_ok=True)
    (temp_project / "artifacts").mkdir(parents=True, exist_ok=True)
    (temp_project / "artifacts" / "tdd_failing_test.log").write_text("AssertionError: mock failure")
    hooks_json = json.loads((plugin_dir / "hooks" / "hooks.json").read_text())
    payloads = {
        "UserPromptSubmit": {"hook_event_name": "UserPromptSubmit", "prompt": "build a login flow"},
        "PreToolUse": {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "src/app.py", "content": "print('ok')"},
        },
        "PostToolUse": {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/unit"},
        },
        "PostToolUseFailure": {
            "hook_event_name": "PostToolUseFailure",
            "type": "PostToolUseFailure",
            "error": "boom",
        },
        "PreCompact": {"hook_event_name": "PreCompact"},
        "Stop": {"hook_event_name": "Stop"},
        "ConfigChange": {"hook_event_name": "ConfigChange", "changes": []},
    }

    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(plugin_dir),
        "CLAUDE_PROJECT_DIR": str(temp_project),
    }
    for event_name, matcher_groups in hooks_json["hooks"].items():
        for group in matcher_groups:
            for hook in group["hooks"]:
                command = hook["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_dir))
                result = subprocess.run(
                    shlex.split(command),
                    input=json.dumps(payloads[event_name]),
                    cwd=temp_project,
                    capture_output=True,
                    text=True,
                    env=env,
                )
                assert result.returncode == 0, f"{event_name} failed: {result.stdout}\n{result.stderr}"

def test_hook_state_persistence(temp_project):
    run_harness_init(temp_project, "2", llm="anthropic", include_plugin=True, mock_should_gen_plugin=True)
    plugin_dir = temp_project / ".claude" / "plugin-generated"
    state_dir = plugin_dir / "state"
    state_dir.mkdir(exist_ok=True)
    
    # Base state
    base_state_path = state_dir / "campaign_state.json"
    base_state_path.write_text(json.dumps({"global": "base_val"}))
    
    # Load hook definitions
    hooks_json = json.loads((plugin_dir / "hooks" / "hooks.json").read_text())
    pre_tool_cmd = hooks_json["hooks"]["PreToolUse"][0]["hooks"][0]["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_dir))
    
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin_dir), "CLAUDE_PROJECT_DIR": str(temp_project)}
    
    # Run hook
    res1 = subprocess.run(shlex.split(pre_tool_cmd), input=json.dumps(payload), cwd=temp_project, capture_output=True, text=True, env=env)
    assert res1.returncode == 0
    
    # Run hook again
    res2 = subprocess.run(shlex.split(pre_tool_cmd), input=json.dumps(payload), cwd=temp_project, capture_output=True, text=True, env=env)
    assert res2.returncode == 0
    
    # Check that state exists and retains the value
    assert base_state_path.exists()
    st = json.loads(base_state_path.read_text())
    assert st["global"] == "base_val"

if __name__ == "__main__":
    pytest.main([__file__])
