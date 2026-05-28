"""
langfuse_instrumentation.py

Central module for Langfuse lifecycle management.

Responsibilities:
- init_langfuse_trace(project_root)  — Set up session-level trace using
  CLAUDE_SESSION_ID or GEMINI_SESSION_ID from environment.
- init_langfuse_prompt_span(prompt_text) — Create a named child span for the
  current prompt.
- ensure_flush() — Flush Langfuse traces explicitly.
- _get_session_id() — Extract session ID with priority:
    HARNESS_SESSION_ID → CLAUDE_SESSION_ID → GEMINI_SESSION_ID → str(os.getppid())

Inputs:
  project_root (str): Absolute path to the project root directory.
  prompt_text (str): The raw user prompt text.

Outputs:
  Side effects only — sets LANGFUSE_TRACE_ID and LANGFUSE_SESSION_ID env vars,
  calls langfuse client methods.

Failure modes:
  All public functions are defensively wrapped; Langfuse errors are swallowed
  to prevent hook failures from breaking the main prompt pipeline.

Compatibility: Langfuse v4+. Uses `langfuse.get_client()` and `langfuse.observe`.
  The `langfuse.decorators` module was removed in v4; this module uses the v4 API.
"""

import os
import uuid
from typing import Any

try:
    from langfuse import get_client
except ImportError:
    get_client = None  # type: ignore[assignment]

try:
    from opentelemetry.trace import NoOpTracer as _NoOpTracer
    NoOpTracer = _NoOpTracer
except ImportError:
    NoOpTracer = None  # type: ignore[assignment,misc]


def _is_client_active(client: Any) -> bool:
    """Return True if the Langfuse client has a real OTel tracer.

    A disabled client (no credentials) is initialized with a ``NoOpTracer``
    and returns early from ``__init__`` before setting up the OTLP exporter.
    Calling ``update_current_span`` on such a client produces a spurious
    "No active span in current context" warning because the ``NoOpTracer``
    never places a span into the OTel context.

    Inputs:
        client: A Langfuse client instance (or any object).

    Returns:
        True  — client has a functional tracer and update_current_span works.
        False — client is in no-op mode (missing credentials); skip span calls.
    """
    if NoOpTracer is None:
        return False
    otel_tracer = getattr(client, "_otel_tracer", None)
    if otel_tracer is None:
        return False
    return not isinstance(otel_tracer, NoOpTracer)


def _get_session_id() -> str:
    """Return a platform-agnostic session identifier.

    Priority order:
    1. HARNESS_SESSION_ID  — explicit test/manual override
    2. CLAUDE_SESSION_ID   — provided by Claude Code at hook runtime
    3. GEMINI_SESSION_ID   — provided by Gemini CLI
    4. str(os.getppid())   — reliable fallback for persistent CLI runs
    """
    if "HARNESS_SESSION_ID" in os.environ:
        return os.environ["HARNESS_SESSION_ID"]
    if "CLAUDE_SESSION_ID" in os.environ:
        return os.environ["CLAUDE_SESSION_ID"]
    if "GEMINI_SESSION_ID" in os.environ:
        return os.environ["GEMINI_SESSION_ID"]
    return str(os.getppid())


def init_langfuse_trace(project_root: str) -> None:
    """Set up a session-level trace for the current prompt submission.

    Sets:
        LANGFUSE_TRACE_ID  — fresh uuid4 for this prompt
        LANGFUSE_SESSION_ID — session identifier from environment

    Calls (Langfuse v4):
        lf.update_current_span(
            metadata={"project": project_root, "session_id": session_id}
        )

    Failure mode: Langfuse errors are caught and swallowed so that the hook
    pipeline is never interrupted by observability failures.
    """
    trace_id = str(uuid.uuid4())
    os.environ["LANGFUSE_TRACE_ID"] = trace_id

    session_id = _get_session_id()
    os.environ["LANGFUSE_SESSION_ID"] = session_id

    try:
        lf = get_client()
        if _is_client_active(lf):
            lf.update_current_span(
                metadata={"project": project_root, "session_id": session_id},
            )
    except Exception:
        pass


def init_langfuse_prompt_span(prompt_text: str) -> None:
    """Create a named child span for the current user prompt.

    Calls (Langfuse v4):
        lf.update_current_span(name="prompt", input=prompt_text)

    Failure mode: Langfuse errors are caught and swallowed.
    """
    try:
        lf = get_client()
        if _is_client_active(lf):
            lf.update_current_span(
                name="prompt",
                input=prompt_text,
            )
    except Exception:
        pass


def ensure_flush() -> None:
    """Flush all pending Langfuse traces synchronously.

    Calls (Langfuse v4):
        lf.flush()

    Failure mode: Langfuse errors are caught and swallowed.
    """
    try:
        lf = get_client()
        lf.flush()
    except Exception:
        pass
