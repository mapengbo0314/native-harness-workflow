# Branches where product/business direction shapes the work (planning, questions).
_BUSINESS_BRANCHES = ("B", "C")
# Hard cap on the rendered business block so a verbose section can't bloat a turn.
_BUSINESS_RENDER_CAP = 600
_BUSINESS_FIELDS = ("direction", "priorities", "constraints", "non_goals")


def _render_business(business: dict) -> str:
    """Render the compiled business digest as a compact, capped block. Returns
    "" when there's nothing to show."""
    lines = []
    for k in _BUSINESS_FIELDS:
        v = business.get(k)
        if not v:
            continue
        if isinstance(v, (list, tuple)):
            v = "; ".join(str(x) for x in v)
        lines.append(f"  {k}: {v}")
    if not lines:
        return ""
    block = 'Product direction (domain_ops "business"):\n' + "\n".join(lines)
    if len(block) > _BUSINESS_RENDER_CAP:
        block = block[:_BUSINESS_RENDER_CAP].rstrip() + " …"
    return block + "\n"


def build_context(phase: str, target_agent: str, auth_msg: str, branch: str, missing_documents: list[str], manifest_state: dict = None, business: dict = None, search_first_pending: bool = False) -> str:
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

    # Push the tiny business digest only where judgment matters (planning/questions).
    if business and branch in _BUSINESS_BRANCHES:
        system_state += _render_business(business)

    if manifest_state and branch == "B":

        system_state += f"In-Progress Designs: {', '.join(manifest_state.get('progress_found', [])) or 'None'}\n"

    # F4 steering layer: surface the search-first gate status on Branch-B
    # prompts when research has not been recorded.  The caller computes the
    # predicate (toggle on + research_done unset); enforcement lives in
    # pre_tool_use, keyed to the persisted phase (R2) — this line only steers.
    if search_first_pending and branch == "B":
        system_state += (
            "Search-First Gate: research_done NOT set — run the search-first skill "
            "(or record its proportionality waiver) before source edits.\n"
        )

    if "Execution" in phase:
        system_state += "JIT RULE: You MUST strictly follow Test-Driven Development (TDD). Write the failing test first.\n"
        
    system_state += "====================\n"
    
    return system_state
