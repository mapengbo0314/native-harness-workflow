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

def test_build_context_planning_jit():
    result = build_context(
        phase="3 (Planning)",
        target_agent="@generalist",
        auth_msg="Authorized",
        branch="B",
        missing_documents=[]
    )
    
    assert "=== SYSTEM STATE ===" in result
    assert "JIT RULE: You MUST adhere to Domain-Driven Design (DDD) principles. Ensure the ubiquitous language is used." in result

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
