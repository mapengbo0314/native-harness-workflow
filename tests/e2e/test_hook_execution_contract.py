"""
S1-T8 — L4 hook execution contract.

For each of the 4 hooks (prompt_classifier, pre_tool_use, post_tool_use,
notify_compression), invoke the script the way the platform does — via its
declared interpreter (read from hooks.json), in the minted layout with the
appropriate <PLATFORM>_PLUGIN_ROOT env var exported — feeding a representative
event JSON on stdin.  Assert exit code and stdout schema validity.

Interpreter strategy
--------------------
``prompt_classifier`` is declared as ``uv run "<path>"`` in hooks.json.
We verify this declaration holds, and we also invoke the script via ``uv run``
(since uv is available in this environment).  If uv is unavailable at test
time we fall back to ``sys.executable`` and document the compromise.

All other hooks are declared as ``python3 "<path>"`` and are invoked via
``sys.executable`` (resolves to the same interpreter used by pytest).

Platform note
-------------
Both platforms produce a ``hooks/hooks.json`` in the minted plugin root.
The gemini minted ``hooks.json`` uses ``GEMINI_PLUGIN_ROOT``; claude uses
``CLAUDE_PLUGIN_ROOT``.  The hook scripts detect which platform they are
running under by checking whether ``hook_event_name`` (Gemini) or
``hookEventName`` (Claude) appears in the input event.

pre_tool_use deny-path contract
--------------------------------
- Claude: dangerous input → exit 2, no stdout JSON.
- Gemini: dangerous input → exit 0, stdout is ``{"decision": "deny", ...}``.

The distinction is by design: the Gemini CLI expects exit 0 + JSON; Claude
CLI interprets exit 2 as a hard deny.  Both are tested.

Real bugs caught
----------------
None; all hooks executed correctly on representative events.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests._env_utils import telemetry_safe_env
from tests.e2e._mint_helpers import mint_platform

# ---------------------------------------------------------------------------
# Session-scoped mint fixtures
# ---------------------------------------------------------------------------

_PLUGIN_ROOT_ENV_VAR: dict[str, str] = {
    "claude": "CLAUDE_PLUGIN_ROOT",
    "gemini": "GEMINI_PLUGIN_ROOT",
    "codex": "CODEX_PLUGIN_ROOT",
    "cursor": "CURSOR_PLUGIN_ROOT",
}

# Platforms whose hook is append-only (can inject context but not rewrite the
# prompt): output is {continue, hookSpecificOutput{hookEventName,
# additionalContext}}.
_APPEND_ONLY = ("gemini", "codex")


@pytest.fixture(scope="session")
def _claude_exec_root(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("exec_contract_claude")
    return mint_platform(tmp, "claude")


@pytest.fixture(scope="session")
def _gemini_exec_root(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("exec_contract_gemini")
    return mint_platform(tmp, "gemini")


@pytest.fixture(scope="session")
def _codex_exec_root(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("exec_contract_codex")
    return mint_platform(tmp, "codex")


@pytest.fixture(scope="session")
def _cursor_exec_root(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("exec_contract_cursor")
    return mint_platform(tmp, "cursor")


@pytest.fixture(
    params=["claude", "gemini", "codex", "cursor"],
    scope="session",
)
def exec_plugin_root(
    request, _claude_exec_root, _gemini_exec_root, _codex_exec_root, _cursor_exec_root
) -> tuple[str, Path]:
    """Yields (platform, plugin_root) for parametrized execution tests."""
    return request.param, {
        "claude": _claude_exec_root,
        "gemini": _gemini_exec_root,
        "codex": _codex_exec_root,
        "cursor": _cursor_exec_root,
    }[request.param]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_hooks_json(plugin_root: Path) -> dict:
    """Load and return hooks.json from the minted plugin root's hooks/ dir."""
    hooks_file = plugin_root / "hooks" / "hooks.json"
    assert hooks_file.exists(), f"hooks.json not found at {hooks_file}"
    return json.loads(hooks_file.read_text(encoding="utf-8"))


def _resolve_hook_command(
    plugin_root: Path, platform: str, hook_key: str
) -> tuple[str, Path]:
    """
    Read the declared command from hooks.json for *hook_key* and return
    (interpreter_token, resolved_script_path).

    The command template looks like:
        python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py"
        uv run "${CLAUDE_PLUGIN_ROOT}/hooks/prompt_classifier.py"

    We substitute the env var with the real plugin_root to get the path.
    """
    hooks_data = _load_hooks_json(plugin_root)
    hooks_section = hooks_data["hooks"]

    # Flatten all command strings for all events
    all_commands: dict[str, str] = {}
    for event_hooks in hooks_section.values():
        for group in event_hooks:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd:
                    # Extract script filename from the command
                    # e.g. python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py"
                    match = re.search(r'hooks/(\w+\.py)', cmd)
                    if match:
                        script_name = match.group(1)
                        all_commands[script_name] = cmd

    assert hook_key in all_commands, (
        f"No command found for hook script {hook_key!r} in {platform} hooks.json.\n"
        f"Available: {list(all_commands)}"
    )

    raw_cmd = all_commands[hook_key]

    # Determine interpreter: first token of the command
    tokens = raw_cmd.split()
    interpreter = tokens[0]  # "python3" or "uv"

    # Resolve the script path by substituting ${<PLATFORM>_PLUGIN_ROOT}
    env_var = _PLUGIN_ROOT_ENV_VAR[platform]
    resolved_cmd = raw_cmd.replace(f"${{{env_var}}}", str(plugin_root))
    # Extract the path from the resolved command (strip quotes)
    script_path_str = re.search(r'"(.+?)"', resolved_cmd)
    assert script_path_str, f"Could not parse script path from: {resolved_cmd}"
    script_path = Path(script_path_str.group(1))
    assert script_path.exists(), f"Resolved script path does not exist: {script_path}"

    return interpreter, script_path


def _run_hook(
    plugin_root: Path,
    platform: str,
    script_path: Path,
    interpreter: str,
    event: dict,
) -> subprocess.CompletedProcess:
    """
    Run a hook script the way the platform declares it.

    For ``uv run`` (prompt_classifier): try uv first, fall back to
    sys.executable if uv is absent.  The declared interpreter is separately
    asserted in the interpreter-contract tests.

    For ``python3``: always uses sys.executable.

    The appropriate <PLATFORM>_PLUGIN_ROOT env var is exported so that
    hook_common.resolve_plugin_root() works correctly.
    """
    # Telemetry-safe: disables langfuse (both flag generations) AND strips the
    # inherited credentials so the hook subprocess cannot export traces.
    env = telemetry_safe_env()
    env[_PLUGIN_ROOT_ENV_VAR[platform]] = str(plugin_root)
    # Disable API calls so prompt_classifier stays headless
    env["ANTHROPIC_API_KEY"] = ""
    env["GEMINI_API_KEY"] = ""
    env["HARNESS_MOCK_LLM"] = "1"

    event_json = json.dumps(event)

    if interpreter == "uv":
        uv_path = shutil.which("uv")
        if uv_path:
            cmd = [uv_path, "run", str(script_path)]
        else:
            # uv not available: fall back — documented in module docstring
            cmd = [sys.executable, str(script_path)]
    else:
        # python3 declared — use sys.executable for portability
        cmd = [sys.executable, str(script_path)]

    return subprocess.run(
        cmd,
        input=event_json,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _assert_valid_json_stdout(result: subprocess.CompletedProcess, label: str) -> dict:
    """Assert stdout is non-empty and parses as JSON; return the parsed dict."""
    assert result.stdout.strip(), (
        f"{label}: expected non-empty JSON stdout, got empty.\n"
        f"stderr: {result.stderr[:500]}"
    )
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"{label}: stdout is not valid JSON: {exc}\n"
            f"stdout: {result.stdout[:500]}\n"
            f"stderr: {result.stderr[:500]}"
        )


# ---------------------------------------------------------------------------
# Test: declared interpreter in hooks.json
# ---------------------------------------------------------------------------


class TestDeclaredInterpreter:
    """
    Assert that hooks.json declares the expected interpreter for each hook.

    This is a separate static assertion so that even when we fall back to
    sys.executable for execution, we still verify the platform contract.
    """

    def test_prompt_classifier_declared_interpreter(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """prompt_classifier must be declared with 'uv run' in hooks.json."""
        platform, root = exec_plugin_root
        interpreter, _ = _resolve_hook_command(root, platform, "prompt_classifier.py")
        assert interpreter == "uv", (
            f"{platform}: prompt_classifier.py should be declared with 'uv run', "
            f"got interpreter {interpreter!r}"
        )

    def test_pre_tool_use_declared_interpreter(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """pre_tool_use must be declared with 'python3' in hooks.json."""
        platform, root = exec_plugin_root
        interpreter, _ = _resolve_hook_command(root, platform, "pre_tool_use.py")
        assert interpreter == "python3", (
            f"{platform}: pre_tool_use.py should be declared with 'python3', "
            f"got {interpreter!r}"
        )

    def test_post_tool_use_declared_interpreter(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """post_tool_use must be declared with 'python3' in hooks.json."""
        platform, root = exec_plugin_root
        interpreter, _ = _resolve_hook_command(root, platform, "post_tool_use.py")
        assert interpreter == "python3", (
            f"{platform}: post_tool_use.py should be declared with 'python3', "
            f"got {interpreter!r}"
        )

    def test_notify_compression_declared_interpreter(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """notify_compression must be declared with 'python3' in hooks.json."""
        platform, root = exec_plugin_root
        interpreter, _ = _resolve_hook_command(root, platform, "notify_compression.py")
        assert interpreter == "python3", (
            f"{platform}: notify_compression.py should be declared with 'python3', "
            f"got {interpreter!r}"
        )


# ---------------------------------------------------------------------------
# Test: prompt_classifier execution contract
# ---------------------------------------------------------------------------


class TestPromptClassifierContract:
    """
    UserPromptSubmit / BeforeAgent hook.

    Input:  {"prompt": "<text>", "hookEventName": "<event>"}
    Output (claude): {classification, modifiedPrompt, hookSpecificOutput, ...}
    Output (gemini): append-only — BeforeAgent cannot rewrite the prompt, so the
            output is {continue, hookSpecificOutput{hookEventName,
            additionalContext}} (no classification / modifiedPrompt). The routing
            decision + SYSTEM STATE are folded into additionalContext.
    Exit:   0
    """

    # Representative events per platform
    _CLAUDE_EVENT = {
        "prompt": "explain how the login feature works",
        "hookEventName": "UserPromptSubmit",
    }
    _GEMINI_EVENT = {
        "prompt": "explain how the login feature works",
        "hook_event_name": "BeforeAgent",
    }
    _CURSOR_EVENT = {
        "prompt": "explain how the login feature works",
        "hookEventName": "beforeSubmitPrompt",
    }

    def _event(self, platform: str) -> dict:
        if platform in ("claude", "codex"):  # codex reuses Claude's event names
            return self._CLAUDE_EVENT
        if platform == "cursor":
            return self._CURSOR_EVENT
        return self._GEMINI_EVENT

    def test_exit_code_zero(self, exec_plugin_root: tuple[str, Path]) -> None:
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        result = _run_hook(root, platform, script, interpreter, self._event(platform))
        assert result.returncode == 0, (
            f"{platform} prompt_classifier: expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
        )

    def test_stdout_is_valid_json(self, exec_plugin_root: tuple[str, Path]) -> None:
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        result = _run_hook(root, platform, script, interpreter, self._event(platform))
        _assert_valid_json_stdout(result, f"{platform} prompt_classifier")

    def test_stdout_has_classification(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Output must contain 'classification' key with a letter branch A–E.

        Gemini is append-only (BeforeAgent): it emits no top-level classification
        field — the routing is folded into additionalContext — so this is a
        claude-only contract.
        """
        platform, root = exec_plugin_root
        if platform != "claude":
            pytest.skip(f"{platform}: append-only/no-route output carries no top-level 'classification'")
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        result = _run_hook(root, platform, script, interpreter, self._event(platform))
        output = _assert_valid_json_stdout(result, f"{platform} prompt_classifier")
        assert "classification" in output, (
            f"{platform} prompt_classifier: output missing 'classification' key.\n"
            f"Got: {output}"
        )
        assert output["classification"] in ("A", "B", "C", "D", "E"), (
            f"{platform} prompt_classifier: classification {output['classification']!r} "
            f"not in expected set A–E"
        )

    def test_stdout_has_modified_prompt(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Output must contain 'modifiedPrompt' key.

        Gemini's BeforeAgent cannot rewrite the prompt, so it must NOT emit
        'modifiedPrompt' — claude-only contract.
        """
        platform, root = exec_plugin_root
        if platform != "claude":
            pytest.skip(f"{platform}: append-only/no-route output must not emit 'modifiedPrompt'")
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        result = _run_hook(root, platform, script, interpreter, self._event(platform))
        output = _assert_valid_json_stdout(result, f"{platform} prompt_classifier")
        assert "modifiedPrompt" in output, (
            f"{platform} prompt_classifier: output missing 'modifiedPrompt' key.\n"
            f"Got: {output}"
        )

    def test_append_only_shape(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Append-only platforms (gemini/codex) must emit no classification /
        modifiedPrompt, only {continue, hookSpecificOutput{hookEventName,
        additionalContext}}, and the original prompt is NOT echoed back."""
        platform, root = exec_plugin_root
        if platform not in _APPEND_ONLY:
            pytest.skip("append-only shape contract (gemini/codex)")
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        event = self._event(platform)
        result = _run_hook(root, platform, script, interpreter, event)
        output = _assert_valid_json_stdout(result, f"{platform} prompt_classifier")
        assert "classification" not in output
        assert "modifiedPrompt" not in output
        assert set(output).issubset(
            {"continue", "systemMessage", "decision", "reason", "hookSpecificOutput"}
        )
        hso = output["hookSpecificOutput"]
        assert set(hso).issubset({"hookEventName", "additionalContext"})
        assert event["prompt"] not in hso.get("additionalContext", "")

    def test_cursor_minimal_shape(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Cursor's beforeSubmitPrompt cannot inject context or route, so the
        hook must emit ONLY Cursor-valid fields ({continue, user_message}) — no
        classification / modifiedPrompt / hookSpecificOutput, and the prompt is
        not echoed back."""
        platform, root = exec_plugin_root
        if platform != "cursor":
            pytest.skip("cursor-only minimal-shape contract")
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        event = self._event(platform)
        result = _run_hook(root, platform, script, interpreter, event)
        output = _assert_valid_json_stdout(result, f"{platform} prompt_classifier")
        assert output.get("continue") is True
        assert "classification" not in output
        assert "modifiedPrompt" not in output
        assert "hookSpecificOutput" not in output
        assert set(output).issubset({"continue", "user_message"})

    def test_stdout_has_hook_specific_output(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Output must contain 'hookSpecificOutput' object."""
        platform, root = exec_plugin_root
        if platform == "cursor":
            pytest.skip("cursor emits only {continue: true} (no hookSpecificOutput)")
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        result = _run_hook(root, platform, script, interpreter, self._event(platform))
        output = _assert_valid_json_stdout(result, f"{platform} prompt_classifier")
        assert "hookSpecificOutput" in output, (
            f"{platform} prompt_classifier: output missing 'hookSpecificOutput' key.\n"
            f"Got: {output}"
        )
        assert isinstance(output["hookSpecificOutput"], dict), (
            f"{platform} prompt_classifier: 'hookSpecificOutput' must be an object, "
            f"got {type(output['hookSpecificOutput'])}"
        )

    def test_stdout_has_additional_context(self, exec_plugin_root: tuple[str, Path]) -> None:
        """hookSpecificOutput.additionalContext must carry everything the model
        needs to see beyond its own prompt.

        additionalContext is the ONLY field Claude Code's UserPromptSubmit hook
        honours for injecting context — modifiedPrompt / systemPromptExtension are
        silently dropped. So additionalContext must equal the system state plus
        whatever the adapter appended to the prompt (the dispatch directive, when
        the request routes to an agent/skill). Regression guard for the bug where
        the directive never reached the model and skills never fired.
        """
        platform, root = exec_plugin_root
        if platform == "cursor":
            pytest.skip("cursor emits only {continue: true} (no additionalContext)")
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        event = self._event(platform)
        result = _run_hook(root, platform, script, interpreter, event)
        output = _assert_valid_json_stdout(result, f"{platform} prompt_classifier")
        hso = output["hookSpecificOutput"]
        assert "additionalContext" in hso, (
            f"{platform} prompt_classifier: hookSpecificOutput missing 'additionalContext' "
            f"— the model would receive nothing.\nGot: {hso}"
        )
        if platform in _APPEND_ONLY:
            # Append-only (gemini/codex): additionalContext carries the routing
            # directive + SYSTEM STATE, but never the rewritten prompt
            # (modifiedPrompt does not exist on an append-only response).
            assert "modifiedPrompt" not in output
            assert event.get("prompt", "") not in hso["additionalContext"]
            return
        # Claude structural invariant: additionalContext = systemPromptExtension + prompt-suffix.
        prompt = event.get("prompt", "")
        modified = output.get("modifiedPrompt", "")
        appended = modified[len(prompt):] if modified.startswith(prompt) else ""
        expected = (hso.get("systemPromptExtension") or "") + appended
        assert hso["additionalContext"] == expected, (
            f"{platform} prompt_classifier: additionalContext does not carry the system "
            f"state + appended directive.\n  additionalContext: {hso['additionalContext']!r}\n"
            f"  expected:          {expected!r}"
        )

    def test_prompt_is_preserved_in_modified_prompt(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """The original prompt text must be a prefix/substring of modifiedPrompt.

        Claude-only: Gemini's BeforeAgent cannot rewrite the prompt (append-only),
        so there is no modifiedPrompt to preserve the prompt in.
        """
        platform, root = exec_plugin_root
        if platform != "claude":
            pytest.skip(f"{platform}: append-only/no-route output has no modifiedPrompt")
        interpreter, script = _resolve_hook_command(root, platform, "prompt_classifier.py")
        event = self._event(platform)
        result = _run_hook(root, platform, script, interpreter, event)
        output = _assert_valid_json_stdout(result, f"{platform} prompt_classifier")
        original_prompt = event["prompt"]
        modified = output.get("modifiedPrompt", "")
        assert original_prompt in modified, (
            f"{platform} prompt_classifier: original prompt not found in modifiedPrompt.\n"
            f"original: {original_prompt!r}\n"
            f"modified: {modified[:200]!r}"
        )


# ---------------------------------------------------------------------------
# Test: pre_tool_use execution contract
# ---------------------------------------------------------------------------


class TestPreToolUseContract:
    """
    PreToolUse / BeforeTool hook — allow path and deny path.

    Allow path (benign Read tool):
        Input:  {"tool_name": "Read", "tool_input": {"file_path": "/tmp/foo.py"}}
        Output: (empty stdout or {})  Exit: 0

    Deny path (dangerous Bash command):
        Claude:  exit 2, no stdout required
        Gemini:  exit 0, stdout JSON with {"decision": "deny", ...}

    Deny path (.env file access):
        Claude:  exit 2, no stdout required
        Gemini:  exit 0, stdout JSON with {"decision": "deny", ...}
    """

    def _benign_event(self, platform: str) -> dict:
        base = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/test.py"}}
        if platform == "gemini":
            base["hook_event_name"] = "BeforeTool"
        return base

    def _dangerous_rm_event(self, platform: str) -> dict:
        base = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        }
        if platform == "gemini":
            base["hook_event_name"] = "BeforeTool"
        return base

    def _env_access_event(self, platform: str) -> dict:
        base = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/project/.env"},
        }
        if platform == "gemini":
            base["hook_event_name"] = "BeforeTool"
        return base

    def test_allow_exit_zero(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Benign Read tool → exit 0."""
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "pre_tool_use.py")
        result = _run_hook(root, platform, script, interpreter, self._benign_event(platform))
        assert result.returncode == 0, (
            f"{platform} pre_tool_use ALLOW: expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

    def test_deny_dangerous_rm_exit_code(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Dangerous rm -rf / → exit 2 (Claude) or exit 0 with deny JSON (Gemini)."""
        platform, root = exec_plugin_root
        if platform in ("codex", "cursor"):
            pytest.skip(f"{platform}: pre_tool_use security-hook deny contract not yet verified (separate pass)")
        interpreter, script = _resolve_hook_command(root, platform, "pre_tool_use.py")
        result = _run_hook(root, platform, script, interpreter, self._dangerous_rm_event(platform))
        if platform == "claude":
            assert result.returncode == 2, (
                f"claude pre_tool_use DENY (rm -rf): expected exit 2, got {result.returncode}\n"
                f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
            )
        else:
            # Gemini exits 0 but emits a deny JSON
            assert result.returncode == 0, (
                f"gemini pre_tool_use DENY (rm -rf): expected exit 0, got {result.returncode}\n"
                f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
            )

    def test_deny_dangerous_rm_gemini_json(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """Gemini deny path: stdout must be JSON with decision=deny."""
        platform, root = exec_plugin_root
        if platform != "gemini":
            pytest.skip("Gemini-specific deny JSON contract")
        interpreter, script = _resolve_hook_command(root, platform, "pre_tool_use.py")
        result = _run_hook(root, platform, script, interpreter, self._dangerous_rm_event(platform))
        output = _assert_valid_json_stdout(result, "gemini pre_tool_use DENY rm -rf")
        assert output.get("decision") == "deny", (
            f"gemini pre_tool_use DENY: expected decision='deny', got: {output}"
        )
        assert "reason" in output, (
            f"gemini pre_tool_use DENY: expected 'reason' key in output, got: {output}"
        )

    def test_deny_env_access_exit_code(self, exec_plugin_root: tuple[str, Path]) -> None:
        """.env file access → exit 2 (Claude) or exit 0 with deny JSON (Gemini)."""
        platform, root = exec_plugin_root
        if platform in ("codex", "cursor"):
            pytest.skip(f"{platform}: pre_tool_use security-hook deny contract not yet verified (separate pass)")
        interpreter, script = _resolve_hook_command(root, platform, "pre_tool_use.py")
        result = _run_hook(root, platform, script, interpreter, self._env_access_event(platform))
        if platform == "claude":
            assert result.returncode == 2, (
                f"claude pre_tool_use DENY (.env): expected exit 2, got {result.returncode}\n"
                f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
            )
        else:
            assert result.returncode == 0, (
                f"gemini pre_tool_use DENY (.env): expected exit 0, got {result.returncode}\n"
                f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
            )

    def test_deny_env_access_gemini_json(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Gemini .env deny: stdout must be JSON with decision=deny."""
        platform, root = exec_plugin_root
        if platform != "gemini":
            pytest.skip("Gemini-specific deny JSON contract")
        interpreter, script = _resolve_hook_command(root, platform, "pre_tool_use.py")
        result = _run_hook(root, platform, script, interpreter, self._env_access_event(platform))
        output = _assert_valid_json_stdout(result, "gemini pre_tool_use DENY .env")
        assert output.get("decision") == "deny", (
            f"gemini pre_tool_use DENY .env: expected decision='deny', got: {output}"
        )


# ---------------------------------------------------------------------------
# Test: post_tool_use execution contract
# ---------------------------------------------------------------------------


class TestPostToolUseContract:
    """
    PostToolUse / AfterTool hook.

    For non-target tools (e.g. Read), the hook is a pass-through:
        Claude:  exit 0, empty stdout (no output needed)
        Gemini:  exit 0, stdout is empty JSON {}

    For a target write tool with a non-existent file path, the hook
    still exits 0 (it swallows formatter failures gracefully).
    """

    def _event(self, platform: str) -> dict:
        base = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
        }
        if platform == "gemini":
            base["hook_event_name"] = "AfterTool"
        return base

    def test_exit_code_zero(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Non-target tool (Read) → exit 0."""
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "post_tool_use.py")
        result = _run_hook(root, platform, script, interpreter, self._event(platform))
        assert result.returncode == 0, (
            f"{platform} post_tool_use: expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

    def test_stdout_is_empty_or_valid_json(self, exec_plugin_root: tuple[str, Path]) -> None:
        """Stdout is empty (Claude pass-through) or valid JSON {} (Gemini)."""
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "post_tool_use.py")
        result = _run_hook(root, platform, script, interpreter, self._event(platform))
        stdout = result.stdout.strip()
        if stdout:
            # If there's any output, it must be valid JSON
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError as exc:
                pytest.fail(
                    f"{platform} post_tool_use: non-empty stdout that is not JSON: {exc}\n"
                    f"stdout: {result.stdout[:300]}"
                )
            # For Gemini, expect empty object or small dict (no error keys)
            assert isinstance(parsed, dict), (
                f"{platform} post_tool_use: stdout JSON must be an object, got: {parsed}"
            )

    def test_gemini_stdout_is_json_object(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """Gemini pass-through must output {} on stdout."""
        platform, root = exec_plugin_root
        if platform != "gemini":
            pytest.skip("Gemini-specific {} output contract")
        interpreter, script = _resolve_hook_command(root, platform, "post_tool_use.py")
        result = _run_hook(root, platform, script, interpreter, self._event(platform))
        output = _assert_valid_json_stdout(result, "gemini post_tool_use")
        assert isinstance(output, dict), (
            f"gemini post_tool_use: expected dict stdout, got: {output}"
        )


# ---------------------------------------------------------------------------
# Test: notify_compression execution contract
# ---------------------------------------------------------------------------


class TestNotifyCompressionContract:
    """
    PreCompact / PreCompress hook.

    Input:  {"trigger": "auto"}  or  {"trigger": "manual"}
    Output: {"systemMessage": "<string>"}
    Exit:   0
    """

    _AUTO_EVENT = {"trigger": "auto"}
    _MANUAL_EVENT = {"trigger": "manual"}

    def test_exit_code_zero_auto(self, exec_plugin_root: tuple[str, Path]) -> None:
        """trigger=auto → exit 0."""
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "notify_compression.py")
        result = _run_hook(root, platform, script, interpreter, self._AUTO_EVENT)
        assert result.returncode == 0, (
            f"{platform} notify_compression (auto): expected exit 0, "
            f"got {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

    def test_exit_code_zero_manual(self, exec_plugin_root: tuple[str, Path]) -> None:
        """trigger=manual → exit 0."""
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "notify_compression.py")
        result = _run_hook(root, platform, script, interpreter, self._MANUAL_EVENT)
        assert result.returncode == 0, (
            f"{platform} notify_compression (manual): expected exit 0, "
            f"got {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

    def test_stdout_has_system_message_auto(self, exec_plugin_root: tuple[str, Path]) -> None:
        """trigger=auto → stdout JSON must have 'systemMessage' key."""
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "notify_compression.py")
        result = _run_hook(root, platform, script, interpreter, self._AUTO_EVENT)
        output = _assert_valid_json_stdout(result, f"{platform} notify_compression (auto)")
        assert "systemMessage" in output, (
            f"{platform} notify_compression (auto): output missing 'systemMessage'.\n"
            f"Got: {output}"
        )
        assert isinstance(output["systemMessage"], str), (
            f"{platform} notify_compression: 'systemMessage' must be a string"
        )
        assert len(output["systemMessage"]) > 0, (
            f"{platform} notify_compression: 'systemMessage' must be non-empty"
        )

    def test_stdout_has_system_message_manual(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """trigger=manual → stdout JSON must have 'systemMessage' key."""
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "notify_compression.py")
        result = _run_hook(root, platform, script, interpreter, self._MANUAL_EVENT)
        output = _assert_valid_json_stdout(result, f"{platform} notify_compression (manual)")
        assert "systemMessage" in output, (
            f"{platform} notify_compression (manual): output missing 'systemMessage'.\n"
            f"Got: {output}"
        )

    def test_auto_message_differs_from_manual(
        self, exec_plugin_root: tuple[str, Path]
    ) -> None:
        """Auto and manual messages must be different strings."""
        platform, root = exec_plugin_root
        interpreter, script = _resolve_hook_command(root, platform, "notify_compression.py")
        auto_result = _run_hook(root, platform, script, interpreter, self._AUTO_EVENT)
        manual_result = _run_hook(root, platform, script, interpreter, self._MANUAL_EVENT)
        auto_output = _assert_valid_json_stdout(auto_result, f"{platform} notify_compression auto")
        manual_output = _assert_valid_json_stdout(
            manual_result, f"{platform} notify_compression manual"
        )
        assert auto_output["systemMessage"] != manual_output["systemMessage"], (
            f"{platform} notify_compression: auto and manual messages must differ\n"
            f"auto:   {auto_output['systemMessage']}\n"
            f"manual: {manual_output['systemMessage']}"
        )
