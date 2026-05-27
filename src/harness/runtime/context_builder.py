def build_context(phase: str, target_agent: str, auth_msg: str, branch: str, artifacts_missing: list) -> str:
    if phase == "Unknown":
        return ""
        
    artifacts_str = ', '.join(artifacts_missing) if artifacts_missing else 'None'
    
    system_state = (
        f"\n\n=== SYSTEM STATE ===\n"
        f"Active Branch: {branch}\n"
        f"Current Phase: {phase}\n"
        f"Target Agent: {target_agent}\n"
        f"Artifacts Missing: {artifacts_str}\n"
        f"Authorization: {auth_msg}\n"
    )
    
    if phase == "3 (Planning)":
        system_state += "JIT RULE: You MUST adhere to Domain-Driven Design (DDD) principles. Ensure the ubiquitous language is used.\n"
    elif "Execution" in phase:
        system_state += "JIT RULE: You MUST strictly follow Test-Driven Development (TDD). Write the failing test first.\n"
        
    system_state += "====================\n"
    
    return system_state
