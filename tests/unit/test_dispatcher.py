import pytest
import json
from pathlib import Path
from harness.runtime.dispatcher import OrchestratorDispatcher

def test_evaluate_artifacts_branch_c(tmp_path):
    dispatcher = OrchestratorDispatcher(str(tmp_path))
    result = dispatcher.evaluate_artifacts("C", tmp_path)
    assert result["phase"] == "Read-Only"
    assert result["target_agent"] == "@architect" # Or whatever is appropriate, maybe @generalist
    assert "UNAUTHORIZED to mutate" in result["auth_msg"]

def test_evaluate_artifacts_branch_d(tmp_path):
    dispatcher = OrchestratorDispatcher(str(tmp_path))
    result = dispatcher.evaluate_artifacts("D", tmp_path)
    assert result["phase"] == "4 (Surgical Edit authorized)"
    assert result["target_agent"] == "@implementer"
    assert "authorized for surgical edits" in result["auth_msg"]

def test_evaluate_artifacts_branch_a_no_diagnosis(tmp_path):
    dispatcher = OrchestratorDispatcher(str(tmp_path))
    result = dispatcher.evaluate_artifacts("A", tmp_path)
    assert result["phase"] == "Discovery"
    assert result["target_agent"] == "@diagnose" # or @planner
    assert "UNAUTHORIZED to modify" in result["auth_msg"]

def test_evaluate_artifacts_branch_a_with_diagnosis_no_plan(tmp_path):
    dispatcher = OrchestratorDispatcher(str(tmp_path))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "manifest.json").write_text(json.dumps({"docs": [{"state": "proposed"}]}))
    result = dispatcher.evaluate_artifacts("A", tmp_path)
    assert result["phase"] == "Planning"
    assert result["target_agent"] == "@planner"
    assert "UNAUTHORIZED to write code" in result["auth_msg"]

def test_evaluate_artifacts_branch_b_no_plan(tmp_path):
    dispatcher = OrchestratorDispatcher(str(tmp_path))
    result = dispatcher.evaluate_artifacts("B", tmp_path)
    assert result["phase"] == "Discovery"
    assert result["target_agent"] == "@planner"
    assert "UNAUTHORIZED to write code" in result["auth_msg"]

def test_evaluate_artifacts_with_plan_no_tdd(tmp_path):
    dispatcher = OrchestratorDispatcher(str(tmp_path))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "manifest.json").write_text(json.dumps({"docs": [{"state": "proposed"}]}))
    result = dispatcher.evaluate_artifacts("B", tmp_path)
    assert result["phase"] == "Planning"
    assert result["target_agent"] == "@planner"
    assert "UNAUTHORIZED to write code" in result["auth_msg"]

def test_evaluate_artifacts_with_tdd(tmp_path):
    dispatcher = OrchestratorDispatcher(str(tmp_path))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "manifest.json").write_text(json.dumps({"docs": [{"state": "inprogress"}]}))
    result = dispatcher.evaluate_artifacts("B", tmp_path)
    assert result["phase"] == "Execution/TDD"
    assert result["target_agent"] == "@implementer"
    assert "authorized to execute" in result["auth_msg"]
