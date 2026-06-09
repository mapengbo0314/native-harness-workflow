import os
from pathlib import Path
from typing import Dict, List
from harness.adapters.base import PlatformAdapter
from harness.adapters.profile import load_profile


class CodexAdapter(PlatformAdapter):
    def get_platform_name(self) -> str:
        return load_profile("codex").platform_name

    def get_config_dir_name(self) -> str:
        return load_profile("codex").config_dir

    def get_plugin_env_var_name(self) -> str:
        return load_profile("codex").plugin_env_var

    def get_tool_mappings(self) -> Dict[str, str]:
        return load_profile("codex").tool_mappings

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def format_skill_invocation(self, skill_name: str) -> str:
        return load_profile("codex").skill_invocation(skill_name)

    def format_subagent_invocation(self, agent_name: str, description: str) -> str:
        return load_profile("codex").subagent_invocation(agent_name, description)

    def get_subagent_text_call(self, agent_name: str, skill_name: str = None) -> str:
        return load_profile("codex").subagent_text_call(agent_name, skill=skill_name)

    def get_rules_pointer_files(self) -> List[str]:
        return load_profile("codex").rules_pointer_files

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
        pass

    def configure_cli(self, project_path: Path) -> None:
        # Codex's `codex mcp add` only registers servers globally (~/.codex),
        # not project-locally, so we write the project-local .codex/config.toml
        # directly. We use a text template (no TOML-writer dependency) and an
        # idempotency guard: if the [mcp_servers.domain] table is already
        # present we skip. Existing file content is preserved (tables appended).
        #
        # NOTE: codex only loads project-local config when the user has
        # "trusted" the project — without that, this registration is inert.
        from harness.adapters.profile import load_profile

        root = load_profile("codex").domain_root_rel()
        cfg_path = project_path / self.get_config_dir_name() / "config.toml"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)

        existing = ""
        if cfg_path.exists():
            existing = cfg_path.read_text(encoding="utf-8")
            if "[mcp_servers.domain]" in existing:
                return  # idempotent: already registered

        block = (
            "[mcp_servers.domain]\n"
            'command = "python3"\n'
            'args = ["-m", "server"]\n'
            "\n"
            "[mcp_servers.domain.env]\n"
            f'PYTHONPATH = "{root}/src"\n'
            f'DOMAIN_JSON_PATH = "{root}/domain/domain.json"\n'
        )

        if existing and not existing.endswith("\n"):
            existing += "\n"
        # Separate from any prior content with a blank line for readability.
        new_content = existing + ("\n" if existing else "") + block
        cfg_path.write_text(new_content, encoding="utf-8")

    def get_agent_manifest_format(self) -> str:
        return load_profile("codex").manifest_format

    def format_hook_response(self, original_prompt: str, routing_decision: dict, context_extension: str, hook_event_name: str) -> dict:
        """Codex hook output (deny_unknown_fields, append-only context).

        Codex enforces ``deny_unknown_fields`` and cannot rewrite the prompt, so
        the output carries ONLY Codex-valid fields (``continue`` /
        ``systemMessage`` / ``decision`` / ``reason`` / ``hookSpecificOutput``)
        and the routing decision + SYSTEM STATE are folded into
        ``hookSpecificOutput.additionalContext``. Codex reuses Claude's hook
        *event names* verbatim (``event_mappings = {}``), so ``hook_event_name``
        passes through unchanged.

        Delegates to the profile-driven RuntimeAdapter so the canonical (mint
        time) and runtime (minted) codex outputs stay byte-identical — pinned by
        tests/unit/test_runtime_adapter.py.
        """
        from harness.adapters.runtime_adapter import RuntimeAdapter
        return RuntimeAdapter("codex").format_hook_response(
            original_prompt, routing_decision, context_extension, hook_event_name
        )
