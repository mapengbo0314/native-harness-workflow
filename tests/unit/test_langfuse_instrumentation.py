import pytest
from unittest.mock import MagicMock, patch


def _make_active_client():
    """Return a mock Langfuse client that passes _is_client_active."""
    from opentelemetry.trace import NonRecordingSpan
    mock_tracer = MagicMock()
    mock_tracer.__class__ = type("RealTracer", (), {})  # not NoOpTracer
    client = MagicMock()
    client._otel_tracer = mock_tracer
    return client


class TestCompletePromptSpan:
    def test_calls_update_current_span_with_structured_output(self):
        client = _make_active_client()
        with patch("harness.runtime.langfuse_instrumentation.get_client", return_value=client), \
             patch.dict("os.environ", {"HARNESS_SESSION_ID": "test-session-abc"}):
            from harness.runtime.langfuse_instrumentation import complete_prompt_span
            complete_prompt_span(
                modified_prompt="hello + HARNESS DISPATCH",
                system_state="=== SYSTEM STATE ===\nBranch: B",
                routing_decision={"classification": "B", "phase": "Planning", "target_agent": "@planner"},
            )
        client.update_current_span.assert_called_once_with(
            output={
                "modified_prompt": "hello + HARNESS DISPATCH",
                "system_prompt_extension": "=== SYSTEM STATE ===\nBranch: B",
                "branch": "B",
                "phase": "Planning",
                "target_agent": "@planner",
                "session_id": "test-session-abc",
            }
        )

    def test_no_op_when_get_client_is_none(self):
        import harness.runtime.langfuse_instrumentation as lf_mod
        original = lf_mod.get_client
        try:
            lf_mod.get_client = None
            lf_mod.complete_prompt_span("p", "s", {})  # must not raise
        finally:
            lf_mod.get_client = original

    def test_no_op_when_client_inactive(self):
        from opentelemetry.trace import NoOpTracer
        client = MagicMock()
        client._otel_tracer = NoOpTracer()
        with patch("harness.runtime.langfuse_instrumentation.get_client", return_value=client):
            from harness.runtime.langfuse_instrumentation import complete_prompt_span
            complete_prompt_span("p", "s", {"classification": "B", "phase": "P", "target_agent": "t"})
        client.update_current_span.assert_not_called()

    def test_missing_routing_keys_use_none(self):
        client = _make_active_client()
        with patch("harness.runtime.langfuse_instrumentation.get_client", return_value=client), \
             patch.dict("os.environ", {"HARNESS_SESSION_ID": "test-session-xyz"}):
            from harness.runtime.langfuse_instrumentation import complete_prompt_span
            complete_prompt_span("p", "s", {})
        client.update_current_span.assert_called_once_with(
            output={
                "modified_prompt": "p",
                "system_prompt_extension": "s",
                "branch": None,
                "phase": None,
                "target_agent": None,
                "session_id": "test-session-xyz",
            }
        )

    def test_exception_from_update_is_swallowed(self):
        client = _make_active_client()
        client.update_current_span.side_effect = RuntimeError("langfuse exploded")
        with patch("harness.runtime.langfuse_instrumentation.get_client", return_value=client):
            from harness.runtime.langfuse_instrumentation import complete_prompt_span
            # Must not raise
            complete_prompt_span("p", "s", {"classification": "B", "phase": "P", "target_agent": "t"})
