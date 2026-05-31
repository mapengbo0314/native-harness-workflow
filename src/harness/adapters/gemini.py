import os
import shutil
from pathlib import Path
from typing import Dict, List
from harness.adapters.base import PlatformAdapter
from harness.adapters.profile import load_profile


class GeminiAdapter(PlatformAdapter):
    def get_platform_name(self) -> str:
        return "gemini"

    def get_config_dir_name(self) -> str:
        return load_profile("gemini").config_dir

    def get_plugin_env_var_name(self) -> str:
        return load_profile("gemini").plugin_env_var

    def get_tool_mappings(self) -> Dict[str, str]:
        return load_profile("gemini").tool_mappings

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def get_rules_pointer_files(self) -> List[str]:
        return load_profile("gemini").rules_pointer_files

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
                    
                    if file == "hooks.json":
                        new_content = new_content.replace('"PreCompact":', '"PreCompress":')
                        new_content = new_content.replace('"PostToolUse":', '"AfterTool":')
                    
                    if new_content != content:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)

    def assemble_layout(self, project_path: Path) -> None:
        """Embedded (no-op) layout for Gemini (supports_plugin=False).

        Gemini does not use a plugin-stack subdirectory — all artefacts land
        directly in ``.gemini/``.  Nothing needs to be moved or created here;
        the standard boilerplate copy (performed before this call) is
        sufficient.
        """
        # supports_plugin is False — no harness-wr-plugin/ directory is created.
        pass

    def generate_core_infrastructure(self, project_path: Path) -> None:
        """Backward-compatible entry point: delegates to assemble_layout."""
        self.assemble_layout(project_path)

    def configure_cli(self, project_path: Path) -> None:
        import subprocess
        import shlex
        gemini = shutil.which("gemini")
        if not gemini:
            print("[HARNESS] Warning: 'gemini' CLI not found. Please register MCP tools manually.")
            return
            
        commands = [
            [gemini, "mcp", "add", "codegraph", "npx", "-y", "@colbymchenry/codegraph", "serve", "--mcp"],
        ]

        for command in commands:
            result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, env=os.environ.copy())
            if result.returncode != 0:
                raise Exception(f"CLI MCP registration failed: {' '.join(command)}\nError: {result.stderr}")

    def get_agent_manifest_format(self) -> str:
        return load_profile("gemini").manifest_format

    def format_skill_invocation(self, skill_name: str) -> str:
        return load_profile("gemini").skill_invocation(skill_name)

    def format_subagent_invocation(self, agent_name: str, description: str) -> str:
        return load_profile("gemini").subagent_invocation(agent_name, description)

    def get_subagent_text_call(self, agent_name: str, skill_name: str = None) -> str:
        return load_profile("gemini").subagent_text_call(agent_name, skill=skill_name)

    def format_hook_response(self, original_prompt: str, routing_decision: dict, context_extension: str, hook_event_name: str) -> dict:
        branch = routing_decision.get("classification")
        target_skill = routing_decision.get("target_skill")
        target_agent = routing_decision.get("target_agent")

        agent_invokes_skill = routing_decision.get("agent_invokes_skill", False)

        if target_skill and target_agent:
            agent_name = target_agent.lstrip("@")
            skill_ref = self.format_skill_invocation(target_skill)
            agent_ref = self.get_subagent_text_call(agent_name, target_skill if agent_invokes_skill else None)
            dispatch_directive = (
                f"\n\nHARNESS DISPATCH:\n"
                f"  {skill_ref} → {agent_ref}\n\n"
                f"Invoke the skill as your first action. The skill will direct you to dispatch the agent. Do not answer directly."
            )
            modified_prompt = original_prompt + dispatch_directive
        elif target_agent:
            agent_name = target_agent.lstrip("@")
            description = f"Branch {branch}: Answer this question. Read-only — do not modify files."
            dispatch_directive = (
                f"\n\nHARNESS DISPATCH:\n"
                f"  {self.format_subagent_invocation(agent_name, description)}\n\n"
                f"Make this agent call now. Do not answer directly."
            )
            modified_prompt = original_prompt + dispatch_directive
        else:
            modified_prompt = original_prompt

        return {
            "classification": branch,
            "modifiedPrompt": modified_prompt,
            "target_agent": target_agent,
            "target_skill": target_skill,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "systemPromptExtension": context_extension,
                "modifiedPrompt": modified_prompt,
            }
        }
