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
                        # Gemini CLI's hook taxonomy differs from Claude's:
                        # UserPromptSubmit->BeforeAgent, PreToolUse->BeforeTool,
                        # PostToolUse->AfterTool, PreCompact->PreCompress. The
                        # boilerplate hooks.json ships Claude's event-name keys,
                        # so they MUST be rewritten or the hooks bind to events
                        # that don't exist on Gemini and never fire. Driven from
                        # the profile's event_mappings so it stays single-sourced.
                        # Refs: https://geminicli.com/docs/hooks/reference/
                        for claude_event, gemini_event in load_profile("gemini").event_mappings.items():
                            new_content = new_content.replace(
                                f'"{claude_event}":', f'"{gemini_event}":'
                            )
                    
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
        # supports_plugin is False — no harness-wf-plugin/ directory is created.
        pass

    def generate_core_infrastructure(self, project_path: Path) -> None:
        """Backward-compatible entry point: delegates to assemble_layout."""
        self.assemble_layout(project_path)

    def configure_cli(self, project_path: Path) -> None:
        import subprocess
        gemini = shutil.which("gemini")
        if not gemini:
            print("[HARNESS] Warning: 'gemini' CLI not found. Please register MCP tools manually.")
            return
            
        # Domain MCP: serves domain_ops(topic) from the deployed domain.json.
        # Gemini has no add-json; use `mcp add` with -e env flags. The command
        # (`python3`) is the `commandOrUrl` positional and `-m server` are the
        # trailing variadic args — gemini's yargs parser captures them as the
        # server's args (verified: settings.json args == ["-m", "server"]). We
        # intentionally do NOT use a `--` separator: the installed gemini CLI
        # drops everything after `--`, which would strip `python3 -m server`.
        # The deployed root for an embedded platform is the config dir itself
        # (.gemini), so the server (src/) and manifest (domain/domain.json)
        # live directly under it.
        _root = load_profile("gemini").domain_root_rel()
        commands = [
            [gemini, "mcp", "add", "codegraph", "npx", "-y", "@colbymchenry/codegraph", "serve", "--mcp"],
            [
                gemini, "mcp", "add", "--scope", "project",
                "-e", f"PYTHONPATH={_root}/src",
                "-e", f"DOMAIN_JSON_PATH={_root}/domain/domain.json",
                "domain", "python3", "-m", "server",
            ],
        ]

        for command in commands:
            result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, env=os.environ.copy())
            if result.returncode != 0:
                if "already exists" in result.stderr or "already exists" in result.stdout:
                    print(f"[HARNESS] Info: MCP server already registered for command: {' '.join(command)}")
                    continue
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
        """Gemini hook output (BeforeAgent, append-only — no prompt rewrite).

        Gemini CLI has no ``UserPromptSubmit`` event; its prompt-submit hook is
        ``BeforeAgent``, whose ``hookSpecificOutput.additionalContext`` is "text
        appended to the prompt for this turn". It cannot rewrite the prompt, so —
        like Codex — the routing decision + SYSTEM STATE are folded into
        ``additionalContext`` and the output carries only append-only-valid fields
        (``modifiedPrompt`` / ``systemPromptExtension`` / ``target_agent`` are
        invented and ignored by Gemini). Refs:
        https://geminicli.com/docs/hooks/reference/ ,
        https://geminicli.com/docs/hooks/ .

        Delegates to the profile-driven RuntimeAdapter so the canonical (mint
        time) and runtime (minted) gemini outputs stay byte-identical — pinned by
        tests/unit/test_runtime_adapter.py.
        """
        from harness.adapters.runtime_adapter import RuntimeAdapter
        return RuntimeAdapter("gemini").format_hook_response(
            original_prompt, routing_decision, context_extension, hook_event_name
        )
