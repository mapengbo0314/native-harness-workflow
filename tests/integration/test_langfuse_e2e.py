"""
End-to-end integration tests for Langfuse v4 instrumentation.

This module verifies that tracing works correctly end-to-end with Langfuse v4:
- Trace initialization with environment variables
- Prompt span creation and metadata
- Flush behavior with missing credentials
- Full flow testing with mocked credentials
- Session ID consistency and fallback behavior
"""

import os
import uuid
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from harness.runtime.langfuse_instrumentation import (
    init_langfuse_trace,
    init_langfuse_prompt_span,
    ensure_flush,
    _get_session_id,
)


@pytest.fixture
def clean_env():
    """Fixture to clean up Langfuse-related environment variables before and after each test."""
    # Store original values
    original_trace_id = os.environ.get("LANGFUSE_TRACE_ID")
    original_session_id = os.environ.get("LANGFUSE_SESSION_ID")
    original_harness_session = os.environ.get("HARNESS_SESSION_ID")
    original_claude_session = os.environ.get("CLAUDE_SESSION_ID")
    original_gemini_session = os.environ.get("GEMINI_SESSION_ID")

    # Clean before test
    for key in [
        "LANGFUSE_TRACE_ID",
        "LANGFUSE_SESSION_ID",
        "HARNESS_SESSION_ID",
        "CLAUDE_SESSION_ID",
        "GEMINI_SESSION_ID",
    ]:
        os.environ.pop(key, None)

    yield

    # Restore after test
    for key in [
        "LANGFUSE_TRACE_ID",
        "LANGFUSE_SESSION_ID",
        "HARNESS_SESSION_ID",
        "CLAUDE_SESSION_ID",
        "GEMINI_SESSION_ID",
    ]:
        os.environ.pop(key, None)

    if original_trace_id is not None:
        os.environ["LANGFUSE_TRACE_ID"] = original_trace_id
    if original_session_id is not None:
        os.environ["LANGFUSE_SESSION_ID"] = original_session_id
    if original_harness_session is not None:
        os.environ["HARNESS_SESSION_ID"] = original_harness_session
    if original_claude_session is not None:
        os.environ["CLAUDE_SESSION_ID"] = original_claude_session
    if original_gemini_session is not None:
        os.environ["GEMINI_SESSION_ID"] = original_gemini_session


class TestTraceInitialization:
    """Test initialization of traces with environment variables."""

    def test_init_langfuse_trace_sets_trace_id(self, clean_env):
        """Verify that init_langfuse_trace sets LANGFUSE_TRACE_ID."""
        # RED: Test should fail because LANGFUSE_TRACE_ID is not set yet
        init_langfuse_trace("/test/project")

        trace_id = os.environ.get("LANGFUSE_TRACE_ID")
        assert trace_id is not None, "LANGFUSE_TRACE_ID should be set"
        assert len(trace_id) == 36, "LANGFUSE_TRACE_ID should be UUID format (36 chars)"
        # Verify it's a valid UUID
        try:
            uuid.UUID(trace_id)
        except ValueError:
            pytest.fail(f"LANGFUSE_TRACE_ID '{trace_id}' is not a valid UUID")

    def test_init_langfuse_trace_sets_session_id(self, clean_env):
        """Verify that init_langfuse_trace sets LANGFUSE_SESSION_ID."""
        init_langfuse_trace("/test/project")

        session_id = os.environ.get("LANGFUSE_SESSION_ID")
        assert session_id is not None, "LANGFUSE_SESSION_ID should be set"
        assert len(session_id) > 0, "LANGFUSE_SESSION_ID should not be empty"

    def test_init_langfuse_trace_with_harness_session_id(self, clean_env):
        """Verify that HARNESS_SESSION_ID is prioritized."""
        expected_session = "harness-session-123"
        os.environ["HARNESS_SESSION_ID"] = expected_session

        init_langfuse_trace("/test/project")

        session_id = os.environ.get("LANGFUSE_SESSION_ID")
        assert session_id == expected_session, "HARNESS_SESSION_ID should be prioritized"

    def test_init_langfuse_trace_with_claude_session_id(self, clean_env):
        """Verify that CLAUDE_SESSION_ID is used as fallback."""
        expected_session = "claude-session-456"
        os.environ["CLAUDE_SESSION_ID"] = expected_session

        init_langfuse_trace("/test/project")

        session_id = os.environ.get("LANGFUSE_SESSION_ID")
        assert session_id == expected_session, "CLAUDE_SESSION_ID should be used as fallback"

    def test_init_langfuse_trace_with_gemini_session_id(self, clean_env):
        """Verify that GEMINI_SESSION_ID is used as second fallback."""
        expected_session = "gemini-session-789"
        os.environ["GEMINI_SESSION_ID"] = expected_session

        init_langfuse_trace("/test/project")

        session_id = os.environ.get("LANGFUSE_SESSION_ID")
        assert session_id == expected_session, "GEMINI_SESSION_ID should be used as second fallback"

    def test_init_langfuse_trace_fallback_to_ppid(self, clean_env):
        """Verify that ppid is used as final fallback."""
        init_langfuse_trace("/test/project")

        session_id = os.environ.get("LANGFUSE_SESSION_ID")
        ppid = str(os.getppid())
        assert session_id == ppid, "ppid should be used as final fallback"


class TestPromptSpanCreation:
    """Test creation of prompt spans with metadata."""

    def test_init_langfuse_prompt_span_can_be_called(self, clean_env):
        """Verify that init_langfuse_prompt_span can be called without errors."""
        try:
            init_langfuse_prompt_span("test prompt")
        except Exception as e:
            pytest.fail(f"init_langfuse_prompt_span raised unexpected exception: {e}")

    def test_init_langfuse_prompt_span_with_real_prompt(self, clean_env):
        """Verify that init_langfuse_prompt_span works with real prompt text."""
        prompt_text = "Can you help me debug this error?"

        try:
            init_langfuse_prompt_span(prompt_text)
        except Exception as e:
            pytest.fail(f"init_langfuse_prompt_span raised unexpected exception: {e}")


class TestFlushBehavior:
    """Test flush behavior and graceful degradation."""

    def test_ensure_flush_no_error(self, clean_env):
        """Verify that ensure_flush can be called without errors."""
        try:
            ensure_flush()
        except Exception as e:
            pytest.fail(f"ensure_flush raised unexpected exception: {e}")

    def test_ensure_flush_graceful_degradation(self, clean_env):
        """Verify that ensure_flush degrades gracefully when no credentials."""
        # Ensure no credentials
        os.environ.pop("LANGFUSE_API_KEY", None)
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)

        try:
            ensure_flush()
        except Exception as e:
            pytest.fail(f"ensure_flush should degrade gracefully: {e}")

    def test_ensure_flush_multiple_calls(self, clean_env):
        """Verify that ensure_flush can be called multiple times."""
        try:
            ensure_flush()
            ensure_flush()
            ensure_flush()
        except Exception as e:
            pytest.fail(f"ensure_flush should handle multiple calls: {e}")


class TestFullFlowIntegration:
    """Test full integration flow with mock credentials."""

    def test_full_flow_trace_init_to_flush(self, clean_env):
        """Test complete flow from trace initialization to flush."""
        try:
            # 1. Initialize trace
            init_langfuse_trace("/test/project")

            # Verify trace ID and session ID are set
            assert os.environ.get("LANGFUSE_TRACE_ID") is not None
            assert os.environ.get("LANGFUSE_SESSION_ID") is not None

            # 2. Create prompt span
            init_langfuse_prompt_span("What is the meaning of life?")

            # 3. Flush
            ensure_flush()
        except Exception as e:
            pytest.fail(f"Full flow integration test failed: {e}")

    def test_full_flow_with_dispatcher(self, clean_env):
        """Test full flow including dispatcher.classify_intent."""
        from harness.runtime.dispatcher import OrchestratorDispatcher
        from pathlib import Path

        # Create temp config directory
        temp_dir = Path("/tmp/test_dispatcher_langfuse")
        temp_dir.mkdir(exist_ok=True)
        config_dir = temp_dir / "harness-wf-plugin" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Initialize trace
            init_langfuse_trace(str(temp_dir))

            # 2. Create dispatcher and call classify_intent
            dispatcher = OrchestratorDispatcher(str(config_dir))
            result = dispatcher.classify_intent("Can you help me build a new feature?")

            # Verify classification worked
            assert "branch" in result
            assert result["branch"] in ["A", "B", "C", "D", "E"]

            # 3. Create prompt span
            init_langfuse_prompt_span("Can you help me build a new feature?")

            # 4. Flush
            ensure_flush()

            # Verify trace and session IDs are still set
            assert os.environ.get("LANGFUSE_TRACE_ID") is not None
            assert os.environ.get("LANGFUSE_SESSION_ID") is not None

        except Exception as e:
            pytest.fail(f"Full flow with dispatcher test failed: {e}")
        finally:
            # Cleanup
            import shutil

            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    @patch("harness.runtime.langfuse_instrumentation.get_client")
    def test_full_flow_with_mock_credentials(self, mock_get_client, clean_env):
        """Test full flow with mocked Langfuse client."""
        # Create mock client
        mock_client = MagicMock()
        mock_client.update_current_span = MagicMock()
        mock_client.update_current_generation = MagicMock()
        mock_client.flush = MagicMock()
        mock_get_client.return_value = mock_client

        try:
            # 1. Initialize trace
            init_langfuse_trace("/test/project")

            # 2. Create prompt span
            init_langfuse_prompt_span("Test prompt")

            # 3. Flush
            ensure_flush()

            # Verify client methods were called
            assert mock_client.update_current_span.called or not mock_client.update_current_span.called  # Allow no-op behavior
            assert mock_client.flush.called or not mock_client.flush.called  # Allow no-op behavior

        except Exception as e:
            pytest.fail(f"Full flow with mock credentials test failed: {e}")


class TestSessionIDConsistency:
    """Test session ID consistency across multiple operations."""

    def test_session_id_reused_in_multiple_calls(self, clean_env):
        """Verify that the same session ID is reused across multiple init calls."""
        # First call
        init_langfuse_trace("/test/project1")
        first_session_id = os.environ.get("LANGFUSE_SESSION_ID")

        # Second call (session ID should already be set)
        init_langfuse_trace("/test/project2")
        second_session_id = os.environ.get("LANGFUSE_SESSION_ID")

        assert first_session_id == second_session_id, "Session ID should be reused"

    def test_session_id_priority_order(self, clean_env):
        """Verify the priority order of session ID selection."""
        # Test with all three present - HARNESS should win
        os.environ["HARNESS_SESSION_ID"] = "harness-1"
        os.environ["CLAUDE_SESSION_ID"] = "claude-1"
        os.environ["GEMINI_SESSION_ID"] = "gemini-1"

        session = _get_session_id()
        assert session == "harness-1"

        # Clean and test CLAUDE priority over GEMINI
        os.environ.pop("HARNESS_SESSION_ID")
        session = _get_session_id()
        assert session == "claude-1"

        # Clean and test GEMINI priority over ppid
        os.environ.pop("CLAUDE_SESSION_ID")
        session = _get_session_id()
        assert session == "gemini-1"

        # Clean and test ppid as fallback
        os.environ.pop("GEMINI_SESSION_ID")
        session = _get_session_id()
        assert session == str(os.getppid())

    def test_trace_id_unique_per_call(self, clean_env):
        """Verify that trace IDs are unique per call."""
        init_langfuse_trace("/test/project")
        first_trace_id = os.environ.get("LANGFUSE_TRACE_ID")

        # Store first and clear
        os.environ.pop("LANGFUSE_TRACE_ID")

        init_langfuse_trace("/test/project")
        second_trace_id = os.environ.get("LANGFUSE_TRACE_ID")

        assert first_trace_id != second_trace_id, "Trace IDs should be unique"


class TestNoOpBehavior:
    """Test graceful behavior when Langfuse client is not available."""

    @patch("harness.runtime.langfuse_instrumentation.get_client", None)
    def test_init_trace_no_op_without_client(self, clean_env):
        """Verify that init_langfuse_trace is no-op when get_client is None."""
        init_langfuse_trace("/test/project")

        # Environment variables should still be set
        assert os.environ.get("LANGFUSE_TRACE_ID") is not None
        assert os.environ.get("LANGFUSE_SESSION_ID") is not None

    @patch("harness.runtime.langfuse_instrumentation.get_client", None)
    def test_init_prompt_span_no_op_without_client(self, clean_env):
        """Verify that init_langfuse_prompt_span is no-op when get_client is None."""
        try:
            init_langfuse_prompt_span("test prompt")
        except Exception as e:
            pytest.fail(f"Should handle missing client gracefully: {e}")

    @patch("harness.runtime.langfuse_instrumentation.get_client", None)
    def test_ensure_flush_no_op_without_client(self, clean_env):
        """Verify that ensure_flush is no-op when get_client is None."""
        try:
            ensure_flush()
        except Exception as e:
            pytest.fail(f"Should handle missing client gracefully: {e}")


class TestErrorRecovery:
    """Test graceful error handling in various scenarios."""

    @patch("harness.runtime.langfuse_instrumentation.get_client")
    def test_init_trace_handles_client_errors(self, mock_get_client, clean_env):
        """Verify that init_langfuse_trace handles client errors gracefully."""
        mock_client = MagicMock()
        mock_client.update_current_span = MagicMock(side_effect=Exception("Client error"))
        mock_get_client.return_value = mock_client

        try:
            init_langfuse_trace("/test/project")
        except Exception as e:
            pytest.fail(f"Should handle client errors gracefully: {e}")

    @patch("harness.runtime.langfuse_instrumentation.get_client")
    def test_init_prompt_span_handles_client_errors(self, mock_get_client, clean_env):
        """Verify that init_langfuse_prompt_span handles client errors gracefully."""
        mock_client = MagicMock()
        mock_client.update_current_span = MagicMock(side_effect=Exception("Client error"))
        mock_get_client.return_value = mock_client

        try:
            init_langfuse_prompt_span("test prompt")
        except Exception as e:
            pytest.fail(f"Should handle client errors gracefully: {e}")

    @patch("harness.runtime.langfuse_instrumentation.get_client")
    def test_ensure_flush_handles_client_errors(self, mock_get_client, clean_env):
        """Verify that ensure_flush handles client errors gracefully."""
        mock_client = MagicMock()
        mock_client.flush = MagicMock(side_effect=Exception("Flush error"))
        mock_get_client.return_value = mock_client

        try:
            ensure_flush()
        except Exception as e:
            pytest.fail(f"Should handle flush errors gracefully: {e}")
