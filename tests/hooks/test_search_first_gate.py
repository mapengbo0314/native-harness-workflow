"""Phase 4 (F4 ECC port): Search-First gate — deterministic enforcement layer.

The gate blocks source-file writes while the persisted session phase is
``planning`` until ``research_done`` is recorded (M1, R2).  It is keyed to the
persisted phase from the Phase 2 session store — NEVER to the per-prompt branch
classification, which observably flips mid-workflow.

Covers:
  - research_done set/get round-trip (hook_common helpers)
  - source write blocked while phase=planning without the flag
  - allowed once research_done is set
  - no persisted phase ⇒ passthrough (R2)
  - non-planning phase ⇒ passthrough
  - classification flip mid-phase does NOT drop the gate (R2)
  - toggle off (pipeline.dispatcher.gates.search_first=false) ⇒ passthrough
  - test-file writes and non-write tools pass through
  - no interference with the TDD gate (both fire independently)
  - end-to-end: hook process denies via exit 2 / gemini deny JSON
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)
PRE_TOOL_USE = HOOKS_DIR / "pre_tool_use.py"


@pytest.fixture(scope="module")
def hook_common():
    spec = importlib.util.spec_from_file_location(
        "hook_common_sfg_test", HOOKS_DIR / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pre_tool_use():
    """Import the hook module with hooks dir on sys.path so its
    `from hook_common import …` resolves for real."""
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("pre_tool_use_sfg_test", PRE_TOOL_USE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(HOOKS_DIR))


@pytest.fixture
def plugin_root(tmp_path):
    (tmp_path / "state").mkdir()
    return tmp_path


def _edit_input(path="src/foo.py"):
    return "Edit", {"file_path": path}


# ---------------------------------------------------------------------------
# research_done helpers (hook_common)
# ---------------------------------------------------------------------------


class TestResearchDoneHelpers:
    def test_roundtrip(self, hook_common, plugin_root):
        assert not hook_common.get_research_done(plugin_root, "s1")
        hook_common.set_research_done(plugin_root, "s1", note="waiver: well-trodden ground")
        assert hook_common.get_research_done(plugin_root, "s1")

    def test_per_session_isolation(self, hook_common, plugin_root):
        hook_common.set_research_done(plugin_root, "s1")
        assert not hook_common.get_research_done(plugin_root, "s2")

    def test_corrupt_session_file_fails_open_to_unset(self, hook_common, plugin_root):
        f = hook_common._session_file(plugin_root, "s3")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{not json")
        assert not hook_common.get_research_done(plugin_root, "s3")


# ---------------------------------------------------------------------------
# _check_search_first — gate predicate (R2: persisted phase only)
# ---------------------------------------------------------------------------


class TestSearchFirstGate:
    def test_blocked_while_planning_without_flag(self, pre_tool_use, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "s1", "planning")
        tool, tin = _edit_input()
        msg = pre_tool_use._check_search_first(tool, tin, "s1", plugin_root)
        assert msg is not None
        assert "research" in msg.lower()
        assert "search-first" in msg.lower()

    def test_allowed_once_research_done(self, pre_tool_use, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "s1", "planning")
        hook_common.set_research_done(plugin_root, "s1")
        tool, tin = _edit_input()
        assert pre_tool_use._check_search_first(tool, tin, "s1", plugin_root) is None

    def test_no_persisted_phase_passthrough(self, pre_tool_use, plugin_root):
        tool, tin = _edit_input()
        assert pre_tool_use._check_search_first(tool, tin, "s1", plugin_root) is None

    def test_non_planning_phase_passthrough(self, pre_tool_use, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "s1", "execution")
        tool, tin = _edit_input()
        assert pre_tool_use._check_search_first(tool, tin, "s1", plugin_root) is None

    def test_classification_flip_does_not_drop_gate(self, pre_tool_use, hook_common, plugin_root, monkeypatch):
        """R2: the per-prompt classifier flipping branches (B→E→C) must not
        release the gate — only the persisted phase and the flag matter."""
        hook_common.set_phase(plugin_root, "s1", "planning")
        # Simulate every advisory branch signal an environment could carry.
        monkeypatch.setenv("HARNESS_BRANCH", "E")
        monkeypatch.setenv("HARNESS_ACTIVE_BRANCH", "C")
        tool, tin = _edit_input()
        msg = pre_tool_use._check_search_first(tool, tin, "s1", plugin_root)
        assert msg is not None, "gate must hold regardless of per-prompt classification"

    def test_phase_cleared_releases_gate(self, pre_tool_use, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "s1", "planning")
        hook_common.clear_phase(plugin_root, "s1", exit_artifact="docs/design.md")
        tool, tin = _edit_input()
        assert pre_tool_use._check_search_first(tool, tin, "s1", plugin_root) is None

    def test_toggle_off_passthrough(self, pre_tool_use, hook_common, plugin_root):
        (plugin_root / "features.json").write_text(
            json.dumps({"pipeline": {"dispatcher": {"gates": {"search_first": False}}}})
        )
        hook_common.set_phase(plugin_root, "s1", "planning")
        tool, tin = _edit_input()
        assert pre_tool_use._check_search_first(tool, tin, "s1", plugin_root) is None

    def test_test_file_write_passthrough(self, pre_tool_use, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "s1", "planning")
        msg = pre_tool_use._check_search_first("Write", {"file_path": "tests/test_foo.py"}, "s1", plugin_root)
        assert msg is None

    def test_non_write_tool_passthrough(self, pre_tool_use, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "s1", "planning")
        assert pre_tool_use._check_search_first("Read", {"file_path": "src/foo.py"}, "s1", plugin_root) is None
        assert pre_tool_use._check_search_first("Bash", {"command": "ls"}, "s1", plugin_root) is None


# ---------------------------------------------------------------------------
# Coexistence with the TDD gate (independent predicates, no interference)
# ---------------------------------------------------------------------------


class TestTddCoexistence:
    def test_tdd_still_blocks_when_research_done(self, pre_tool_use, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "s1", "planning")
        hook_common.set_research_done(plugin_root, "s1")
        tool, tin = _edit_input()
        assert pre_tool_use._check_search_first(tool, tin, "s1", plugin_root) is None
        tdd = pre_tool_use._check_tdd(tool, tin, "s1", plugin_root)
        assert tdd is not None and "TDD" in tdd

    def test_search_gate_blocks_when_tdd_satisfied(self, pre_tool_use, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "s1", "planning")
        # Satisfy TDD: write a test file first.
        assert pre_tool_use._check_tdd("Write", {"file_path": "tests/test_foo.py"}, "s1", plugin_root) is None
        tool, tin = _edit_input()
        assert pre_tool_use._check_tdd(tool, tin, "s1", plugin_root) is None
        msg = pre_tool_use._check_search_first(tool, tin, "s1", plugin_root)
        assert msg is not None


# ---------------------------------------------------------------------------
# End-to-end: hook process wiring
# ---------------------------------------------------------------------------


def _run_hook(plugin_root: Path, payload: dict, gemini: bool = False):
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env["HARNESS_SESSION_ID"] = "e2e"
    return subprocess.run(
        [sys.executable, str(PRE_TOOL_USE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestHookProcessWiring:
    def test_blocked_write_exits_2(self, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "e2e", "planning")
        p = _run_hook(plugin_root, {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}})
        assert p.returncode == 2
        assert "search-first" in p.stderr.lower()

    def test_gemini_deny_json(self, hook_common, plugin_root):
        hook_common.set_phase(plugin_root, "e2e", "planning")
        p = _run_hook(plugin_root, {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}, "hook_event_name": "PreToolUse"})
        assert p.returncode == 0
        out = json.loads(p.stdout.splitlines()[-1])
        assert out.get("decision") == "deny"

    def test_passthrough_without_phase(self, plugin_root):
        p = _run_hook(plugin_root, {"tool_name": "Edit", "tool_input": {"file_path": "tests/test_foo.py"}})
        assert p.returncode == 0


# ---------------------------------------------------------------------------
# scripts/session_phase.py — the deterministic entry point skills invoke
# ---------------------------------------------------------------------------

SESSION_PHASE = HOOKS_DIR.parent / "scripts" / "session_phase.py"


def _run_phase_script(plugin_root: Path, *args):
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env["HARNESS_SESSION_ID"] = "script-test"
    return subprocess.run(
        [sys.executable, str(SESSION_PHASE), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestSessionPhaseScript:
    def test_set_phase_planning(self, hook_common, plugin_root):
        p = _run_phase_script(plugin_root, "set-phase", "planning")
        assert p.returncode == 0, p.stderr
        phase = hook_common.get_phase(plugin_root, "script-test")
        assert phase and phase["phase"] == "planning"
        assert phase.get("phase_entered_at")

    def test_clear_phase_with_artifact(self, hook_common, plugin_root):
        _run_phase_script(plugin_root, "set-phase", "planning")
        p = _run_phase_script(plugin_root, "clear-phase", "--artifact", "docs/designs/x.md")
        assert p.returncode == 0, p.stderr
        assert hook_common.get_phase(plugin_root, "script-test") is None

    def test_set_research_done(self, hook_common, plugin_root):
        p = _run_phase_script(plugin_root, "set-research-done", "--note", "waiver: known approach")
        assert p.returncode == 0, p.stderr
        assert hook_common.get_research_done(plugin_root, "script-test")

    def test_research_done_releases_live_gate(self, hook_common, plugin_root):
        """Full loop: planning phase blocks, waiver via the script releases."""
        _run_phase_script(plugin_root, "set-phase", "planning")
        env_payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
        env["HARNESS_SESSION_ID"] = "script-test"
        blocked = subprocess.run(
            [sys.executable, str(PRE_TOOL_USE)], input=json.dumps(env_payload),
            capture_output=True, text=True, env=env, timeout=30,
        )
        assert blocked.returncode == 2
        _run_phase_script(plugin_root, "set-research-done", "--note", "waiver")
        released = subprocess.run(
            [sys.executable, str(PRE_TOOL_USE)], input=json.dumps(env_payload),
            capture_output=True, text=True, env=env, timeout=30,
        )
        # search gate released; TDD gate may still apply but src write without
        # test triggers TDD, so write a test file first to isolate the search gate
        assert "search-first" not in released.stderr.lower()

    def test_unknown_subcommand_fails(self, plugin_root):
        p = _run_phase_script(plugin_root, "bogus")
        assert p.returncode != 0


# ---------------------------------------------------------------------------
# Contract: brainstorming skill produces/clears the phase (R2)
# ---------------------------------------------------------------------------

BRAINSTORM_SKILL = HOOKS_DIR.parent / "skills" / "harness-brainstorming-plans" / "SKILL.md"


class TestBrainstormingSkillPhaseContract:
    def test_skill_sets_planning_phase_on_entry(self):
        text = BRAINSTORM_SKILL.read_text(encoding="utf-8")
        assert "session_phase.py" in text, "skill must invoke the session_phase script"
        assert "set-phase planning" in text, "skill must set phase=planning on entry"

    def test_skill_clears_phase_on_signoff(self):
        text = BRAINSTORM_SKILL.read_text(encoding="utf-8")
        assert "clear-phase" in text, "skill must clear the phase at sign-off"
        assert "--artifact" in text, "phase exit must record the design doc artifact"


# ---------------------------------------------------------------------------
# Contract: search-first skill content + registration
# ---------------------------------------------------------------------------

SEARCH_FIRST_SKILL = HOOKS_DIR.parent / "skills" / "search-first" / "SKILL.md"
SKILLS_JSON = HOOKS_DIR.parent / "skills.json"


class TestSearchFirstSkillContract:
    def test_skill_exists_and_registered(self):
        assert SEARCH_FIRST_SKILL.exists(), "search-first SKILL.md must be authored"
        skills = json.loads(SKILLS_JSON.read_text(encoding="utf-8"))["skills"]
        assert "search-first" in skills
        assert skills["search-first"]["path"] == "search-first/SKILL.md"

    def test_step_one_is_proportionality_waiver(self):
        text = SEARCH_FIRST_SKILL.read_text(encoding="utf-8")
        assert "proportionality" in text.lower()
        assert "waiver" in text.lower()
        assert "set-research-done" in text, "waiver path must set research_done via session_phase.py"

    def test_adopt_extend_compose_build_matrix(self):
        text = SEARCH_FIRST_SKILL.read_text(encoding="utf-8")
        for word in ("Adopt", "Extend", "Compose", "Build"):
            assert word in text, f"decision matrix must include {word}"

    def test_post_research_depth_checkpoint(self):
        """HITL checkpoint: quick implementation (findings attached, phase
        cleared) vs full planning pipeline; matrix outcome = recommended default."""
        text = SEARCH_FIRST_SKILL.read_text(encoding="utf-8")
        assert "AskUserQuestion" in text, "depth checkpoint must be a HITL AskUserQuestion"
        assert "quick implementation" in text.lower()
        assert "full planning" in text.lower()
        assert "clear-phase" in text, "quick path must clear the planning phase to release the gate"
        assert "recommended default" in text.lower()
