"""Audit the generated Claude plugin against the Phase 3.5 contract."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from harness.init.plugin_generator import generate_orchestrator_plugin


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="e2g-plugin-audit-") as tmp_dir:
        project = Path(tmp_dir) / "project"
        project.mkdir()
        (project / "docs" / "domain").mkdir(parents=True)
        (project / "docs" / "domain" / "CONTEXT.md").write_text("# Audit Context\n")

        plugin_dir = Path(generate_orchestrator_plugin(str(project), "AuditProject"))
        harness_dir = plugin_dir.parent

        required = [
            plugin_dir / ".claude-plugin" / "plugin.json",
            plugin_dir / "hooks" / "hooks.json",
            harness_dir / ".claude-plugin" / "marketplace.json",
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            print("Missing required plugin audit files:")
            for path in missing:
                print(f"  - {path}")
            return 1

        obsolete = [
            plugin_dir / "src" / "hooks",
            plugin_dir / "src" / "hook_validator.py",
            plugin_dir / "src" / "orchestrator_plugin.py",
            plugin_dir / "src" / "interceptor.py",
            plugin_dir / "src" / "tools.py",
        ]
        generated_obsolete = [str(path) for path in obsolete if path.exists()]
        if generated_obsolete:
            print("Legacy plugin payload was generated:")
            for path in generated_obsolete:
                print(f"  - {path}")
            return 1

        manifest = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text())
        forbidden = {"tools", "entry_point"}
        present = sorted(forbidden.intersection(manifest))
        if present:
            print(f"Plugin manifest contains nonstandard fields: {present}")
            return 1

        hooks = json.loads((plugin_dir / "hooks" / "hooks.json").read_text())
        for event_name, groups in hooks.get("hooks", {}).items():
            for group in groups:
                for hook in group.get("hooks", []):
                    command = hook.get("command", "")
                    if "${CLAUDE_PLUGIN_ROOT}" not in command:
                        print(f"{event_name} command is not plugin-root based: {command}")
                        return 1

        claude = shutil.which("claude")
        if not claude:
            print("claude CLI not found; skipped strict Claude plugin validation.")
            return 0

        for path in (plugin_dir, harness_dir):
            result = subprocess.run(
                [claude, "plugin", "validate", str(path), "--strict"],
                capture_output=True,
                text=True,
            )
            print(result.stdout, end="")
            if result.returncode != 0:
                print(result.stderr, end="", file=sys.stderr)
                return result.returncode

        print("Phase 3.5 plugin audit passed.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
