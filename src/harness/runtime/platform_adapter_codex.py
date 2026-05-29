"""Standalone Codex platform adapter — baked into the generated plugin at mint time.

No harness.* imports. Runs in user environments where the harness package is not installed.
"""


class PlatformAdapter:
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


def get_adapter():
    return PlatformAdapter()
