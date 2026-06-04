import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from harness.adapters.base import PlatformAdapter
from harness.adapters.profile import load_profile
from harness.init.plugin_generator import generate_orchestrator_plugin


class ClaudeAdapter(PlatformAdapter):
    def get_platform_name(self) -> str:
        return "claude"

    def get_config_dir_name(self) -> str:
        return load_profile("claude").config_dir

    def get_plugin_env_var_name(self) -> str:
        return load_profile("claude").plugin_env_var

    def get_tool_mappings(self) -> Dict[str, str]:
        return load_profile("claude").tool_mappings

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def get_rules_pointer_files(self) -> List[str]:
        return load_profile("claude").rules_pointer_files

    def get_hook_directory(self) -> str:
        return f"{self.get_config_dir_name()}/hooks"

    def install_hooks(self, project_path: Path) -> None:
        # For Claude, the hooks are part of the plugin generation
        pass

    def assemble_layout(self, project_path: Path) -> None:
        """Plugin-stack assembly for Claude (supports_plugin=True).

        Moves the boilerplate payload directories from .harness_tmp (or the
        config dir) into the ``harness-wf-plugin`` subdirectory and rewrites
        any template placeholders.  The directory name is sourced from
        ``load_profile("claude").plugin_dir_name`` so future renames are
        a 1-line change in platform_profiles.json.
        """
        import re
        profile = load_profile("claude")
        if not profile.supports_plugin:
            # Guard: this branch should never be reached for claude, but be safe.
            return

        harness_dir = project_path / ".harness_tmp"
        if not harness_dir.exists():
            harness_dir = project_path / self.get_config_dir_name()

        plugin_dir = harness_dir / profile.plugin_dir_name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Move payload directories into harness-wf-plugin
        payload_dirs = ["skills", "agents", "hooks", "scripts", "src", "rules"]
        payload_files = ["pyproject.toml", "agent.json", "skills.json"]

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

        # Rewrite template placeholders in plugin assets
        for p_dir in ["skills", "scripts", "hooks"]:
            dir_path = plugin_dir / p_dir
            if dir_path.exists():
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        if file.endswith((".py", ".json", ".md")):
                            filepath = Path(root) / file
                            with open(filepath, "r", encoding="utf-8") as f:
                                content = f.read()

                            new_content = content.replace(
                                "${HARNESS_PLUGIN_ROOT}",
                                f"${{{self.get_plugin_env_var_name()}}}",
                            )
                            new_content = re.sub(
                                r'(^|[\s/"\'])\.claude([\s/"\']|$)',
                                r'\1' + self.get_config_dir_name() + r'\2',
                                new_content,
                            )

                            if new_content != content:
                                with open(filepath, "w", encoding="utf-8") as f:
                                    f.write(new_content)

    def generate_core_infrastructure(self, project_path: Path) -> None:
        """Backward-compatible entry point: delegates to assemble_layout."""
        self.assemble_layout(project_path)

    def configure_cli(self, project_path: Path) -> None:
        import subprocess
        import shlex
        import json
        claude = shutil.which("claude")
        if not claude:
            print("[HARNESS] Warning: 'claude' CLI not found. Please register MCP tools manually.")
            return

        # Register codegraph with alwaysLoad so its tools are never deferred behind
        # Tool Search. `claude mcp add` has no alwaysLoad flag, so use add-json.
        # `--scope project` writes the registration to the repo-level .mcp.json
        # (committed, portable) instead of the machine-local ~/.claude.json, so a
        # fresh clone gets codegraph without a per-machine setup step. Options are
        # placed before the positionals so <json> remains the final argv element.
        codegraph_config = json.dumps({
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@colbymchenry/codegraph", "serve", "--mcp"],
            "alwaysLoad": True,
        })
        commands = [
            [claude, "mcp", "add-json", "--scope", "project", "codegraph", codegraph_config],
        ]

        for command in commands:
            result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, env=os.environ.copy())
            if result.returncode != 0:
                if "already exists" in result.stderr or "already exists" in result.stdout:
                    print(f"[HARNESS] Info: MCP server already registered for command: {' '.join(command)}")
                    continue
                raise Exception(f"CLI MCP registration failed: {' '.join(command)}\nError: {result.stderr}")

    def get_agent_manifest_format(self) -> str:
        return load_profile("claude").manifest_format

    def format_skill_invocation(self, skill_name: str) -> str:
        return load_profile("claude").skill_invocation(skill_name)

    def format_subagent_invocation(self, agent_name: str, description: str) -> str:
        return load_profile("claude").subagent_invocation(agent_name, description)

    def get_subagent_text_call(self, agent_name: str, skill_name: str = None) -> str:
        return load_profile("claude").subagent_text_call(agent_name, skill=skill_name)

    def format_hook_response(self, original_prompt: str, routing_decision: dict, context_extension: str, hook_event_name: str) -> dict:
        branch = routing_decision.get("classification")
        target_skill = routing_decision.get("target_skill")
        target_agent = routing_decision.get("target_agent")

        agent_invokes_skill = routing_decision.get("agent_invokes_skill", False)
        dispatch_directive = ""

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
            if agent_name == "generalist":
                agent_name = "general-purpose"
            description = f"Branch {branch}: Answer this question. Read-only — do not modify files."
            dispatch_directive = (
                f"\n\nHARNESS DISPATCH:\n"
                f"  {self.format_subagent_invocation(agent_name, description)}\n\n"
                f"Make this Task call now. Do not answer directly."
            )
            modified_prompt = original_prompt + dispatch_directive
        else:
            modified_prompt = original_prompt

        # Claude's UserPromptSubmit hook only honours hookSpecificOutput.additionalContext
        # — modifiedPrompt / systemPromptExtension are NOT recognised and get dropped. So
        # everything the model must see beyond its own prompt (system state + dispatch
        # directive) must be delivered via additionalContext.
        additional_context = (context_extension or "") + dispatch_directive

        return {
            "classification": branch,
            "modifiedPrompt": modified_prompt,
            "target_agent": target_agent,
            "target_skill": target_skill,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "additionalContext": additional_context,
                "systemPromptExtension": context_extension,
                "modifiedPrompt": modified_prompt,
            }
        }
