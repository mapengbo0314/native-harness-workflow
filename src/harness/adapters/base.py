from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional


class PlatformAdapter(ABC):
    """Abstract Base Class defining the contract for platform-specific behaviors."""

    @abstractmethod
    def get_platform_name(self) -> str:
        """Returns the nominal string (e.g., 'gemini', 'claude')."""
        pass

    @abstractmethod
    def get_config_dir_name(self) -> str:
        """Returns the global config directory (e.g., '.gemini', '.claude')."""
        pass

    @abstractmethod
    def get_plugin_env_var_name(self) -> str:
        """Returns the env var prefix for hook templating (e.g., 'GEMINI_PLUGIN_ROOT')."""
        pass

    @abstractmethod
    def get_tool_mappings(self) -> Dict[str, str]:
        """Returns tool name translations (e.g., 'read_file' -> 'Read')."""
        pass

    @abstractmethod
    def format_subagent_prompt(self, task_desc: str) -> str:
        """Formats the payload/prompt for the subagent."""
        pass

    @abstractmethod
    def get_rules_pointer_files(self) -> List[str]:
        """Returns the pointer files to generate (e.g., ['GEMINI.md'])."""
        pass

    @abstractmethod
    def get_hook_directory(self) -> str:
        """Returns the platform-specific directory for hooks (e.g., '.gemini/hooks')."""
        pass

    @abstractmethod
    def install_hooks(self, project_path: Path) -> None:
        """Handles templating and placement of pre/post execution hooks."""
        pass

    @abstractmethod
    def generate_core_infrastructure(self, project_path: Path) -> None:
        """Guarantees the generation of required state, contracts, and skills directories for ALL platforms."""
        pass

    @abstractmethod
    def configure_cli(self, project_path: Path) -> None:
        """Handles CLI setup (e.g., claude mcp add vs gemini mcp add)."""
        pass

    @abstractmethod
    def get_agent_manifest_format(self) -> str:
        """Determines if agents are rendered as standalone markdown files or combined Codex YAML."""
        pass

    @abstractmethod
    def format_skill_invocation(self, skill_name: str) -> str:
        """Returns platform-specific directive to invoke a skill (used in modifiedPrompt)."""
        pass

    @abstractmethod
    def format_subagent_invocation(self, agent_name: str, description: str) -> str:
        """Returns platform-specific directive to dispatch a subagent (used in modifiedPrompt)."""
        pass

    @abstractmethod
    def get_subagent_text_call(self, agent_name: str, skill_name: str = None) -> str:
        """Returns platform-specific subagent dispatch syntax for use inside skill file text.
        Used as a Jinja2 callable during minting: <!--$ subagent('implementer') $-->
        When skill_name is provided, embeds skill invocation in the dispatch instruction.
        """
        pass

    @abstractmethod
    def format_hook_response(self, original_prompt: str, routing_decision: dict, context_extension: str, hook_event_name: str) -> dict:
        """Formats the final JSON output for the prompt classifier hook."""
        pass
