"""S2-T4 — Builder / profile delegation tests.

Asserts:
  (a) Syntax methods on the concrete adapters now return exactly what
      ``load_profile(platform)`` provides.
  (b) ``assemble_layout`` produces a plugin-stack layout for claude
      (``supports_plugin=True``) and is a no-op (embedded) for gemini
      (``supports_plugin=False``).
  (c) ``supports_plugin`` is the flag that drives the branch.
  (d) ``generate_core_infrastructure`` remains callable and is
      behaviour-identical to ``assemble_layout``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from harness.adapters import get_adapter
from harness.adapters.profile import load_profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_harness_tmp(base: Path, platform_dir: str) -> Path:
    """
    Replicate the directory shape that the minting pipeline creates before
    calling generate_core_infrastructure / assemble_layout.

    The minting engine copies boilerplate into .harness_tmp (or the config
    dir), then generate_core_infrastructure/assemble_layout moves the payload
    into harness-wr-plugin/.  We need at least one payload directory to exist
    so the move logic has something to work with.
    """
    harness_tmp = base / ".harness_tmp"
    for sub in ("skills", "agents", "hooks", "scripts", "src"):
        (harness_tmp / sub).mkdir(parents=True, exist_ok=True)
        # Plant a marker file so we can assert the move occurred
        (harness_tmp / sub / f"sample_{sub}.md").write_text(f"# {sub} stub\n")
    # pyproject.toml payload file
    (harness_tmp / "pyproject.toml").write_text("[tool.example]\n")
    return harness_tmp


# ---------------------------------------------------------------------------
# (a) Syntax methods delegate to profile
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_get_tool_mappings_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    assert adapter.get_tool_mappings() == profile.tool_mappings


@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_format_skill_invocation_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    skill = "my-test-skill"
    assert adapter.format_skill_invocation(skill) == profile.skill_invocation(skill)


@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_format_subagent_invocation_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    agent, desc = "coder", "implement the feature"
    assert adapter.format_subagent_invocation(agent, desc) == profile.subagent_invocation(agent, desc)


@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_get_subagent_text_call_without_skill_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    agent = "coder"
    assert adapter.get_subagent_text_call(agent) == profile.subagent_text_call(agent)


@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_get_subagent_text_call_with_skill_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    agent, skill = "coder", "my-skill"
    assert adapter.get_subagent_text_call(agent, skill) == profile.subagent_text_call(agent, skill=skill)


@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_get_config_dir_name_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    assert adapter.get_config_dir_name() == profile.config_dir


@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_get_plugin_env_var_name_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    assert adapter.get_plugin_env_var_name() == profile.plugin_env_var


@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_get_rules_pointer_files_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    assert adapter.get_rules_pointer_files() == profile.rules_pointer_files


@pytest.mark.parametrize("platform", ["claude", "gemini"])
def test_get_agent_manifest_format_matches_profile(platform: str) -> None:
    adapter = get_adapter(platform)
    profile = load_profile(platform)
    assert adapter.get_agent_manifest_format() == profile.manifest_format


# ---------------------------------------------------------------------------
# (b) assemble_layout: plugin-stack for claude, no-op for gemini
# ---------------------------------------------------------------------------

def test_assemble_layout_claude_creates_plugin_generated(tmp_path: Path) -> None:
    """Claude (supports_plugin=True) must assemble the plugin directory (harness-wr-plugin/)."""
    adapter = get_adapter("claude")
    project = tmp_path / "myproject"
    project.mkdir()
    _make_harness_tmp(project, ".claude")

    adapter.assemble_layout(project)

    plugin_dir = project / ".harness_tmp" / "harness-wr-plugin"
    assert plugin_dir.exists(), "harness-wr-plugin/ must be created for claude"
    # At least one payload dir should have been moved inside
    assert any(plugin_dir.iterdir()), "harness-wr-plugin/ must not be empty"


def test_assemble_layout_gemini_no_plugin_generated(tmp_path: Path) -> None:
    """Gemini (supports_plugin=False) must NOT create a harness-wr-plugin/ directory."""
    adapter = get_adapter("gemini")
    project = tmp_path / "myproject"
    project.mkdir()
    # Gemini has no .harness_tmp pre-step; but even if we create it there should
    # be no harness-wr-plugin after assemble_layout.
    harness_dir = project / ".gemini"
    harness_dir.mkdir(parents=True, exist_ok=True)

    adapter.assemble_layout(project)

    assert not (harness_dir / "harness-wr-plugin").exists(), (
        "gemini assemble_layout must not create harness-wr-plugin/"
    )


def test_assemble_layout_folder_name_is_harness_wr_plugin(tmp_path: Path) -> None:
    """The plugin directory is now named 'harness-wr-plugin' (renamed by S2-T4b)."""
    adapter = get_adapter("claude")
    project = tmp_path / "myproject"
    project.mkdir()
    _make_harness_tmp(project, ".claude")

    adapter.assemble_layout(project)

    plugin_dir = project / ".harness_tmp" / "harness-wr-plugin"
    assert plugin_dir.exists(), "folder must be 'harness-wr-plugin' (renamed by S2-T4b)"
    assert not (project / ".harness_tmp" / "plugin-generated").exists(), (
        "old plugin-generated name must NOT be used after S2-T4b"
    )


# ---------------------------------------------------------------------------
# (c) supports_plugin drives the branch
# ---------------------------------------------------------------------------

def test_claude_supports_plugin_is_true() -> None:
    profile = load_profile("claude")
    assert profile.supports_plugin is True


def test_gemini_supports_plugin_is_false() -> None:
    profile = load_profile("gemini")
    assert profile.supports_plugin is False


# ---------------------------------------------------------------------------
# (d) generate_core_infrastructure is still callable and identical to assemble_layout
# ---------------------------------------------------------------------------

def test_generate_core_infrastructure_claude_identical_to_assemble_layout(
    tmp_path: Path,
) -> None:
    """Both entry points for claude produce the same artifact structure (harness-wr-plugin/)."""
    adapter = get_adapter("claude")

    # Run via assemble_layout
    proj_a = tmp_path / "via_assemble"
    proj_a.mkdir()
    _make_harness_tmp(proj_a, ".claude")
    adapter.assemble_layout(proj_a)

    # Run via generate_core_infrastructure
    proj_b = tmp_path / "via_generate"
    proj_b.mkdir()
    _make_harness_tmp(proj_b, ".claude")
    adapter.generate_core_infrastructure(proj_b)

    # Both should end up with harness-wr-plugin/
    assert (proj_a / ".harness_tmp" / "harness-wr-plugin").exists()
    assert (proj_b / ".harness_tmp" / "harness-wr-plugin").exists()


def test_generate_core_infrastructure_gemini_no_plugin_generated(
    tmp_path: Path,
) -> None:
    """generate_core_infrastructure for gemini (no-op) must not create a plugin stack directory."""
    adapter = get_adapter("gemini")
    project = tmp_path / "myproject"
    project.mkdir()
    harness_dir = project / ".gemini"
    harness_dir.mkdir(parents=True, exist_ok=True)

    adapter.generate_core_infrastructure(project)

    assert not (harness_dir / "harness-wr-plugin").exists()
    assert not (harness_dir / "harness-wr-plugin").exists()
