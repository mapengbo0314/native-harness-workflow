import os
from pathlib import Path
from typing import Dict, List
from harness.adapters.base import PlatformAdapter


class CursorAdapter(PlatformAdapter):
    def get_platform_name(self) -> str:
        return "cursor"

    def get_config_dir_name(self) -> str:
        return ".cursor"

    def get_plugin_env_var_name(self) -> str:
        return "CURSOR_PLUGIN_ROOT"

    def get_tool_mappings(self) -> Dict[str, str]:
        return {}

    def get_subagent_syntax(self) -> str:
        return "@"

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def get_rules_pointer_files(self) -> List[str]:
        return [".cursorrules", ".github/copilot-instructions.md"]

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
                        
                    new_content = content.replace("${CLAUDE_PLUGIN_ROOT}", f"${{{self.get_plugin_env_var_name()}}}")
                    new_content = re.sub(r'(^|[\s/"\'])\.claude([\s/"\']|$)', r'\1' + self.get_config_dir_name() + r'\2', new_content)
                    
                    if new_content != content:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)

    def generate_core_infrastructure(self, project_path: Path) -> None:
        pass

    def configure_cli(self, project_path: Path) -> None:
        pass

    def get_agent_manifest_format(self) -> str:
        return "markdown"

    def format_hook_response(self, original_prompt: str, routing_decision: dict, context_extension: str, hook_event_name: str) -> dict:
        branch = routing_decision.get("classification")
        reason = routing_decision.get("reason")
        target_agent = routing_decision.get("target_agent") or "@generalist"

        modified_prompt = f"{target_agent} {original_prompt}" if target_agent else original_prompt
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
