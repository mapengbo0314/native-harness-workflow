"""Parity tests for non-claude platforms (gemini/cursor/codex).

Covers the pre-existing parity bugs and the multi-platform domain MCP
registration:

1. cursor/codex install_hooks resolve the ``${HARNESS_PLUGIN_ROOT}`` placeholder
   that the boilerplate hooks.json actually uses (they previously replaced the
   wrong ``${CLAUDE_PLUGIN_ROOT}`` token, leaving hooks unresolved).
2. hook_common.resolve_plugin_root honours CURSOR_PLUGIN_ROOT and
   CODEX_PLUGIN_ROOT.
3. configure_cli registers the ``domain`` MCP server for every platform, with
   the per-platform deployed root (.gemini / .cursor / .codex).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent
BOILERPLATE_HOOKS = REPO_ROOT / "src" / "harness" / "templates" / "boilerplate" / "hooks"


def _write_hooks(project_path: Path, config_dir: str) -> Path:
    """Write a minimal hooks dir with a hooks.json that uses the real
    ${HARNESS_PLUGIN_ROOT} placeholder used by the shipped boilerplate."""
    hooks_dir = project_path / config_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    hooks_json = hooks_dir / "hooks.json"
    hooks_json.write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "command": 'python3 "${HARNESS_PLUGIN_ROOT}/hooks/prompt_classifier.py"'
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return hooks_json


# ---------------------------------------------------------------------------
# 1. install_hooks placeholder resolution (cursor/codex)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("platform,config_dir,env_var", [
    ("cursor", ".cursor", "CURSOR_PLUGIN_ROOT"),
    ("codex", ".codex", "CODEX_PLUGIN_ROOT"),
])
def test_install_hooks_resolves_harness_plugin_root(platform, config_dir, env_var, tmp_path):
    from harness.adapters import get_adapter

    hooks_json = _write_hooks(tmp_path, config_dir)
    get_adapter(platform).install_hooks(tmp_path)

    content = hooks_json.read_text()
    assert "${HARNESS_PLUGIN_ROOT}" not in content, (
        f"{platform}: ${{HARNESS_PLUGIN_ROOT}} placeholder left unresolved"
    )
    assert f"${{{env_var}}}" in content, (
        f"{platform}: expected placeholder rewritten to ${{{env_var}}}"
    )


# ---------------------------------------------------------------------------
# 1b. gemini install_hooks remaps Claude event names to Gemini's taxonomy
# ---------------------------------------------------------------------------
# Gemini CLI has NO UserPromptSubmit / PreToolUse / PostToolUse / PreCompact
# events. Its taxonomy is BeforeAgent (prompt submit) / BeforeTool / AfterTool /
# PreCompress. A minted hooks.json ships with Claude's event-name keys, so
# install_hooks MUST rewrite them — otherwise the prompt-classifier and
# security hooks are bound to non-existent events and never fire.
# Refs: https://geminicli.com/docs/hooks/reference/ , https://geminicli.com/docs/hooks/

def _write_full_hooks(project_path: Path, config_dir: str) -> Path:
    """Write a hooks.json with all four Claude event keys the boilerplate uses."""
    hooks_dir = project_path / config_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    hooks_json = hooks_dir / "hooks.json"
    hooks_json.write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [{"hooks": [{"command": "x"}]}],
                    "PreToolUse": [{"matcher": "*", "hooks": [{"command": "y"}]}],
                    "PostToolUse": [{"matcher": "*", "hooks": [{"command": "z"}]}],
                    "PreCompact": [{"matcher": "*", "hooks": [{"command": "w"}]}],
                }
            }
        ),
        encoding="utf-8",
    )
    return hooks_json


def test_gemini_py_has_no_unused_shlex_import():
    """gemini.py imported shlex inside configure_cli but never used it."""
    gemini_src = (
        REPO_ROOT / "src" / "harness" / "adapters" / "gemini.py"
    ).read_text(encoding="utf-8")
    assert "import shlex" not in gemini_src, (
        "gemini.py still imports shlex (unused)"
    )


def test_prompt_classifier_crash_fallback_is_honest():
    """The minted prompt_classifier's except-path fallback (used only if the
    adapter's format_hook_response raises) must NOT emit the invented routing
    schema — codex rejects unknown fields (deny_unknown_fields) and
    cursor/gemini ignore them. The degraded path must stay honest: a minimal
    {continue, hookSpecificOutput{hookEventName, additionalContext}}.
    """
    src = (
        REPO_ROOT / "src" / "harness" / "templates" / "boilerplate"
        / "hooks" / "prompt_classifier.py"
    ).read_text(encoding="utf-8")
    assert "Adapter formatting failed" in src, "fallback marker moved — update this guard"
    fallback = src.split("Adapter formatting failed")[1].split("langfuse_instrumentation")[0]
    for bad in ('"modifiedPrompt"', '"system_prompt_extension"',
                '"target_agent"', '"classification"', '"systemPromptExtension"'):
        assert bad not in fallback, (
            f"prompt_classifier crash fallback still emits invented field {bad}"
        )


def test_gemini_install_hooks_remaps_event_names(tmp_path):
    from harness.adapters import get_adapter

    hooks_json = _write_full_hooks(tmp_path, ".gemini")
    get_adapter("gemini").install_hooks(tmp_path)

    data = json.loads(hooks_json.read_text())
    keys = set(data["hooks"])
    # Gemini's real event names.
    assert keys == {"BeforeAgent", "BeforeTool", "AfterTool", "PreCompress"}, (
        f"gemini hooks.json keys not remapped to Gemini taxonomy: {keys}"
    )
    # None of Claude's event names survive.
    for claude_event in ("UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact"):
        assert claude_event not in keys, (
            f"gemini: Claude event name {claude_event!r} not rewritten"
        )


# ---------------------------------------------------------------------------
# 2. resolve_plugin_root env-var support
# ---------------------------------------------------------------------------

def _load_hook_common():
    spec = importlib.util.spec_from_file_location(
        "hc_for_test", BOILERPLATE_HOOKS / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("env_var", [
    "CURSOR_PLUGIN_ROOT",
    "CODEX_PLUGIN_ROOT",
])
def test_resolve_plugin_root_honours_platform_env_var(env_var, tmp_path, monkeypatch):
    hc = _load_hook_common()
    for v in ("GEMINI_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "CURSOR_PLUGIN_ROOT", "CODEX_PLUGIN_ROOT"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv(env_var, str(tmp_path))
    assert hc.resolve_plugin_root() == tmp_path.resolve()


# ---------------------------------------------------------------------------
# 3. domain MCP registration per platform
# ---------------------------------------------------------------------------

def test_gemini_configure_cli_registers_domain(tmp_path, monkeypatch):
    from harness.adapters import get_adapter
    import subprocess
    import shutil as _shutil

    captured: list[list[str]] = []

    def _which(name):
        return f"/usr/local/bin/{name}"

    def _run(cmd, **kwargs):
        captured.append(list(cmd))
        from unittest.mock import MagicMock
        return MagicMock(returncode=0)

    monkeypatch.setattr(_shutil, "which", _which)
    monkeypatch.setattr(subprocess, "run", _run)

    get_adapter("gemini").configure_cli(tmp_path)

    domain_calls = [c for c in captured if "domain" in c and "mcp" in c]
    assert domain_calls, f"gemini: no domain MCP registration call. calls={captured}"
    cmd = domain_calls[0]
    # mirrors codegraph: gemini mcp add --scope project -e ... domain python3 -m server
    # No `--` separator: the installed gemini CLI drops everything after `--`,
    # which would strip the server command. yargs captures `-m server` as the
    # variadic args of the `python3` commandOrUrl positional instead.
    assert "add" in cmd
    assert "--" not in cmd, "gemini domain registration must NOT use a -- separator"
    assert cmd[-3:] == ["python3", "-m", "server"]
    joined = " ".join(cmd)
    assert "PYTHONPATH=.gemini/src" in joined
    assert "DOMAIN_JSON_PATH=.gemini/domain/domain.json" in joined


def test_generic_configure_cli_is_noop_no_domain_mcp(tmp_path):
    """Generic is a catch-all with no specific CLI and no agreed MCP-registration
    convention (codex=.codex/config.toml, cursor=.cursor/mcp.json, gemini=CLI;
    there is no universal .agents/mcp.json standard). Fabricating one would be
    dishonest, so domain MCP registration is N/A for generic: configure_cli is a
    no-op and writes nothing claiming domain_ops. (Documented in
    docs/platform-support.md.)"""
    from harness.adapters import get_adapter

    get_adapter("generic").configure_cli(tmp_path)

    # No MCP-registration artefacts of any kind.
    assert not (tmp_path / ".agents" / "mcp.json").exists()
    assert not (tmp_path / ".agents" / "config.toml").exists()
    assert not (tmp_path / ".mcp.json").exists()
    # Nothing under .agents references the domain MCP server.
    for p in (tmp_path / ".agents").rglob("*"):
        if p.is_file():
            assert "domain" not in p.read_text(encoding="utf-8", errors="ignore")


def test_cursor_configure_cli_writes_mcp_json(tmp_path):
    from harness.adapters import get_adapter

    get_adapter("cursor").configure_cli(tmp_path)

    mcp_json = tmp_path / ".cursor" / "mcp.json"
    assert mcp_json.exists(), "cursor: .cursor/mcp.json not written"
    data = json.loads(mcp_json.read_text())
    domain = data["mcpServers"]["domain"]
    assert domain["command"] == "python3"
    assert domain["args"] == ["-m", "server"]
    assert domain["env"]["PYTHONPATH"] == ".cursor/src"
    assert domain["env"]["DOMAIN_JSON_PATH"] == ".cursor/domain/domain.json"


def test_cursor_configure_cli_merges_existing_servers(tmp_path):
    from harness.adapters import get_adapter

    mcp_json = tmp_path / ".cursor" / "mcp.json"
    mcp_json.parent.mkdir(parents=True)
    mcp_json.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))

    get_adapter("cursor").configure_cli(tmp_path)

    data = json.loads(mcp_json.read_text())
    assert "other" in data["mcpServers"], "cursor: existing server clobbered"
    assert "domain" in data["mcpServers"]


def test_cursor_configure_cli_recovers_from_non_object_json(tmp_path):
    # A valid-but-non-object .cursor/mcp.json (e.g. a list) must not crash the
    # mint — it should be replaced with a fresh object containing domain.
    from harness.adapters import get_adapter

    mcp_json = tmp_path / ".cursor" / "mcp.json"
    mcp_json.parent.mkdir(parents=True)
    mcp_json.write_text(json.dumps(["not", "an", "object"]))

    get_adapter("cursor").configure_cli(tmp_path)  # must not raise

    data = json.loads(mcp_json.read_text())
    assert isinstance(data, dict)
    assert "domain" in data["mcpServers"]


def test_codex_configure_cli_writes_config_toml(tmp_path):
    from harness.adapters import get_adapter

    get_adapter("codex").configure_cli(tmp_path)

    cfg = tmp_path / ".codex" / "config.toml"
    assert cfg.exists(), "codex: .codex/config.toml not written"
    text = cfg.read_text()
    assert "[mcp_servers.domain]" in text
    assert 'command = "python3"' in text
    assert 'args = ["-m", "server"]' in text
    assert "[mcp_servers.domain.env]" in text
    assert 'PYTHONPATH = ".codex/src"' in text
    assert 'DOMAIN_JSON_PATH = ".codex/domain/domain.json"' in text


def test_codex_configure_cli_preserves_existing_and_is_idempotent(tmp_path):
    from harness.adapters import get_adapter

    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('[existing]\nkey = "value"\n')

    adapter = get_adapter("codex")
    adapter.configure_cli(tmp_path)
    adapter.configure_cli(tmp_path)  # second run must be a no-op (idempotent)

    text = cfg.read_text()
    assert "[existing]" in text, "codex: existing content dropped"
    assert text.count("[mcp_servers.domain]") == 1, "codex: domain table duplicated"
