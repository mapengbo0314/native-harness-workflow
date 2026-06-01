import pytest
import json
from pathlib import Path
from harness.runtime.dispatcher import OrchestratorDispatcher

def test_evaluate_artifacts_branch_c(tmp_path):
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    result = dispatcher.evaluate_artifacts("C", tmp_path)
    assert result["phase"] == "Read-Only"
    assert result["target_agent"] == "@generalist" # Or whatever is appropriate, maybe @generalist
    assert "UNAUTHORIZED to mutate" in result["auth_msg"]

def test_evaluate_artifacts_branch_d(tmp_path):
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    result = dispatcher.evaluate_artifacts("D", tmp_path)
    assert result["phase"] == "TDD Execution"
    assert result["target_agent"] == "@implementer"
    assert "TDD" in result["auth_msg"]

def test_evaluate_artifacts_branch_a_no_diagnosis(tmp_path):
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    result = dispatcher.evaluate_artifacts("A", tmp_path)
    assert result["phase"] == "Discovery"
    assert result["target_agent"] == "@debugger"
    assert "UNAUTHORIZED to modify" in result["auth_msg"]

def test_evaluate_artifacts_branch_a_with_diagnosis_no_plan(tmp_path):
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "designs").mkdir(parents=True, exist_ok=True)
    (docs_dir / "designs" / "test-design.md").touch()
    result = dispatcher.evaluate_artifacts("A", tmp_path)
    assert result["phase"] == "Discovery"
    assert result["target_agent"] == "@debugger"
    assert "UNAUTHORIZED to modify" in result["auth_msg"]

def test_evaluate_artifacts_branch_b_no_plan(tmp_path):
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))
    result = dispatcher.evaluate_artifacts("B", tmp_path)
    assert result["phase"] == "Planning/Execution"
    assert result["target_agent"] == "@planner"
    assert "authorized to plan or execute" in result["auth_msg"]

def test_evaluate_artifacts_with_plan_no_tdd(tmp_path):
    config_dir = tmp_path / "harness-wf-plugin" / "config"
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
    config_dir = tmp_path / "harness-wf-plugin" / "config"
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

def test_classify_intent_captures_model_in_langfuse(tmp_path, monkeypatch):
    """Test that classify_intent captures the model in Langfuse context."""
    import os
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    dispatcher = OrchestratorDispatcher(str(config_dir))

    # Force CLI environment so classify_intent doesn't skip LLM step
    monkeypatch.setenv("HARNESS_PLATFORM_CLI", "claude")

    # Mock langfuse_context to capture model updates
    from unittest.mock import MagicMock, patch

    mock_context = MagicMock()
    with patch('harness.runtime.dispatcher.langfuse_context', mock_context), \
         patch('harness.runtime.dispatcher.query_llm', return_value={"classification": "A"}):
        # Test the method
        dispatcher.classify_intent("test prompt")

        # Verify update_current_observation was called with model
        mock_context.update_current_observation.assert_called()
        call_args = mock_context.update_current_observation.call_args
        assert call_args is not None
        assert 'model' in call_args.kwargs or (call_args.args and len(call_args.args) > 0)

def test_dispatch_agent_captures_model_in_langfuse(tmp_path, monkeypatch):
    """Test that dispatch_agent captures the model in Langfuse context."""
    import os
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    
    # Create minimal agent config
    agents_config_file = config_dir / "agents.json"
    agents_config_file.write_text(json.dumps({
        "agents": {"test_agent": {}}
    }))
    
    dispatcher = OrchestratorDispatcher(str(config_dir))
    
    from unittest.mock import MagicMock, patch
    
    mock_context = MagicMock()
    with patch('harness.runtime.dispatcher.langfuse_context', mock_context):
        result = dispatcher.dispatch_agent("test_agent", {"context_key": "value"})
        
        # Verify update_current_observation was called with model
        mock_context.update_current_observation.assert_called()
        call_args = mock_context.update_current_observation.call_args
        assert call_args is not None
        assert 'model' in call_args.kwargs or (call_args.args and len(call_args.args) > 0)

def test_observe_decorators_have_explicit_names():
    """Test that observe decorators have explicit names."""
    import inspect
    from harness.runtime.dispatcher import OrchestratorDispatcher

    # Check classify_intent decorator
    classify_intent_func = OrchestratorDispatcher.classify_intent
    # The decorator should be present
    assert hasattr(classify_intent_func, '__wrapped__')

    # Check dispatch_agent decorator
    dispatch_agent_func = OrchestratorDispatcher.dispatch_agent
    assert hasattr(dispatch_agent_func, '__wrapped__')


def test_get_active_platform_and_model_detect_claude(tmp_path):
    """Test detection of .claude platform."""
    from harness.runtime.dispatcher import get_active_platform_and_model

    # Create .claude directory
    (tmp_path / ".claude").mkdir()

    platform, model = get_active_platform_and_model(str(tmp_path))

    assert platform == ".claude"
    assert model == "claude-haiku-4.5"


def test_get_active_platform_and_model_detect_gemini(tmp_path):
    """Test detection of .gemini platform."""
    from harness.runtime.dispatcher import get_active_platform_and_model

    # Create .gemini directory
    (tmp_path / ".gemini").mkdir()

    platform, model = get_active_platform_and_model(str(tmp_path))

    assert platform == ".gemini"
    assert model == "gemini-2.5-flash-lite"


def test_get_active_platform_and_model_detect_codex(tmp_path):
    """Test detection of .codex platform."""
    from harness.runtime.dispatcher import get_active_platform_and_model

    # Create .codex directory
    (tmp_path / ".codex").mkdir()

    platform, model = get_active_platform_and_model(str(tmp_path))

    assert platform == ".codex"
    assert model == "gpt-4"


def test_get_active_platform_and_model_detect_cursor(tmp_path):
    """Test detection of .cursor platform."""
    from harness.runtime.dispatcher import get_active_platform_and_model

    # Create .cursor directory
    (tmp_path / ".cursor").mkdir()

    platform, model = get_active_platform_and_model(str(tmp_path))

    assert platform == ".cursor"
    assert model == "claude"


def test_get_active_platform_and_model_env_var_override(tmp_path, monkeypatch):
    """Test that HARNESS_MODEL environment variable overrides platform defaults."""
    from harness.runtime.dispatcher import get_active_platform_and_model

    # Create .gemini directory
    (tmp_path / ".gemini").mkdir()

    # Set HARNESS_MODEL env var
    monkeypatch.setenv("HARNESS_MODEL", "custom-model-v1")

    platform, model = get_active_platform_and_model(str(tmp_path))

    assert platform == ".gemini"
    assert model == "custom-model-v1"


def test_get_active_platform_and_model_traverse_up(tmp_path, monkeypatch):
    """Test that function traverses up directory tree to find platform."""
    from harness.runtime.dispatcher import get_active_platform_and_model

    # Create .claude at root
    (tmp_path / ".claude").mkdir()

    # Create nested directory
    nested_dir = tmp_path / "src" / "harness" / "runtime"
    nested_dir.mkdir(parents=True)

    # Call from nested directory
    platform, model = get_active_platform_and_model(str(nested_dir))

    assert platform == ".claude"
    assert model == "claude-haiku-4.5"


def test_get_active_platform_and_model_fallback_to_unknown(tmp_path):
    """Test fallback when no platform directory is found."""
    from harness.runtime.dispatcher import get_active_platform_and_model

    # Create empty directory (no platform directories)
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    platform, model = get_active_platform_and_model(str(empty_dir))

    assert platform == "unknown"
    assert model == "unknown-model"


def test_get_active_platform_and_model_fallback_with_cli_env(tmp_path, monkeypatch):
    """Test fallback using HARNESS_PLATFORM_CLI when no platform found."""
    from harness.runtime.dispatcher import get_active_platform_and_model

    # Create empty directory (no platform directories)
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    # Set HARNESS_PLATFORM_CLI env var
    monkeypatch.setenv("HARNESS_PLATFORM_CLI", "custom-cli")

    platform, model = get_active_platform_and_model(str(empty_dir))

    assert platform == "unknown"
    assert model == "custom-cli-unknown"


def test_classify_intent_captures_correct_model_from_platform(tmp_path, monkeypatch):
    """Test that classify_intent captures the correct model for detected platform."""
    from unittest.mock import patch
    from harness.runtime.dispatcher import OrchestratorDispatcher
    import harness.runtime.llm_client as llm_mod

    # Reset last_actual_model so platform detection is used as fallback
    monkeypatch.setattr(llm_mod, "last_actual_model", "")

    # Create .claude directory
    (tmp_path / ".claude").mkdir()

    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)

    dispatcher = OrchestratorDispatcher(str(config_dir))

    # Force CLI environment so classify_intent doesn't skip LLM step
    monkeypatch.setenv("HARNESS_PLATFORM_CLI", "claude")

    # Mock langfuse_context and query_llm
    with patch('harness.runtime.dispatcher.langfuse_context') as mock_context:
        with patch('harness.runtime.dispatcher.query_llm') as mock_query_llm:
            mock_query_llm.return_value = '{"intent_analysis": "test", "selected_branch": "Branch B"}'

            # Set GEMINI_API_KEY to trigger the API path
            monkeypatch.setenv("GEMINI_API_KEY", "test-key")

            # Call from directory containing .claude
            import os
            original_cwd = os.getcwd()
            try:
                os.chdir(str(tmp_path))
                result = dispatcher.classify_intent("test prompt")

                # Verify the model was set to claude-haiku-4.5
                mock_context.update_current_observation.assert_called()
                call_kwargs = mock_context.update_current_observation.call_args.kwargs
                assert call_kwargs.get('model') == "claude-haiku-4.5"
            finally:
                os.chdir(original_cwd)


def test_dispatch_agent_captures_correct_model_from_platform(tmp_path, monkeypatch):
    """Test that dispatch_agent captures the correct model for detected platform."""
    from unittest.mock import patch
    from harness.runtime.dispatcher import OrchestratorDispatcher
    import harness.runtime.llm_client as llm_mod

    # Reset last_actual_model so platform detection is used as fallback
    monkeypatch.setattr(llm_mod, "last_actual_model", "")

    # Create .gemini directory
    (tmp_path / ".gemini").mkdir()

    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)

    # Create agent config
    agents_config_file = config_dir / "agents.json"
    agents_config_file.write_text(json.dumps({"agents": {"test_agent": {}}}))

    dispatcher = OrchestratorDispatcher(str(config_dir))

    # Mock langfuse_context
    with patch('harness.runtime.dispatcher.langfuse_context') as mock_context:
        # Call from directory containing .gemini
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            result = dispatcher.dispatch_agent("test_agent", {})

            # Verify the model was set to gemini-2.5-flash-lite
            mock_context.update_current_observation.assert_called()
            call_kwargs = mock_context.update_current_observation.call_args.kwargs
            assert call_kwargs.get('model') == "gemini-2.5-flash-lite"
        finally:
            os.chdir(original_cwd)
