import json
import os
import tempfile
from pathlib import Path

from tests.sandbox.runner import MockHost, mint_harness


def test_sandbox_uses_root_hook_guard_for_protected_paths():
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        os.environ["HARNESS_HEADLESS"] = "1"
        mint_harness(str(workspace), "RecoveryTestApp")

        host = MockHost(workspace, api_key="mock", dry_run=True)
        result = host.run_hook(
            "prompt_classifier",
            {"prompt": "Hello world"}
        )

        assert "HOOK_REJECTION" not in result
