import pytest
from harness.runtime.context_builder import build_context

def test_build_context_base():
    result = build_context(
        phase="1 (Discovery)",
        target_agent="@generalist",
        auth_msg="Authorized",
        branch="A",
        missing_documents=["docs/plan.md"]
    )
    
    assert "=== SYSTEM STATE ===" in result
    assert "Active Branch: A" in result
    assert "Current Phase: 1 (Discovery)" in result
    assert "Target Agent: @generalist" in result
    assert "Missing Documents: docs/plan.md" in result
    assert "Authorization: Authorized" in result
    assert "JIT RULE:" not in result

def test_build_context_planning_no_ddd_jit():
    # Planning no longer injects a DDD / ubiquitous-language JIT rule; domain
    # knowledge now flows from the project-ops manifest (business digest), not DDD.
    result = build_context(
        phase="3 (Planning)",
        target_agent="@generalist",
        auth_msg="Authorized",
        branch="B",
        missing_documents=[]
    )

    assert "=== SYSTEM STATE ===" in result
    assert "Domain-Driven Design" not in result
    assert "ubiquitous language" not in result
    assert "JIT RULE:" not in result

def test_build_context_execution_jit():
    result = build_context(
        phase="4 (Execution)",
        target_agent="@implementer",
        auth_msg="Authorized",
        branch="C",
        missing_documents=[]
    )
    
    assert "=== SYSTEM STATE ===" in result
    assert "JIT RULE: You MUST strictly follow Test-Driven Development (TDD). Write the failing test first." in result

def test_build_context_unknown_phase():
    result = build_context(
        phase="Unknown",
        target_agent="@generalist",
        auth_msg="",
        branch="Unknown",
        missing_documents=[]
    )
    
    assert result == ""

def test_build_context_no_missing_artifacts():
    result = build_context(
        phase="2 (Design)",
        target_agent="@generalist",
        auth_msg="",
        branch="A",
        missing_documents=[]
    )

    assert "Missing Documents: None" in result


_BIZ = {
    "direction": "Win SMB invoicing on correctness",
    "priorities": ["data integrity", "auditability"],
}


@pytest.mark.parametrize("branch", ["B", "C"])
def test_business_injected_on_planning_and_question_branches(branch):
    result = build_context(
        phase="3 (Planning)", target_agent="@planner", auth_msg="",
        branch=branch, missing_documents=[], business=_BIZ,
    )
    assert 'Product direction (domain_ops "business")' in result
    assert "Win SMB invoicing on correctness" in result
    assert "data integrity; auditability" in result   # list rendered inline


@pytest.mark.parametrize("branch", ["A", "D", "E"])
def test_business_absent_on_other_branches(branch):
    result = build_context(
        phase="4 (Execution)", target_agent="@implementer", auth_msg="",
        branch=branch, missing_documents=[], business=_BIZ,
    )
    assert "Product direction" not in result


def test_business_empty_omitted_on_b():
    result = build_context(
        phase="3 (Planning)", target_agent="@planner", auth_msg="",
        branch="B", missing_documents=[], business={},
    )
    assert "Product direction" not in result


def test_business_render_is_capped():
    big = {"direction": "x" * 5000, "priorities": ["y" * 5000]}
    result = build_context(
        phase="3 (Planning)", target_agent="@planner", auth_msg="",
        branch="B", missing_documents=[], business=big,
    )
    # the business block must be bounded (cap 600 + a little framing), not 10k.
    assert len(result) < 1200


# ---------------------------------------------------------------------------
# Phase 4 (F4): Search-First gate line — steering layer
# ---------------------------------------------------------------------------

def test_branch_b_with_gate_pending_shows_gate_line():
    """Branch B + research not recorded ⇒ the SYSTEM STATE block carries the
    search-first gate status line (steering layer; enforcement is in
    pre_tool_use)."""
    result = build_context(
        phase="3 (Planning)",
        target_agent="@planner",
        auth_msg="Authorized",
        branch="B",
        missing_documents=[],
        search_first_pending=True,
    )
    assert "Search-First Gate: research_done NOT set" in result
    assert "search-first" in result


def test_branch_b_without_gate_flag_has_no_gate_line():
    """research recorded (or toggle off) ⇒ caller passes False ⇒ no line."""
    result = build_context(
        phase="3 (Planning)",
        target_agent="@planner",
        auth_msg="Authorized",
        branch="B",
        missing_documents=[],
        search_first_pending=False,
    )
    assert "Search-First Gate" not in result


def test_non_b_branch_never_shows_gate_line():
    """The gate line is a Branch-B pre-condition only."""
    for branch in ("A", "C", "D", "E"):
        result = build_context(
            phase="4 (Execution)",
            target_agent="@implementer",
            auth_msg="Authorized",
            branch=branch,
            missing_documents=[],
            search_first_pending=True,
        )
        assert "Search-First Gate" not in result, f"branch {branch} must not carry the gate line"


def test_gate_line_default_off_for_legacy_callers():
    """Callers that don't pass the kwarg (legacy) get no gate line."""
    result = build_context(
        phase="3 (Planning)",
        target_agent="@planner",
        auth_msg="Authorized",
        branch="B",
        missing_documents=[],
    )
    assert "Search-First Gate" not in result
