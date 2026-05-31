"""
Tests for src/harness/adapters/profile.py  — S2-T2 (RED → GREEN)

Covers:
- load_profile returns a frozen PlatformProfile dataclass
- All required fields are present with correct types
- Convenience accessor methods produce the same strings the live adapters produce
- Mutating a frozen field raises FrozenInstanceError
- Unknown platform raises ValueError
- Missing required key raises ValueError
"""
import json
import dataclasses
from pathlib import Path
import pytest

from harness.adapters.profile import load_profile, PlatformProfile, ProfileError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_profile(tmp_path: Path, data: dict) -> Path:
    """Write a custom platform_profiles.json next to a fake profile.py stub."""
    profiles_path = tmp_path / "platform_profiles.json"
    profiles_path.write_text(json.dumps(data))
    return profiles_path


# ---------------------------------------------------------------------------
# Basic load
# ---------------------------------------------------------------------------

class TestLoadProfileReturnsCorrectShape:
    def test_claude_returns_platform_profile_instance(self):
        p = load_profile("claude")
        assert isinstance(p, PlatformProfile)

    def test_gemini_returns_platform_profile_instance(self):
        p = load_profile("gemini")
        assert isinstance(p, PlatformProfile)

    def test_codex_returns_platform_profile_instance(self):
        p = load_profile("codex")
        assert isinstance(p, PlatformProfile)

    def test_cursor_returns_platform_profile_instance(self):
        p = load_profile("cursor")
        assert isinstance(p, PlatformProfile)

    def test_generic_returns_platform_profile_instance(self):
        p = load_profile("generic")
        assert isinstance(p, PlatformProfile)


# ---------------------------------------------------------------------------
# Field values — claude
# ---------------------------------------------------------------------------

class TestClaudeFieldValues:
    def setup_method(self):
        self.p = load_profile("claude")

    def test_config_dir(self):
        assert self.p.config_dir == ".claude"

    def test_plugin_env_var(self):
        assert self.p.plugin_env_var == "CLAUDE_PLUGIN_ROOT"

    def test_manifest_format(self):
        assert self.p.manifest_format == "markdown"

    def test_supports_plugin(self):
        assert self.p.supports_plugin is True

    def test_plugin_dir_name(self):
        assert self.p.plugin_dir_name == "harness-wr-plugin"

    def test_rules_pointer_files(self):
        assert self.p.rules_pointer_files == ["CLAUDE.md"]

    def test_tool_mappings_is_dict(self):
        assert isinstance(self.p.tool_mappings, dict)
        assert self.p.tool_mappings["read_file"] == "Read"

    def test_event_mappings_is_dict(self):
        assert isinstance(self.p.event_mappings, dict)

    def test_skill_invocation_template(self):
        assert self.p.skill_invocation_tpl == 'Skill("{skill}")'

    def test_subagent_invocation_template(self):
        assert self.p.subagent_invocation_tpl == 'Task(subagent_type="{agent}", description="{description}")'

    def test_subagent_text_call_without_skill(self):
        assert self.p.subagent_text_call_without_skill == 'Task(subagent_type="{agent}")'

    def test_subagent_text_call_with_skill(self):
        assert self.p.subagent_text_call_with_skill == (
            'Task(subagent_type="{agent}", description="Invoke Skill(\'{skill}\') as your first action.")'
        )


# ---------------------------------------------------------------------------
# Field values — gemini (spot-checks)
# ---------------------------------------------------------------------------

class TestGeminiFieldValues:
    def setup_method(self):
        self.p = load_profile("gemini")

    def test_config_dir(self):
        assert self.p.config_dir == ".gemini"

    def test_supports_plugin_false(self):
        assert self.p.supports_plugin is False

    def test_plugin_dir_name_none(self):
        assert self.p.plugin_dir_name is None

    def test_event_mappings(self):
        assert self.p.event_mappings == {"PreCompact": "PreCompress", "PostToolUse": "AfterTool"}

    def test_rules_pointer_files(self):
        assert self.p.rules_pointer_files == ["GEMINI.md"]


# ---------------------------------------------------------------------------
# Frozen — mutating raises
# ---------------------------------------------------------------------------

class TestFrozenDataclass:
    def test_mutating_config_dir_raises(self):
        p = load_profile("claude")
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            p.config_dir = "hacked"

    def test_mutating_supports_plugin_raises(self):
        p = load_profile("gemini")
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            p.supports_plugin = True


# ---------------------------------------------------------------------------
# Unknown platform
# ---------------------------------------------------------------------------

class TestUnknownPlatform:
    def test_unknown_platform_raises_value_error(self):
        with pytest.raises((ValueError, ProfileError)):
            load_profile("nonexistent_platform")

    def test_empty_string_raises(self):
        with pytest.raises((ValueError, ProfileError)):
            load_profile("")


# ---------------------------------------------------------------------------
# Missing required keys — via injectable path
# ---------------------------------------------------------------------------

class TestMissingRequiredKeys:
    def test_missing_config_dir_raises(self, tmp_path):
        data = {
            "myplatform": {
                # config_dir intentionally omitted
                "plugin_env_var": "MY_VAR",
                "tool_mappings": {},
                "event_mappings": {},
                "skill_invocation": "Use {skill}",
                "subagent_invocation": "@{agent} {description}",
                "subagent_text_call": {
                    "without_skill": "@{agent}",
                    "with_skill": "@{agent} — invoke skill {skill} first",
                },
                "manifest_format": "markdown",
                "rules_pointer_files": [],
                "supports_plugin": False,
                "plugin_dir_name": None,
            }
        }
        profiles_path = _write_profile(tmp_path, data)
        with pytest.raises((ValueError, ProfileError, KeyError)):
            load_profile("myplatform", _profiles_path=profiles_path)

    def test_missing_skill_invocation_raises(self, tmp_path):
        data = {
            "myplatform": {
                "config_dir": ".myp",
                "plugin_env_var": "MY_VAR",
                "tool_mappings": {},
                "event_mappings": {},
                # skill_invocation intentionally omitted
                "subagent_invocation": "@{agent} {description}",
                "subagent_text_call": {
                    "without_skill": "@{agent}",
                    "with_skill": "@{agent} — invoke skill {skill} first",
                },
                "manifest_format": "markdown",
                "rules_pointer_files": [],
                "supports_plugin": False,
                "plugin_dir_name": None,
            }
        }
        profiles_path = _write_profile(tmp_path, data)
        with pytest.raises((ValueError, ProfileError, KeyError)):
            load_profile("myplatform", _profiles_path=profiles_path)

    def test_missing_subagent_text_call_raises(self, tmp_path):
        data = {
            "myplatform": {
                "config_dir": ".myp",
                "plugin_env_var": "MY_VAR",
                "tool_mappings": {},
                "event_mappings": {},
                "skill_invocation": "Use {skill}",
                "subagent_invocation": "@{agent} {description}",
                # subagent_text_call intentionally omitted
                "manifest_format": "markdown",
                "rules_pointer_files": [],
                "supports_plugin": False,
                "plugin_dir_name": None,
            }
        }
        profiles_path = _write_profile(tmp_path, data)
        with pytest.raises((ValueError, ProfileError, KeyError)):
            load_profile("myplatform", _profiles_path=profiles_path)


# ---------------------------------------------------------------------------
# Convenience accessor methods
# ---------------------------------------------------------------------------

class TestConvenienceAccessors:
    """
    Test that accessor methods produce the same strings the live adapters produce.
    Reference: ClaudeAdapter.format_skill_invocation / format_subagent_invocation /
               get_subagent_text_call in src/harness/adapters/claude.py
    """

    # --- claude ---

    def test_claude_skill_invocation(self):
        p = load_profile("claude")
        assert p.skill_invocation("foo") == 'Skill("foo")'

    def test_claude_skill_invocation_spaces(self):
        p = load_profile("claude")
        assert p.skill_invocation("my-skill") == 'Skill("my-skill")'

    def test_claude_subagent_invocation(self):
        p = load_profile("claude")
        assert p.subagent_invocation("coder", "do the thing") == (
            'Task(subagent_type="coder", description="do the thing")'
        )

    def test_claude_subagent_text_call_without_skill(self):
        p = load_profile("claude")
        assert p.subagent_text_call("coder") == 'Task(subagent_type="coder")'

    def test_claude_subagent_text_call_with_skill(self):
        p = load_profile("claude")
        assert p.subagent_text_call("coder", skill="my-skill") == (
            "Task(subagent_type=\"coder\", description=\"Invoke Skill('my-skill') as your first action.\")"
        )

    # --- gemini ---

    def test_gemini_skill_invocation(self):
        p = load_profile("gemini")
        assert p.skill_invocation("bar") == 'activate_skill("bar")'

    def test_gemini_subagent_invocation(self):
        p = load_profile("gemini")
        assert p.subagent_invocation("researcher", "analyse this") == "@researcher analyse this"

    def test_gemini_subagent_text_call_without_skill(self):
        p = load_profile("gemini")
        assert p.subagent_text_call("researcher") == "@researcher"

    def test_gemini_subagent_text_call_with_skill(self):
        p = load_profile("gemini")
        assert p.subagent_text_call("researcher", skill="meta-learning") == (
            '@researcher — activate_skill("meta-learning") as your first action'
        )

    # --- codex ---

    def test_codex_skill_invocation(self):
        p = load_profile("codex")
        assert p.skill_invocation("baz") == "Activate skill baz"

    def test_codex_subagent_text_call_without_skill(self):
        p = load_profile("codex")
        assert p.subagent_text_call("agent-x") == "Hand off to agent-x"

    def test_codex_subagent_text_call_with_skill(self):
        p = load_profile("codex")
        assert p.subagent_text_call("agent-x", skill="diagnose") == (
            "Hand off to agent-x — invoke skill diagnose first"
        )
