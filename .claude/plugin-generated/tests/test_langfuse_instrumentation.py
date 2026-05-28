"""
Tests for langfuse_instrumentation.py

TDD flow: RED (failing) → GREEN (passing) → REFACTOR

Tests mock `langfuse.get_client` at the call site inside each function
(lazy import pattern in v4). All Langfuse API calls are mocked to avoid
real network/auth requirements.
"""
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make src importable
SRC_DIR = str(Path(__file__).parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import langfuse_instrumentation


# ---------------------------------------------------------------------------
# _get_session_id tests
# ---------------------------------------------------------------------------

class TestGetSessionId:
    def test_harness_session_id_takes_priority(self, monkeypatch):
        monkeypatch.setenv("HARNESS_SESSION_ID", "harness-123")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "claude-456")
        monkeypatch.setenv("GEMINI_SESSION_ID", "gemini-789")
        assert langfuse_instrumentation._get_session_id() == "harness-123"

    def test_claude_session_id_second_priority(self, monkeypatch):
        monkeypatch.delenv("HARNESS_SESSION_ID", raising=False)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "claude-456")
        monkeypatch.setenv("GEMINI_SESSION_ID", "gemini-789")
        assert langfuse_instrumentation._get_session_id() == "claude-456"

    def test_gemini_session_id_third_priority(self, monkeypatch):
        monkeypatch.delenv("HARNESS_SESSION_ID", raising=False)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.setenv("GEMINI_SESSION_ID", "gemini-789")
        assert langfuse_instrumentation._get_session_id() == "gemini-789"

    def test_fallback_to_ppid(self, monkeypatch):
        monkeypatch.delenv("HARNESS_SESSION_ID", raising=False)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.delenv("GEMINI_SESSION_ID", raising=False)
        result = langfuse_instrumentation._get_session_id()
        assert result == str(os.getppid())


# ---------------------------------------------------------------------------
# init_langfuse_trace tests
# ---------------------------------------------------------------------------

class TestInitLangfuseTrace:
    def test_sets_langfuse_trace_id_env_var(self, monkeypatch):
        """init_langfuse_trace must set LANGFUSE_TRACE_ID to a valid uuid4."""
        monkeypatch.delenv("LANGFUSE_TRACE_ID", raising=False)
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-1")

        mock_client = MagicMock()
        with patch("langfuse_instrumentation.get_client", return_value=mock_client):
            langfuse_instrumentation.init_langfuse_trace("/some/project")

        trace_id = os.environ.get("LANGFUSE_TRACE_ID")
        assert trace_id is not None
        # Must be a valid UUID
        uuid.UUID(trace_id)

    def test_sets_langfuse_session_id_env_var(self, monkeypatch):
        """init_langfuse_trace must set LANGFUSE_SESSION_ID from session ID."""
        monkeypatch.delenv("LANGFUSE_SESSION_ID", raising=False)
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-abc")

        mock_client = MagicMock()
        with patch("langfuse_instrumentation.get_client", return_value=mock_client):
            langfuse_instrumentation.init_langfuse_trace("/my/project")

        assert os.environ.get("LANGFUSE_SESSION_ID") == "test-session-abc"

    def test_calls_update_current_span_with_correct_args(self, monkeypatch):
        """init_langfuse_trace calls lf.update_current_span with session_id and project in metadata."""
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-xyz")

        mock_client = MagicMock()
        with patch("langfuse_instrumentation.get_client", return_value=mock_client):
            langfuse_instrumentation.init_langfuse_trace("/workspace/myproject")

            mock_client.update_current_span.assert_called_once_with(
                metadata={"project": "/workspace/myproject", "session_id": "test-session-xyz"},
            )

    def test_overwrites_existing_trace_id_with_fresh_uuid(self, monkeypatch):
        """If LANGFUSE_TRACE_ID is already set, it should be replaced with a fresh uuid."""
        monkeypatch.setenv("LANGFUSE_TRACE_ID", "existing-id")
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-1")

        mock_client = MagicMock()
        with patch("langfuse_instrumentation.get_client", return_value=mock_client):
            langfuse_instrumentation.init_langfuse_trace("/project")

        # A new uuid4 should have replaced the old one
        new_id = os.environ.get("LANGFUSE_TRACE_ID")
        assert new_id != "existing-id"
        uuid.UUID(new_id)  # Must be valid UUID

    def test_graceful_on_langfuse_error(self, monkeypatch):
        """init_langfuse_trace must not raise even if get_client() throws."""
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-err")

        with patch("langfuse_instrumentation.get_client", side_effect=RuntimeError("Langfuse down")):
            # Should not propagate
            langfuse_instrumentation.init_langfuse_trace("/project")


# ---------------------------------------------------------------------------
# init_langfuse_prompt_span tests
# ---------------------------------------------------------------------------

class TestInitLangfusePromptSpan:
    def test_calls_update_current_span_with_name_and_input(self, monkeypatch):
        """init_langfuse_prompt_span calls lf.update_current_span(name='prompt', input=prompt_text)."""
        prompt_text = "Fix the broken authentication logic"

        mock_client = MagicMock()
        with patch("langfuse_instrumentation.get_client", return_value=mock_client):
            langfuse_instrumentation.init_langfuse_prompt_span(prompt_text)

            mock_client.update_current_span.assert_called_once_with(
                name="user_prompt",
                input=prompt_text,
            )

    def test_handles_empty_prompt(self, monkeypatch):
        """init_langfuse_prompt_span works with an empty string."""
        mock_client = MagicMock()
        with patch("langfuse_instrumentation.get_client", return_value=mock_client):
            langfuse_instrumentation.init_langfuse_prompt_span("")

            mock_client.update_current_span.assert_called_once_with(
                name="user_prompt",
                input="",
            )

    def test_graceful_on_langfuse_error(self, monkeypatch):
        """init_langfuse_prompt_span must not raise even if get_client() throws."""
        with patch("langfuse_instrumentation.get_client", side_effect=RuntimeError("Langfuse down")):
            langfuse_instrumentation.init_langfuse_prompt_span("some prompt")


# ---------------------------------------------------------------------------
# ensure_flush tests
# ---------------------------------------------------------------------------

class TestEnsureFlush:
    def test_calls_flush(self, monkeypatch):
        """ensure_flush calls lf.flush() exactly once."""
        mock_client = MagicMock()
        with patch("langfuse_instrumentation.get_client", return_value=mock_client):
            langfuse_instrumentation.ensure_flush()

            mock_client.flush.assert_called_once()

    def test_graceful_on_langfuse_error(self, monkeypatch):
        """ensure_flush must not raise even if get_client() throws."""
        with patch("langfuse_instrumentation.get_client", side_effect=RuntimeError("Langfuse flush failed")):
            langfuse_instrumentation.ensure_flush()  # Must not propagate


# ---------------------------------------------------------------------------
# No-op client (no credentials) tests
# ---------------------------------------------------------------------------

class TestNoOpClientBehavior:
    """When Langfuse client has no real OTel tracer (no credentials), all
    instrumentation calls must be silent no-ops with no spurious warnings."""

    def _make_noop_client(self):
        """Return a MagicMock that simulates a disabled Langfuse client.

        A disabled client (no public_key) is set up with a NoOpTracer which
        means _get_current_otel_span returns None and update_current_span
        emits a warning. We test that _is_client_active returns False for it.
        """
        from opentelemetry.trace import NoOpTracer
        mock_client = MagicMock()
        mock_client._otel_tracer = NoOpTracer()
        # Simulate no 'api' attribute (early return in __init__ skips api setup)
        del mock_client.api
        return mock_client

    def test_is_client_active_returns_false_for_noop_tracer(self):
        """_is_client_active returns False when client has a NoOpTracer."""
        from opentelemetry.trace import NoOpTracer
        mock_client = MagicMock()
        mock_client._otel_tracer = NoOpTracer()
        assert langfuse_instrumentation._is_client_active(mock_client) is False

    def test_is_client_active_returns_true_for_real_tracer(self):
        """_is_client_active returns True when client has a non-NoOp tracer."""
        from opentelemetry.trace import NoOpTracer
        mock_client = MagicMock()
        # Real tracer is NOT a NoOpTracer
        mock_client._otel_tracer = MagicMock()
        assert langfuse_instrumentation._is_client_active(mock_client) is True

    def test_init_langfuse_trace_no_warning_when_client_inactive(self, monkeypatch, caplog):
        """init_langfuse_trace must not call update_current_span on a disabled client."""
        import logging
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-noop")
        noop_client = self._make_noop_client()

        with patch("langfuse_instrumentation.get_client", return_value=noop_client):
            with caplog.at_level(logging.WARNING):
                langfuse_instrumentation.init_langfuse_trace("/project")

        # update_current_span must NOT be called on a disabled client
        noop_client.update_current_span.assert_not_called()

    def test_init_langfuse_prompt_span_no_call_when_client_inactive(self, monkeypatch):
        """init_langfuse_prompt_span must not call update_current_span on a disabled client."""
        noop_client = self._make_noop_client()

        with patch("langfuse_instrumentation.get_client", return_value=noop_client):
            langfuse_instrumentation.init_langfuse_prompt_span("test prompt")

        noop_client.update_current_span.assert_not_called()

    def test_ensure_flush_still_called_when_client_inactive(self, monkeypatch):
        """ensure_flush calls flush() even on a disabled client (flush is always safe)."""
        noop_client = self._make_noop_client()

        with patch("langfuse_instrumentation.get_client", return_value=noop_client):
            langfuse_instrumentation.ensure_flush()

        noop_client.flush.assert_called_once()
