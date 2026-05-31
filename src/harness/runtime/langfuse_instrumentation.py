"""
Central module for Langfuse lifecycle management (Langfuse v4 API).

Public API:
- init_langfuse_trace(project_root)   — Set session ID + trace ID, update current span
- init_langfuse_prompt_span(prompt)   — Name the current span with prompt input
- complete_prompt_span(...)           — Log assembled dispatch payload as span output
- ensure_flush()                      — Flush all pending traces synchronously

All functions are defensively wrapped — Langfuse errors never interrupt the hook pipeline.
Span update calls are skipped when Langfuse has no credentials (NoOpTracer mode).
"""

import os
import uuid

try:
    from langfuse import get_client
except ImportError:
    get_client = None  # type: ignore[assignment]

try:
    from opentelemetry.trace import NoOpTracer as _NoOpTracer
    _NOOP_TRACER_TYPE = _NoOpTracer
except ImportError:
    _NOOP_TRACER_TYPE = None  # type: ignore[assignment,misc]


def _get_session_id() -> str:
    """Priority: HARNESS_SESSION_ID → CLAUDE_SESSION_ID → GEMINI_SESSION_ID → ppid."""
    if "HARNESS_SESSION_ID" in os.environ:
        return os.environ["HARNESS_SESSION_ID"]
    if "CLAUDE_SESSION_ID" in os.environ:
        return os.environ["CLAUDE_SESSION_ID"]
    if "GEMINI_SESSION_ID" in os.environ:
        return os.environ["GEMINI_SESSION_ID"]
    return str(os.getppid())


def _is_client_active(client) -> bool:
    """Return True only if the client has real credentials (not a NoOpTracer)."""
    if _NOOP_TRACER_TYPE is None:
        return False
    otel_tracer = getattr(client, "_otel_tracer", None)
    if otel_tracer is None:
        return False
    return not isinstance(otel_tracer, _NOOP_TRACER_TYPE)


def init_langfuse_trace(project_root: str) -> None:
    """Set LANGFUSE_TRACE_ID + LANGFUSE_SESSION_ID and update the current span metadata."""
    os.environ["LANGFUSE_TRACE_ID"] = str(uuid.uuid4())
    session_id = _get_session_id()
    os.environ["LANGFUSE_SESSION_ID"] = session_id

    if get_client is None:
        return
    try:
        lf = get_client()
        if _is_client_active(lf):
            lf.update_current_span(
                metadata={"project": project_root, "session_id": session_id},
            )
    except Exception:
        pass


def init_langfuse_prompt_span(prompt_text: str) -> None:
    """Update the current observation with the prompt text as input."""
    if get_client is None:
        return
    try:
        lf = get_client()
        if _is_client_active(lf):
            lf.update_current_span(name="user_prompt", input=prompt_text)
    except Exception:
        pass


def complete_prompt_span(
    modified_prompt: str,
    system_state: str,
    routing_decision: dict,
) -> None:
    """Update the user_prompt span output with the assembled dispatch payload."""
    if get_client is None:
        return
    try:
        lf = get_client()
        if _is_client_active(lf):
            lf.update_current_span(
                output={
                    "modified_prompt": modified_prompt,
                    "system_prompt_extension": system_state,
                    "branch": routing_decision.get("classification"),
                    "phase": routing_decision.get("phase"),
                    "target_agent": routing_decision.get("target_agent"),
                }
            )
    except Exception:
        pass


def ensure_flush() -> None:
    """Flush all pending Langfuse traces synchronously."""
    if get_client is None:
        return
    try:
        get_client().flush()
    except Exception:
        pass
