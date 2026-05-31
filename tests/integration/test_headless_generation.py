import os
import shutil
import sys
import tempfile
import subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize("choice, target_dir_name", [
    ("1", ".gemini"),
    ("2", ".claude"),
    ("3", ".cursor"),
    ("4", ".agents"),
    ("5", ".codex")
])
def test_headless_harness_generation(choice, target_dir_name):
    cli_script = Path(__file__).parent.parent.parent / "src" / "harness" / "init" / "cli.py"

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            env = os.environ.copy()
            env["HARNESS_HEADLESS"] = "1"
            env["HARNESS_PLATFORM"] = choice
            
            # Mock HARNESS_EVAL_MODE to skip langfuse logic if it fails without credentials
            env["HARNESS_EVAL_MODE"] = "0"

            # Mock .codegraph to bypass npm installation
            (Path(tmpdir) / ".codegraph").mkdir()
            (Path(tmpdir) / ".codegraph" / "codegraph.db").touch()

            result = subprocess.run(
                [sys.executable, str(cli_script), "init", "--project-path", tmpdir],
                env=env,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0, f"Platform {choice} failed: {result.stderr}\nOutput: {result.stdout}"
            
            target_path = Path(tmpdir) / target_dir_name
            assert target_path.exists(), f"Target dir {target_dir_name} not found for platform {choice}"

            # Validate expected payload directories based on platform
            if choice == "2":  # Claude
                payload_base = target_path / "harness-wr-plugin"
            else:
                payload_base = target_path

            assert (payload_base / "skills").exists(), f"skills/ not found in {payload_base} for platform {choice}"
            assert (payload_base / "agents").exists(), f"agents/ not found in {payload_base} for platform {choice}"
            assert (target_path / "AGENTS.md").exists(), f"AGENTS.md not found in {target_path} for platform {choice}"

        finally:
            # The tempfile.TemporaryDirectory cleans up stragglers automatically
            pass
