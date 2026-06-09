"""S2-T6 — runtime_adapter equality-with-canonical tests.

Verifies:
(a) runtime_adapter.get_adapter(platform).format_hook_response(...) is byte-identical
    to canonical harness.adapters.get_adapter(platform).format_hook_response(...)
    for all routing branches — including the claude generalist→general-purpose remap.
(b) runtime_adapter.get_adapter(platform).get_subagent_text_call(...) is byte-identical
    to canonical output.
(c) After a fresh mint, the plugin's src/platform_adapter.py:
      - exposes a no-arg get_adapter()
      - has zero harness.* imports
(d) src/profile.py, src/runtime_adapter.py, src/platform_profiles.json are all
    present in the minted plugin.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness.adapters import get_adapter as _canonical_get_adapter
from harness.adapters.runtime_adapter import get_adapter as _runtime_get_adapter

# ---------------------------------------------------------------------------
# Routing fixtures — mirrors the drift-guard's _ROUTING_CASES
# ---------------------------------------------------------------------------

_ROUTING_CASES: list[tuple[str, dict]] = [
    (
        "both_skill_and_agent_ais_true",
        {
            "classification": "SKILL",
            "target_skill": "do-work",
            "target_agent": "@implementer",
            "agent_invokes_skill": True,
        },
    ),
    (
        "both_skill_and_agent_ais_false",
        {
            "classification": "SKILL",
            "target_skill": "do-work",
            "target_agent": "@implementer",
            "agent_invokes_skill": False,
        },
    ),
    (
        "agent_only_generalist",
        {
            "classification": "AGENT",
            "target_agent": "@generalist",
            "target_skill": None,
        },
    ),
    (
        "agent_only_named",
        {
            "classification": "AGENT",
            "target_agent": "@researcher",
            "target_skill": None,
        },
    ),
    (
        "neither",
        {
            "classification": "DIRECT",
            "target_agent": None,
            "target_skill": None,
        },
    ),
]

_SUBAGENT_CALL_CASES: list[tuple[str, str, str | None]] = [
    ("with_skill", "my-agent", "my-skill"),
    ("without_skill", "my-agent", None),
]


# ---------------------------------------------------------------------------
# (a) format_hook_response equality with canonical
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", ["claude", "gemini", "codex", "cursor"])
@pytest.mark.parametrize("routing_label,routing_decision", _ROUTING_CASES)
def test_runtime_adapter_format_hook_response_equals_canonical(
    platform: str, routing_label: str, routing_decision: dict
) -> None:
    """runtime_adapter output must be byte-identical to canonical adapter output."""
    canonical = _canonical_get_adapter(platform)
    runtime = _runtime_get_adapter(platform)

    original_prompt = "Please help me with this task."
    context_extension = "Additional context here."
    hook_event_name = "UserPromptSubmit"

    result_canonical = canonical.format_hook_response(
        original_prompt, routing_decision, context_extension, hook_event_name
    )
    result_runtime = runtime.format_hook_response(
        original_prompt, routing_decision, context_extension, hook_event_name
    )

    assert result_canonical == result_runtime, (
        f"[{platform}/{routing_label}] runtime_adapter != canonical\n"
        f"  canonical: {result_canonical}\n"
        f"  runtime:   {result_runtime}"
    )


# ---------------------------------------------------------------------------
# (b) get_subagent_text_call equality with canonical
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", ["claude", "gemini"])
@pytest.mark.parametrize("case_label,agent_name,skill_name", _SUBAGENT_CALL_CASES)
def test_runtime_adapter_get_subagent_text_call_equals_canonical(
    platform: str, case_label: str, agent_name: str, skill_name: str | None
) -> None:
    """runtime_adapter.get_subagent_text_call must match canonical adapter."""
    canonical = _canonical_get_adapter(platform)
    runtime = _runtime_get_adapter(platform)

    result_canonical = canonical.get_subagent_text_call(agent_name, skill_name)
    result_runtime = runtime.get_subagent_text_call(agent_name, skill_name)

    assert result_canonical == result_runtime, (
        f"[{platform}/{case_label}] runtime_adapter get_subagent_text_call != canonical\n"
        f"  canonical: {result_canonical!r}\n"
        f"  runtime:   {result_runtime!r}"
    )


# ---------------------------------------------------------------------------
# Claude-specific: generalist → general-purpose remap confirmed
# ---------------------------------------------------------------------------


def test_claude_generalist_remap_in_modified_prompt() -> None:
    """Claude runtime adapter must remap 'generalist' to 'general-purpose' in agent-only branch."""
    runtime = _runtime_get_adapter("claude")
    routing = {
        "classification": "AGENT",
        "target_agent": "@generalist",
        "target_skill": None,
    }
    result = runtime.format_hook_response(
        "test", routing, "", "UserPromptSubmit"
    )
    assert "general-purpose" in result["modifiedPrompt"], (
        "Claude runtime adapter: 'general-purpose' not found in modifiedPrompt — "
        "generalist remap is missing"
    )
    assert "generalist" not in result["modifiedPrompt"], (
        "Claude runtime adapter: raw 'generalist' still appears in modifiedPrompt — "
        "remap did not fully apply"
    )


def test_gemini_no_generalist_remap() -> None:
    """Gemini runtime adapter must NOT remap 'generalist' — keep it as-is."""
    runtime = _runtime_get_adapter("gemini")
    routing = {
        "classification": "AGENT",
        "target_agent": "@generalist",
        "target_skill": None,
    }
    result = runtime.format_hook_response(
        "test", routing, "", "BeforeAgent"
    )
    assert "generalist" in result["modifiedPrompt"], (
        "Gemini runtime adapter: 'generalist' not found in modifiedPrompt — "
        "unexpected remap applied"
    )
    assert "general-purpose" not in result["modifiedPrompt"], (
        "Gemini runtime adapter: 'general-purpose' appeared — claude remap leaked"
    )


# ---------------------------------------------------------------------------
# Mint-artifact tests: session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _claude_mint_root(tmp_path_factory) -> Path:
    from tests.e2e._mint_helpers import mint_platform
    tmp = tmp_path_factory.mktemp("runtime_adapter_claude")
    return mint_platform(tmp, "claude")


@pytest.fixture(scope="session")
def _gemini_mint_root(tmp_path_factory) -> Path:
    from tests.e2e._mint_helpers import mint_platform
    tmp = tmp_path_factory.mktemp("runtime_adapter_gemini")
    return mint_platform(tmp, "gemini")


@pytest.fixture(scope="session")
def _codex_mint_root(tmp_path_factory) -> Path:
    from tests.e2e._mint_helpers import mint_platform
    tmp = tmp_path_factory.mktemp("runtime_adapter_codex")
    return mint_platform(tmp, "codex")


@pytest.fixture(scope="session")
def _cursor_mint_root(tmp_path_factory) -> Path:
    from tests.e2e._mint_helpers import mint_platform
    tmp = tmp_path_factory.mktemp("runtime_adapter_cursor")
    return mint_platform(tmp, "cursor")


@pytest.fixture(
    params=["claude", "gemini"],
    scope="session",
)
def mint_plugin_root(request, _claude_mint_root, _gemini_mint_root) -> tuple[str, Path]:
    if request.param == "claude":
        return "claude", _claude_mint_root
    return "gemini", _gemini_mint_root


# ---------------------------------------------------------------------------
# (c) Minted platform_adapter.py: no-arg get_adapter() + zero harness.* imports
# ---------------------------------------------------------------------------


class TestMintedPlatformAdapter:
    """Verify the emitted platform_adapter.py in a freshly-minted plugin."""

    def test_platform_adapter_py_exists(self, mint_plugin_root: tuple[str, Path]) -> None:
        platform, root = mint_plugin_root
        pa = root / "src" / "platform_adapter.py"
        assert pa.exists(), f"{platform}: src/platform_adapter.py missing from minted plugin"

    def test_platform_adapter_has_no_arg_get_adapter(
        self, mint_plugin_root: tuple[str, Path]
    ) -> None:
        """The minted platform_adapter.py must expose a callable no-arg get_adapter()."""
        platform, root = mint_plugin_root
        pa = root / "src" / "platform_adapter.py"
        assert pa.exists(), f"{platform}: src/platform_adapter.py missing"

        # Load the module fresh from the minted src/ dir
        src_dir = str(root / "src")
        spec = importlib.util.spec_from_file_location(
            f"_minted_pa_{platform}", pa,
            submodule_search_locations=[src_dir],
        )
        mod = importlib.util.module_from_spec(spec)
        # Insert src_dir first so `from runtime_adapter import …` resolves locally
        old_path = sys.path[:]
        sys.path.insert(0, src_dir)
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path[:] = old_path

        assert hasattr(mod, "get_adapter"), (
            f"{platform}: minted platform_adapter.py has no 'get_adapter' symbol"
        )
        import inspect
        sig = inspect.signature(mod.get_adapter)
        params = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
        ]
        assert len(params) == 0, (
            f"{platform}: minted get_adapter() has required parameters: {list(sig.parameters)}"
        )

        # Call it — must return an object with format_hook_response
        adapter = mod.get_adapter()
        assert hasattr(adapter, "format_hook_response"), (
            f"{platform}: get_adapter() returned object lacking 'format_hook_response'"
        )

    def test_platform_adapter_zero_harness_imports(
        self, mint_plugin_root: tuple[str, Path]
    ) -> None:
        """The minted platform_adapter.py must contain zero harness.* imports."""
        platform, root = mint_plugin_root
        pa = root / "src" / "platform_adapter.py"
        assert pa.exists(), f"{platform}: src/platform_adapter.py missing"
        content = pa.read_text(encoding="utf-8")
        violations = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("import harness") or stripped.startswith("from harness"):
                violations.append(f"  line {lineno}: {stripped!r}")
        assert not violations, (
            f"{platform}: minted platform_adapter.py has harness.* imports:\n"
            + "\n".join(violations)
        )

    def test_platform_adapter_bakes_correct_platform(
        self, mint_plugin_root: tuple[str, Path]
    ) -> None:
        """The minted platform_adapter.py must hard-code the minted platform id."""
        platform, root = mint_plugin_root
        pa = root / "src" / "platform_adapter.py"
        assert pa.exists(), f"{platform}: src/platform_adapter.py missing"

        src_dir = str(root / "src")
        spec = importlib.util.spec_from_file_location(
            f"_minted_pa_plat_{platform}", pa,
            submodule_search_locations=[src_dir],
        )
        mod = importlib.util.module_from_spec(spec)
        old_path = sys.path[:]
        sys.path.insert(0, src_dir)
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path[:] = old_path

        adapter = mod.get_adapter()
        assert adapter.get_platform_name() == platform, (
            f"{platform}: minted get_adapter().get_platform_name() returned "
            f"{adapter.get_platform_name()!r}, expected {platform!r}"
        )


# ---------------------------------------------------------------------------
# (d) Required runtime slice files present in minted src/
# ---------------------------------------------------------------------------


class TestMintedRuntimeSliceFiles:
    """Verify runtime_adapter.py, profile.py, platform_profiles.json land in src/."""

    def test_runtime_adapter_py_present(self, mint_plugin_root: tuple[str, Path]) -> None:
        platform, root = mint_plugin_root
        f = root / "src" / "runtime_adapter.py"
        assert f.exists(), f"{platform}: src/runtime_adapter.py missing from minted plugin"

    def test_profile_py_present(self, mint_plugin_root: tuple[str, Path]) -> None:
        platform, root = mint_plugin_root
        f = root / "src" / "profile.py"
        assert f.exists(), f"{platform}: src/profile.py missing from minted plugin"

    def test_platform_profiles_json_present(self, mint_plugin_root: tuple[str, Path]) -> None:
        platform, root = mint_plugin_root
        f = root / "src" / "platform_profiles.json"
        assert f.exists(), f"{platform}: src/platform_profiles.json missing from minted plugin"

    def test_platform_profiles_json_valid(self, mint_plugin_root: tuple[str, Path]) -> None:
        platform, root = mint_plugin_root
        f = root / "src" / "platform_profiles.json"
        assert f.exists(), f"{platform}: src/platform_profiles.json missing"
        content = f.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{platform}: src/platform_profiles.json is invalid JSON: {exc}")
        assert platform in data, (
            f"{platform}: platform_profiles.json does not contain key {platform!r}"
        )

    def test_runtime_adapter_py_zero_harness_imports(
        self, mint_plugin_root: tuple[str, Path]
    ) -> None:
        """Copied runtime_adapter.py must have no harness.* imports."""
        platform, root = mint_plugin_root
        f = root / "src" / "runtime_adapter.py"
        assert f.exists(), f"{platform}: src/runtime_adapter.py missing"
        content = f.read_text(encoding="utf-8")
        violations = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("import harness") or stripped.startswith("from harness"):
                violations.append(f"  line {lineno}: {stripped!r}")
        assert not violations, (
            f"{platform}: minted runtime_adapter.py has harness.* imports — "
            f"import-rewrite pass missed it:\n" + "\n".join(violations)
        )

    def test_profile_py_zero_harness_imports(
        self, mint_plugin_root: tuple[str, Path]
    ) -> None:
        """Copied profile.py must have no harness.* imports (it was already standalone)."""
        platform, root = mint_plugin_root
        f = root / "src" / "profile.py"
        assert f.exists(), f"{platform}: src/profile.py missing"
        content = f.read_text(encoding="utf-8")
        violations = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("import harness") or stripped.startswith("from harness"):
                violations.append(f"  line {lineno}: {stripped!r}")
        assert not violations, (
            f"{platform}: minted profile.py has harness.* imports:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# (e) Minted get_adapter() output equals canonical for the minted platform
# ---------------------------------------------------------------------------


class TestMintedAdapterEquality:
    """The minted no-arg get_adapter() output must equal the canonical adapter."""

    def _load_minted_adapter(self, root: Path, platform: str):
        """Load minted platform_adapter module and return get_adapter() result."""
        pa = root / "src" / "platform_adapter.py"
        src_dir = str(root / "src")
        spec = importlib.util.spec_from_file_location(
            f"_minted_pa_eq_{platform}_{id(root)}", pa,
            submodule_search_locations=[src_dir],
        )
        mod = importlib.util.module_from_spec(spec)
        old_path = sys.path[:]
        sys.path.insert(0, src_dir)
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path[:] = old_path
        return mod.get_adapter()

    @pytest.mark.parametrize("routing_label,routing_decision", _ROUTING_CASES)
    def test_claude_minted_adapter_format_hook_response(
        self, routing_label: str, routing_decision: dict, _claude_mint_root: Path
    ) -> None:
        """Minted claude get_adapter().format_hook_response equals canonical."""
        minted = self._load_minted_adapter(_claude_mint_root, "claude")
        canonical = _canonical_get_adapter("claude")
        r_minted = minted.format_hook_response(
            "test prompt", routing_decision, "ctx", "UserPromptSubmit"
        )
        r_canonical = canonical.format_hook_response(
            "test prompt", routing_decision, "ctx", "UserPromptSubmit"
        )
        assert r_minted == r_canonical, (
            f"[claude/{routing_label}] minted adapter != canonical\n"
            f"  canonical: {r_canonical}\n"
            f"  minted:    {r_minted}"
        )

    @pytest.mark.parametrize("routing_label,routing_decision", _ROUTING_CASES)
    def test_gemini_minted_adapter_format_hook_response(
        self, routing_label: str, routing_decision: dict, _gemini_mint_root: Path
    ) -> None:
        """Minted gemini get_adapter().format_hook_response equals canonical."""
        minted = self._load_minted_adapter(_gemini_mint_root, "gemini")
        canonical = _canonical_get_adapter("gemini")
        r_minted = minted.format_hook_response(
            "test prompt", routing_decision, "ctx", "UserPromptSubmit"
        )
        r_canonical = canonical.format_hook_response(
            "test prompt", routing_decision, "ctx", "UserPromptSubmit"
        )
        assert r_minted == r_canonical, (
            f"[gemini/{routing_label}] minted adapter != canonical\n"
            f"  canonical: {r_canonical}\n"
            f"  minted:    {r_minted}"
        )

    @pytest.mark.parametrize("routing_label,routing_decision", _ROUTING_CASES)
    def test_codex_minted_adapter_format_hook_response(
        self, routing_label: str, routing_decision: dict, _codex_mint_root: Path
    ) -> None:
        """Minted codex get_adapter().format_hook_response equals canonical and
        emits only Codex-valid (deny_unknown_fields) hook output."""
        minted = self._load_minted_adapter(_codex_mint_root, "codex")
        canonical = _canonical_get_adapter("codex")
        r_minted = minted.format_hook_response(
            "test prompt", routing_decision, "ctx", "UserPromptSubmit"
        )
        r_canonical = canonical.format_hook_response(
            "test prompt", routing_decision, "ctx", "UserPromptSubmit"
        )
        assert r_minted == r_canonical, (
            f"[codex/{routing_label}] minted adapter != canonical\n"
            f"  canonical: {r_canonical}\n"
            f"  minted:    {r_minted}"
        )
        # Codex schema guard: no invented fields survive into the minted output.
        assert set(r_minted).issubset(
            {"continue", "systemMessage", "decision", "reason", "hookSpecificOutput"}
        )
        assert set(r_minted["hookSpecificOutput"]).issubset(
            {"hookEventName", "additionalContext"}
        )

    @pytest.mark.parametrize("routing_label,routing_decision", _ROUTING_CASES)
    def test_cursor_minted_adapter_format_hook_response(
        self, routing_label: str, routing_decision: dict, _cursor_mint_root: Path
    ) -> None:
        """Minted cursor get_adapter().format_hook_response equals canonical and
        emits only Cursor-valid hook output (per-turn routing is OFF for Cursor:
        beforeSubmitPrompt can only return {continue, user_message})."""
        minted = self._load_minted_adapter(_cursor_mint_root, "cursor")
        canonical = _canonical_get_adapter("cursor")
        r_minted = minted.format_hook_response(
            "test prompt", routing_decision, "ctx", "UserPromptSubmit"
        )
        r_canonical = canonical.format_hook_response(
            "test prompt", routing_decision, "ctx", "UserPromptSubmit"
        )
        assert r_minted == r_canonical, (
            f"[cursor/{routing_label}] minted adapter != canonical\n"
            f"  canonical: {r_canonical}\n"
            f"  minted:    {r_minted}"
        )
        # Cursor schema guard: only {continue, user_message}; no routing fields.
        assert set(r_minted).issubset({"continue", "user_message"})
        assert "modifiedPrompt" not in r_minted
        assert "hookSpecificOutput" not in r_minted
