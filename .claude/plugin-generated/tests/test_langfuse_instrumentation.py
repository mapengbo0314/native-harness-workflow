"""
Tests for langfuse_instrumentation.py

TDD flow: RED (failing) → GREEN (passing) → REFACTOR

Tests mock langfuse_instrumentation.langfuse_context (the already-bound name
in the module under test) to avoid real API calls.
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

        with patch("langfuse_instrumentation.langfuse_context"):
            langfuse_instrumentation.init_langfuse_trace("/some/project")

        trace_id = os.environ.get("LANGFUSE_TRACE_ID")
        assert trace_id is not None
        # Must be a valid UUID
        uuid.UUID(trace_id)

    def test_sets_langfuse_session_id_env_var(self, monkeypatch):
        """init_langfuse_trace must set LANGFUSE_SESSION_ID from session ID."""
        monkeypatch.delenv("LANGFUSE_SESSION_ID", raising=False)
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-abc")

        with patch("langfuse_instrumentation.langfuse_context"):
            langfuse_instrumentation.init_langfuse_trace("/my/project")

        assert os.environ.get("LANGFUSE_SESSION_ID") == "test-session-abc"

    def test_calls_update_current_trace_with_correct_args(self, monkeypatch):
        """init_langfuse_trace calls langfuse_context.update_current_trace with session_id, name, metadata."""
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-xyz")

        with patch("langfuse_instrumentation.langfuse_context") as mock_ctx:
            langfuse_instrumentation.init_langfuse_trace("/workspace/myproject")

            mock_ctx.update_current_trace.assert_called_once_with(
                session_id="test-session-xyz",
                name="UserPromptSubmit",
                metadata={"project": "/workspace/myproject"},
            )

    def test_overwrites_existing_trace_id_with_fresh_uuid(self, monkeypatch):
        """If LANGFUSE_TRACE_ID is already set, it should be replaced with a fresh uuid."""
        monkeypatch.setenv("LANGFUSE_TRACE_ID", "existing-id")
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-1")

        with patch("langfuse_instrumentation.langfuse_context"):
            langfuse_instrumentation.init_langfuse_trace("/project")

        # A new uuid4 should have replaced the old one
        new_id = os.environ.get("LANGFUSE_TRACE_ID")
        assert new_id != "existing-id"
        uuid.UUID(new_id)  # Must be valid UUID

    def test_graceful_on_langfuse_error(self, monkeypatch):
        """init_langfuse_trace must not raise even if langfuse_context throws."""
        monkeypatch.setenv("HARNESS_SESSION_ID", "test-session-err")

        with patch("langfuse_instrumentation.langfuse_context") as mock_ctx:
            mock_ctx.update_current_trace.side_effect = RuntimeError("Langfuse down")
            # Should not propagate
            langfuse_instrumentation.init_langfuse_trace("/project")


# ---------------------------------------------------------------------------
# init_langfuse_prompt_span tests
# ---------------------------------------------------------------------------

class TestInitLangfusePromptSpan:
    def test_calls_update_current_observation_with_name_and_input(self, monkeypatch):
        """init_langfuse_prompt_span calls update_current_observation(name='prompt', input=prompt_text)."""
        prompt_text = "Fix the broken authentication logic"

        with patch("langfuse_instrumentation.langfuse_context") as mock_ctx:
            langfuse_instrumentation.init_langfuse_prompt_span(prompt_text)

            mock_ctx.update_current_observation.assert_called_once_with(
                name="prompt",
                input=prompt_text,
            )

    def test_handles_empty_prompt(self, monkeypatch):
        """init_langfuse_prompt_span works with an empty string."""
        with patch("langfuse_instrumentation.langfuse_context") as mock_ctx:
            langfuse_instrumentation.init_langfuse_prompt_span("")

            mock_ctx.update_current_observation.assert_called_once_with(
                name="prompt",
                input="",
            )

    def test_graceful_on_langfuse_error(self, monkeypatch):
        """init_langfuse_prompt_span must not raise even if langfuse_context throws."""
        with patch("langfuse_instrumentation.langfuse_context") as mock_ctx:
            mock_ctx.update_current_observation.side_effect = RuntimeError("Langfuse down")
            langfuse_instrumentation.init_langfuse_prompt_span("some prompt")


# ---------------------------------------------------------------------------
# ensure_flush tests
# ---------------------------------------------------------------------------

class TestEnsureFlush:
    def test_calls_langfuse_context_flush(self, monkeypatch):
        """ensure_flush calls langfuse_context.flush() exactly once."""
        with patch("langfuse_instrumentation.langfuse_context") as mock_ctx:
            langfuse_instrumentation.ensure_flush()

            mock_ctx.flush.assert_called_once()

    def test_graceful_on_langfuse_error(self, monkeypatch):
        """ensure_flush must not raise even if langfuse_context.flush() throws."""
        with patch("langfuse_instrumentation.langfuse_context") as mock_ctx:
            mock_ctx.flush.side_effect = RuntimeError("Langfuse flush failed")
            langfuse_instrumentation.ensure_flush()  # Must not propagate
