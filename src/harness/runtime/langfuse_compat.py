"""Langfuse v4 compatibility layer.

This module provides compatibility between Langfuse v3 API (langfuse_context)
and v4 API (client-based). It wraps the v4 client API to provide the v3 interface.
"""
from langfuse import get_client
from typing import Any, Dict, Optional, List


class LangfuseContextCompat:
    """Compatibility wrapper for Langfuse v3 langfuse_context API in v4.

    In Langfuse v3, langfuse_context was a module-level object that allowed
    updating the current trace/observation. In v4, this was removed in favor
    of using the client directly. This class provides backward compatibility.

    Usage:
        from harness.runtime.langfuse_compat import langfuse_context

        # Update current observation with model info
        langfuse_context.update_current_observation(model="gpt-4")

        # Update current trace with session and tags
        langfuse_context.update_current_trace(
            session_id="session-123",
            tags=["production", "v1"]
        )

        # Get current trace ID
        trace_id = langfuse_context.get_current_trace_id()
    """

    def __init__(self):
        """Initialize the compatibility wrapper with the Langfuse client."""
        self._client = get_client()

    def update_current_observation(
        self,
        model: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """Update the current observation (generation or span).

        In v4, this maps to update_current_generation() which supports the model parameter.

        Args:
            model: The model name being used (e.g., "gpt-4", "claude-3-sonnet")
            input: Input to the observation
            output: Output from the observation
            metadata: Additional metadata as a dictionary
            **kwargs: Additional arguments passed to update_current_generation
        """
        self._client.update_current_generation(
            model=model,
            input=input,
            output=output,
            metadata=metadata,
            **kwargs
        )

    def update_current_trace(
        self,
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """Update the current trace.

        In v4, there's no update_current_trace(). Instead, we use update_current_span()
        to update the root span of the current trace, and pass session_id and tags
        as part of the metadata.

        Args:
            session_id: Session ID for this trace
            tags: List of tags for this trace
            metadata: Additional metadata as a dictionary
            **kwargs: Additional arguments passed to update_current_span
        """
        # Merge all metadata
        merged_metadata = metadata or {}
        if session_id is not None:
            merged_metadata['session_id'] = session_id
        if tags is not None:
            merged_metadata['tags'] = tags

        # Update the current span (which is the root of the trace)
        self._client.update_current_span(
            metadata=merged_metadata,
            **kwargs
        )

    def get_current_trace_id(self) -> Optional[str]:
        """Get the ID of the current trace.

        Returns:
            The current trace ID, or None if no trace is active
        """
        return self._client.get_current_trace_id()

    def get_current_observation_id(self) -> Optional[str]:
        """Get the ID of the current observation.

        Returns:
            The current observation ID, or None if no observation is active
        """
        return self._client.get_current_observation_id()

    def flush(self) -> None:
        """Flush any pending events to Langfuse.

        In v4, the client automatically batches and sends events asynchronously.
        This method ensures any pending events are sent before the application exits.
        """
        self._client.flush()


# Global instance for compatibility
langfuse_context = LangfuseContextCompat()
