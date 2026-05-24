import sys
import json
from hook_common import update_state, resolve_state_path

def classify(prompt):
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
        branch = classify(prompt)
        
        def modifier(state):
            state["current_branch"] = branch
            state["last_prompt"] = prompt[:100]
            
        state_path = resolve_state_path(input_data)
        
        # Inner try block removed. Errors will trigger the global exception block.
        update_state(state_path, modifier)
            
        # Output compact labels/reasons only
        print(json.dumps({"classification": branch, "reason": "Keyword match"}))
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in prompt_classifier: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
