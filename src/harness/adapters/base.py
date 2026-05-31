from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional


class RuntimeAdapter(ABC):
    """Abstract interface for runtime (plugin-side) behaviours.

    These methods ship into the generated plugin and run inside the user's AI
    environment. They are stdlib-only — no harness.* imports allowed at runtime.

    Responsibility: format prompts, translate tool names, dispatch agents/skills,
    and shape hook JSON responses.

    Platform identity accessors (``get_platform_name``, ``get_config_dir_name``,
    ``get_plugin_env_var_name``) live here because the runtime slice needs them
    to locate plugin assets (e.g. the config dir, the env-var prefix used in
    path templates).
    """

    # -- Platform identity (needed by runtime to locate plugin assets) --------

    @abstractmethod
    def get_platform_name(self) -> str:
        """Returns the nominal platform string (e.g., 'gemini', 'claude')."""
        pass

    @abstractmethod
    def get_config_dir_name(self) -> str:
        """Returns the global config directory (e.g., '.gemini', '.claude')."""
        pass

    @abstractmethod
    def get_plugin_env_var_name(self) -> str:
        """Returns the env var prefix for hook templating (e.g., 'GEMINI_PLUGIN_ROOT')."""
        pass

    # -- Runtime dispatch / formatting ----------------------------------------

    @abstractmethod
    def get_tool_mappings(self) -> Dict[str, str]:
        """Returns tool name translations (e.g., 'read_file' -> 'Read')."""
        pass

    @abstractmethod
    def format_subagent_prompt(self, task_desc: str) -> str:
        """Formats the payload/prompt for the subagent."""
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


class PlatformBuilder(ABC):
    """Abstract interface for mint-time (structure/process) behaviours.

    These methods run during harness installation («minting») on the developer's
    machine. They assemble the project layout, install hooks, configure the CLI,
    and declare which pointer/manifest files to generate.

    ``assemble_layout`` is the canonical name for the structural assembly step
    (currently implemented as ``generate_core_infrastructure`` in concretes).
    In this task (S2-T3) it is declared abstract here; ``PlatformAdapter``
    provides a backward-compatible default that delegates to
    ``generate_core_infrastructure``. Concretes will be migrated to implement
    ``assemble_layout`` directly in S2-T4.
    """

    @abstractmethod
    def assemble_layout(self, project_path: Path) -> None:
        """Assemble the required state, contracts, and skills directories.

        This is the canonical mint-time structural step. The default
        implementation on ``PlatformAdapter`` delegates to
        ``generate_core_infrastructure`` for backward compatibility.
        """
        pass

    @abstractmethod
    def install_hooks(self, project_path: Path) -> None:
        """Handles templating and placement of pre/post execution hooks."""
        pass

    @abstractmethod
    def configure_cli(self, project_path: Path) -> None:
        """Handles CLI setup (e.g., claude mcp add vs gemini mcp add)."""
        pass

    @abstractmethod
    def get_rules_pointer_files(self) -> List[str]:
        """Returns the pointer files to generate (e.g., ['GEMINI.md'])."""
        pass

    @abstractmethod
    def get_agent_manifest_format(self) -> str:
        """Determines if agents are rendered as standalone markdown files or combined Codex YAML."""
        pass

    @abstractmethod
    def get_hook_directory(self) -> str:
        """Returns the platform-specific directory for hooks (e.g., '.gemini/hooks')."""
        pass


class PlatformAdapter(RuntimeAdapter, PlatformBuilder):
    """Unified adapter composed of RuntimeAdapter and PlatformBuilder.

    Exists for backward compatibility: all concrete adapters (ClaudeAdapter,
    GeminiAdapter, etc.) subclass PlatformAdapter and automatically satisfy
    both segregated interfaces.

    ``assemble_layout`` is provided here as a concrete default that delegates
    to ``generate_core_infrastructure``, so existing concretes need no changes
    in S2-T3. Migration to direct ``assemble_layout`` implementations happens
    in S2-T4.
    """

    @abstractmethod
    def generate_core_infrastructure(self, project_path: Path) -> None:
        """Guarantees the generation of required state, contracts, and skills directories for ALL platforms.

        Deprecated in favour of ``assemble_layout``; kept abstract so existing
        concretes continue to implement it. Will be replaced by a direct
        ``assemble_layout`` override in S2-T4.
        """
        pass

    def assemble_layout(self, project_path: Path) -> None:
        """Backward-compatible default: delegates to generate_core_infrastructure.

        Concrete adapters may override this directly once migrated in S2-T4.
        """
        self.generate_core_infrastructure(project_path)
