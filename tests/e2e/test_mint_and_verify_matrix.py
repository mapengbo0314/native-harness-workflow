"""
S1-T3 — L1 existence + L2 wiring/registration matrix test.

Parametrized over ["claude", "gemini"].  Mints each platform once per test
function via the shared helper and asserts:

  L1 — required paths exist (plugin/config, hooks config, skills/, MCP config,
        AGENTS/orchestrator, src/)
  L2 — wiring/registration correctness:
        - every hooks.json command script exists on disk
        - hook event names are the platform-correct set
        - agents.json entries (claude-only) resolve under the plugin root
        - plugin.json name+description are substituted (not empty, not '. for .')

Verified artifact structures (real mint runs, 2026-05-30):

  claude  (.claude/plugin-generated/)
    hooks/hooks.json            — events: UserPromptSubmit, PreCompact,
                                           PreToolUse, PostToolUse
    hooks/{prompt_classifier,pre_tool_use,post_tool_use,notify_compression}.py
    hooks/hook_common.py
    agents.json                 — absolute paths baked to project dir
    agents/{adversary,debugger,implementer,planner,reviewer,verifier}.md
    skills/*/SKILL.md
    .claude-plugin/plugin.json  — {"name":"orchestrator-plugin","description":
                                    "Auto-generated orchestrator plugin for <project>"}
    src/

  gemini  (.gemini/)
    hooks/hooks.json            — events: UserPromptSubmit, PreCompress,
                                           PreToolUse, AfterTool
    hooks/{prompt_classifier,pre_tool_use,post_tool_use,notify_compression}.py
    hooks/hook_common.py
    agents/{adversary,debugger,implementer,planner,reviewer,verifier}.md
    skills/*/SKILL.md
    agent.json                  — top-level orchestrator manifest
    skills.json                 — skill-index manifest
    src/
    (NO agents.json, NO .claude-plugin/plugin.json)

Real mint bugs caught by this suite
------------------------------------
  BUG-1  agents.json uses absolute OS paths (baked to the minted project dir).
         Consequence: paths are NOT portable across machines or after tmp cleanup.
         Handled: xfail — the paths are absolute but DO exist during the test, so
         the "exists" check passes.  A separate assertion verifies they are
         relative (or resolve under plugin_root), marked xfail to document the
         bug without hiding it.  Tracked for fix in the minting code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.e2e._mint_helpers import mint_platform

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOOK_ENV_VAR: dict[str, str] = {
    "claude": "CLAUDE_PLUGIN_ROOT",
    "gemini": "GEMINI_PLUGIN_ROOT",
}

# Expected hook event names per platform (verified from real mint, 2026-05-30)
_EXPECTED_HOOK_EVENTS: dict[str, set[str]] = {
    "claude": {"UserPromptSubmit", "PreCompact", "PreToolUse", "PostToolUse"},
    "gemini": {"UserPromptSubmit", "PreCompress", "PreToolUse", "AfterTool"},
}

# Minimum set of skill directories expected in skills/
_MIN_SKILLS: list[str] = [
    "diagnose",
    "harness-test-driven-development",
    "harness-brainstorming-plans",
]

# Core hook script filenames expected in hooks/
_HOOK_SCRIPTS: list[str] = [
    "prompt_classifier.py",
    "pre_tool_use.py",
    "post_tool_use.py",
    "notify_compression.py",
    "hook_common.py",
]


def _extract_script_path(command: str, plugin_root: Path, platform: str) -> Path | None:
    """
    Parse a hook command string and return the resolved script path.

    Hook commands look like:
      python3 "${CLAUDE_PLUGIN_ROOT}/hooks/notify_compression.py"
      uv run "${GEMINI_PLUGIN_ROOT}/hooks/prompt_classifier.py"

    We substitute the env-var placeholder with the actual plugin_root.
    Returns None if no script path can be parsed.
    """
    env_var = _HOOK_ENV_VAR[platform]
    # Replace ${VAR} (or $VAR) with plugin_root
    substituted = re.sub(
        r"\$\{?" + re.escape(env_var) + r"\}?",
        str(plugin_root),
        command,
    )
    # Extract the first path-like token that ends with .py
    for token in substituted.split():
        token = token.strip('"').strip("'")
        if token.endswith(".py"):
            return Path(token)
    return None


# ---------------------------------------------------------------------------
# Session-scoped fixtures — mint once per platform per test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def claude_root(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("mint_matrix")
    return mint_platform(tmp, "claude")


@pytest.fixture(scope="session")
def gemini_root(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("mint_matrix")
    return mint_platform(tmp, "gemini")


@pytest.fixture(
    params=["claude", "gemini"],
    scope="session",
)
def plugin_root(request, claude_root, gemini_root) -> tuple[str, Path]:
    """Yields (platform, plugin_root) for parametrized tests."""
    if request.param == "claude":
        return "claude", claude_root
    return "gemini", gemini_root


# ---------------------------------------------------------------------------
# L1 — Existence assertions
# ---------------------------------------------------------------------------


class TestArtifactsExist:
    """L1: Required paths exist in the minted plugin root."""

    def test_plugin_root_is_directory(self, plugin_root):
        platform, root = plugin_root
        assert root.is_dir(), (
            f"{platform}: plugin_root does not exist or is not a directory: {root}"
        )

    def test_hooks_json_exists(self, plugin_root):
        platform, root = plugin_root
        hooks_file = root / "hooks" / "hooks.json"
        assert hooks_file.exists(), (
            f"{platform}: hooks/hooks.json missing at {hooks_file}"
        )

    def test_hook_scripts_exist(self, plugin_root):
        """All core hook Python scripts must be present."""
        platform, root = plugin_root
        missing = [s for s in _HOOK_SCRIPTS if not (root / "hooks" / s).exists()]
        assert not missing, (
            f"{platform}: missing hook scripts in hooks/: {missing}\n"
            f"  hooks/ contents: {list((root / 'hooks').iterdir())}"
        )

    def test_agents_directory_exists(self, plugin_root):
        platform, root = plugin_root
        agents_dir = root / "agents"
        assert agents_dir.is_dir(), (
            f"{platform}: agents/ directory missing at {agents_dir}"
        )

    def test_skills_directory_exists(self, plugin_root):
        platform, root = plugin_root
        skills_dir = root / "skills"
        assert skills_dir.is_dir(), (
            f"{platform}: skills/ directory missing at {skills_dir}"
        )

    def test_minimum_skills_present(self, plugin_root):
        """Minimum required skill directories must exist with a SKILL.md."""
        platform, root = plugin_root
        skills_dir = root / "skills"
        missing = [
            s for s in _MIN_SKILLS if not (skills_dir / s / "SKILL.md").exists()
        ]
        assert not missing, (
            f"{platform}: missing SKILL.md in skills/{s} for skill(s): {missing}"
        )

    def test_src_directory_exists(self, plugin_root):
        platform, root = plugin_root
        src_dir = root / "src"
        assert src_dir.is_dir(), (
            f"{platform}: src/ directory missing at {src_dir}"
        )

    # --- claude-only L1 ---

    def test_claude_agents_json_exists(self, claude_root):
        """Claude: agents.json manifest must exist."""
        agents_json = claude_root / "agents.json"
        assert agents_json.exists(), (
            f"claude: agents.json missing at {agents_json}"
        )

    def test_claude_plugin_json_exists(self, claude_root):
        """Claude: .claude-plugin/plugin.json must exist."""
        plugin_json = claude_root / ".claude-plugin" / "plugin.json"
        assert plugin_json.exists(), (
            f"claude: .claude-plugin/plugin.json missing at {plugin_json}"
        )

    # --- gemini-only L1 ---

    def test_gemini_agent_json_exists(self, gemini_root):
        """Gemini: top-level agent.json orchestrator manifest must exist."""
        agent_json = gemini_root / "agent.json"
        assert agent_json.exists(), (
            f"gemini: agent.json missing at {agent_json}"
        )

    def test_gemini_skills_json_exists(self, gemini_root):
        """Gemini: skills.json skill-index manifest must exist."""
        skills_json = gemini_root / "skills.json"
        assert skills_json.exists(), (
            f"gemini: skills.json missing at {skills_json}"
        )

    def test_gemini_no_plugin_generated(self, gemini_root):
        """Gemini is embedded — it must NOT have a plugin-generated subdirectory."""
        plugin_generated = gemini_root / "plugin-generated"
        assert not plugin_generated.exists(), (
            "gemini: unexpected plugin-generated/ directory found — "
            "gemini uses embedded layout"
        )


# ---------------------------------------------------------------------------
# L2 — Wiring / registration assertions
# ---------------------------------------------------------------------------


class TestWiring:
    """L2: Every manifest reference resolves; event names and substitution are correct."""

    # ---- Hook command wiring ----

    def test_hook_commands_reference_existing_scripts(self, plugin_root):
        """
        Every hook command in hooks.json must reference a script file that
        exists on disk.  The ${PLATFORM_PLUGIN_ROOT} placeholder is resolved
        to the actual plugin_root.
        """
        platform, root = plugin_root
        hooks_file = root / "hooks" / "hooks.json"
        data = json.loads(hooks_file.read_text())

        hooks_map = data.get("hooks", {})
        missing: list[str] = []

        for event_name, entries in hooks_map.items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    command = hook.get("command", "")
                    if not command:
                        continue
                    script_path = _extract_script_path(command, root, platform)
                    if script_path is None:
                        continue
                    # Resolve to handle macOS /private/tmp symlink
                    if not script_path.resolve().exists():
                        missing.append(
                            f"  event={event_name!r}, command={command!r}, "
                            f"resolved={script_path.resolve()}"
                        )

        assert not missing, (
            f"{platform}: hook commands reference non-existent scripts:\n"
            + "\n".join(missing)
        )

    def test_hook_event_names_are_platform_correct(self, plugin_root):
        """
        The set of hook event names in hooks.json must exactly match the
        platform-correct set.

        claude: {UserPromptSubmit, PreCompact, PreToolUse, PostToolUse}
        gemini: {UserPromptSubmit, PreCompress, PreToolUse, AfterTool}
        """
        platform, root = plugin_root
        hooks_file = root / "hooks" / "hooks.json"
        data = json.loads(hooks_file.read_text())

        actual_events = set(data.get("hooks", {}).keys())
        expected_events = _EXPECTED_HOOK_EVENTS[platform]

        assert actual_events == expected_events, (
            f"{platform}: hook event names mismatch.\n"
            f"  expected : {sorted(expected_events)}\n"
            f"  actual   : {sorted(actual_events)}\n"
            f"  missing  : {sorted(expected_events - actual_events)}\n"
            f"  extra    : {sorted(actual_events - expected_events)}"
        )

    # ---- agents.json (claude-only) ----

    def test_claude_agents_json_entries_files_exist(self, claude_root):
        """
        Every agent path in agents.json must point to a file that exists.
        (Resolves macOS /private/tmp symlink via .resolve().)
        """
        agents_json = claude_root / "agents.json"
        data = json.loads(agents_json.read_text())
        agents = data.get("agents", {})

        missing: list[str] = []
        for name, info in agents.items():
            path_str = info.get("path", "")
            if not path_str:
                missing.append(f"  {name!r}: no 'path' key")
                continue
            p = Path(path_str)
            if not p.resolve().exists():
                missing.append(f"  {name!r}: path does not exist: {path_str}")

        assert not missing, (
            "claude: agents.json entries reference non-existent files:\n"
            + "\n".join(missing)
        )

    @pytest.mark.xfail(
        reason=(
            "S1-T3 caught real mint bug BUG-1: agents.json paths are absolute "
            "(baked to the project tmp dir). Absolute paths break portability — "
            "they should be relative to the plugin root. "
            "Tracked for fix in the minting/manifest-export code."
        ),
        strict=True,
    )
    def test_claude_agents_json_entries_are_relative_paths(self, claude_root):
        """
        BUG-1 (xfail): agents.json paths should be relative (not absolute).
        Absolute paths are baked to the minted project directory and break
        when the project is moved or shared across machines.
        """
        agents_json = claude_root / "agents.json"
        data = json.loads(agents_json.read_text())
        agents = data.get("agents", {})

        absolute_paths: list[str] = []
        for name, info in agents.items():
            path_str = info.get("path", "")
            if path_str and Path(path_str).is_absolute():
                absolute_paths.append(f"  {name!r}: {path_str}")

        assert not absolute_paths, (
            "claude: agents.json contains absolute paths (not portable):\n"
            + "\n".join(absolute_paths)
        )

    # ---- plugin.json substitution (claude-only) ----

    def test_claude_plugin_json_name_is_substituted(self, claude_root):
        """
        plugin.json 'name' must be non-empty and NOT a degenerate placeholder.
        """
        plugin_json = claude_root / ".claude-plugin" / "plugin.json"
        data = json.loads(plugin_json.read_text())

        name = data.get("name", "")
        assert name, "claude: plugin.json 'name' is empty"
        assert name != ".", "claude: plugin.json 'name' is '.' (not substituted)"
        assert not name.endswith(" for ."), (
            f"claude: plugin.json 'name' ends with ' for .' (degenerate): {name!r}"
        )

    def test_claude_plugin_json_description_is_substituted(self, claude_root):
        """
        plugin.json 'description' must be non-empty and NOT end with 'for .'
        (the observed degenerate substitution pattern when project name is empty).
        """
        plugin_json = claude_root / ".claude-plugin" / "plugin.json"
        data = json.loads(plugin_json.read_text())

        desc = data.get("description", "")
        assert desc, "claude: plugin.json 'description' is empty"
        assert not desc.endswith("for ."), (
            f"claude: plugin.json 'description' ends with 'for .' "
            f"(project name not substituted): {desc!r}"
        )
        assert " for ." not in desc, (
            f"claude: plugin.json 'description' contains ' for .' "
            f"(degenerate substitution pattern): {desc!r}"
        )

    # ---- gemini agent.json + skills.json sanity ----

    def test_gemini_agent_json_has_required_fields(self, gemini_root):
        """Gemini: agent.json must have non-empty 'name' and 'description'."""
        agent_json = gemini_root / "agent.json"
        data = json.loads(agent_json.read_text())

        name = data.get("name", "")
        desc = data.get("description", "")
        assert name, "gemini: agent.json 'name' is empty"
        assert desc, "gemini: agent.json 'description' is empty"

    def test_gemini_skills_json_entries_resolve(self, gemini_root):
        """
        Gemini: every skill path in skills.json must resolve to an existing
        file relative to the skills/ directory.
        """
        skills_json = gemini_root / "skills.json"
        data = json.loads(skills_json.read_text())
        skills = data.get("skills", {})
        skills_dir = gemini_root / "skills"

        missing: list[str] = []
        for skill_name, info in skills.items():
            rel_path = info.get("path", "")
            if not rel_path:
                missing.append(f"  {skill_name!r}: no 'path' key")
                continue
            full_path = skills_dir / rel_path
            if not full_path.exists():
                missing.append(
                    f"  {skill_name!r}: path does not exist: {full_path}"
                )

        assert not missing, (
            "gemini: skills.json entries reference non-existent files:\n"
            + "\n".join(missing)
        )
