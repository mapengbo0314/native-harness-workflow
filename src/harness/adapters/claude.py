import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from harness.adapters.base import PlatformAdapter
from harness.init.plugin_generator import generate_orchestrator_plugin


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
        import shutil
        import re
        harness_dir = project_path / ".harness_tmp"
        if not harness_dir.exists():
            harness_dir = project_path / self.get_config_dir_name()
            
        plugin_dir = harness_dir / "plugin-generated"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # Move payload directories into plugin-generated
        payload_dirs = ["skills", "agents", "hooks", "scripts", "src"]
        payload_files = ["pyproject.toml"]
        
        for p_dir in payload_dirs:
            src_path = harness_dir / p_dir
            if src_path.exists():
                dest_path = plugin_dir / p_dir
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.move(str(src_path), str(dest_path))
                
        for p_file in payload_files:
            src_path = harness_dir / p_file
            if src_path.exists():
                shutil.move(str(src_path), str(plugin_dir / p_file))

        # Restore template logic for plugin assets
        for p_dir in ["skills", "scripts", "hooks"]:
            dir_path = plugin_dir / p_dir
            if dir_path.exists():
                for root, _, files in os.walk(dir_path):
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

    def configure_cli(self, project_path: Path) -> None:
        import subprocess
        import shlex
        claude = shutil.which("claude")
        if not claude:
            print("[HARNESS] Warning: 'claude' CLI not found. Please register MCP tools manually.")
            return
            
        commands = [
            [claude, "mcp", "add", "codegraph", "--", "npx", "-y", "@colbymchenry/codegraph", "serve", "--mcp"],
        ]

        for command in commands:
            result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, env=os.environ.copy())
            if result.returncode != 0:
                raise Exception(f"CLI MCP registration failed: {' '.join(command)}\nError: {result.stderr}")

    def get_agent_manifest_format(self) -> str:
        return "markdown"

    def format_hook_response(self, original_prompt: str, routing_decision: dict, context_extension: str, hook_event_name: str) -> dict:
        branch = routing_decision.get("classification")
        reason = routing_decision.get("reason")
        target_agent = routing_decision.get("target_agent", "@generalist")

        agent_name = target_agent.lstrip("@")
        modified_prompt = f"Task tool (superpowers:{agent_name}):\\n{original_prompt}" if target_agent else original_prompt
        modified_prompt += context_extension

        return {
            "classification": branch,
            "reason": reason,
            "modifiedPrompt": modified_prompt,
            "system_prompt_extension": context_extension,
            "target_agent": target_agent,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "systemPromptExtension": context_extension,
                "modifiedPrompt": modified_prompt,
                "target_agent": target_agent
            }
        }
