"""Standalone Gemini platform adapter — baked into the generated plugin at mint time.

No harness.* imports. Runs in user environments where the harness package is not installed.
"""


class PlatformAdapter:
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


def get_adapter():
    return PlatformAdapter()
