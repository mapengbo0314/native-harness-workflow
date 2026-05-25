import sys
import json
import os
import uuid
from pathlib import Path
from hook_common import update_state, resolve_state_path

def fallback_classify(prompt):
    prompt = prompt.lower()
    if any(k in prompt for k in ["broken", "bug", "error", "fix", "stack trace"]):
        return "Branch A"
    elif any(k in prompt for k in ["build", "implement", "design", "architecture", "plan", "feature"]):
        return "Branch B"
    elif any(k in prompt for k in ["how", "where", "explain"]):
        return "Branch C"
    else:
        return "Branch D"

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
        src_dir = plugin_root / "src"
        config_dir = plugin_root / "config"
        
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
            
        try:
            # 2. Ensure LANGFUSE_TRACE_ID is set
            if not os.environ.get("LANGFUSE_TRACE_ID"):
                os.environ["LANGFUSE_TRACE_ID"] = str(uuid.uuid4())
                
            from dispatcher import OrchestratorDispatcher
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
            
        # Output expected JSON format
        print(json.dumps({"classification": branch, "reason": reason}))
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in prompt_classifier: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()