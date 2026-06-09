import os
from pathlib import Path
from typing import Dict, List
from harness.adapters.base import PlatformAdapter
from harness.adapters.profile import load_profile


class CursorAdapter(PlatformAdapter):
    def get_platform_name(self) -> str:
        return load_profile("cursor").platform_name

    def get_config_dir_name(self) -> str:
        return load_profile("cursor").config_dir

    def get_plugin_env_var_name(self) -> str:
        return load_profile("cursor").plugin_env_var

    def get_tool_mappings(self) -> Dict[str, str]:
        return load_profile("cursor").tool_mappings

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def format_skill_invocation(self, skill_name: str) -> str:
        return load_profile("cursor").skill_invocation(skill_name)

    def format_subagent_invocation(self, agent_name: str, description: str) -> str:
        return load_profile("cursor").subagent_invocation(agent_name, description)

    def get_subagent_text_call(self, agent_name: str, skill_name: str = None) -> str:
        return load_profile("cursor").subagent_text_call(agent_name, skill=skill_name)

    def get_rules_pointer_files(self) -> List[str]:
        return load_profile("cursor").rules_pointer_files

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
        # Cursor has no MCP-registration CLI, so write the project-local
        # .cursor/mcp.json directly. Read-merge any existing file so other
        # servers the user registered are preserved. The deployed root for an
        # embedded platform is the config dir itself (.cursor), so the server
        # (src/) and manifest (domain/domain.json) live directly under it.
        import json
        from harness.adapters.profile import load_profile

        root = load_profile("cursor").domain_root_rel()
        mcp_path = project_path / self.get_config_dir_name() / "mcp.json"
        mcp_path.parent.mkdir(parents=True, exist_ok=True)

        data: Dict = {}
        if mcp_path.exists():
            try:
                loaded = json.loads(mcp_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (json.JSONDecodeError, OSError):
                data = {}
        servers = data.setdefault("mcpServers", {})
        servers["domain"] = {
            "command": "python3",
            "args": ["-m", "server"],
            "env": {
                "PYTHONPATH": f"{root}/src",
                "DOMAIN_JSON_PATH": f"{root}/domain/domain.json",
            },
        }
        mcp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def get_agent_manifest_format(self) -> str:
        return load_profile("cursor").manifest_format

    def format_hook_response(self, original_prompt: str, routing_decision: dict, context_extension: str, hook_event_name: str) -> dict:
        """Cursor hook output (honest — no per-turn routing).

        Cursor's ``beforeSubmitPrompt`` can only return
        ``{continue, user_message}``; it cannot inject context or rewrite the
        prompt. Per-turn routing is therefore OFF for Cursor (accepted product
        decision) — the harness ships via rules files (``AGENTS.md``), native
        subagents (``.cursor/agents/*.md``) and MCP instead. So the output must
        carry ONLY Cursor-valid fields and must NOT emit the invented routing
        schema (``modifiedPrompt`` / ``target_agent`` / ``hookSpecificOutput``).

        Delegates to the profile-driven RuntimeAdapter so the canonical (mint
        time) and runtime (minted) cursor outputs stay byte-identical — pinned
        by tests/unit/test_runtime_adapter.py.
        """
        from harness.adapters.runtime_adapter import RuntimeAdapter
        return RuntimeAdapter("cursor").format_hook_response(
            original_prompt, routing_decision, context_extension, hook_event_name
        )
