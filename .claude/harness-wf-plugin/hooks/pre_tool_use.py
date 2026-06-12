#!/usr/bin/env python3
import json
import sys
import re
from pathlib import Path

try:
    from hook_common import resolve_plugin_root, get_session_id, publish_session_pointer
    _HOOK_COMMON_AVAILABLE = True
except ImportError:
    _HOOK_COMMON_AVAILABLE = False


# ---------------------------------------------------------------------------
# TDD enforcement helpers
# ---------------------------------------------------------------------------

def _is_test_file(file_path: str) -> bool:
    p = Path(file_path)
    name = p.name
    parts = p.parts
    return (
        name.startswith("test_") or
        name.endswith("_test.py") or
        "tests" in parts or
        "test" in parts
    )


def _is_source_write(tool_name: str, tool_input: dict):
    """Return file_path if this is a write to a non-test Python source file, else None."""
    if tool_name not in {"Write", "Edit", "MultiEdit", "write_file", "replace"}:
        return None
    file_path = tool_input.get("file_path", "")
    if not file_path or Path(file_path).suffix != ".py":
        return None
    if _is_test_file(file_path):
        return None
    return file_path


def _tdd_state_file(session_id: str, state_root: Path) -> Path:
    return state_root / "state" / f"tdd_{session_id}.json"


def _get_tdd_state(session_id: str, state_root: Path) -> dict:
    try:
        f = _tdd_state_file(session_id, state_root)
        if f.exists():
            return json.loads(f.read_text())
    except Exception:
        pass
    return {}


def _mark_test_written(session_id: str, state_root: Path) -> None:
    try:
        state_dir = state_root / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        _tdd_state_file(session_id, state_root).write_text(
            json.dumps({"test_written": True})
        )
    except Exception:
        pass


def _check_tdd(tool_name: str, tool_input: dict, session_id: str, state_root: Path):
    """Return a block message string if TDD mandate is violated, else None."""
    file_path = tool_input.get("file_path", "")

    # A test file write → mark RED phase started, always allow
    if tool_name in {"Write", "Edit", "MultiEdit", "write_file", "replace"}:
        if file_path and _is_test_file(file_path):
            _mark_test_written(session_id, state_root)
            return None

    # Source file write → block until a test has been written this session
    source_path = _is_source_write(tool_name, tool_input)
    if source_path:
        if not _get_tdd_state(session_id, state_root).get("test_written"):
            return (
                "TDD mandate violation: write a failing test before editing source files.\n"
                "  1. Write a test in tests/ that reproduces the issue.\n"
                "  2. Run pytest to confirm it fails (RED phase).\n"
                f"  3. Then edit {source_path} (GREEN phase)."
            )
    return None


# ---------------------------------------------------------------------------
# Search-First gate (F4 — enforcement layer, M1/R2)
# ---------------------------------------------------------------------------

def _check_search_first(tool_name: str, tool_input: dict, session_id: str, plugin_root):
    """Return a block message if a source write happens while the persisted
    session phase is ``planning`` and research_done is unset, else None.

    Keyed to the PERSISTED phase from the session store (R2) — never to the
    per-prompt branch classification, which observably flips mid-workflow.
    No persisted phase ⇒ passthrough.  Toggle off ⇒ passthrough.  Fail-open
    on any error: enforcement must never break normal tool use.
    """
    try:
        if _is_source_write(tool_name, tool_input) is None:
            return None
        from hook_common import feature_enabled, get_phase, get_research_done
        if not feature_enabled("pipeline.dispatcher.gates.search_first", plugin_root):
            return None
        phase = get_phase(plugin_root, session_id)
        if not isinstance(phase, dict) or phase.get("phase") != "planning":
            return None
        if get_research_done(plugin_root, session_id):
            return None
        return (
            "Search-First gate: the session is in the planning phase and no research "
            "has been recorded.\n"
            "  1. Run the search-first skill — research existing solutions "
            "(Adopt / Extend / Compose / Build) before writing source code.\n"
            "  2. If the approach is already decided or well-trodden, record its "
            "one-line proportionality waiver instead (sets research_done).\n"
            "  3. Exiting the planning phase (design sign-off) also releases this gate."
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Dispatch-budget backstop (F2 — R5)
# ---------------------------------------------------------------------------

_BUDGET_DEFAULT_MAX_TOOL_CALLS = 30
_BUDGET_DEFAULT_MAX_FILE_READS = 12
_READ_TOOLS = {"Read", "read_file"}


def _budget_sidecar(session_id: str, state_root: Path) -> Path:
    return state_root / "state" / f"budget_{session_id}.json"


def _check_budget(tool_name: str, tool_input: dict, session_id: str, state_root: Path):
    """Deterministic Tier-2 dispatch budget (R5): when a budget sidecar exists
    for this session, count tool calls / file reads against its limits and
    block past them with a summarize-and-finish message.

    A budget in a dispatch prompt is a directive the agent may ignore — this
    is the enforcement wall behind that steering.  No sidecar ⇒ passthrough
    (zero cost to normal sessions).  Corrupt sidecar ⇒ fail-open passthrough.
    """
    try:
        sidecar = _budget_sidecar(session_id, state_root)
        if not sidecar.exists():
            return None
        data = json.loads(sidecar.read_text())
        if not isinstance(data, dict):
            return None
        max_calls = data.get("max_tool_calls", _BUDGET_DEFAULT_MAX_TOOL_CALLS)
        max_reads = data.get("max_file_reads", _BUDGET_DEFAULT_MAX_FILE_READS)
        used_calls = data.get("tool_calls", 0)
        used_reads = data.get("file_reads", 0)
        is_read = tool_name in _READ_TOOLS
        # Check BEFORE write (Phase 6a hardening): a rejected attempt is not
        # persisted, so the effective budget is exactly the configured max.
        if used_calls + 1 > max_calls or (is_read and used_reads + 1 > max_reads):
            return (
                f"Dispatch budget reached ({used_calls} tool calls / "
                f"{used_reads} file reads; limits {max_calls}/{max_reads}).\n"
                "Summarize what you have found so far and finish — do not make "
                "further tool calls."
            )
        data.update({
            "tool_calls": used_calls + 1,
            "file_reads": used_reads + (1 if is_read else 0),
        })
        # Atomic write (same tmp+rename discipline as _save_session): a crash
        # mid-write must not corrupt the sidecar into fail-open.
        tmp = sidecar.with_suffix(".budget-tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(sidecar)
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------

def is_dangerous_rm_command(command):
    """
    Comprehensive detection of dangerous rm commands.
    Matches various forms of rm -rf and similar destructive patterns.
    """
    normalized = ' '.join(command.lower().split())
    
    patterns = [
        r'\brm\s+.*-[a-z]*r[a-z]*f',
        r'\brm\s+.*-[a-z]*f[a-z]*r',
        r'\brm\s+--recursive\s+--force',
        r'\brm\s+--force\s+--recursive',
        r'\brm\s+-r\s+.*-f',
        r'\brm\s+-f\s+.*-r',
    ]
    
    for pattern in patterns:
        if re.search(pattern, normalized):
            return True
            
    dangerous_paths = [
        r'/', r'/\*', r'~', r'~/', r'\$HOME', r'\.\.', r'\*', r'\.', r'\.\s*$'
    ]
    
    if re.search(r'\brm\s+.*-[a-z]*r', normalized):
        for path in dangerous_paths:
            if re.search(path, normalized):
                return True
                
    return False

def is_env_file_access(tool_name, tool_input):
    """
    Check if any tool is trying to access .env files containing sensitive data.
    Supports both Claude Code and Gemini CLI tool names.
    """
    file_tools = ['Read', 'Edit', 'MultiEdit', 'Write', 'read_file', 'write_file', 'replace']
    bash_tools = ['Bash', 'run_shell_command']
    
    if tool_name in file_tools:
        file_path = tool_input.get('file_path', '')
        if '.env' in file_path and not file_path.endswith('.env.sample'):
            return True
            
    if tool_name in bash_tools:
        command = tool_input.get('command', '')
        env_patterns = [
            r'\b\.env\b(?!\.sample)',
            r'cat\s+.*\.env\b(?!\.sample)',
            r'echo\s+.*>\s*\.env\b(?!\.sample)',
            r'touch\s+.*\.env\b(?!\.sample)',
            r'cp\s+.*\.env\b(?!\.sample)',
            r'mv\s+.*\.env\b(?!\.sample)'
        ]
        
        for pattern in env_patterns:
            if re.search(pattern, command):
                return True
                
    return False

def _deny(message: str, is_gemini: bool) -> None:
    """Single block-and-exit ritual shared by every gate (exit 2 on Claude,
    deny-JSON on gemini)."""
    print(f"BLOCKED: {message}", file=sys.stderr)
    if is_gemini:
        print(json.dumps({"decision": "deny", "reason": message}))
        sys.exit(0)
    sys.exit(2)


def main():
    try:
        input_str = sys.stdin.read()
        if not input_str.strip():
            # For Gemini, output {}
            print(json.dumps({}))
            sys.exit(0)

        input_data = json.loads(input_str)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        is_gemini = "hook_event_name" in input_data

        if is_env_file_access(tool_name, tool_input):
            print("Use .env.sample for template files instead", file=sys.stderr)
            _deny("Access to .env files containing sensitive data is prohibited", is_gemini)

        if tool_name in ['Bash', 'run_shell_command']:
            command = tool_input.get('command', '')
            if is_dangerous_rm_command(command):
                _deny("Dangerous rm command detected and prevented", is_gemini)

        # Resolve identity ONCE for the whole gate chain (Phase 6a): the
        # payload session_id is the platform's truth; publish it so
        # skill-invoked scripts share this store.
        if _HOOK_COMMON_AVAILABLE:
            session_id = get_session_id(input_data)
            state_root = resolve_plugin_root()
            publish_session_pointer(state_root, session_id)

            # Search-First gate (F4) — block source writes while persisted
            # phase=planning until research_done is set (R2: persisted phase,
            # never per-prompt branch classification)
            sf_block = _check_search_first(tool_name, tool_input, session_id, state_root)
            if sf_block:
                _deny(sf_block, is_gemini)

            # TDD enforcement — block source writes until a test is written first
            tdd_block = _check_tdd(tool_name, tool_input, session_id, state_root)
            if tdd_block:
                _deny(tdd_block, is_gemini)

            # Dispatch-budget backstop (F2/R5) — LAST in the chain (Phase 6a
            # hardening): a call another gate rejects never consumes budget.
            budget_block = _check_budget(tool_name, tool_input, session_id, state_root)
            if budget_block:
                _deny(budget_block, is_gemini)

        # Ensure log directory exists
        if not _HOOK_COMMON_AVAILABLE:
            sys.exit(0)
        log_dir = resolve_plugin_root() / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'pre_tool_use.json'
        
        log_data = []
        if log_path.exists():
            try:
                with open(log_path, 'r') as f:
                    log_data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                log_data = []
        
        log_data.append(input_data)
        
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
            
        if is_gemini:
            print(json.dumps({}))
            sys.exit(0)
        else:
            sys.exit(0)
            
    except Exception as e:
        # Fallback empty response for Gemini to not break execution loop
        if 'input_str' in locals() and 'hook_event_name' in input_str:
            print(json.dumps({}))
        sys.exit(0)

if __name__ == '__main__':
    main()