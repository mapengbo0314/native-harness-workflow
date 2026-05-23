import os
import subprocess
import tempfile
import shutil
import time
from pathlib import Path
import pytest
from harness.reporting import default_report

def test_full_harness_lifecycle():
    """
    Ultimate E2E Live Harness Audit (NO MOCKS)
    Verifies the full lifecycle from init to functional plugin.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")

    # Use gemini-2.5-flash-lite as requested
    model_name = "gemini-2.5-flash-lite"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        project_path = tmp_path / "my-app"
        
        # Step 1: Init - Spawn a temporary project from sample-py-app
        shutil.copytree("tests/fixtures/boilerplates/sample-py-app", project_path)
        
        # Set environment variables
        env = os.environ.copy()
        env["HARNESS_HEADLESS"] = "1"
        env["GEMINI_API_KEY"] = api_key
        env["HARNESS_MODEL"] = model_name
        env["HARNESS_PLATFORM"] = "2" # Claude Code for plugin generation
        
        # Run the REAL harness-wf init command with Retries
        # Gemini can return 503 UNAVAILABLE under load
        max_retries = 3
        retry_delay = 5
        result = None
        
        for attempt in range(max_retries):
            print(f"Attempt {attempt + 1}/{max_retries}: Running harness-wf init...")
            result = subprocess.run(
                ["python3", "-m", "harness.cli", "init", "--project-path", str(project_path), "--llm", "gemini"],
                env=env,
                capture_output=True,
                text=True
            )
            
            # Check for success and lack of placeholders
            onboarding_doc = project_path / "ONBOARDING_DOMAIN.md"
            success = result.returncode == 0
            has_placeholders = False
            if onboarding_doc.exists():
                content = onboarding_doc.read_text()
                has_placeholders = "[USER INPUT REQUIRED]" in content
            
            if success and not has_placeholders:
                break
            
            # If we failed or have placeholders, consider retrying if it looks like a provider issue
            error_output = result.stderr + (result.stdout if result.stdout else "")
            is_transient = "503" in error_output or "UNAVAILABLE" in error_output or "rate limit" in error_output.lower() or has_placeholders
            
            if is_transient and attempt < max_retries - 1:
                print(f"Transient failure or placeholders detected. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2 # Exponential backoff
            else:
                break

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        assert result.returncode == 0, f"harness-wf init failed after {max_retries} attempts: {result.stderr}"

        # Step 2: Verification (Internal)
        # Verify ONBOARDING_DOMAIN.md was generated with real content
        onboarding_doc = project_path / "ONBOARDING_DOMAIN.md"
        assert onboarding_doc.exists(), "ONBOARDING_DOMAIN.md was not generated"
        content = onboarding_doc.read_text()
        
        # Better Assertion: If it still contains placeholders, it's a provider failure but we want to know
        if "[USER INPUT REQUIRED]" in content:
            pytest.fail("ONBOARDING_DOMAIN.md still contains placeholders after retries. This usually indicates a persistent Gemini API failure/fallback during SME profiling.")
        
        # Verify .claude/ exists (since we chose platform 2)
        harness_dir = project_path / ".claude"
        assert harness_dir.exists(), ".claude folder was not generated"
        assert (harness_dir / "orchestrator.md").exists(), "orchestrator.md missing"

        # Step 3: Setup - Run the real setup_harness.sh
        setup_script = harness_dir / "scripts" / "setup_harness.sh"
        assert setup_script.exists(), "setup_harness.sh missing"
        
        # Run setup script
        # We need to be in project_path for setup_harness.sh to work correctly
        result_setup = subprocess.run(
            ["bash", str(setup_script)],
            cwd=project_path,
            env=env,
            capture_output=True,
            text=True
        )
        print("SETUP STDOUT:", result_setup.stdout)
        print("SETUP STDERR:", result_setup.stderr)
        assert result_setup.returncode == 0, f"setup_harness.sh failed: {result_setup.stderr}"

        # Step 4: Active Verification
        # Run hook_validator.py inside the generated plugin
        plugin_dir = project_path / ".claude" / "plugin-generated"
        assert plugin_dir.exists(), "Plugin-generated directory missing"
        
        validator_script = plugin_dir / "src" / "hook_validator.py"
        assert validator_script.exists(), "hook_validator.py missing"
        
        result_val = subprocess.run(
            ["python3", str(validator_script)],
            cwd=project_path,
            env=env,
            capture_output=True,
            text=True
        )
        print("VALIDATOR STDOUT:", result_val.stdout)
        print("VALIDATOR STDERR:", result_val.stderr)
        assert result_val.returncode == 0, f"hook_validator.py failed: {result_val.stderr}"
        assert "✅ Discovery OK" in result_val.stdout
        assert "✅ prompt_interceptor OK" in result_val.stdout

        # Record results in Section 6: E2E Lifecycle
        manifest = f"""
Successfully minted and verified a live project from `sample-py-app` boilerplate.

**Project Path:** `{project_path}`
**Model:** `{model_name}`
**Harness Platform:** Claude Code

### Manifest of Generated Artifacts:
- `.claude/` (Harness Home)
  - `orchestrator.md` (Main Routing)
  - `scripts/setup_harness.sh` (Initialization)
  - `plugin-generated/` (The active plugin)
- `ONBOARDING_DOMAIN.md` (AI-generated domain context)

### Setup Script Log:
<details>
<summary>Click to view full setup log (STDOUT/STDERR)</summary>

```text
{result_setup.stdout}
{result_setup.stderr}
```
</details>

### Verification Evidence (Hook Validator):
```text
{result_val.stdout}
```
"""
        default_report.add_section("Section 6: E2E Lifecycle", manifest)
