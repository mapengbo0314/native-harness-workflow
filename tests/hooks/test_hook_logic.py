import os
import shutil
import tempfile
import subprocess
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to sys.path to allow importing harness modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from harness.cli import main

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
    with patch('harness.discovery_engine.query_llm') as mock_query_llm, \
         patch('subprocess.run') as mock_run, \
         patch('urllib.request.urlopen') as mock_urlopen, \
         patch('harness.cli.parse_args') as mock_parse_args, \
         patch('harness.minting_engine.should_generate_orchestrator_plugin') as mock_should_gen, \
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

        if mock_should_gen_plugin is not None:
            mock_should_gen.return_value = mock_should_gen_plugin
        else:
            mock_should_gen.return_value = (include_plugin and platform_choice == "2")

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

def test_hook_validator_functional_correctness(temp_project):
    # 1. Mint a Claude-platform harness (Platform 2) with plugin
    # We must ensure the plugin is generated so hook_validator.py exists
    run_harness_init(temp_project, "2", llm="anthropic", include_plugin=True, mock_should_gen_plugin=True)
    
    # 2. Locate the generated .claude/plugin-generated/src/hook_validator.py
    validator_path = temp_project / ".claude" / "plugin-generated" / "src" / "hook_validator.py"
    assert validator_path.exists(), f"hook_validator.py was not generated at {validator_path}"
    
    # 3. Execute it using the same Python interpreter.
    # The validator runs from its own directory to find relative hooks
    # We need to make sure the project root's artifacts directory exists for stop_monitor tests
    (temp_project / "artifacts").mkdir(parents=True, exist_ok=True)
    
    result = subprocess.run(
        [sys.executable, str(validator_path)],
        cwd=temp_project,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(temp_project)}
    )
    
    # Log output for debugging if test fails
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")
    
    # 4. Verify Output
    assert result.returncode == 0, f"hook_validator.py failed with exit code {result.returncode}"
    
    # Check for success markers as specified in Task 3.2
    # Updated to match actual output from plugin_generator.py
    expected_markers = [
        "✅ Discovery OK",
        "✅ prompt_interceptor OK",
        "✅ post_tool_monitor (red) OK",
        "✅ post_tool_monitor (green) OK",
        "✅ pre_tool_guard (TDD enforcement) OK",
        "✅ sudo (lowercase) OK",
        "✅ sudo (uppercase) OK",
        "✅ rm split flags OK",
        "✅ rm space padding OK",
        "✅ rm case sensitivity OK",
        "✅ Escalation OK",
        "✅ precompact_monitor OK",
        "✅ stop_monitor (gate active) OK",
        "✅ stop_monitor (gate passed) OK"
    ]
    
    for marker in expected_markers:
        assert marker in result.stdout, f"Success marker '{marker}' not found in hook_validator output"

if __name__ == "__main__":
    pytest.main([__file__])
