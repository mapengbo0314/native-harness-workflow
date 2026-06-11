"""
S1-T3/T4/T5 — L1 existence + L2 wiring/registration + L3 skills/MCP + L5 routing matrix test.

Parametrized over ["claude", "gemini"].  Mints each platform once per test
function via the shared helper and asserts:

  L1 — required paths exist (plugin/config, hooks config, skills/, MCP config,
        AGENTS/orchestrator, src/)
  L2 — wiring/registration correctness:
        - every hooks.json command script exists on disk
        - hook event names are the platform-correct set
        - agents.json entries (claude-only) resolve under the plugin root
        - plugin.json name+description are substituted (not empty, not '. for .')
  L3 (S1-T4) — skills completeness + MCP registration wiring:
        - every boilerplate skill in src/harness/templates/boilerplate/skills/
          is present in the minted plugin's skills/ (full-set assertion)
        - the MCP codegraph registration command is wired correctly:
          configure_cli() is called with the correct subprocess command.
          We use Approach 2 (command assertion) because no .mcp.json config
          file is written to the plugin directory — mcp.json generation was
          explicitly removed (see minting_engine.py comment "mcp.json
          generation removed in task 2") and the MCP is registered via the
          external CLI (claude/gemini mcp add codegraph …).  Since the mock
          in mint_platform patches subprocess.run globally AND shutil.which
          returns None on CI (no claude/gemini CLI installed), configure_cli
          exits early before calling subprocess.run.  The correct test calls
          configure_cli() directly with shutil.which patched to a fake path.
  L5 (S1-T5) — routing behavior against canned scenarios:
        - loads every *.yaml under tests/sandbox/scenarios/ (including captured/)
        - only scenarios that declare expected_behavior (branch + optional agent)
          are asserted
        - run_scenario() is called with query_llm patched to None to force the
          deterministic keyword classifier (no LLM call)
        - asserts RoutingResult.branch matches expected_behavior.branch
        - asserts RoutingResult.agent matches expected_behavior.agent when declared
        - scenarios where current routing diverges from declared expectation are
          marked xfail(strict) with an explanatory reason

Verified artifact structures (real mint runs, 2026-05-30):

  claude  (.claude/harness-wf-plugin/)
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
    hooks/hooks.json            — events: BeforeAgent, BeforeTool,
                                           AfterTool, PreCompress
    hooks/{prompt_classifier,pre_tool_use,post_tool_use,notify_compression}.py
    hooks/hook_common.py
    agents/{adversary,debugger,implementer,planner,reviewer,verifier}.md
    skills/*/SKILL.md
    agent.json                  — top-level orchestrator manifest
    skills.json                 — skill-index manifest
    src/
    (NO agents.json, NO .claude-plugin/plugin.json)

Real mint bugs / routing mismatches caught by this suite
----------------------------------------------------------
  BUG-1  agents.json uses absolute OS paths (baked to the minted project dir).
         Consequence: paths are NOT portable across machines or after tmp cleanup.
         Handled: xfail — the paths are absolute but DO exist during the test, so
         the "exists" check passes.  A separate assertion verifies they are
         relative (or resolve under plugin_root), marked xfail to document the
         bug without hiding it.  Tracked for fix in the minting code.

  BUG-2  (L5, S1-T5) Routing miss: "Rename LoginComponent to AuthComponent
         everywhere in the codebase" should route to branch D (code edit / TDD)
         but the deterministic keyword classifier produces branch B (feature /
         planning) because the prompt contains no D-branch keywords ("typo",
         "fix the", "change color", "minor update").  The scenario
         captured/example_routing_miss.yaml documents this as expected_behavior
         branch D.  Marked xfail(strict) — the net caught a real routing gap.
         Fix: extend D-branch keyword list to cover rename/refactor patterns.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from tests.e2e._mint_helpers import mint_platform
from tests.sandbox.runner import run_scenario, RoutingResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOOK_ENV_VAR: dict[str, str] = {
    "claude": "CLAUDE_PLUGIN_ROOT",
    "gemini": "GEMINI_PLUGIN_ROOT",
}

# Expected hook event names per platform. Gemini CLI has its own event taxonomy
# (no UserPromptSubmit/PreToolUse/PostToolUse/PreCompact); install_hooks remaps
# all four Claude keys to BeforeAgent/BeforeTool/AfterTool/PreCompress.
# (Gemini deep-research pass, June 2026 — see .claude/docs/platform-support.md.)
_EXPECTED_HOOK_EVENTS: dict[str, set[str]] = {
    "claude": {
        "UserPromptSubmit", "PreCompact", "PreToolUse", "PostToolUse",
        # Phase 2 (ECC): session memory hooks
        "Stop", "SessionStart", "SessionEnd",
    },
    "gemini": {"BeforeAgent", "BeforeTool", "AfterTool", "PreCompress", "SessionEnd"},
}

# Minimum set of skill directories expected in skills/
_MIN_SKILLS: list[str] = [
    "diagnose",
    "harness-test-driven-development",
    "harness-brainstorming-plans",
]

# Canonical boilerplate skills: read once from the source tree.
# Source: src/harness/templates/boilerplate/skills/
# This is the authoritative set — every directory here must appear in
# the minted plugin's skills/ directory.
_BOILERPLATE_SKILLS_DIR: Path = (
    Path(__file__).parent.parent.parent
    / "src" / "harness" / "templates" / "boilerplate" / "skills"
)
_CANONICAL_SKILLS: frozenset[str] = frozenset(
    d.name for d in _BOILERPLATE_SKILLS_DIR.iterdir() if d.is_dir()
)

# Expected MCP codegraph registration command fragments per platform.
# The full commands (verified from real adapter source):
#   claude: [<claude>, "mcp", "add-json", "codegraph", "<json>"]  where <json>
#            carries the stdio command plus "alwaysLoad": true (so codegraph's
#            tools are never deferred behind Tool Search). `claude mcp add` has
#            no alwaysLoad flag, hence add-json with a JSON payload.
#   gemini: [<gemini>, "mcp", "add", "codegraph", "npx", "-y",
#            "@colbymchenry/codegraph", "serve", "--mcp"]
# We assert the presence of the key semantic tokens as standalone argv elements;
# for claude, "@colbymchenry/codegraph" and "alwaysLoad" live inside the JSON
# payload arg and are checked separately below.
_MCP_COMMAND_TOKENS: dict[str, list[str]] = {
    "claude": ["mcp", "add-json", "codegraph"],
    "gemini": ["mcp", "add", "codegraph", "@colbymchenry/codegraph"],
}

# Fake CLI binary paths used when patching shutil.which for MCP tests
_FAKE_CLI_PATH: dict[str, str] = {
    "claude": "/usr/local/bin/claude",
    "gemini": "/usr/local/bin/gemini",
}

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
        """Gemini is embedded — it must NOT have a plugin stack subdirectory."""
        # Neither the old name nor the new name should appear under gemini root
        for name in ("harness-wf-plugin", "harness-wf-plugin"):
            assert not (gemini_root / name).exists(), (
                f"gemini: unexpected {name}/ directory found — "
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
        gemini: {BeforeAgent, BeforeTool, AfterTool, PreCompress}
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


# ---------------------------------------------------------------------------
# L3 (S1-T4) — Full skills completeness + MCP registration wiring
# ---------------------------------------------------------------------------


class TestSkillsAndMcpInstalled:
    """
    S1-T4: every boilerplate skill is present in the minted plugin's skills/,
    and the codegraph MCP registration command is wired correctly.

    MCP assertion approach: Approach 2 — command assertion.

    Rationale: No .mcp.json or equivalent config file is written to the minted
    plugin directory (mcp.json generation was explicitly removed per the comment
    in minting_engine.py: "mcp.json generation removed in task 2").  The MCP is
    registered solely via the external CLI (``claude mcp add codegraph …`` /
    ``gemini mcp add codegraph …``) inside ``configure_cli()``.  During
    mint_platform(), subprocess.run is mocked globally AND shutil.which returns
    None for the platform CLI (not installed on CI), so configure_cli() exits
    early without calling subprocess.run.  We therefore call configure_cli()
    directly in this test with shutil.which patched to return a fake binary
    path and a fresh subprocess.run mock, then assert the mock was invoked with
    the correct MCP command tokens.  This verifies the wiring intent at the
    adapter level without coupling to an installed external tool.

    Commands asserted (from real adapter source, 2026-05-30):
      claude: ['/usr/local/bin/claude', 'mcp', 'add', 'codegraph', '--',
               'npx', '-y', '@colbymchenry/codegraph', 'serve', '--mcp']
      gemini: ['/usr/local/bin/gemini', 'mcp', 'add', 'codegraph',
               'npx', '-y', '@colbymchenry/codegraph', 'serve', '--mcp']
    """

    def test_all_boilerplate_skills_present(self, plugin_root):
        """
        Every directory in src/harness/templates/boilerplate/skills/ must
        appear as a subdirectory containing SKILL.md in the minted plugin's
        skills/ directory.

        Catches any skill silently dropped during minting.
        """
        platform, root = plugin_root
        skills_dir = root / "skills"

        assert skills_dir.is_dir(), (
            f"{platform}: skills/ directory missing at {skills_dir}"
        )

        minted_skills: frozenset[str] = frozenset(
            d.name for d in skills_dir.iterdir() if d.is_dir()
        )

        # Every canonical skill must exist with its SKILL.md
        missing_dirs: list[str] = []
        missing_skill_md: list[str] = []

        for skill_name in sorted(_CANONICAL_SKILLS):
            if skill_name not in minted_skills:
                missing_dirs.append(skill_name)
            elif not (skills_dir / skill_name / "SKILL.md").exists():
                missing_skill_md.append(skill_name)

        errors: list[str] = []
        if missing_dirs:
            errors.append(
                f"Skills missing from minted skills/ ({len(missing_dirs)}):\n"
                + "\n".join(f"  - {s}" for s in missing_dirs)
            )
        if missing_skill_md:
            errors.append(
                f"Skills present but missing SKILL.md ({len(missing_skill_md)}):\n"
                + "\n".join(f"  - {s}" for s in missing_skill_md)
            )

        assert not errors, (
            f"{platform}: boilerplate skills not fully minted.\n"
            f"  canonical source: {_BOILERPLATE_SKILLS_DIR}\n"
            f"  canonical count : {len(_CANONICAL_SKILLS)}\n"
            f"  minted count    : {len(minted_skills)}\n"
            + "\n".join(errors)
        )

    def test_mcp_codegraph_registration_command(self, plugin_root, tmp_path):
        """
        configure_cli() must invoke subprocess.run with a command that registers
        the codegraph MCP server.

        Approach 2 (command assertion): patch shutil.which to return a fake CLI
        binary and capture the subprocess.run call.  Assert that the call
        contains the required tokens: 'mcp', 'add', 'codegraph', and
        '@colbymchenry/codegraph'.

        This verifies the adapter wiring at the code level, independent of
        whether the external CLI is installed on the test machine.
        """
        platform, _ = plugin_root

        from harness.adapters import get_adapter

        adapter = get_adapter(platform)
        fake_cli = _FAKE_CLI_PATH[platform]
        expected_tokens = _MCP_COMMAND_TOKENS[platform]

        captured_calls: list[list[str]] = []

        def _mock_run(cmd, **kwargs):
            captured_calls.append(list(cmd))
            return MagicMock(returncode=0)

        with (
            patch("shutil.which", return_value=fake_cli),
            patch("subprocess.run", side_effect=_mock_run),
        ):
            adapter.configure_cli(tmp_path)

        assert captured_calls, (
            f"{platform}: configure_cli() did not call subprocess.run — "
            f"no MCP registration command was issued.  "
            f"Expected a command containing: {expected_tokens}"
        )

        # Find the codegraph mcp add call among all subprocess.run calls
        mcp_codegraph_calls = [
            cmd for cmd in captured_calls
            if "mcp" in cmd and "codegraph" in cmd
        ]

        assert mcp_codegraph_calls, (
            f"{platform}: no subprocess.run call contained both 'mcp' and "
            f"'codegraph'.  All captured calls:\n"
            + "\n".join(f"  {c}" for c in captured_calls)
        )

        # Assert all required tokens appear in the command
        cmd = mcp_codegraph_calls[0]
        missing_tokens = [t for t in expected_tokens if t not in cmd]
        assert not missing_tokens, (
            f"{platform}: MCP codegraph registration command is missing "
            f"required tokens: {missing_tokens}\n"
            f"  expected tokens : {expected_tokens}\n"
            f"  actual command  : {cmd}"
        )

        # Claude registers via add-json so it can set alwaysLoad — the package
        # spec and the alwaysLoad flag live inside the JSON payload arg, not as
        # standalone argv tokens. Verify both are present and well-formed.
        if platform == "claude":
            payload = json.loads(cmd[-1])
            assert "@colbymchenry/codegraph" in payload.get("args", []), (
                f"claude: add-json payload missing codegraph package: {cmd[-1]}"
            )
            assert payload.get("alwaysLoad") is True, (
                f"claude: add-json payload must set alwaysLoad=true so codegraph "
                f"is never deferred behind Tool Search.  payload: {cmd[-1]}"
            )


# ---------------------------------------------------------------------------
# L4 — domain MCP registration across ALL platforms
# ---------------------------------------------------------------------------


class TestDomainMcpRegistrationMatrix:
    """Every supported platform registers the ``domain`` MCP server pointed at
    its own deployed root. claude/gemini register via the platform CLI;
    cursor/codex have no usable project-scope CLI so they write the project-
    local config file directly.

    Registration is asserted at the adapter level (call configure_cli with the
    CLI patched / on a tmp project), independent of an installed external tool.
    """

    def _capture_cli(self, adapter, tmp_path: Path) -> list[list[str]]:
        captured: list[list[str]] = []

        def _mock_run(cmd, **kwargs):
            captured.append(list(cmd))
            return MagicMock(returncode=0)

        with (
            patch("shutil.which", return_value="/usr/local/bin/cli"),
            patch("subprocess.run", side_effect=_mock_run),
        ):
            adapter.configure_cli(tmp_path)
        return captured

    def test_claude_registers_domain_via_add_json(self, tmp_path):
        from harness.adapters import get_adapter

        captured = self._capture_cli(get_adapter("claude"), tmp_path)
        domain_calls = [c for c in captured if "domain" in c and "mcp" in c]
        assert domain_calls, f"claude: no domain registration call: {captured}"
        cmd = domain_calls[0]
        assert "add-json" in cmd
        payload = json.loads(cmd[-1])
        assert payload["env"]["PYTHONPATH"] == ".claude/harness-wf-plugin/src"
        assert payload["env"]["DOMAIN_JSON_PATH"] == (
            ".claude/harness-wf-plugin/domain/domain.json"
        )

    def test_gemini_registers_domain_via_cli(self, tmp_path):
        from harness.adapters import get_adapter

        captured = self._capture_cli(get_adapter("gemini"), tmp_path)
        domain_calls = [c for c in captured if "domain" in c and "mcp" in c]
        assert domain_calls, f"gemini: no domain registration call: {captured}"
        cmd = domain_calls[0]
        assert "--" not in cmd  # installed gemini CLI drops args after --
        assert cmd[-3:] == ["python3", "-m", "server"]
        joined = " ".join(cmd)
        assert "PYTHONPATH=.gemini/src" in joined
        assert "DOMAIN_JSON_PATH=.gemini/domain/domain.json" in joined

    def test_cursor_writes_project_mcp_json(self, tmp_path):
        from harness.adapters import get_adapter

        get_adapter("cursor").configure_cli(tmp_path)
        data = json.loads((tmp_path / ".cursor" / "mcp.json").read_text())
        env = data["mcpServers"]["domain"]["env"]
        assert env["PYTHONPATH"] == ".cursor/src"
        assert env["DOMAIN_JSON_PATH"] == ".cursor/domain/domain.json"

    def test_codex_writes_project_config_toml(self, tmp_path):
        from harness.adapters import get_adapter

        get_adapter("codex").configure_cli(tmp_path)
        text = (tmp_path / ".codex" / "config.toml").read_text()
        assert "[mcp_servers.domain]" in text
        assert 'PYTHONPATH = ".codex/src"' in text
        assert 'DOMAIN_JSON_PATH = ".codex/domain/domain.json"' in text


# ---------------------------------------------------------------------------
# L5 (S1-T5) — Routing behavior / scenario matrix
# ---------------------------------------------------------------------------

# Discover all scenario YAML files that declare expected_behavior.
# Collected once at module-import time so pytest can parametrize properly.

_SCENARIOS_DIR: Path = (
    Path(__file__).parent.parent / "sandbox" / "scenarios"
)


def _load_all_scenarios() -> list[dict[str, Any]]:
    """Return every scenario dict from tests/sandbox/scenarios/**/*.yaml."""
    scenarios: list[dict[str, Any]] = []
    for yaml_path in sorted(_SCENARIOS_DIR.rglob("*.yaml")):
        try:
            with yaml_path.open() as fh:
                data = yaml.safe_load(fh)
            if isinstance(data, dict):
                # Attach the source path for diagnostics
                data["_yaml_path"] = str(yaml_path)
                scenarios.append(data)
        except Exception:
            pass  # malformed YAML — skip silently
    return scenarios


def _scenario_has_expectations(scenario: dict[str, Any]) -> bool:
    """True when the scenario declares at least a branch expectation."""
    eb = scenario.get("expected_behavior")
    return isinstance(eb, dict) and bool(eb.get("branch"))


_ALL_SCENARIOS: list[dict[str, Any]] = _load_all_scenarios()
_ASSERTABLE_SCENARIOS: list[dict[str, Any]] = [
    s for s in _ALL_SCENARIOS if _scenario_has_expectations(s)
]

# Scenario IDs for parametrize display (e.g. "example_routing_miss")
_SCENARIO_IDS: list[str] = [s.get("name", "unknown") for s in _ASSERTABLE_SCENARIOS]

# Known routing mismatches between declared expectations and current keyword
# classifier behavior.  Each entry: (scenario_name, reason).
# These are marked xfail(strict) so the test suite documents the gap without
# silently suppressing it.  Fix the routing classifier — not these entries.
_KNOWN_ROUTING_MISMATCHES: dict[str, str] = {
    "example_routing_miss": (
        "BUG-2: keyword classifier routes 'Rename X to Y everywhere' to branch B "
        "(default / feature) but expected_behavior declares branch D (code edit / TDD). "
        "The D-branch keyword list lacks rename/refactor patterns. "
        "Fix: extend classifier keywords before removing this xfail."
    ),
}


def _make_routing_scenario_params() -> list[Any]:
    """Build pytest.param objects for the cross-product platform × scenario."""
    params: list[Any] = []
    for platform in ("claude", "gemini"):
        for scenario in _ASSERTABLE_SCENARIOS:
            name = scenario.get("name", "unknown")
            test_id = f"{platform}-{name}"
            mismatch_reason = _KNOWN_ROUTING_MISMATCHES.get(name)
            marks = []
            if mismatch_reason:
                marks.append(
                    pytest.mark.xfail(strict=True, reason=mismatch_reason)
                )
            params.append(pytest.param(platform, scenario, id=test_id, marks=marks))
    return params


class TestRoutingScenarios:
    """L5 (S1-T5): each canned scenario routes to the expected skill+agent.

    Parametrized over ["claude", "gemini"] × assertable scenarios.  Only
    scenarios that declare expected_behavior are included.

    Determinism: query_llm is patched to None so the deterministic keyword
    classifier is always used — no LLM call, no network, reproducible results.
    """

    @pytest.mark.parametrize("platform,scenario", _make_routing_scenario_params())
    def test_routing_scenarios(
        self,
        platform: str,
        scenario: dict[str, Any],
        claude_root: Path,
        gemini_root: Path,
    ) -> None:
        """Assert that run_scenario() returns the expected branch (and agent).

        Steps:
          1. Resolve plugin_root from the session-scoped fixture.
          2. Patch query_llm → None to force deterministic keyword routing.
          3. Call run_scenario(plugin_root, scenario) → RoutingResult.
          4. Assert branch matches expected_behavior.branch.
          5. Assert agent matches expected_behavior.agent (if declared).
        """
        plugin_root = claude_root if platform == "claude" else gemini_root

        expected_behavior: dict[str, Any] = scenario["expected_behavior"]
        expected_branch: str = expected_behavior["branch"]
        expected_agent: str | None = expected_behavior.get("agent")

        import harness.runtime.dispatcher as _dispatcher_module

        with patch.object(_dispatcher_module, "query_llm", None):
            result = run_scenario(plugin_root, scenario)

        assert result.branch == expected_branch, (
            f"[{platform}] scenario={scenario.get('name')!r}: "
            f"expected branch={expected_branch!r}, got branch={result.branch!r}.\n"
            f"  prompt   : {scenario.get('prompt')!r}\n"
            f"  result   : {result}\n"
            f"  scenario : {scenario.get('_yaml_path')}"
        )

        if expected_agent is not None:
            assert result.agent == expected_agent, (
                f"[{platform}] scenario={scenario.get('name')!r}: "
                f"expected agent={expected_agent!r}, got agent={result.agent!r}.\n"
                f"  branch   : {result.branch}\n"
                f"  result   : {result}\n"
                f"  scenario : {scenario.get('_yaml_path')}"
            )
