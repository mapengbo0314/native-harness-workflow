"""Golden tests for per-platform standalone adapters and copy_runtime_modules.

Covers:
1. Each platform adapter's identity methods return the correct values.
2. format_hook_response produces the correct platform-specific output for every
   routing scenario (skill+agent, agent-only, no target).
3. copy_runtime_modules deploys only the selected platform's adapter — no
   multi-platform dispatch table, no harness.* imports in any generated file.
4. The generated platform_adapter.py is importable standalone (simulating a user
   environment with no harness package installed) and get_adapter() returns the
   correct adapter with no arguments.
5. prompt_classifier.py template has no _detect_platform and calls get_adapter()
   with no arguments.
"""

import importlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
RUNTIME_SRC = REPO_ROOT / "src" / "harness" / "runtime"

PLATFORMS = ["claude", "gemini", "codex", "cursor", "generic"]

SKILL_AGENT_DECISION = {
    "classification": "A",
    "target_skill": "harness-systematic-debugging",
    "target_agent": "@debugger",
    "agent_invokes_skill": True,
}

AGENT_ONLY_DECISION = {
    "classification": "C",
    "target_skill": None,
    "target_agent": "@generalist",
    "agent_invokes_skill": False,
}

NO_TARGET_DECISION = {
    "classification": "E",
    "target_skill": None,
    "target_agent": None,
    "agent_invokes_skill": False,
}

CONTEXT_EXT = "=== SYSTEM STATE ==="
HOOK_EVENT = "UserPromptSubmit"
PROMPT = "fix the login bug"


def _load_standalone(path: Path, module_name: str):
    """Load a .py file in a fully isolated namespace — no sys.path pollution."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_deployed_adapter(src_dir: Path):
    """Load the platform_adapter.py that was deployed into src_dir.

    The minted platform_adapter.py is a shim that imports from runtime_adapter,
    which lives in the same src_dir.  We temporarily add src_dir to sys.path so
    the relative import resolves, then restore sys.path.
    """
    src_dir_str = str(src_dir)
    old_path = sys.path[:]
    sys.path.insert(0, src_dir_str)
    try:
        return _load_standalone(src_dir / "platform_adapter.py", "deployed_platform_adapter")
    finally:
        sys.modules.pop("runtime_adapter", None)
        sys.modules.pop("profile", None)
        sys.path[:] = old_path


# ---------------------------------------------------------------------------
# 1. Per-platform source adapter identity
# ---------------------------------------------------------------------------

class TestAdapterIdentity:
    @pytest.mark.parametrize("platform,expected_name,expected_cfg,expected_env", [
        ("claude",  "claude",  ".claude",  "CLAUDE_PLUGIN_ROOT"),
        ("gemini",  "gemini",  ".gemini",  "GEMINI_PLUGIN_ROOT"),
        ("codex",   "codex",   ".codex",   "CODEX_PLUGIN_ROOT"),
        ("cursor",  "cursor",  ".cursor",  "CURSOR_PLUGIN_ROOT"),
        ("generic", "agents",  ".agents",  "AGENTS_PLUGIN_ROOT"),
    ])
    def test_identity_methods(self, platform, expected_name, expected_cfg, expected_env):
        from harness.adapters.runtime_adapter import get_adapter
        adapter = get_adapter(platform)
        assert adapter.get_platform_name() == expected_name
        assert adapter.get_config_dir_name() == expected_cfg
        assert adapter.get_plugin_env_var_name() == expected_env


# ---------------------------------------------------------------------------
# 2. format_hook_response — platform-specific dispatch syntax
# ---------------------------------------------------------------------------

class TestFormatHookResponse:
    def _adapter(self, platform):
        from harness.adapters.runtime_adapter import get_adapter
        return get_adapter(platform)

    # Claude ----------------------------------------------------------------

    def test_claude_skill_and_agent(self):
        out = self._adapter("claude").format_hook_response(
            PROMPT, SKILL_AGENT_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        mp = out["modifiedPrompt"]
        assert 'Skill("harness-systematic-debugging")' in mp
        assert 'Task(subagent_type="debugger"' in mp
        assert "Invoke Skill('harness-systematic-debugging')" in mp
        assert out["target_agent"] == "@debugger"
        assert out["target_skill"] == "harness-systematic-debugging"
        assert out["hookSpecificOutput"]["systemPromptExtension"] == CONTEXT_EXT

    def test_claude_agent_only(self):
        out = self._adapter("claude").format_hook_response(
            PROMPT, AGENT_ONLY_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        mp = out["modifiedPrompt"]
        assert 'Task(subagent_type="general-purpose"' in mp
        assert "Skill(" not in mp

    def test_claude_generalist_renamed_to_general_purpose(self):
        decision = {**AGENT_ONLY_DECISION, "target_agent": "@generalist"}
        out = self._adapter("claude").format_hook_response(PROMPT, decision, "", HOOK_EVENT)
        assert "general-purpose" in out["modifiedPrompt"]
        assert "generalist" not in out["modifiedPrompt"]

    def test_claude_no_target_passthrough(self):
        out = self._adapter("claude").format_hook_response(
            PROMPT, NO_TARGET_DECISION, "", HOOK_EVENT
        )
        assert out["modifiedPrompt"] == PROMPT

    # Gemini ----------------------------------------------------------------

    def test_gemini_skill_and_agent(self):
        out = self._adapter("gemini").format_hook_response(
            PROMPT, SKILL_AGENT_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        mp = out["modifiedPrompt"]
        assert "activate_skill(" in mp
        assert "@debugger" in mp
        assert "Skill(" not in mp
        assert "Task(" not in mp

    def test_gemini_agent_only(self):
        out = self._adapter("gemini").format_hook_response(
            PROMPT, AGENT_ONLY_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        mp = out["modifiedPrompt"]
        assert "@generalist" in mp
        assert "activate_skill(" not in mp

    def test_gemini_no_target_passthrough(self):
        out = self._adapter("gemini").format_hook_response(
            PROMPT, NO_TARGET_DECISION, "", HOOK_EVENT
        )
        assert out["modifiedPrompt"] == PROMPT

    # Codex -----------------------------------------------------------------

    def test_codex_uses_handoff_syntax(self):
        out = self._adapter("codex").format_hook_response(
            PROMPT, SKILL_AGENT_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        mp = out["modifiedPrompt"]
        assert "Hand off to" in mp
        assert "Skill(" not in mp
        assert "Task(" not in mp

    def test_codex_no_target_passthrough(self):
        out = self._adapter("codex").format_hook_response(
            PROMPT, NO_TARGET_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        assert out["modifiedPrompt"] == PROMPT

    # Cursor ----------------------------------------------------------------

    def test_cursor_agent_only(self):
        decision = {**AGENT_ONLY_DECISION, "target_agent": "@planner"}
        out = self._adapter("cursor").format_hook_response(
            PROMPT, decision, "", HOOK_EVENT
        )
        mp = out["modifiedPrompt"]
        assert "@planner" in mp
        assert "HARNESS DISPATCH" in mp

    def test_cursor_no_target_passthrough(self):
        out = self._adapter("cursor").format_hook_response(
            PROMPT, NO_TARGET_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        assert out["modifiedPrompt"] == PROMPT

    # Generic ---------------------------------------------------------------

    def test_generic_skill_and_agent(self):
        out = self._adapter("generic").format_hook_response(
            PROMPT, SKILL_AGENT_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        mp = out["modifiedPrompt"]
        assert "Use harness-systematic-debugging" in mp
        assert "@debugger" in mp
        assert "HARNESS DISPATCH" in mp

    # Shared output shape ---------------------------------------------------

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_output_always_has_required_keys(self, platform):
        out = self._adapter(platform).format_hook_response(
            PROMPT, SKILL_AGENT_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        assert "classification" in out
        assert "modifiedPrompt" in out
        assert "hookSpecificOutput" in out
        hso = out["hookSpecificOutput"]
        assert "hookEventName" in hso
        assert "systemPromptExtension" in hso
        assert "modifiedPrompt" in hso

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_classification_preserved(self, platform):
        out = self._adapter(platform).format_hook_response(
            PROMPT, SKILL_AGENT_DECISION, CONTEXT_EXT, HOOK_EVENT
        )
        assert out["classification"] == "A"


# ---------------------------------------------------------------------------
# 3. copy_runtime_modules deploys the right per-platform adapter
# ---------------------------------------------------------------------------

class TestCopyRuntimeModules:
    @pytest.fixture(autouse=True)
    def _import(self):
        from harness.init.minting_engine import copy_runtime_modules
        self.copy_runtime_modules = copy_runtime_modules

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_deploys_correct_platform_name(self, platform, tmp_path):
        self.copy_runtime_modules(tmp_path, platform_id=platform)
        mod = _get_deployed_adapter(tmp_path / "src")
        expected = {
            "claude": "claude", "gemini": "gemini", "codex": "codex",
            "cursor": "cursor", "generic": "agents",
        }[platform]
        assert mod.get_adapter().get_platform_name() == expected

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_deployed_adapter_contains_only_one_platform(self, platform, tmp_path):
        self.copy_runtime_modules(tmp_path, platform_id=platform)
        text = (tmp_path / "src" / "platform_adapter.py").read_text()
        other_platforms = {
            "claude": ["gemini", "codex", "cursor"],
            "gemini": ["claude", "codex", "cursor"],
            "codex":  ["claude", "gemini", "cursor"],
            "cursor": ["claude", "gemini", "codex"],
            "generic": ["claude", "gemini", "codex", "cursor"],
        }[platform]
        for other in other_platforms:
            # The file must not contain another platform's identity string
            assert f'return "{other}"' not in text, (
                f"platform_adapter.py for {platform!r} leaks identity of {other!r}"
            )

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_no_harness_imports_in_generated_src(self, platform, tmp_path):
        self.copy_runtime_modules(tmp_path, platform_id=platform)
        src_dir = tmp_path / "src"
        violations = []
        for py_file in src_dir.glob("*.py"):
            for line in py_file.read_text().splitlines():
                stripped = line.lstrip()
                if not (stripped.startswith("import ") or stripped.startswith("from ")):
                    continue
                if "harness.runtime" in stripped or "harness.init" in stripped or "harness.adapters" in stripped:
                    violations.append(f"{py_file.name}: {line.strip()}")
        assert not violations, "harness.* imports found in deployed src/:\n" + "\n".join(violations)

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_required_modules_present(self, platform, tmp_path):
        self.copy_runtime_modules(tmp_path, platform_id=platform)
        src_dir = tmp_path / "src"
        required = [
            "dispatcher.py", "llm_client.py", "context_builder.py",
            "langfuse_compat.py", "langfuse_instrumentation.py",
            "platform_adapter.py", "discovery_engine.py",
            "runtime_adapter.py", "profile.py", "platform_profiles.json"
        ]
        for name in required:
            assert (src_dir / name).exists(), f"{name} missing from generated src/"

    def test_unknown_platform_falls_back_to_generic(self, tmp_path):
        self.copy_runtime_modules(tmp_path, platform_id="unknown_xyz")
        mod = _get_deployed_adapter(tmp_path / "src")
        assert mod.get_adapter().get_platform_name() == "agents"

    def test_default_platform_is_generic(self, tmp_path):
        self.copy_runtime_modules(tmp_path)
        mod = _get_deployed_adapter(tmp_path / "src")
        assert mod.get_adapter().get_platform_name() == "agents"


# ---------------------------------------------------------------------------
# 4. Standalone importability — simulates a user env with no harness installed
# ---------------------------------------------------------------------------

class TestStandaloneImportability:
    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_deployed_src_importable_without_harness(self, platform, tmp_path):
        """Subprocess with harness removed from sys.path must still import all src modules."""
        from harness.init.minting_engine import copy_runtime_modules
        copy_runtime_modules(tmp_path, platform_id=platform)
        src_dir = str(tmp_path / "src")

        script = (
            "import sys\n"
            f"sys.path = [p for p in sys.path if 'harness' not in p and 'e-2-g' not in p]\n"
            f"sys.path.insert(0, {src_dir!r})\n"
            "from platform_adapter import get_adapter\n"
            "from context_builder import build_context\n"
            "a = get_adapter()\n"
            "assert hasattr(a, 'format_hook_response'), 'missing method'\n"
            "assert hasattr(a, 'get_platform_name'), 'missing method'\n"
            "print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"Standalone import failed for {platform!r}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "OK" in result.stdout

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_get_adapter_no_args_in_subprocess(self, platform, tmp_path):
        """get_adapter() must accept zero arguments in the deployed module."""
        from harness.init.minting_engine import copy_runtime_modules
        copy_runtime_modules(tmp_path, platform_id=platform)
        src_dir = str(tmp_path / "src")

        script = (
            "import sys\n"
            f"sys.path.insert(0, {src_dir!r})\n"
            "from platform_adapter import get_adapter\n"
            "import inspect\n"
            "sig = inspect.signature(get_adapter)\n"
            "required = [p for p in sig.parameters.values() if p.default is inspect.Parameter.empty]\n"
            "assert len(required) == 0, f'get_adapter has required args: {required}'\n"
            "a = get_adapter()\n"
            "assert a is not None\n"
            "print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"get_adapter() arg check failed for {platform!r}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# 5. prompt_classifier.py template contract
# ---------------------------------------------------------------------------

class TestPromptClassifierTemplate:
    @pytest.fixture(autouse=True)
    def _load_template(self):
        self.template = (
            REPO_ROOT / "src" / "harness" / "templates" / "boilerplate"
            / "hooks" / "prompt_classifier.py"
        ).read_text()

    def test_no_detect_platform_function(self):
        assert "_detect_platform" not in self.template, (
            "prompt_classifier.py must not contain _detect_platform — "
            "platform is baked in at mint time"
        )

    def test_no_harness_imports(self):
        for line in self.template.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            assert "from harness." not in stripped, f"harness import found: {line!r}"
            assert "import harness." not in stripped, f"harness import found: {line!r}"

    def test_get_adapter_called_with_no_args(self):
        assert "get_adapter()" in self.template, (
            "prompt_classifier.py must call get_adapter() with no arguments"
        )
        assert "get_adapter(platform" not in self.template, (
            "prompt_classifier.py must not pass a platform_id arg to get_adapter"
        )

    def test_uses_platform_adapter_import(self):
        assert "from platform_adapter import get_adapter" in self.template

    def test_bootstrap_env_defined_before_langfuse_import(self):
        lines = self.template.splitlines()
        bootstrap_line = next(
            (i for i, l in enumerate(lines) if "_bootstrap_env()" in l and not l.lstrip().startswith("#")), None
        )
        langfuse_line = next(
            (i for i, l in enumerate(lines) if "from langfuse import" in l), None
        )
        assert bootstrap_line is not None, "prompt_classifier.py must call _bootstrap_env()"
        assert langfuse_line is not None, "prompt_classifier.py must import langfuse"
        assert bootstrap_line < langfuse_line, (
            f"_bootstrap_env() (line {bootstrap_line}) must run before "
            f"'from langfuse import' (line {langfuse_line})"
        )

    def test_bootstrap_loads_both_env_files(self):
        assert '".env"' in self.template or "/ \".env\"" in self.template or '/ ".env"' in self.template
        assert ".env.telemetry-harness" in self.template

    def test_no_harness_imports_in_bootstrap(self):
        in_bootstrap = False
        for line in self.template.splitlines():
            if "_bootstrap_env" in line and "def " in line:
                in_bootstrap = True
            elif in_bootstrap and line and not line.startswith(" ") and not line.startswith("\t"):
                in_bootstrap = False
            if in_bootstrap:
                stripped = line.lstrip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    assert "harness." not in stripped, (
                        f"_bootstrap_env must not import harness.*: {line!r}"
                    )
