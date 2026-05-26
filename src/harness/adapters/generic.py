import os
from pathlib import Path
from typing import Dict, List
from harness.adapters.base import PlatformAdapter


class GenericAdapter(PlatformAdapter):
    def get_platform_name(self) -> str:
        return "agents"

    def get_config_dir_name(self) -> str:
        return ".agents"

    def get_plugin_env_var_name(self) -> str:
        return "AGENTS_PLUGIN_ROOT"

    def get_tool_mappings(self) -> Dict[str, str]:
        return {}

    def get_subagent_syntax(self) -> str:
        return "@"

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def get_rules_pointer_files(self) -> List[str]:
        return []

    def get_hook_directory(self) -> str:
        return f"{self.get_config_dir_name()}/hooks"

    def install_hooks(self, project_path: Path) -> None:
        pass

    def generate_core_infrastructure(self, project_path: Path) -> None:
        pass

    def configure_cli(self, project_path: Path) -> None:
        pass

    def get_agent_manifest_format(self) -> str:
        return "markdown"
