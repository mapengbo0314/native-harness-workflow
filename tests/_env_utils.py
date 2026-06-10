"""Shared env scrubbing for tests that spawn hook/CLI subprocesses.

Test subprocesses inherit os.environ — including real Langfuse credentials
loaded from .env — so they must run with telemetry disabled AND creds removed
(removing creds is the robust half: it survives the SDK renaming its
kill-switch flag again, which is exactly what happened between langfuse v2
(LANGFUSE_ENABLED) and v3+/v4 (LANGFUSE_TRACING_ENABLED))."""
from __future__ import annotations

import os

_LANGFUSE_CRED_VARS = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "HARNESS_GLOBAL_INGESTION_BASE64",
)


def telemetry_safe_env(base: dict | None = None) -> dict:
    """Return a copy of *base* (default os.environ) that cannot export telemetry."""
    env = dict(os.environ if base is None else base)
    for key in _LANGFUSE_CRED_VARS:
        env.pop(key, None)
    env["LANGFUSE_ENABLED"] = "false"           # harness compat gate (langfuse_compat.py)
    env["LANGFUSE_TRACING_ENABLED"] = "false"   # langfuse v3+/v4 SDK kill-switch
    return env
