"""Standalone platform adapters for generated plugins.

This module is copied into the generated plugin's src/ directory by copy_runtime_modules.
It MUST have zero dependencies on harness.* packages — it runs in user environments
where the harness package is not installed.
"""


class _ClaudeAdapter:
    def get_platform_name(self):
        return "claude"

    def get_config_dir_name(self):
        return ".claude"

    def get_plugin_env_var_name(self):
        return "CLAUDE_PLUGIN_ROOT"

    def get_tool_mappings(self):
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
            "glob": "Glob",
        }

    def format_subagent_prompt(self, task_desc):
        return task_desc

    def format_skill_invocation(self, skill_name):
        return f'Skill("{skill_name}")'

    def format_subagent_invocation(self, agent_name, description):
        return f'Task(subagent_type="{agent_name}", description="{description}")'

    def get_subagent_text_call(self, agent_name, skill_name=None):
        if skill_name:
            return f'Task(subagent_type="{agent_name}", description="Invoke Skill(\'{skill_name}\') as your first action.")'
        return f'Task(subagent_type="{agent_name}")'

    def get_agent_manifest_format(self):
        return "markdown"

    def format_hook_response(self, original_prompt, routing_decision, context_extension, hook_event_name):
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

        return {
            "classification": branch,
            "modifiedPrompt": modified_prompt,
            "target_agent": target_agent,
            "target_skill": target_skill,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "systemPromptExtension": context_extension,
                "modifiedPrompt": modified_prompt,
            },
        }


class _GeminiAdapter:
    def get_platform_name(self):
        return "gemini"

    def get_config_dir_name(self):
        return ".gemini"

    def get_plugin_env_var_name(self):
        return "GEMINI_PLUGIN_ROOT"

    def get_tool_mappings(self):
        return {
            "- read_file": "- read_file",
            "- grep_search": "- grep_search",
            "- replace": "- replace",
            "- write_file": "- write_file",
            "- run_shell_command": "- run_shell_command",
            "- glob": "- glob",
        }

    def format_subagent_prompt(self, task_desc):
        return task_desc

    def format_skill_invocation(self, skill_name):
        return f'activate_skill("{skill_name}")'

    def format_subagent_invocation(self, agent_name, description):
        return f"@{agent_name} {description}"

    def get_subagent_text_call(self, agent_name, skill_name=None):
        if skill_name:
            return f'@{agent_name} — activate_skill("{skill_name}") as your first action'
        return f"@{agent_name}"

    def get_agent_manifest_format(self):
        return "markdown"

    def format_hook_response(self, original_prompt, routing_decision, context_extension, hook_event_name):
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
            },
        }


class _CodexAdapter:
    def get_platform_name(self):
        return "codex"

    def get_config_dir_name(self):
        return ".codex"

    def get_plugin_env_var_name(self):
        return "CODEX_PLUGIN_ROOT"

    def get_tool_mappings(self):
        return {}

    def format_subagent_prompt(self, task_desc):
        return task_desc

    def format_skill_invocation(self, skill_name):
        return f"Activate skill {skill_name}"

    def format_subagent_invocation(self, agent_name, description):
        return f"Hand off to {agent_name}: {description}"

    def get_subagent_text_call(self, agent_name, skill_name=None):
        if skill_name:
            return f"Hand off to {agent_name} — invoke skill {skill_name} first"
        return f"Hand off to {agent_name}"

    def get_agent_manifest_format(self):
        return "yaml"

    def format_hook_response(self, original_prompt, routing_decision, context_extension, hook_event_name):
        branch = routing_decision.get("classification")
        target_agent = routing_decision.get("target_agent") or "@generalist"
        agent_name = target_agent.lstrip("@")
        modified_prompt = f"Hand off to {agent_name}:\n{original_prompt}" if target_agent else original_prompt
        modified_prompt += context_extension

        return {
            "classification": branch,
            "modifiedPrompt": modified_prompt,
            "system_prompt_extension": context_extension,
            "target_agent": target_agent,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "systemPromptExtension": context_extension,
                "modifiedPrompt": modified_prompt,
                "target_agent": target_agent,
            },
        }


class _CursorAdapter:
    def get_platform_name(self):
        return "cursor"

    def get_config_dir_name(self):
        return ".cursor"

    def get_plugin_env_var_name(self):
        return "CURSOR_PLUGIN_ROOT"

    def get_tool_mappings(self):
        return {}

    def format_subagent_prompt(self, task_desc):
        return task_desc

    def format_skill_invocation(self, skill_name):
        return f"Use {skill_name}"

    def format_subagent_invocation(self, agent_name, description):
        return f"@{agent_name} {description}"

    def get_subagent_text_call(self, agent_name, skill_name=None):
        if skill_name:
            return f"@{agent_name} — invoke skill {skill_name} first"
        return f"@{agent_name}"

    def get_agent_manifest_format(self):
        return "markdown"

    def format_hook_response(self, original_prompt, routing_decision, context_extension, hook_event_name):
        branch = routing_decision.get("classification")
        target_agent = routing_decision.get("target_agent") or "@generalist"
        modified_prompt = f"{target_agent} {original_prompt}" if target_agent else original_prompt
        modified_prompt += context_extension

        return {
            "classification": branch,
            "modifiedPrompt": modified_prompt,
            "system_prompt_extension": context_extension,
            "target_agent": target_agent,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "systemPromptExtension": context_extension,
                "modifiedPrompt": modified_prompt,
                "target_agent": target_agent,
            },
        }


class _GenericAdapter:
    def get_platform_name(self):
        return "agents"

    def get_config_dir_name(self):
        return ".agents"

    def get_plugin_env_var_name(self):
        return "AGENTS_PLUGIN_ROOT"

    def get_tool_mappings(self):
        return {}

    def format_subagent_prompt(self, task_desc):
        return task_desc

    def format_skill_invocation(self, skill_name):
        return f"Use {skill_name}"

    def format_subagent_invocation(self, agent_name, description):
        return f"@{agent_name} {description}"

    def get_subagent_text_call(self, agent_name, skill_name=None):
        if skill_name:
            return f"@{agent_name} — invoke skill {skill_name} first"
        return f"@{agent_name}"

    def get_agent_manifest_format(self):
        return "markdown"

    def format_hook_response(self, original_prompt, routing_decision, context_extension, hook_event_name):
        branch = routing_decision.get("classification")
        target_agent = routing_decision.get("target_agent")
        modified_prompt = original_prompt + context_extension

        return {
            "classification": branch,
            "modifiedPrompt": modified_prompt,
            "system_prompt_extension": context_extension,
            "target_agent": target_agent,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "systemPromptExtension": context_extension,
                "modifiedPrompt": modified_prompt,
                "target_agent": target_agent,
            },
        }


def get_adapter(platform_id):
    """Return the standalone adapter for the given platform. No harness.* dependencies."""
    _adapters = {
        "claude": _ClaudeAdapter,
        "gemini": _GeminiAdapter,
        "codex": _CodexAdapter,
        "cursor": _CursorAdapter,
    }
    cls = _adapters.get(platform_id.lower(), _GenericAdapter)
    return cls()
