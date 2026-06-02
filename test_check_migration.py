import os
import json
import subprocess
from pathlib import Path

workspace = Path("tmp_workspace_check")
workspace.mkdir(exist_ok=True)
claude_dir = workspace / ".claude"
claude_dir.mkdir(exist_ok=True)
plugin_dir = claude_dir / "harness-wf-plugin"
plugin_dir.mkdir(exist_ok=True)

import harness
package_root = Path(harness.__file__).parent
from harness.update.manifest import _read_harness_version
h_version = _read_harness_version(package_root)

manifest = {
    "harness_version": h_version,
    "owned": {}
}
(plugin_dir / ".harness-meta.json").write_text(json.dumps(manifest))
(claude_dir / "agent.json").write_text('{"description": "old agent"}')

print("Running --check:")
subprocess.run(["uv", "run", "harness-wf", "update", "--project-path", str(workspace), "--check"])

print("\nRunning apply:")
subprocess.run(["uv", "run", "harness-wf", "update", "--project-path", str(workspace)])
