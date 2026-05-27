import pytest
import json
from pathlib import Path
from harness.runtime.dispatcher import OrchestratorDispatcher

def test_evaluate_artifacts_branch_c(tmp_path):
    config_dir = tmp_path / "plugin-generated" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    result = dispatcher.evaluate_artifacts("C", tmp_path)
    assert result["phase"] == "Read-Only"
    assert result["target_agent"] == "@generalist" # Or whatever is appropriate, maybe @generalist
    assert "UNAUTHORIZED to mutate" in result["auth_msg"]

def test_evaluate_artifacts_branch_d(tmp_path):
    config_dir = tmp_path / "plugin-generated" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    result = dispatcher.evaluate_artifacts("D", tmp_path)
    assert result["phase"] == "4 (Surgical Edit authorized)"
    assert result["target_agent"] == "@implementer"
    assert "authorized for surgical edits" in result["auth_msg"]

def test_evaluate_artifacts_branch_a_no_diagnosis(tmp_path):
    config_dir = tmp_path / "plugin-generated" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    result = dispatcher.evaluate_artifacts("A", tmp_path)
    assert result["phase"] == "Discovery"
    assert result["target_agent"] == "@diagnose" # or @planner
    assert "UNAUTHORIZED to modify" in result["auth_msg"]

def test_evaluate_artifacts_branch_a_with_diagnosis_no_plan(tmp_path):
    config_dir = tmp_path / "plugin-generated" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "designs").mkdir(parents=True, exist_ok=True)
    (docs_dir / "designs" / "test-design.md").touch()
    result = dispatcher.evaluate_artifacts("A", tmp_path)
    assert result["phase"] == "Discovery"
    assert result["target_agent"] == "@diagnose"
    assert "UNAUTHORIZED to modify" in result["auth_msg"]

def test_evaluate_artifacts_branch_b_no_plan(tmp_path):
    config_dir = tmp_path / "plugin-generated" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    result = dispatcher.evaluate_artifacts("B", tmp_path)
    assert result["phase"] == "Planning/Execution"
    assert result["target_agent"] == "@planner"
    assert "authorized to plan or execute" in result["auth_msg"]

def test_evaluate_artifacts_with_plan_no_tdd(tmp_path):
    config_dir = tmp_path / "plugin-generated" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "designs").mkdir(parents=True, exist_ok=True)
    (docs_dir / "designs" / "test-design.md").touch()
    result = dispatcher.evaluate_artifacts("B", tmp_path)
    assert result["phase"] == "Planning/Execution"
    assert result["target_agent"] == "@planner"
    assert "authorized to plan or execute" in result["auth_msg"]

def test_evaluate_artifacts_with_tdd(tmp_path):
    config_dir = tmp_path / "plugin-generated" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "progress").mkdir(parents=True, exist_ok=True)
    (docs_dir / "progress" / "test-design-progress.md").touch()
    result = dispatcher.evaluate_artifacts("B", tmp_path)
    assert result["phase"] == "Planning/Execution"
    assert result["target_agent"] == "@planner"
    assert "authorized to plan or execute" in result["auth_msg"]
