import sys
import json
import os
import shlex
from pathlib import Path
from hook_common import resolve_plugin_root, resolve_project_root, resolve_state_path, read_json, update_state

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
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)

        tool_name = input_data.get("tool_name") or input_data.get("toolName", "")
        tool_input = input_data.get("tool_input") or input_data.get("toolInput", {})
        
        project_root = resolve_project_root(input_data)
        
        if tool_name in ["Write", "Edit", "MultiEdit", "Bash", "run_shell_command", "write_file", "replace"]:
            for candidate in _candidate_paths(tool_input):
                if is_protected_path(candidate, input_data):
                    print(f"Error: Access to protected path '{candidate}' is blocked.", file=sys.stderr)
                    sys.exit(2)
                    
        # Check Circuit Breaker
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        
        if state.get("consecutive_tool_failures", 0) >= 3:
            # Reset the counter before hard stopping to prevent permanent system deadlocks across agent restarts
            def reset_breaker(s):
                s["consecutive_tool_failures"] = 0
            update_state(state_path, reset_breaker)
            print("Error: Circuit breaker tripped! 3 consecutive tool failures detected. Hard stopping agent.", file=sys.stderr)
            sys.exit(2)
            
        current_branch = state.get("current_branch")
        
        # Bypass for maintenance mode
        if state.get("maintenance_mode"):
            print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))
            sys.exit(0)
            
        # New Gatekeeper V3 Logic
        is_mutation_tool = tool_name in ["Write", "Edit", "MultiEdit", "write_file", "replace"]
        is_bash_tool = tool_name in ["Bash", "run_shell_command"]
        
        is_mutating_action = False
        if is_mutation_tool:
            is_mutating_action = True
        elif is_bash_tool:
            command = tool_input.get("command", "") if isinstance(tool_input, dict) else str(tool_input)
            try:
                cmd_parts = shlex.split(command)
                base_cmd = cmd_parts[0] if cmd_parts else ""
                if base_cmd in ["echo", "sed", "patch", "rm", "mv", "cp", "touch", "mkdir"]:
                    is_mutating_action = True
            except ValueError:
                pass
                
        is_dispatch_tool = tool_name in ["Task", "Agent", "generalist", "planner", "verifier", "implementer", "adversary", "reviewer", "refactorer"]

        candidate_paths = _candidate_paths(tool_input) if is_mutation_tool else []
        is_writing_artifact = False
        if is_mutation_tool and candidate_paths:
            if all("artifacts" in Path(p).parts for p in candidate_paths):
                is_writing_artifact = True

        # Branch C (Questioning) - STRICT READ-ONLY
        if current_branch == "C" and is_mutating_action:
            print("Error: Branch C is strict read-only. File mutations are blocked.", file=sys.stderr)
            sys.exit(2)
            
        # Phase 1 (Diagnosis) - Branch A ONLY
        if current_branch == "A" and is_mutating_action and not is_writing_artifact:
            diagnosis_path = project_root / "artifacts" / "diagnosis_report.md"
            if not diagnosis_path.exists():
                print("Error: Gatekeeper Phase 1. Missing artifacts/diagnosis_report.md.", file=sys.stderr)
                sys.exit(2)
                
        # Phase 3 (Planning) - Excluding Branch D & C
        if current_branch not in ["D", "C"] and is_dispatch_tool:
            is_exec_agent = tool_name in ["implementer", "verifier", "reviewer"]
            if tool_name in ["Task", "Agent", "generalist"]:
                prompt_str = str(tool_input).lower()
                if any(x in prompt_str for x in ["implementer", "verifier", "reviewer"]):
                    is_exec_agent = True
                    
            if is_exec_agent:
                plan_path = project_root / "artifacts" / "implementation_plan.md"
                has_plan = False
                if plan_path.exists():
                    content = plan_path.read_text()
                    if "Verification Criteria" in content or "Sphinch Marks" in content:
                        has_plan = True
                
                prompt = str(tool_input).lower()
                if not has_plan and "explicit" not in prompt:
                    print("Error: Gatekeeper Phase 3. Implementation plan missing or lacks Verification Criteria. Dispatch @planner first.", file=sys.stderr)
                    sys.exit(2)

        # Phase 4 (Execution - TDD) - Excluding Branch C & D
        if current_branch not in ["C", "D"] and is_mutating_action and not is_writing_artifact:
            # allow writes strictly to test directories
            is_test_write = False
            if is_mutation_tool:
                paths = _candidate_paths(tool_input)
                # If ALL paths are test files
                if paths and all(any(test_dir in Path(p).parts or Path(p).name.startswith("test_") for test_dir in ["tests", "__tests__"]) for p in paths):
                    is_test_write = True
                
            if not is_test_write:
                # Require TDD log
                tdd_log_path = project_root / "artifacts" / "tdd_failing_test.log"
                has_valid_log = False
                if tdd_log_path.exists():
                    content = tdd_log_path.read_text()
                    if any(x in content for x in ["AssertionError", "FAILED", "Expected", "ModuleNotFoundError", "ImportError"]):
                        if not any(x in content for x in ["SyntaxError"]):
                            has_valid_log = True
                
                if not has_valid_log:
                    print("Error: Gatekeeper Phase 4 (TDD). tdd_failing_test.log is missing or does not contain a verifiable assertion failure. Write a proof of concept test that fails under current circumstances first.", file=sys.stderr)
                    sys.exit(2)
                    
        # Phase 5 (Review/QA)
        is_finalization_bash = False
        if is_bash_tool:
            command = tool_input.get("command", "") if isinstance(tool_input, dict) else str(tool_input)
            try:
                cmd_parts = shlex.split(command)
                if len(cmd_parts) >= 2 and cmd_parts[0] == "git" and cmd_parts[1] in ["push", "commit"]:
                    is_finalization_bash = True
                elif len(cmd_parts) >= 2 and cmd_parts[0] == "gh" and cmd_parts[1] == "pr":
                    is_finalization_bash = True
            except ValueError:
                pass
                
        is_finalization_tool = tool_name in ["complete_task", "finish_branch"]
        
        if is_finalization_tool or is_finalization_bash:
            review_path = project_root / "artifacts" / "code_review_report.md"
            qa_path = project_root / "artifacts" / "qa_report.md"
            if not review_path.exists() or not qa_path.exists():
                print("Error: Gatekeeper Phase 5. code_review_report.md and qa_report.md are required before finalization.", file=sys.stderr)
                sys.exit(2)

        # Legacy Branch D check for explicit planner override
        if tool_name in ["Task", "Agent", "generalist", "planner", "verifier"]:
            if current_branch == "D":
                prompt = str(tool_input).lower()
                if "explicit" not in prompt:
                    print("Error: Planner/verifier escalation blocked in Branch D unless explicit.", file=sys.stderr)
                    sys.exit(2)
                    
        # If passed
        print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in pre_tool_guard: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
