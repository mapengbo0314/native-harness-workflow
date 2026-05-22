import subprocess
import json
import time

def generate_mock_stack_trace():
    """Generates a highly verbose, realistic-looking stack trace."""
    trace = "Traceback (most recent call last):\n"
    # Vendor noise
    for i in range(50):
        trace += f'  File "/usr/local/lib/python3.11/site-packages/vendor_lib/module_{i}.py", line {i*10 + 5}, in execute\n'
        trace += f'    return self._internal_call_{i}(args)\n'
    # Repo frame
    trace += '  File "/Users/pengbolicious/pengbo-apps/e-2-g/harness/cli.py", line 42, in main\n'
    trace += '    result = processor.process_data(data)\n'
    # More vendor noise
    for i in range(20):
        trace += f'  File "/usr/local/lib/python3.11/site-packages/core_lib/utils_{i}.py", line {i*5 + 2}, in handle\n'
        trace += f'    raise ProcessingError("Failed at step {i}")\n'
    trace += 'Exception: Processing failed due to unexpected null value in data payload.'
    return trace

def get_token_count(text):
    """Estimation using wc (words * 1.3 roughly approximates tokens)."""
    # For a rough benchmark, 1 word ~= 1.3 tokens. 
    # Or just count characters / 4.
    return len(text) // 4

def simulate_workflow(use_gate=False):
    print(f"\n--- Simulating Workflow (Use Gate: {use_gate}) ---")
    raw_trace = generate_mock_stack_trace()
    raw_tokens = get_token_count(raw_trace)
    
    total_tokens_consumed = 0
    session_history = []
    
    # TURN 1: User Input
    user_prompt = f"I hit this error when running the CLI:\n{raw_trace}"
    session_history.append(user_prompt)
    
    # Cost to Orchestrator to read turn 1
    current_history_tokens = sum(get_token_count(m) for m in session_history)
    total_tokens_consumed += current_history_tokens
    
    if use_gate:
        print("  [Gate Active] Orchestrator delegates to context-intake...")
        # TURN 2: Orchestrator delegates to context-intake
        delegation_prompt = f"Subagent, use context-intake on this:\n{user_prompt}"
        session_history.append(delegation_prompt)
        total_tokens_consumed += sum(get_token_count(m) for m in session_history)
        
        # Subagent processes and returns summary
        summary = "SUMMARY:\nIntent: Fix CLI error.\nError: Exception: Processing failed due to unexpected null value.\nLocation: harness/cli.py:42\nEvidence: result = processor.process_data(data)\nNext Process: use diagnose."
        session_history.append(summary)
        
        # Cost to context-intake agent (reads delegation prompt)
        total_tokens_consumed += get_token_count(delegation_prompt)
        
        print("  [Gate Active] Orchestrator delegates to implementer with summary...")
        # TURN 3: Orchestrator delegates to implementer
        impl_delegation = f"Implementer, fix the bug based on this summary:\n{summary}"
        session_history.append(impl_delegation)
        total_tokens_consumed += sum(get_token_count(m) for m in session_history)
        
        # Cost to Implementer (reads summary, not raw trace)
        total_tokens_consumed += get_token_count(impl_delegation)
        
    else:
        print("  [Gate Inactive] Orchestrator delegates directly to implementer...")
        # TURN 2: Orchestrator delegates to implementer with raw trace
        impl_delegation = f"Implementer, fix the bug based on this trace:\n{user_prompt}"
        session_history.append(impl_delegation)
        total_tokens_consumed += sum(get_token_count(m) for m in session_history)
        
        # Cost to Implementer (reads massive raw trace)
        total_tokens_consumed += get_token_count(impl_delegation)

    print(f"  Raw Trace Size: ~{raw_tokens} tokens")
    print(f"  Total Session Tokens Consumed: ~{total_tokens_consumed} tokens")
    return total_tokens_consumed

if __name__ == "__main__":
    tokens_no_gate = simulate_workflow(use_gate=False)
    tokens_with_gate = simulate_workflow(use_gate=True)
    
    print("\n=== Results ===")
    print(f"Without Gate: {tokens_no_gate} tokens")
    print(f"With Gate:    {tokens_with_gate} tokens")
    
    if tokens_with_gate > tokens_no_gate:
        print("\nCONCLUSION: The Adversary was right (The Token Fallacy).")
        print("Because the raw trace stays in the Orchestrator's history, adding extra turns for the gate *increases* total session token consumption, even though the implementer subagent's specific prompt is smaller.")
    else:
        print("\nCONCLUSION: Token savings achieved!")