# Phase 4.2 Implementation Plan: OrchestratorDispatcher inside prompt_classifier

## Context
The `prompt_classifier.py` hook currently uses a hardcoded keyword matching function to classify user prompts into execution branches. To improve intent routing and enable observability, we need to upgrade it to use the `OrchestratorDispatcher` which utilizes a Large Language Model (via `query_llm`) and Langfuse for tracing.

## Design Doc

### Problem Statement
The hardcoded prompt classification in `prompt_classifier.py` is rigid and lacks telemetry. We need the hook to leverage the intelligence of `OrchestratorDispatcher` and send traces to Langfuse, exactly like our existing evaluators, without breaking the core functionality or requiring an authenticated Claude Code account for testing.

### Proposed Design
1. **Dynamic Path Injection**: The hook will use `Path(__file__).parent.parent / "src"` to locate the `src` directory dynamically and add it to `sys.path`. This enables it to import `OrchestratorDispatcher` and `langfuse_context`.
2. **Dispatcher Instantiation**: Instantiate `OrchestratorDispatcher` using the `config` directory located at `Path(__file__).parent.parent / "config"`.
3. **Trace Management**: Ensure `LANGFUSE_TRACE_ID` is set in the environment before dispatching to link telemetry traces properly.
4. **Agent Dispatch & Fallback**: Call `dispatch_agent("orchestrator", {"prompt": prompt})`. Extract `intent_branch` and `intent_justification`. If any error occurs (e.g., missing API key, missing dependencies), gracefully fall back to the legacy regex-based `classify()` function.
5. **Telemetry Flush**: Crucially, invoke `langfuse_context.flush()` before the hook exits to prevent trace loss.
6. **Headless Testing**: Create a task to initialize the harness headlessly (`HARNESS_HEADLESS=1`) and test the newly minted hook by piping a JSON payload into it.

### Alternatives
- **Direct LLM Query in Hook**: We could directly use `query_llm` inside the hook. *Rejected* because it bypasses the `OrchestratorDispatcher` routing rules, state management, and built-in telemetry tagging.
- **External API Call**: The hook could call a local server. *Rejected* due to added complexity of managing a background process.

### Sphinch Marks (Pass/Fail Assertions)
- [ ] `src/harness/templates/boilerplate/hooks/prompt_classifier.py` dynamically adds its parent `src` to `sys.path`.
- [ ] `OrchestratorDispatcher` is instantiated with the correct `config_dir`.
- [ ] `LANGFUSE_TRACE_ID` is reliably present or generated before dispatch.
- [ ] `dispatch_agent` is called, and `intent_branch` + `intent_justification` are extracted.
- [ ] The original keyword matching is preserved as a fallback (`fallback_classify`).
- [ ] `langfuse_context.flush()` is explicitly called on the happy path.
- [ ] The hook still outputs `{"classification": branch, "reason": justification}` to standard out.
- [ ] A headless minting test successfully executes without requiring Claude Code auth.

## Plan

### Step 1: Update `prompt_classifier.py` Boilerplate
Rewrite `src/harness/templates/boilerplate/hooks/prompt_classifier.py` to integrate `OrchestratorDispatcher`.

**Target File**: `src/harness/templates/boilerplate/hooks/prompt_classifier.py`

**Implementation Details**:
```python
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
```

### Step 2: Add Comprehensive Headless Test Script
Create a shell script to automate minting, verify all matrix branches, and ensure the fallback logic successfully catches failures.

**Target File**: `scripts/test_headless_hook.sh`

**Implementation Details**:
```bash
#!/bin/bash
set -e

echo "1. Minting fresh workspace with new hook..."
HARNESS_HEADLESS=1 HARNESS_PLATFORM=2 python src/harness/cli.py init --project-path . --llm gemini

echo -e "\n2. Testing Branch D (Surgical Edit)"
echo '{"prompt": "Fix the typo in README", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\n3. Testing Branch B (Feature Request)"
echo '{"prompt": "Implement a new authentication system", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\n4. Testing Fallback Logic"
# Unset key to force failure in the LLM dispatcher
env -u GEMINI_API_KEY echo '{"prompt": "There is a bug in the code", "cwd": "'$(pwd)'"}' | python .claude/plugin-generated/hooks/prompt_classifier.py

echo -e "\nAll tests completed. Check Langfuse to verify traces for steps 2 and 3."
```

### Step 3: Run Tests and Commit
Make the script executable, run the headless validation suite, and commit.

**Commands to run**:
```bash
chmod +x scripts/test_headless_hook.sh
./scripts/test_headless_hook.sh

git add src/harness/templates/boilerplate/hooks/prompt_classifier.py scripts/test_headless_hook.sh
git commit -m "feat: upgrade prompt classifier hook to use OrchestratorDispatcher with langfuse"
```

## Verification
- Run `./scripts/test_headless_hook.sh`. It should successfully mint and output standard JSON classifications for all three test scenarios.
- The third test must successfully fallback to the keyword matcher (outputting "reason": "Fallback keyword match").
- Check Langfuse dashboard to ensure traces appear for the first two scenarios.
