import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from harness.adapters.base import PlatformAdapter
from harness.plugin_generator import generate_orchestrator_plugin


class ClaudeAdapter(PlatformAdapter):
    def get_platform_name(self) -> str:
        return "claude"

    def get_config_dir_name(self) -> str:
        return ".claude"

    def get_plugin_env_var_name(self) -> str:
        return "CLAUDE_PLUGIN_ROOT"

    def get_tool_mappings(self) -> Dict[str, str]:
        return {
            "- read_file": "- Read",
            "- grep_search": "- Grep",
            "- replace": "- Edit",
            "- write_file": "- Write",
            "- run_shell_command": "- Bash",
            "- glob": "- Glob",
            "read_file": "Read",
            "grep_search": "Grep",
            "replace": "Edit",
            "write_file": "Write",
            "run_shell_command": "Bash",
            "glob": "Glob"
        }

    def get_subagent_syntax(self) -> str:
        return "Task tool: "

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def get_rules_pointer_files(self) -> List[str]:
        return ["CLAUDE.md"]

    def get_hook_directory(self) -> str:
        return f"{self.get_config_dir_name()}/hooks"

    def install_hooks(self, project_path: Path) -> None:
        # For Claude, the hooks are part of the plugin generation
        pass

    def generate_core_infrastructure(self, project_path: Path) -> None:
        # Claude specifically generates an orchestrator plugin
        # This replaces the logic that was conditionally driven by should_generate_orchestrator_plugin
        # Note: cli.py handles the actual generation call right now, but we can encapsulate it here or keep it in cli.py.
        # Since the plan says "Call adapter.generate_core_infrastructure() to provision common harness assets... for all platforms."
        # And "Obsolete function should_generate_orchestrator_plugin is entirely removed"
        pass

    def configure_cli(self, project_path: Path, mcps_to_install: List[dict]) -> None:
        import subprocess
        import shlex
        claude = shutil.which("claude")
        if not claude:
            print("[HARNESS] Warning: 'claude' CLI not found. Please register MCP tools manually.")
            return
            
        commands = [
            [claude, "mcp", "add", "codegraph", "npx", "-y", "@colbymchenry/codegraph", "serve", "--mcp"],
        ]
        
        for mcp in mcps_to_install or []:
            try:
                parts = shlex.split(mcp.get("command", ""))
            except ValueError as exc:
                print(f"[HARNESS] Warning: Invalid command string for MCP {mcp.get('name')}: {exc}")
                continue
            if parts:
                commands.append([claude, "mcp", "add", mcp["name"], *parts])
                
        for command in commands:
            result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, env=os.environ.copy())
            if result.returncode != 0:
                print(f"[HARNESS] Warning: Optional CLI MCP registration failed: {' '.join(command[:4])}")

    def get_agent_manifest_format(self) -> str:
        return "markdown"
