from harness.adapters.base import PlatformAdapter, PlatformBuilder, RuntimeAdapter
from harness.adapters.claude import ClaudeAdapter
from harness.adapters.gemini import GeminiAdapter
from harness.adapters.codex import CodexAdapter
from harness.adapters.cursor import CursorAdapter
from harness.adapters.generic import GenericAdapter

# ---------------------------------------------------------------------------
# Platform registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[PlatformAdapter]] = {
    "claude": ClaudeAdapter,
    "gemini": GeminiAdapter,
    "codex": CodexAdapter,
    "cursor": CursorAdapter,
    "generic": GenericAdapter,
}

_DEFAULT_CLASS: type[PlatformAdapter] = GenericAdapter


def get_builder(platform: str) -> PlatformBuilder:
    """Return a ``PlatformBuilder`` for the given platform.

    Looks up the platform in the registry (case-insensitive).  Falls back to
    the embedded/generic builder (``GenericAdapter``) for unknown platforms.
    """
    cls = _REGISTRY.get(platform.lower(), _DEFAULT_CLASS)
    instance = cls()
    assert isinstance(instance, PlatformBuilder)
    return instance


def get_runtime_adapter(platform: str) -> RuntimeAdapter:
    """Return a ``RuntimeAdapter`` for the given platform.

    Looks up the platform in the registry (case-insensitive).  Falls back to
    ``GenericAdapter`` for unknown platforms.
    """
    cls = _REGISTRY.get(platform.lower(), _DEFAULT_CLASS)
    instance = cls()
    assert isinstance(instance, RuntimeAdapter)
    return instance


def get_adapter(platform_id: str) -> PlatformAdapter:
    """Return the instantiated adapter based on a logical identifier.

    The platform_id is expected to be a string like 'gemini', 'claude', etc.
    Unknown platforms default to ``GenericAdapter``.
    """
    cls = _REGISTRY.get(platform_id.lower(), _DEFAULT_CLASS)
    return cls()
