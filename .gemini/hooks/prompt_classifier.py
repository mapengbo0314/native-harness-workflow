import sys
import json
import os
import uuid
import logging
from pathlib import Path
from hook_common import resolve_project_root

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
        project_root = resolve_project_root(input_data)
        branch = None
        reason = None
        routing_decision = {}
        
        # 1. Setup paths to import OrchestratorDispatcher
        current_dir = Path(__file__).parent
        plugin_root = current_dir.parent
        src_dir = plugin_root / "src"
        config_dir = plugin_root / "config"
        
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
            
        try:
            # 2. Ensure LANGFUSE_TRACE_ID is set
            if not os.environ.get("LANGFUSE_TRACE_ID"):
                os.environ["LANGFUSE_TRACE_ID"] = str(uuid.uuid4())
                
            from harness.runtime.dispatcher import OrchestratorDispatcher
            from langfuse.decorators import langfuse_context
            
            # 3. Instantiate dispatcher
            dispatcher = OrchestratorDispatcher(str(config_dir))
            
            # 4. Dispatch agent to get intent
            result = dispatcher.dispatch_agent("orchestrator", {
                "prompt": prompt,
                "project_root": str(project_root)
            })
            
            branch = result.get("intent_branch")
            reason = result.get("intent_justification")
            routing_decision = result.get("routing_decision", {})
            
            # CRITICAL: Call langfuse_context.flush() to ensure telemetry upload
            langfuse_context.flush()
        except Exception as e:
            print(f"DEBUG: Dispatcher failed: {e}", file=sys.stderr)
            pass
            
        # 5. Fallback if dispatcher failed
        if not branch:
            branch = fallback_classify(prompt)
            reason = "Fallback keyword match"
            
            try:
                # Attempt to get routing decision directly if dispatcher instantiation works but dispatch failed
                dispatcher = OrchestratorDispatcher(str(config_dir))
                routing_decision = dispatcher.evaluate_artifacts(branch, project_root)
            except Exception:
                pass

        current_phase = routing_decision.get("phase", "Unknown")
        artifacts_missing = routing_decision.get("artifacts_missing", [])
        auth_msg = routing_decision.get("auth_msg", "")
        target_agent = routing_decision.get("target_agent", "@generalist")

        system_state = ""
        if current_phase != "Unknown":
            system_state = f"\n\n=== SYSTEM STATE ===\nActive Branch: {branch}\nCurrent Phase: {current_phase}\nTarget Agent: {target_agent}\nArtifacts Missing: {', '.join(artifacts_missing) if artifacts_missing else 'None'}\nAuthorization: {auth_msg}\n====================\n"
            
        hook_event_name = input_data.get("hookEventName") or input_data.get("hook_event_name", "UserPromptSubmit")
        # Output expected JSON format
        output = {
            "classification": branch, 
            "reason": reason,
            "modifiedPrompt": prompt + system_state,
            "system_prompt_extension": system_state,
            "target_agent": target_agent,
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "systemPromptExtension": system_state,
                "modifiedPrompt": prompt + system_state,
                "target_agent": target_agent
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