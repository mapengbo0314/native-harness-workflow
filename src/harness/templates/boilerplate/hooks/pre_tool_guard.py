import sys
import json
import os
import shlex
from pathlib import Path
from hook_common import resolve_plugin_root, resolve_project_root, resolve_state_path, read_json

PROTECTED_PROJECT_FILES = [
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".env",
    "state/campaign_state.json",
    ".claude/plugin-generated/hooks/hooks.json",
    ".claude/plugin-generated/state/campaign_state.json",
]

PROTECTED_PLUGIN_FILES = [
    "hooks/hooks.json",
    "state/campaign_state.json",
]

def _normalize_text(value) -> str:
    return os.path.expandvars(str(value).strip().strip("'\""))

def _candidate_paths(tool_input) -> list[str]:
    if not isinstance(tool_input, dict):
        try:
            return [_normalize_text(candidate) for candidate in shlex.split(str(tool_input))]
        except ValueError:
            return [_normalize_text(candidate) for candidate in str(tool_input).split()]

    candidates = []
    for key in ("path", "file_path"):
        if tool_input.get(key):
            candidates.append(tool_input[key])

    for edit in tool_input.get("edits", []) or []:
        if isinstance(edit, dict):
            for key in ("path", "file_path"):
                if edit.get(key):
                    candidates.append(edit[key])

    command = tool_input.get("command")
    if command:
        try:
            candidates.extend(shlex.split(str(command)))
        except ValueError:
            candidates.extend(str(command).split())

    return [_normalize_text(candidate) for candidate in candidates if str(candidate).strip()]

def _resolve_candidate(raw_path: str, base: Path) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve(strict=False)

def _protected_targets(project_root: Path, plugin_root: Path) -> set[Path]:
    targets = {
        _resolve_candidate(path, project_root)
        for path in PROTECTED_PROJECT_FILES
    }
    targets.update(
        _resolve_candidate(path, plugin_root)
        for path in PROTECTED_PLUGIN_FILES
    )
    return targets

def is_protected_path(raw_path: str, input_data: dict = None) -> bool:
    project_root = resolve_project_root(input_data)
    plugin_root = resolve_plugin_root()
    targets = _protected_targets(project_root, plugin_root)

    project_candidate = _resolve_candidate(raw_path, project_root)
    plugin_candidate = _resolve_candidate(raw_path, plugin_root)
    return project_candidate in targets or plugin_candidate in targets

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name") or input_data.get("toolName", "")
    tool_input = input_data.get("tool_input") or input_data.get("toolInput", {})
    
    if tool_name in ["Write", "Edit", "MultiEdit", "Bash", "run_shell_command", "write_file", "replace"]:
        for candidate in _candidate_paths(tool_input):
            if is_protected_path(candidate, input_data):
                print(f"Error: Access to protected path '{candidate}' is blocked.", file=sys.stderr)
                sys.exit(2)
                
    # Check Branch D planner/verifier escalation
    if tool_name in ["Task", "Agent", "generalist", "planner", "verifier"]:
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        if state.get("current_branch") == "Branch D":
            prompt = str(tool_input).lower()
            if "explicit" not in prompt:
                print("Error: Planner/verifier escalation blocked in Branch D unless explicit.", file=sys.stderr)
                sys.exit(2)
                
    # If passed
    print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))
    sys.exit(0)

if __name__ == "__main__":
    main()
