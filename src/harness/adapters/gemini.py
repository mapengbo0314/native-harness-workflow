import os
import shutil
from pathlib import Path
from typing import Dict, List
from harness.adapters.base import PlatformAdapter


class GeminiAdapter(PlatformAdapter):
    def get_platform_name(self) -> str:
        return "gemini"

    def get_config_dir_name(self) -> str:
        return ".gemini"

    def get_plugin_env_var_name(self) -> str:
        return "GEMINI_PLUGIN_ROOT"

    def get_tool_mappings(self) -> Dict[str, str]:
        return {
            "- read_file": "- read_file",
            "- grep_search": "- grep_search",
            "- replace": "- replace",
            "- write_file": "- write_file",
            "- run_shell_command": "- run_shell_command",
            "- glob": "- glob",
        }

    def get_subagent_syntax(self) -> str:
        return "@"

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def get_rules_pointer_files(self) -> List[str]:
        return ["GEMINI.md"]

    def get_hook_directory(self) -> str:
        return f"{self.get_config_dir_name()}/hooks"

    def install_hooks(self, project_path: Path) -> None:
        import re
        hooks_dir = project_path / self.get_hook_directory()
        if not hooks_dir.exists():
            return
            
        for root, _, files in os.walk(hooks_dir):
            for file in files:
                if file.endswith((".py", ".json", ".md")):
                    filepath = Path(root) / file
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    new_content = content.replace("${HARNESS_PLUGIN_ROOT}", f"${{{self.get_plugin_env_var_name()}}}")
                    new_content = re.sub(r'(^|[\s/"\'])\.claude([\s/"\']|$)', r'\1' + self.get_config_dir_name() + r'\2', new_content)
                    
                    if new_content != content:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)

    def generate_core_infrastructure(self, project_path: Path) -> None:
        # Standard boilerplate copy already provides hooks, contracts, state, skills.
        # This method can be used for platform-specific rearrangements if necessary.
        pass

    def configure_cli(self, project_path: Path, mcps_to_install: List[dict]) -> None:
        import subprocess
        import shlex
        gemini = shutil.which("gemini")
        if not gemini:
            print("[HARNESS] Warning: 'gemini' CLI not found. Please register MCP tools manually.")
            return
            
        commands = [
            [gemini, "mcp", "add", "codegraph", "npx", "-y", "@colbymchenry/codegraph", "serve", "--mcp"],
        ]
        
        for mcp in mcps_to_install or []:
            try:
                parts = shlex.split(mcp.get("command", ""))
            except ValueError as exc:
                print(f"[HARNESS] Warning: Invalid command string for MCP {mcp.get('name')}: {exc}")
                continue
            if parts:
                commands.append([gemini, "mcp", "add", mcp["name"], *parts])
                
        for command in commands:
            result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, env=os.environ.copy())
            if result.returncode != 0:
                print(f"[HARNESS] Warning: Optional CLI MCP registration failed: {' '.join(command[:4])}")

    def get_agent_manifest_format(self) -> str:
        return "markdown"
