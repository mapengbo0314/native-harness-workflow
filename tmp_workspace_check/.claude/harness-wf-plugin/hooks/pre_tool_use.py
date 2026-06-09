#!/usr/bin/env python3
import json
import sys
import re
from pathlib import Path

try:
    from hook_common import resolve_plugin_root, get_session_id
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
    if tool_name not in {"Write", "Edit", "MultiEdit", "Write", "Edit"}:
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
    if tool_name in {"Write", "Edit", "MultiEdit", "Write", "Edit"}:
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
    file_tools = ['Read', 'Edit', 'MultiEdit', 'Write', 'Read', 'Write', 'Edit']
    bash_tools = ['Bash', 'Bash']
    
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
            print("BLOCKED: Access to .env files containing sensitive data is prohibited", file=sys.stderr)
            print("Use .env.sample for template files instead", file=sys.stderr)
            if is_gemini:
                print(json.dumps({"decision": "deny", "reason": "Access to .env files containing sensitive data is prohibited"}))
                sys.exit(0)
            else:
                sys.exit(2)

        if tool_name in ['Bash', 'Bash']:
            command = tool_input.get('command', '')
            if is_dangerous_rm_command(command):
                print("BLOCKED: Dangerous rm command detected and prevented", file=sys.stderr)
                if is_gemini:
                    print(json.dumps({"decision": "deny", "reason": "Dangerous rm command detected and prevented"}))
                    sys.exit(0)
                else:
                    sys.exit(2)

        # TDD enforcement — block source writes until a test is written first
        if _HOOK_COMMON_AVAILABLE:
            session_id = get_session_id()
            state_root = resolve_plugin_root()
            tdd_block = _check_tdd(tool_name, tool_input, session_id, state_root)
            if tdd_block:
                print(f"BLOCKED: {tdd_block}", file=sys.stderr)
                if is_gemini:
                    print(json.dumps({"decision": "deny", "reason": tdd_block}))
                    sys.exit(0)
                else:
                    sys.exit(2)

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