"""S2-T5: Registry-based adapter factory tests.

Validates:
1. ``get_builder(platform)`` returns a ``PlatformBuilder`` instance for known platforms.
2. ``get_runtime_adapter(platform)`` returns a ``RuntimeAdapter`` instance for known platforms.
3. Unknown platform (e.g. ``"openai"``) defaults to ``GenericAdapter`` for both accessors.
4. Regression: ``get_adapter`` still returns the same concrete types as before.
5. Both ``get_builder`` and ``get_runtime_adapter`` return the same underlying concrete
   instance type (because all concretes implement both interfaces today).
"""

from __future__ import annotations

import pytest

from harness.adapters import get_adapter, get_builder, get_runtime_adapter
from harness.adapters.base import PlatformAdapter, PlatformBuilder, RuntimeAdapter
from harness.adapters.claude import ClaudeAdapter
from harness.adapters.gemini import GeminiAdapter
from harness.adapters.codex import CodexAdapter
from harness.adapters.cursor import CursorAdapter
from harness.adapters.generic import GenericAdapter


# ---------------------------------------------------------------------------
# get_builder
# ---------------------------------------------------------------------------

class TestGetBuilder:
    """get_builder(platform) -> PlatformBuilder"""

    def test_claude_returns_platform_builder(self):
        b = get_builder("claude")
        assert isinstance(b, PlatformBuilder)

    def test_claude_returns_claude_adapter(self):
        b = get_builder("claude")
        assert isinstance(b, ClaudeAdapter)

    def test_gemini_returns_platform_builder(self):
        b = get_builder("gemini")
        assert isinstance(b, PlatformBuilder)
        assert isinstance(b, GeminiAdapter)

    def test_codex_returns_platform_builder(self):
        b = get_builder("codex")
        assert isinstance(b, PlatformBuilder)
        assert isinstance(b, CodexAdapter)

    def test_cursor_returns_platform_builder(self):
        b = get_builder("cursor")
        assert isinstance(b, PlatformBuilder)
        assert isinstance(b, CursorAdapter)

    def test_generic_returns_platform_builder(self):
        b = get_builder("generic")
        assert isinstance(b, PlatformBuilder)
        assert isinstance(b, GenericAdapter)

    def test_unknown_platform_defaults_to_generic(self):
        """Unknown platforms fall back to GenericAdapter (embedded builder)."""
        b = get_builder("openai")
        assert isinstance(b, PlatformBuilder)
        assert isinstance(b, GenericAdapter)

    def test_case_insensitive(self):
        b = get_builder("CLAUDE")
        assert isinstance(b, ClaudeAdapter)


# ---------------------------------------------------------------------------
# get_runtime_adapter
# ---------------------------------------------------------------------------

class TestGetRuntimeAdapter:
    """get_runtime_adapter(platform) -> RuntimeAdapter"""

    def test_gemini_returns_runtime_adapter(self):
        r = get_runtime_adapter("gemini")
        assert isinstance(r, RuntimeAdapter)

    def test_gemini_returns_gemini_adapter(self):
        r = get_runtime_adapter("gemini")
        assert isinstance(r, GeminiAdapter)

    def test_claude_returns_runtime_adapter(self):
        r = get_runtime_adapter("claude")
        assert isinstance(r, RuntimeAdapter)
        assert isinstance(r, ClaudeAdapter)

    def test_codex_returns_runtime_adapter(self):
        r = get_runtime_adapter("codex")
        assert isinstance(r, RuntimeAdapter)
        assert isinstance(r, CodexAdapter)

    def test_cursor_returns_runtime_adapter(self):
        r = get_runtime_adapter("cursor")
        assert isinstance(r, RuntimeAdapter)
        assert isinstance(r, CursorAdapter)

    def test_generic_returns_runtime_adapter(self):
        r = get_runtime_adapter("generic")
        assert isinstance(r, RuntimeAdapter)
        assert isinstance(r, GenericAdapter)

    def test_unknown_platform_defaults_to_generic(self):
        """Unknown platforms fall back to GenericAdapter."""
        r = get_runtime_adapter("openai")
        assert isinstance(r, RuntimeAdapter)
        assert isinstance(r, GenericAdapter)

    def test_case_insensitive(self):
        r = get_runtime_adapter("GEMINI")
        assert isinstance(r, GeminiAdapter)


# ---------------------------------------------------------------------------
# get_adapter regression (contract must be unchanged)
# ---------------------------------------------------------------------------

class TestGetAdapterRegression:
    """Existing callers must still work identically after the registry refactor."""

    @pytest.mark.parametrize("platform,expected_cls", [
        ("claude", ClaudeAdapter),
        ("gemini", GeminiAdapter),
        ("codex", CodexAdapter),
        ("cursor", CursorAdapter),
        ("generic", GenericAdapter),
    ])
    def test_known_platforms_return_correct_type(self, platform, expected_cls):
        a = get_adapter(platform)
        assert isinstance(a, expected_cls)
        assert isinstance(a, PlatformAdapter)

    def test_unknown_platform_returns_generic_adapter(self):
        """Unknown platform → GenericAdapter (unchanged from original else-branch)."""
        a = get_adapter("openai")
        assert isinstance(a, GenericAdapter)

    def test_case_insensitive(self):
        a = get_adapter("CLAUDE")
        assert isinstance(a, ClaudeAdapter)

    def test_returns_platform_adapter_subclass(self):
        """All results are PlatformAdapter (RuntimeAdapter + PlatformBuilder)."""
        for platform in ("claude", "gemini", "codex", "cursor"):
            a = get_adapter(platform)
            assert isinstance(a, PlatformAdapter), f"{platform} should be PlatformAdapter"
            assert isinstance(a, RuntimeAdapter), f"{platform} should be RuntimeAdapter"
            assert isinstance(a, PlatformBuilder), f"{platform} should be PlatformBuilder"
