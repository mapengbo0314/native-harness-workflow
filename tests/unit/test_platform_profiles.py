"""Schema and value tests for src/harness/adapters/platform_profiles.json.

Validates that:
1. The file is valid JSON and parses without error.
2. claude and gemini entries exist with all required keys and correct types.
3. Spot-checked exact values match what the live adapters return today.
"""

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
PROFILES_PATH = REPO_ROOT / "src" / "harness" / "adapters" / "platform_profiles.json"

REQUIRED_KEYS = {
    "config_dir",
    "plugin_env_var",
    "tool_mappings",
    "event_mappings",
    "skill_invocation",
    "subagent_invocation",
    "subagent_text_call",
    "manifest_format",
    "rules_pointer_files",
    "supports_plugin",
    "plugin_dir_name",
}

SUBAGENT_TEXT_CALL_KEYS = {"with_skill", "without_skill"}


@pytest.fixture(scope="module")
def profiles():
    assert PROFILES_PATH.exists(), f"platform_profiles.json not found at {PROFILES_PATH}"
    with open(PROFILES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    return data


# ---------------------------------------------------------------------------
# 1. File parses and top-level structure
# ---------------------------------------------------------------------------

class TestFileStructure:
    def test_parses_as_json(self, profiles):
        assert isinstance(profiles, dict)

    def test_claude_entry_exists(self, profiles):
        assert "claude" in profiles

    def test_gemini_entry_exists(self, profiles):
        assert "gemini" in profiles

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_required_keys_present(self, profiles, platform):
        entry = profiles[platform]
        missing = REQUIRED_KEYS - set(entry.keys())
        assert not missing, f"{platform} entry missing keys: {missing}"

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_subagent_text_call_has_variants(self, profiles, platform):
        stc = profiles[platform]["subagent_text_call"]
        assert isinstance(stc, dict), f"{platform}.subagent_text_call must be a dict"
        missing = SUBAGENT_TEXT_CALL_KEYS - set(stc.keys())
        assert not missing, f"{platform}.subagent_text_call missing keys: {missing}"


# ---------------------------------------------------------------------------
# 2. Type checks
# ---------------------------------------------------------------------------

class TestTypes:
    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_config_dir_is_str(self, profiles, platform):
        assert isinstance(profiles[platform]["config_dir"], str)

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_plugin_env_var_is_str(self, profiles, platform):
        assert isinstance(profiles[platform]["plugin_env_var"], str)

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_tool_mappings_is_dict(self, profiles, platform):
        assert isinstance(profiles[platform]["tool_mappings"], dict)

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_event_mappings_is_dict(self, profiles, platform):
        assert isinstance(profiles[platform]["event_mappings"], dict)

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_skill_invocation_is_str(self, profiles, platform):
        assert isinstance(profiles[platform]["skill_invocation"], str)

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_subagent_invocation_is_str(self, profiles, platform):
        assert isinstance(profiles[platform]["subagent_invocation"], str)

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_manifest_format_is_str(self, profiles, platform):
        assert isinstance(profiles[platform]["manifest_format"], str)

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_rules_pointer_files_is_list(self, profiles, platform):
        assert isinstance(profiles[platform]["rules_pointer_files"], list)

    @pytest.mark.parametrize("platform", ["claude", "gemini"])
    def test_supports_plugin_is_bool(self, profiles, platform):
        assert isinstance(profiles[platform]["supports_plugin"], bool)


# ---------------------------------------------------------------------------
# 3. Exact-value spot checks — must match live adapter behaviour
# ---------------------------------------------------------------------------

class TestClaudeExactValues:
    def test_config_dir(self, profiles):
        assert profiles["claude"]["config_dir"] == ".claude"

    def test_plugin_env_var(self, profiles):
        assert profiles["claude"]["plugin_env_var"] == "CLAUDE_PLUGIN_ROOT"

    def test_tool_mappings_read_file(self, profiles):
        assert profiles["claude"]["tool_mappings"]["read_file"] == "Read"

    def test_tool_mappings_grep_search(self, profiles):
        assert profiles["claude"]["tool_mappings"]["grep_search"] == "Grep"

    def test_tool_mappings_replace(self, profiles):
        assert profiles["claude"]["tool_mappings"]["replace"] == "Edit"

    def test_tool_mappings_write_file(self, profiles):
        assert profiles["claude"]["tool_mappings"]["write_file"] == "Write"

    def test_tool_mappings_run_shell_command(self, profiles):
        assert profiles["claude"]["tool_mappings"]["run_shell_command"] == "Bash"

    def test_tool_mappings_glob(self, profiles):
        assert profiles["claude"]["tool_mappings"]["glob"] == "Glob"

    def test_event_mappings_empty(self, profiles):
        assert profiles["claude"]["event_mappings"] == {}

    def test_skill_invocation_template(self, profiles):
        tmpl = profiles["claude"]["skill_invocation"]
        assert "{skill}" in tmpl
        assert tmpl == 'Skill("{skill}")'

    def test_subagent_invocation_template(self, profiles):
        tmpl = profiles["claude"]["subagent_invocation"]
        assert "{agent}" in tmpl
        assert "{description}" in tmpl
        assert tmpl == 'Task(subagent_type="{agent}", description="{description}")'

    def test_subagent_text_call_without_skill(self, profiles):
        assert profiles["claude"]["subagent_text_call"]["without_skill"] == 'Task(subagent_type="{agent}")'

    def test_subagent_text_call_with_skill(self, profiles):
        tmpl = profiles["claude"]["subagent_text_call"]["with_skill"]
        assert "{agent}" in tmpl
        assert "{skill}" in tmpl

    def test_manifest_format(self, profiles):
        assert profiles["claude"]["manifest_format"] == "markdown"

    def test_rules_pointer_files(self, profiles):
        assert profiles["claude"]["rules_pointer_files"] == ["CLAUDE.md"]

    def test_supports_plugin_true(self, profiles):
        assert profiles["claude"]["supports_plugin"] is True

    def test_plugin_dir_name(self, profiles):
        assert profiles["claude"]["plugin_dir_name"] == "harness-wf-plugin"


class TestGeminiExactValues:
    def test_config_dir(self, profiles):
        assert profiles["gemini"]["config_dir"] == ".gemini"

    def test_plugin_env_var(self, profiles):
        assert profiles["gemini"]["plugin_env_var"] == "GEMINI_PLUGIN_ROOT"

    def test_tool_mappings_identity(self, profiles):
        tm = profiles["gemini"]["tool_mappings"]
        # Gemini tool_mappings are identity mappings (bulleted form)
        assert tm["- read_file"] == "- read_file"
        assert tm["- grep_search"] == "- grep_search"
        assert tm["- replace"] == "- replace"
        assert tm["- write_file"] == "- write_file"
        assert tm["- run_shell_command"] == "- run_shell_command"
        assert tm["- glob"] == "- glob"

    def test_event_mappings_PreCompact(self, profiles):
        assert profiles["gemini"]["event_mappings"]["PreCompact"] == "PreCompress"

    def test_event_mappings_PostToolUse(self, profiles):
        assert profiles["gemini"]["event_mappings"]["PostToolUse"] == "AfterTool"

    def test_skill_invocation_template(self, profiles):
        tmpl = profiles["gemini"]["skill_invocation"]
        assert "{skill}" in tmpl
        assert tmpl == 'activate_skill("{skill}")'

    def test_subagent_invocation_template(self, profiles):
        tmpl = profiles["gemini"]["subagent_invocation"]
        assert "{agent}" in tmpl
        assert "{description}" in tmpl
        assert tmpl == "@{agent} {description}"

    def test_subagent_text_call_without_skill(self, profiles):
        assert profiles["gemini"]["subagent_text_call"]["without_skill"] == "@{agent}"

    def test_subagent_text_call_with_skill(self, profiles):
        tmpl = profiles["gemini"]["subagent_text_call"]["with_skill"]
        assert "{agent}" in tmpl
        assert "{skill}" in tmpl

    def test_manifest_format(self, profiles):
        assert profiles["gemini"]["manifest_format"] == "markdown"

    def test_rules_pointer_files(self, profiles):
        assert profiles["gemini"]["rules_pointer_files"] == ["GEMINI.md"]

    def test_supports_plugin_false(self, profiles):
        assert profiles["gemini"]["supports_plugin"] is False

    def test_plugin_dir_name_null(self, profiles):
        assert profiles["gemini"]["plugin_dir_name"] is None
