"""Canonical standalone runtime adapter — shipped into minted plugins (S2-T6).

Design rules:
  - stdlib + ``profile`` only.  NO harness.* imports at module level.
  - When copied into a plugin's src/ directory by copy_runtime_modules, the
    import-rewrite pass converts ``from harness.adapters.profile import …`` to
    ``from profile import …`` so the module is fully self-contained.
  - Provides ``get_adapter(platform)`` (with a platform argument) for in-repo
    use.  The minted ``platform_adapter.py`` wraps this with a no-arg shim that
    bakes in the platform id at mint time.

Behavior contracts:
  ``format_hook_response`` and ``get_subagent_text_call`` are byte-identical to
  the canonical harness.adapters.{claude,gemini} adapters and the existing
  standalone runtime/platform_adapter_{claude,gemini}.py files.  The drift guard
  (tests/integration/test_adapter_drift_guard.py) pins this.

  Claude-specific logic preserved:
    - Agent-only branch: ``generalist`` → ``general-purpose`` remap
      (controlled by profile.generalist_remap).
    - CTA string: "Make this Task call now." vs "Make this agent call now."
      (read from profile.hook_agent_only_cta).
"""

from __future__ import annotations

from harness.adapters.profile import load_profile, PlatformProfile


class RuntimeAdapter:
    """Profile-driven runtime adapter — zero harness.* imports except profile."""

    def __init__(self, platform: str) -> None:
        self._platform = platform
        self._profile: PlatformProfile = load_profile(platform)

    # ------------------------------------------------------------------
    # Platform identity
    # ------------------------------------------------------------------

    def get_platform_name(self) -> str:
        return self._profile.platform_name

    def get_config_dir_name(self) -> str:
        return self._profile.config_dir

    def get_plugin_env_var_name(self) -> str:
        return self._profile.plugin_env_var

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def get_tool_mappings(self) -> dict:
        return dict(self._profile.tool_mappings)

    def format_subagent_prompt(self, task_desc: str) -> str:
        return task_desc

    def format_skill_invocation(self, skill_name: str) -> str:
        return self._profile.skill_invocation(skill_name)

    def format_subagent_invocation(self, agent_name: str, description: str) -> str:
        return self._profile.subagent_invocation(agent_name, description)

    def get_subagent_text_call(self, agent_name: str, skill_name: str = None) -> str:
        return self._profile.subagent_text_call(agent_name, skill=skill_name)

    def get_agent_manifest_format(self) -> str:
        return self._profile.manifest_format

    # ------------------------------------------------------------------
    # Hook response formatting
    # ------------------------------------------------------------------

    def format_hook_response(
        self,
        original_prompt: str,
        routing_decision: dict,
        context_extension: str,
        hook_event_name: str,
    ) -> dict:
        """Build the HARNESS DISPATCH hook response.

        Behavior is byte-identical to the canonical adapter for the minted
        platform.  Platform-specific logic (generalist remap, CTA string) is
        read from the profile rather than hard-coded.

        Codex and Gemini are append-only special cases: their prompt hooks
        (Codex ``UserPromptSubmit`` / Gemini ``BeforeAgent``) can only *inject*
        context via ``hookSpecificOutput.additionalContext`` and CANNOT rewrite
        the prompt, so their output carries ONLY valid fields and the routing +
        context are folded into ``additionalContext``.
        """
        if self._platform in ("codex", "gemini"):
            return self._format_append_only_hook_response(
                routing_decision, context_extension, hook_event_name
            )
        if self._platform == "cursor":
            return self._format_cursor_hook_response()
        branch = routing_decision.get("classification")
        target_skill = routing_decision.get("target_skill")
        target_agent = routing_decision.get("target_agent")
        agent_invokes_skill = routing_decision.get("agent_invokes_skill", False)
        dispatch_directive = ""

        if target_skill and target_agent:
            agent_name = target_agent.lstrip("@")
            skill_ref = self.format_skill_invocation(target_skill)
            agent_ref = self.get_subagent_text_call(
                agent_name, target_skill if agent_invokes_skill else None
            )
            dispatch_directive = (
                f"\n\nHARNESS DISPATCH:\n"
                f"  {skill_ref} → {agent_ref}\n\n"
                f"Invoke the skill as your first action. The skill will direct you to dispatch the agent. Do not answer directly."
            )
            modified_prompt = original_prompt + dispatch_directive
        elif target_agent:
            agent_name = target_agent.lstrip("@")
            # Claude remaps "generalist" to "general-purpose"; Gemini does not.
            if self._profile.generalist_remap and agent_name == "generalist":
                agent_name = "general-purpose"
            description = (
                f"Branch {branch}: Answer this question. Read-only — do not modify files."
            )
            cta = self._profile.hook_agent_only_cta
            dispatch_directive = (
                f"\n\nHARNESS DISPATCH:\n"
                f"  {self.format_subagent_invocation(agent_name, description)}\n\n"
                f"{cta} Do not answer directly."
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
            },
        }

    # ------------------------------------------------------------------
    # Append-only hook response (codex / gemini: no prompt rewrite)
    # ------------------------------------------------------------------

    def _format_append_only_hook_response(
        self,
        routing_decision: dict,
        context_extension: str,
        hook_event_name: str,
    ) -> dict:
        """Append-only hook output for Codex (``UserPromptSubmit``) and Gemini
        (``BeforeAgent``).

        Both platforms' prompt hooks can only *inject* context (via
        ``hookSpecificOutput.additionalContext``) — they cannot rewrite the
        prompt. Codex additionally rejects unknown fields (``deny_unknown_fields``)
        and Gemini's ``additionalContext`` is documented as "text appended to the
        prompt for this turn", so for both we emit ONLY append-only-valid fields.
        The routing decision that prompt-rewriting platforms prepend is re-expressed
        as an injected instruction and concatenated with the SYSTEM STATE block.

        ``hook_event_name`` is passed through unchanged: Codex reuses Claude's
        event names verbatim, and Gemini's actual event name (``BeforeAgent``) is
        already remapped by the hooks.json install step, so the runtime hook is
        invoked with — and must echo back — the correct event name.
        """
        branch = routing_decision.get("classification")
        target_skill = routing_decision.get("target_skill")
        target_agent = routing_decision.get("target_agent")
        agent_invokes_skill = routing_decision.get("agent_invokes_skill", False)

        directive = ""
        if target_skill and target_agent:
            agent_name = target_agent.lstrip("@")
            skill_ref = self.format_skill_invocation(target_skill)
            agent_ref = self.get_subagent_text_call(
                agent_name, target_skill if agent_invokes_skill else None
            )
            directive = (
                f"HARNESS DISPATCH: invoke {skill_ref} as your first action, "
                f"then {agent_ref}. Do not answer directly. "
            )
        elif target_agent:
            agent_name = target_agent.lstrip("@")
            description = (
                f"Branch {branch}: Answer this question. Read-only — do not modify files."
            )
            cta = self._profile.hook_agent_only_cta
            directive = (
                f"HARNESS DISPATCH: {self.format_subagent_invocation(agent_name, description)}. "
                f"{cta} Do not answer directly. "
            )

        additional_context = directive + (context_extension or "")

        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "additionalContext": additional_context,
            },
        }

    # ------------------------------------------------------------------
    # Cursor-specific hook response (no per-turn routing — rules + subagents)
    # ------------------------------------------------------------------

    def _format_cursor_hook_response(self) -> dict:
        """Cursor hook output (honest, no per-turn routing).

        Cursor's ``beforeSubmitPrompt`` hook can only return
        ``{continue, user_message}`` — it **cannot inject context or rewrite the
        prompt** (an open Cursor feature request). There is no per-turn channel
        for the SYSTEM STATE block or forced routing, so per-turn routing is OFF
        for Cursor (accepted product decision): the harness is delivered through
        Cursor-native mechanisms instead — rules files (``AGENTS.md`` /
        ``.cursor/rules``), native subagents (``.cursor/agents/*.md``), and MCP
        (``domain_ops``).

        Emitting the routing schema (``modifiedPrompt`` / ``target_agent`` /
        ``hookSpecificOutput``) would be dishonest — Cursor ignores those fields
        entirely. So we return only the Cursor-valid ``{continue: true}`` and let
        the prompt proceed unmodified.
        """
        return {"continue": True}


_KNOWN_PLATFORMS = frozenset({"claude", "gemini", "codex", "cursor", "generic"})


def get_adapter(platform: str) -> RuntimeAdapter:
    """Return a RuntimeAdapter for *platform* (profile-driven, stdlib-only).

    Falls back to "generic" for unrecognised platform ids, mirroring the
    behaviour of the old per-platform standalone dispatch table.
    """
    resolved = platform if platform in _KNOWN_PLATFORMS else "generic"
    return RuntimeAdapter(resolved)
