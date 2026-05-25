import sys
import json
import os
import uuid
import logging
from pathlib import Path
from hook_common import update_state, resolve_state_path, resolve_project_root

def fallback_classify(prompt):
    prompt = prompt.lower()
    if any(k in prompt for k in ["broken", "bug", "error", "fix", "stack trace"]):
        return "A"
    elif any(k in prompt for k in ["build", "implement", "design", "architecture", "plan", "feature"]):
        return "B"
    elif any(k in prompt for k in ["how", "where", "explain"]):
        return "C"
    else:
        return "D"

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        prompt = input_data.get("prompt", "")
        branch = None
        reason = None
        
        # 1. Setup paths to import OrchestratorDispatcher
        current_dir = Path(__file__).parent
        plugin_root = current_dir.parent
        project_root_dir = plugin_root.parent
        src_dir = project_root_dir / "src"
        config_dir = plugin_root / "config"
        
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
            
        try:
            # 2. Ensure LANGFUSE_TRACE_ID is set
            if not os.environ.get("LANGFUSE_TRACE_ID"):
                os.environ["LANGFUSE_TRACE_ID"] = str(uuid.uuid4())
                
            from harness.dispatcher import OrchestratorDispatcher
            from langfuse.decorators import langfuse_context
            
            # 3. Instantiate dispatcher
            dispatcher = OrchestratorDispatcher(str(config_dir))
            
            # 4. Dispatch agent to get intent
            result = dispatcher.dispatch_agent("orchestrator", {"prompt": prompt})
            
            branch = result.get("intent_branch")
            reason = result.get("intent_justification")
            
            # CRITICAL: Call langfuse_context.flush() to ensure telemetry upload
            langfuse_context.flush()
        except Exception as e:
            print(f"DEBUG: Dispatcher failed: {e}", file=sys.stderr)
            pass
            
        # 5. Fallback if dispatcher failed
        if not branch:
            branch = fallback_classify(prompt)
            reason = "Fallback keyword match"
        
        def modifier(state):
            state["current_branch"] = branch
            state["last_prompt"] = prompt[:100]
            if reason:
                state["intent_justification"] = reason
            
        state_path = resolve_state_path(input_data)
        update_state(state_path, modifier)
        
        project_root = resolve_project_root(input_data)
        current_phase = "Unknown"
        artifacts_missing = []
        auth_msg = ""
        
        # Re-usable artifact checkers
        def check_diagnosis():
            p = project_root / "artifacts" / "diagnosis_report.md"
            return p.exists(), "artifacts/diagnosis_report.md"
            
        def check_plan():
            p = project_root / "artifacts" / "implementation_plan.md"
            has_plan = False
            if p.exists():
                content = p.read_text()
                if "Verification Criteria" in content or "Sphinch Marks" in content:
                    has_plan = True
            return has_plan, "artifacts/implementation_plan.md"
            
        def check_tdd():
            p = project_root / "artifacts" / "tdd_failing_test.log"
            has_log = False
            if p.exists():
                content = p.read_text()
                if any(x in content for x in ["AssertionError", "FAILED", "Expected", "ModuleNotFoundError", "ImportError", "Traceback"]):
                    if "SyntaxError" not in content:
                        has_log = True
            return has_log, "artifacts/tdd_failing_test.log"

        if branch == "C":
            current_phase = "Read-Only"
            auth_msg = "You are STRICTLY UNAUTHORIZED to mutate any files. You must only read and answer questions."
        elif branch == "D":
            current_phase = "4 (Surgical Edit authorized)"
            auth_msg = "You are authorized for surgical edits. Bypass planner."
        else:
            is_phase1_ok = True
            if branch == "A":
                is_phase1_ok, m = check_diagnosis()
                if not is_phase1_ok:
                    current_phase = "1 (Diagnosis)"
                    artifacts_missing.append(m)
                    auth_msg = "You are UNAUTHORIZED to modify any files. You MUST use read-only tools to diagnose the issue and output the diagnosis report."
            
            if is_phase1_ok:
                is_phase3_ok, m = check_plan()
                if not is_phase3_ok:
                    current_phase = "3 (Planning)"
                    artifacts_missing.append(m)
                    auth_msg = "You are UNAUTHORIZED to write code or dispatch @implementer. You MUST dispatch @planner next."
                else:
                    is_phase4_ok, m = check_tdd()
                    if not is_phase4_ok:
                        current_phase = "4 (Pre-TDD)"
                        artifacts_missing.append(m)
                        auth_msg = "You are UNAUTHORIZED to write production code. You MUST write a proof of concept test that fails under current circumstances first."
                    else:
                        current_phase = "4 (Execution authorized) or 5"
                        auth_msg = "You are authorized to execute. Test logs exist."
                        
        system_state = ""
        if current_phase != "Unknown":
            system_state = f"\n\n=== SYSTEM STATE ===\nActive Branch: {branch}\nCurrent Phase: {current_phase}\nArtifacts Missing: {', '.join(artifacts_missing) if artifacts_missing else 'None'}\nAuthorization: {auth_msg}\n====================\n"
            
        # Output expected JSON format
        output = {
            "classification": branch, 
            "reason": reason,
            "modifiedPrompt": prompt + system_state,
            "system_prompt_extension": system_state,
            "hookSpecificOutput": {
                "systemPromptExtension": system_state,
                "modifiedPrompt": prompt + system_state
            }
        }
        print(json.dumps(output))
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in prompt_classifier: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()