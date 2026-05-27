def build_context(phase: str, target_agent: str, auth_msg: str, branch: str, missing_documents: list[str], manifest_state: dict = None) -> str:
    if phase == "Unknown":
        return ""
        
    documents_str = ', '.join(missing_documents) if missing_documents else 'None'
    
    system_state = (
        f"\n\n=== SYSTEM STATE ===\n"
        f"Active Branch: {branch}\n"
        f"Current Phase: {phase}\n"
        f"Target Agent: {target_agent}\n"
        f"Missing Documents: {documents_str}\n"
        f"Authorization: {auth_msg}\n"
    )
    
    if manifest_state:
        system_state += f"Proposed Designs: {', '.join(manifest_state.get('proposed', [])) or 'None'}\n"
        system_state += f"In-Progress Designs: {', '.join(manifest_state.get('inprogress', [])) or 'None'}\n"
    
    if phase == "3 (Planning)":
        system_state += "JIT RULE: You MUST adhere to Domain-Driven Design (DDD) principles. Ensure the ubiquitous language is used.\n"
    elif "Execution" in phase:
        system_state += "JIT RULE: You MUST strictly follow Test-Driven Development (TDD). Write the failing test first.\n"
        
    system_state += "====================\n"
    
    return system_state
