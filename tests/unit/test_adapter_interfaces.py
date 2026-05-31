"""S2-T3/S2-T4: Interface segregation tests for RuntimeAdapter and PlatformBuilder.

Asserts that:
1. ``RuntimeAdapter`` and ``PlatformBuilder`` are concrete ABCs exposing exactly
   the intended abstract methods.
2. ``PlatformAdapter`` is a subclass of both (multiple inheritance).
3. ``get_adapter("claude")`` / ``get_adapter("gemini")`` instances are
   ``isinstance`` of both ``RuntimeAdapter`` and ``PlatformBuilder``.
4. A successful ``get_adapter()`` call implicitly proves all abstract methods
   are implemented (Python raises TypeError on instantiation if any abstract
   method is unfulfilled).
5. (S2-T4) ``assemble_layout`` is the canonical implementation; the legacy
   ``generate_core_infrastructure`` shim delegates to it (relationship was
   inverted from the S2-T3 direction).
"""

from __future__ import annotations

import inspect
from abc import ABC
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from harness.adapters.base import PlatformAdapter, PlatformBuilder, RuntimeAdapter
from harness.adapters import get_adapter


# ---------------------------------------------------------------------------
# Expected method sets
# ---------------------------------------------------------------------------

# Methods that live on RuntimeAdapter (ship into the plugin, stdlib-only)
RUNTIME_ABSTRACT_METHODS = frozenset({
    "format_hook_response",
    "get_tool_mappings",
    "format_skill_invocation",
    "format_subagent_invocation",
    "get_subagent_text_call",
    "format_subagent_prompt",
})

# Platform-identity accessors that also live on RuntimeAdapter (runtime slice
# needs config_dir / env_var to load plugin assets at runtime).
RUNTIME_IDENTITY_METHODS = frozenset({
    "get_platform_name",
    "get_config_dir_name",
    "get_plugin_env_var_name",
})

# All abstract methods on RuntimeAdapter
RUNTIME_ALL_ABSTRACT = RUNTIME_ABSTRACT_METHODS | RUNTIME_IDENTITY_METHODS

# Methods that live on PlatformBuilder (mint-time structure/process)
BUILDER_ABSTRACT_METHODS = frozenset({
    "assemble_layout",      # NEW alias; delegates to generate_core_infrastructure by default
    "install_hooks",
    "configure_cli",
    "get_rules_pointer_files",
    "get_agent_manifest_format",
    "get_hook_directory",
})

ALL_PLATFORMS = ["claude", "gemini", "codex", "cursor", "generic"]


# ---------------------------------------------------------------------------
# 1. RuntimeAdapter is an ABC with exactly the expected abstract methods
# ---------------------------------------------------------------------------

class TestRuntimeAdapterContract:
    def test_is_abc(self):
        assert issubclass(RuntimeAdapter, ABC)

    def test_runtime_abstract_methods(self):
        """RuntimeAdapter must declare exactly the expected set of abstract methods."""
        actual = frozenset(RuntimeAdapter.__abstractmethods__)
        assert actual == RUNTIME_ALL_ABSTRACT, (
            f"RuntimeAdapter abstract methods mismatch.\n"
            f"  Expected: {sorted(RUNTIME_ALL_ABSTRACT)}\n"
            f"  Actual:   {sorted(actual)}"
        )

    def test_cannot_instantiate_directly(self):
        """RuntimeAdapter must be non-instantiable (abstract methods unfulfilled)."""
        with pytest.raises(TypeError):
            RuntimeAdapter()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 2. PlatformBuilder is an ABC with exactly the expected abstract methods
# ---------------------------------------------------------------------------

class TestPlatformBuilderContract:
    def test_is_abc(self):
        assert issubclass(PlatformBuilder, ABC)

    def test_builder_abstract_methods(self):
        """PlatformBuilder must declare exactly the expected set of abstract methods."""
        actual = frozenset(PlatformBuilder.__abstractmethods__)
        assert actual == BUILDER_ABSTRACT_METHODS, (
            f"PlatformBuilder abstract methods mismatch.\n"
            f"  Expected: {sorted(BUILDER_ABSTRACT_METHODS)}\n"
            f"  Actual:   {sorted(actual)}"
        )

    def test_cannot_instantiate_directly(self):
        """PlatformBuilder must be non-instantiable (abstract methods unfulfilled)."""
        with pytest.raises(TypeError):
            PlatformBuilder()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 3. PlatformAdapter composes RuntimeAdapter + PlatformBuilder
# ---------------------------------------------------------------------------

class TestPlatformAdapterComposition:
    def test_is_subclass_of_runtime_adapter(self):
        assert issubclass(PlatformAdapter, RuntimeAdapter)

    def test_is_subclass_of_platform_builder(self):
        assert issubclass(PlatformAdapter, PlatformBuilder)

    def test_is_subclass_of_abc(self):
        assert issubclass(PlatformAdapter, ABC)

    def test_mro_includes_both_bases(self):
        mro = PlatformAdapter.__mro__
        assert RuntimeAdapter in mro
        assert PlatformBuilder in mro

    def test_assemble_layout_is_concrete_on_platform_adapter(self):
        """PlatformAdapter.assemble_layout must be a concrete default (not abstract),
        so existing concretes don't need to implement it in this task."""
        # If assemble_layout were still abstract on PlatformAdapter, it would
        # appear in __abstractmethods__. It must NOT be there.
        remaining_abstract = getattr(PlatformAdapter, "__abstractmethods__", frozenset())
        assert "assemble_layout" not in remaining_abstract, (
            "assemble_layout must be a concrete default on PlatformAdapter, "
            "not remain abstract (would break existing concretes in this task)."
        )


# ---------------------------------------------------------------------------
# 4. Concrete adapters satisfy both interfaces
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("platform", ALL_PLATFORMS)
class TestConcreteAdaptersSatisfyInterfaces:
    def test_isinstance_runtime_adapter(self, platform):
        adapter = get_adapter(platform)
        assert isinstance(adapter, RuntimeAdapter), (
            f"{platform!r} adapter is not an instance of RuntimeAdapter"
        )

    def test_isinstance_platform_builder(self, platform):
        adapter = get_adapter(platform)
        assert isinstance(adapter, PlatformBuilder), (
            f"{platform!r} adapter is not an instance of PlatformBuilder"
        )

    def test_isinstance_platform_adapter(self, platform):
        adapter = get_adapter(platform)
        assert isinstance(adapter, PlatformAdapter), (
            f"{platform!r} adapter is not an instance of PlatformAdapter"
        )

    def test_all_runtime_methods_callable(self, platform):
        """Verify every RuntimeAdapter method is accessible and callable."""
        adapter = get_adapter(platform)
        for method_name in RUNTIME_ALL_ABSTRACT:
            assert hasattr(adapter, method_name), (
                f"{platform!r} adapter missing RuntimeAdapter method: {method_name!r}"
            )
            assert callable(getattr(adapter, method_name)), (
                f"{platform!r} adapter method {method_name!r} is not callable"
            )

    def test_all_builder_methods_callable(self, platform):
        """Verify every PlatformBuilder method is accessible and callable."""
        adapter = get_adapter(platform)
        for method_name in BUILDER_ABSTRACT_METHODS:
            assert hasattr(adapter, method_name), (
                f"{platform!r} adapter missing PlatformBuilder method: {method_name!r}"
            )
            assert callable(getattr(adapter, method_name)), (
                f"{platform!r} adapter method {method_name!r} is not callable"
            )


# ---------------------------------------------------------------------------
# 5. assemble_layout / generate_core_infrastructure delegation
# ---------------------------------------------------------------------------

class TestAssembleLayoutBackwardCompat:
    """S2-T4: assemble_layout has the real implementation; generate_core_infrastructure
    is a backward-compatible shim that delegates to assemble_layout.

    Previously (S2-T3) assemble_layout delegated to generate_core_infrastructure.
    That relationship was inverted in S2-T4 so that assemble_layout is now the
    canonical entry point and generate_core_infrastructure remains callable for
    legacy callers.
    """

    @pytest.mark.parametrize("platform", ALL_PLATFORMS)
    def test_assemble_layout_exists(self, platform):
        adapter = get_adapter(platform)
        assert hasattr(adapter, "assemble_layout")
        assert callable(adapter.assemble_layout)

    def test_generate_core_infrastructure_delegates_to_assemble_layout(self, tmp_path):
        """Calling generate_core_infrastructure(path) on the claude adapter must invoke
        assemble_layout(path) — the S2-T4 inversion of the S2-T3 delegation."""
        adapter = get_adapter("claude")

        calls = []

        original = adapter.assemble_layout

        def spy(project_path: Path):
            calls.append(project_path)
            return original(project_path)

        adapter.assemble_layout = spy  # type: ignore[method-assign]
        adapter.generate_core_infrastructure(tmp_path)

        assert len(calls) == 1, (
            "generate_core_infrastructure must call assemble_layout exactly once"
        )
        assert calls[0] == tmp_path
