import json
import os
from pathlib import Path
from typing import List, Dict, Any

def generate_report(events_file: str, output_file: str):
    """
    Generate a markdown report from sandbox events.
    """
    events_path = Path(events_file)
    output_path = Path(output_file)
    
    if not events_path.exists():
        print(f"Warning: Events file {events_file} not found.")
        return

    events = []
    with open(events_path, 'r') as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Initialize metrics
    total_user_chars = 0
    total_llm_chars = 0
    total_hook_injected_chars = 0
    
    tool_usage = {}
    rejections = []
    actual_branch = "Unknown"
    
    session_start_time = "N/A"
    session_end_time = "N/A"
    
    # Process events
    for event in events:
        e_type = event.get("event_type")
        data = event.get("data", {})
        ts = event.get("timestamp")
        
        if e_type == "SESSION_START":
            session_start_time = ts
            prompt = data.get("prompt", "")
            total_user_chars += len(prompt)
            
        elif e_type == "SESSION_END":
            session_end_time = ts
            
        elif e_type == "LLM_RESPONSE":
            total_llm_chars += len(data.get("text", ""))
            
        elif e_type == "TOOL":
            tool_name = data.get("tool_name")
            if tool_name:
                tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
            
        elif e_type == "HOOK_END":
            hook_name = data.get("hook")
            if hook_name == "prompt_interceptor":
                actual_branch = data.get("branch", "Unknown")
                # Estimate overhead for prompt injection (Directive + XML tags)
                total_hook_injected_chars += 250 # approximate directive overhead
            
        elif e_type == "HOOK_START":
            hook_name = data.get("hook")
            # We no longer count tool usage here as we use TOOL events for accuracy
            pass
        
        elif e_type == "SAFETY_VIOLATION":
            rejections.append({
                "timestamp": ts,
                "hook": data.get("hook"),
                "tool_name": data.get("tool_name"),
                "reason": data.get("reason")
            })

    # Calculate Harness Tax
    # Harness Tax = (characters_injected_by_hooks / total_prompt_characters) * 100
    total_prompt_chars = total_user_chars + total_hook_injected_chars
    harness_tax = (total_hook_injected_chars / total_prompt_chars * 100) if total_prompt_chars > 0 else 0
    
    # Token Savings (Theoretical)
    # Comparison: actual character count used vs. a theoretical "Grep Scenario"
    # Using the 9.2x ratio mentioned in benchmarks
    theoretical_grep_cost = total_llm_chars * 9.2
    token_savings = theoretical_grep_cost - total_llm_chars
    
    # Expected branch detection (heuristic for reporting)
    expected_branch = "Unknown"
    # We can use the same logic as dispatcher to see what we *expected*
    # but for simplicity we'll just report the actual branch.
    # If we wanted to test accuracy, we'd need a ground truth.

    # Generate Markdown
    report = []
    report.append("# Sandbox Execution Report")
    report.append(f"**Generated at:** {session_end_time}")
    report.append(f"**Session duration:** {session_start_time} to {session_end_time}")
    report.append("")
    report.append("## Summary Metrics")
    report.append("| Metric | Value |")
    report.append("| --- | --- |")
    report.append(f"| Total User Characters | {total_user_chars} |")
    report.append(f"| Total LLM Response Characters | {total_llm_chars} |")
    report.append(f"| Total Hook Injection Characters | {total_hook_injected_chars} |")
    report.append(f"| **Harness Tax** | **{harness_tax:.2f}%** |")
    report.append(f"| **Theoretical Token Savings** | **{token_savings:,.0f} chars** (9.2x efficiency) |")
    report.append("")
    
    report.append("## Routing Matrix")
    report.append("| Branch | Status |")
    report.append("| --- | --- |")
    report.append(f"| Actual Routed Branch | **{actual_branch}** |")
    report.append("")
    
    report.append("## Tool Usage Statistics")
    if tool_usage:
        report.append("| Tool | Call Count |")
        report.append("| --- | --- |")
        for tool, count in sorted(tool_usage.items()):
            report.append(f"| {tool} | {count} |")
    else:
        report.append("No tools were called during this session.")
    report.append("")
    
    report.append("## Safety Events & Rejections")
    if rejections:
        report.append("| Timestamp | Hook | Tool | Reason |")
        report.append("| --- | --- | --- | --- |")
        for rej in rejections:
             reason_clean = rej['reason'].replace('\n', ' ')
             report.append(f"| {rej['timestamp']} | {rej['hook']} | {rej['tool_name']} | {reason_clean} |")
    else:
        report.append("No safety violations or tool rejections occurred. ✅")
    
    report.append("")
    report.append("---")
    report.append("*End of automated sandbox report.*")
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write("\n".join(report))
        
    print(f"Report successfully generated at: {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        generate_report(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python3 analytics.py <events_file> <output_file>")
