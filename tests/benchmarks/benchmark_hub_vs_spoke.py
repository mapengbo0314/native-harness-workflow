import sys

def get_token_count(text):
    """Estimate tokens (roughly 1 token per 4 chars)."""
    return len(text) // 4

def simulate_repo_iteration():
    print("=== Token Benchmark: Monolithic vs. Orchestrator ===\n")
    print("Task: Find a bug by reading 5 large files (2000 tokens each) and fixing 1 file.\n")
    
    file_tokens = 2000
    num_files = 5
    
    # ---------------------------------------------------------
    # SCENARIO A: Monolithic Agent
    # ---------------------------------------------------------
    mono_history = []
    mono_total = 0
    
    # Turn 1: User prompt
    mono_history.append("User: Read these 5 files, find the bug, and fix it.")
    mono_total += sum(get_token_count(m) for m in mono_history)
    
    # Turns 2-6: Agent reads 5 files
    for i in range(num_files):
        mono_history.append(f"ToolCall: read_file(file_{i})")
        mono_total += sum(get_token_count(m) for m in mono_history)
        
        content = "x" * (file_tokens * 4) # simulate 2000 tokens
        mono_history.append(f"ToolResponse: {content}")
        mono_total += sum(get_token_count(m) for m in mono_history)
        
    # Turn 7: Agent writes the fix
    mono_history.append("ToolCall: write_file(file_4, fix)")
    mono_total += sum(get_token_count(m) for m in mono_history)
    
    print(f"Scenario A (Monolithic) Total Tokens: {mono_total:,}")
    
    # ---------------------------------------------------------
    # SCENARIO B: Orchestrator (Hub-and-Spoke)
    # ---------------------------------------------------------
    orch_history = []
    orch_total = 0
    
    # Turn 1: User prompt
    orch_history.append("User: Read these 5 files, find the bug, and fix it.")
    orch_total += sum(get_token_count(m) for m in orch_history)
    
    # Turn 2: Orchestrator delegates to Architect
    orch_history.append("ToolCall: invoke_agent(architect, 'find bug in 5 files')")
    orch_total += sum(get_token_count(m) for m in orch_history)
    
    # --- ARCHITECT SUBAGENT SESSION ---
    arch_history = ["System: You are Architect. Find bug in 5 files."]
    arch_total = sum(get_token_count(m) for m in arch_history)
    
    for i in range(num_files):
        arch_history.append(f"ToolCall: read_file(file_{i})")
        arch_total += sum(get_token_count(m) for m in arch_history)
        
        content = "x" * (file_tokens * 4)
        arch_history.append(f"ToolResponse: {content}")
        arch_total += sum(get_token_count(m) for m in arch_history)
        
    arch_history.append("ToolCall: write_file(artifacts/plan.md, 'Bug is in file_4.')")
    arch_total += sum(get_token_count(m) for m in arch_history)
    # --- END ARCHITECT ---
    
    # Turn 3: Orchestrator gets response and delegates to Implementer
    orch_history.append("ToolResponse: Architect finished. Plan at artifacts/plan.md")
    orch_total += sum(get_token_count(m) for m in orch_history)
    
    orch_history.append("ToolCall: invoke_agent(implementer, 'fix based on artifacts/plan.md')")
    orch_total += sum(get_token_count(m) for m in orch_history)
    
    # --- IMPLEMENTER SUBAGENT SESSION ---
    imp_history = ["System: You are Implementer. Fix based on plan."]
    imp_total = sum(get_token_count(m) for m in imp_history)
    
    imp_history.append("ToolCall: read_file(artifacts/plan.md)")
    imp_total += sum(get_token_count(m) for m in imp_history)
    
    imp_history.append("ToolResponse: 'Bug is in file_4.'")
    imp_total += sum(get_token_count(m) for m in imp_history)
    
    # Implementer ONLY reads file_4 (because Architect told it where the bug is)
    imp_history.append("ToolCall: read_file(file_4)")
    imp_total += sum(get_token_count(m) for m in imp_history)
    
    content = "x" * (file_tokens * 4)
    imp_history.append(f"ToolResponse: {content}")
    imp_total += sum(get_token_count(m) for m in imp_history)
    
    imp_history.append("ToolCall: write_file(file_4, fix)")
    imp_total += sum(get_token_count(m) for m in imp_history)
    # --- END IMPLEMENTER ---
    
    # Turn 4: Orchestrator finishes
    orch_history.append("ToolResponse: Implementer finished.")
    orch_total += sum(get_token_count(m) for m in orch_history)
    
    total_hub_spoke = arch_total + imp_total + orch_total
    print(f"Scenario B (Hub-and-Spoke) Total Tokens: {total_hub_spoke:,}")
    print(f"  - Architect cost:   {arch_total:,}")
    print(f"  - Implementer cost: {imp_total:,}")
    print(f"  - Orchestrator overhead: {orch_total:,}\n")
    
    # ---------------------------------------------------------
    # SCENARIO C: The Session Bloat (3 Consecutive Tasks)
    # ---------------------------------------------------------
    print("=== Multi-Task Session Bloat ===")
    print("What happens when the user asks for 3 similar tasks in a single session?\n")
    
    # Monolithic compounding
    mono_multi_history = []
    mono_multi_total = 0
    for task in range(3):
        mono_multi_history.append(f"User: Do task {task}")
        for i in range(num_files):
            mono_multi_history.append(f"ToolCall: read_file(file_{i})")
            mono_multi_history.append(f"ToolResponse: " + ("x" * file_tokens * 4))
            mono_multi_total += sum(get_token_count(m) for m in mono_multi_history)
    
    # Orchestrator stays lean (Subagents die, so their cost is static * 3)
    orch_multi_subagents = total_hub_spoke * 3
    orch_main_history = []
    orch_main_cost = 0
    for task in range(3):
        orch_main_history.append(f"User: Do task {task}")
        orch_main_history.append("ToolResponse: Done")
        orch_main_cost += sum(get_token_count(m) for m in orch_main_history)
        
    print(f"Monolithic 3-Task Session:  {mono_multi_total:,} tokens")
    print(f"Orchestrator 3-Task Session: {orch_multi_subagents + orch_main_cost:,} tokens")

if __name__ == '__main__':
    simulate_repo_iteration()