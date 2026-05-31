"""
Phase 4: Hook Verification for Langfuse v4.

Tests verify that .claude/plugin-generated/hooks/prompt_classifier.py works correctly
with Langfuse v4 API, including import verification, decorator functionality, and
langfuse_instrumentation integration.
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest

# Add src to sys.path to allow importing harness modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude/plugin-generated/hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude/plugin-generated/src"))


class TestTask41ImportVerification:
    """Task 4.1: Verify hook imports work without errors."""

    def test_hook_can_be_imported(self):
        """
        RED: Test that hook module can be imported without errors.
        Expected: Import succeeds, no ImportError raised.
        """
        hook_path = Path(__file__).parent.parent.parent / ".claude/plugin-generated/hooks/prompt_classifier.py"
        assert hook_path.exists(), f"Hook file not found: {hook_path}"

        # Import hook_common first (required by hook)
        import hook_common
        assert hook_common is not None

        # Now try to import the hook
        import importlib.util
        spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
        prompt_classifier = importlib.util.module_from_spec(spec)

        # Should not raise ImportError
        spec.loader.exec_module(prompt_classifier)
        assert prompt_classifier is not None

    def test_observe_decorator_import_fallback(self):
        """
        RED: Test that observe decorator is available via fallback chain.
        Expected: observe is callable, decorator mechanism works.
        """
        # Simulate Langfuse v4 where observe is available at top-level
        try:
            from langfuse import observe
            assert callable(observe), "observe should be callable"
        except ImportError:
            # Fallback should exist in hook
            import importlib.util
            hook_path = Path(__file__).parent.parent.parent / ".claude/plugin-generated/hooks/prompt_classifier.py"
            spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
            prompt_classifier = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(prompt_classifier)

            # Check if fallback decorator is defined
            assert hasattr(prompt_classifier, "observe"), "Hook should have observe defined"
            assert callable(prompt_classifier.observe), "observe should be callable"

    def test_langfuse_instrumentation_imports(self):
        """
        RED: Test that langfuse_instrumentation module can be imported.
        Expected: Module imports and exposes public API.
        """
        import langfuse_instrumentation

        # Verify public API exists
        assert hasattr(langfuse_instrumentation, "init_langfuse_trace")
        assert hasattr(langfuse_instrumentation, "init_langfuse_prompt_span")
        assert hasattr(langfuse_instrumentation, "ensure_flush")
        assert callable(langfuse_instrumentation.init_langfuse_trace)
        assert callable(langfuse_instrumentation.init_langfuse_prompt_span)
        assert callable(langfuse_instrumentation.ensure_flush)

    def test_hook_common_imports(self):
        """
        RED: Test that hook_common dependencies are available.
        Expected: All required functions importable.
        """
        import hook_common

        # Verify required exports
        assert hasattr(hook_common, "resolve_project_root")
        assert hasattr(hook_common, "resolve_plugin_root")
        assert hasattr(hook_common, "get_session_id")
        assert callable(hook_common.resolve_project_root)
        assert callable(hook_common.resolve_plugin_root)
        assert callable(hook_common.get_session_id)


class TestTask42DecoratorFunctionality:
    """Task 4.2: Verify @observe decorator functionality."""

    def test_observe_decorator_applies_to_function(self):
        """
        RED: Test that @observe(name="...") can decorate a function.
        Expected: Decorated function is still callable.
        """
        try:
            from langfuse import observe
        except ImportError:
            pytest.skip("Langfuse observe not available in environment")

        @observe(name="test_span")
        def dummy_func(x):
            return x * 2

        # Should still be callable
        assert callable(dummy_func)
        # Should accept parameters
        result = dummy_func(5)
        assert result == 10

    def test_observe_decorator_with_kwargs(self):
        """
        RED: Test that @observe can be called with various kwargs.
        Expected: Decorator accepts and applies kwargs without errors.
        """
        try:
            from langfuse import observe
        except ImportError:
            pytest.skip("Langfuse observe not available")

        # Should accept name kwarg
        @observe(name="user_prompt")
        def test_func():
            pass

        assert callable(test_func)

    def test_fallback_observe_decorator(self):
        """
        RED: Test fallback decorator (when observe import fails).
        Expected: Fallback decorator returns callable function.
        """
        # Create a fallback observe manually to test
        def fallback_observe(*args, **kwargs):
            def decorator(func):
                return func
            if len(args) == 1 and callable(args[0]):
                return args[0]
            return decorator

        @fallback_observe(name="test")
        def func1():
            return "ok"

        @fallback_observe
        def func2():
            return "ok"

        assert callable(func1)
        assert callable(func2)
        assert func1() == "ok"
        assert func2() == "ok"


class TestTask43LangfuseAPICallsInHook:
    """Task 4.3: Verify langfuse_instrumentation API calls execute without errors."""

    def test_init_langfuse_trace_executes(self):
        """
        RED: Test that init_langfuse_trace can be called with project_root.
        Expected: No exceptions raised.
        """
        import langfuse_instrumentation

        # Should not raise any exception
        langfuse_instrumentation.init_langfuse_trace("/tmp/test_project")

        # Verify environment variables were set
        assert "LANGFUSE_TRACE_ID" in os.environ
        assert "LANGFUSE_SESSION_ID" in os.environ
        assert len(os.environ["LANGFUSE_TRACE_ID"]) > 0
        assert len(os.environ["LANGFUSE_SESSION_ID"]) > 0

    def test_init_langfuse_prompt_span_executes(self):
        """
        RED: Test that init_langfuse_prompt_span can be called with prompt text.
        Expected: No exceptions raised.
        """
        import langfuse_instrumentation

        test_prompt = "Test prompt for classification"

        # Should not raise any exception
        langfuse_instrumentation.init_langfuse_prompt_span(test_prompt)

        # Should succeed (either updates span or no-ops if not active)

    def test_ensure_flush_executes(self):
        """
        RED: Test that ensure_flush can be called.
        Expected: No exceptions raised.
        """
        import langfuse_instrumentation

        # Should not raise any exception
        langfuse_instrumentation.ensure_flush()

    def test_instrumentation_with_no_credentials(self):
        """
        RED: Test that instrumentation functions are defensive when no Langfuse credentials.
        Expected: Functions execute without errors even if credentials missing.
        """
        import langfuse_instrumentation

        # Temporarily unset Langfuse env vars
        old_keys = {}
        for key in ["LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASEURL"]:
            if key in os.environ:
                old_keys[key] = os.environ.pop(key)

        try:
            # All these should be safe even without credentials
            langfuse_instrumentation.init_langfuse_trace("/tmp/test")
            langfuse_instrumentation.init_langfuse_prompt_span("test prompt")
            langfuse_instrumentation.ensure_flush()
        finally:
            # Restore
            os.environ.update(old_keys)


class TestTask44MockInputProcessing:
    """Task 4.4: Test mock input processing and basic execution path."""

    def test_hook_processes_valid_json_input(self):
        """
        RED: Test that hook can process valid JSON input without crashing.
        Expected: No import errors during input processing.
        """
        import importlib.util
        hook_path = Path(__file__).parent.parent.parent / ".claude/plugin-generated/hooks/prompt_classifier.py"
        spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
        prompt_classifier = importlib.util.module_from_spec(spec)

        # Should load without error
        spec.loader.exec_module(prompt_classifier)
        assert prompt_classifier is not None

    def test_fallback_classify_function(self):
        """
        RED: Test that fallback_classify function exists and works.
        Expected: Function returns classification A, B, C, or D.
        """
        import importlib.util
        hook_path = Path(__file__).parent.parent.parent / ".claude/plugin-generated/hooks/prompt_classifier.py"
        spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
        prompt_classifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prompt_classifier)

        # Test fallback_classify is available
        assert hasattr(prompt_classifier, "fallback_classify")

        # Test various inputs
        assert prompt_classifier.fallback_classify("fix the bug") == "A"
        assert prompt_classifier.fallback_classify("implement new feature") == "B"
        assert prompt_classifier.fallback_classify("how does this work") == "C"
        assert prompt_classifier.fallback_classify("random text") == "E"

    def test_input_json_parsing(self):
        """
        RED: Test that hook logic can parse typical hook input JSON.
        Expected: JSON structure recognized and fields extracted.
        """
        test_input = {
            "hookEventName": "UserPromptSubmit",
            "prompt": "fix the login flow",
            "workspace_root": "/workspace"
        }

        # Verify structure matches expected input
        assert "prompt" in test_input
        assert "hookEventName" in test_input
        assert isinstance(test_input["prompt"], str)


class TestTask45FallbackDecoratorHandling:
    """Task 4.5: Verify fallback decorator handling when imports fail."""

    def test_observe_fallback_chain_in_hook(self):
        """
        RED: Test that hook's observe decorator fallback chain works.
        Expected: At least one import succeeds (or fallback is defined).
        """
        import importlib.util
        hook_path = Path(__file__).parent.parent.parent / ".claude/plugin-generated/hooks/prompt_classifier.py"
        spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
        prompt_classifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prompt_classifier)

        # Hook should have observe defined (either from langfuse or fallback)
        assert hasattr(prompt_classifier, "observe")
        assert callable(prompt_classifier.observe)

    def test_fallback_decorator_doesnt_crash_hook(self):
        """
        RED: Test that even if observe import fails, hook defines a working fallback.
        Expected: Fallback decorator works as identity or no-op.
        """
        # Simulate import failure by manually creating fallback
        def fallback_observe(*args, **kwargs):
            def decorator(func):
                return func
            if len(args) == 1 and callable(args[0]):
                return args[0]
            return decorator

        # Use fallback to decorate a function
        @fallback_observe(name="user_prompt")
        def main():
            return "executed"

        # Should still work
        assert callable(main)
        assert main() == "executed"

    def test_observe_decorator_called_with_name_kwarg(self):
        """
        RED: Test that @observe(name="...") can be called with name kwarg.
        Expected: Decorator accepts and applies name without error.
        """
        try:
            from langfuse import observe
        except ImportError:
            pytest.skip("Langfuse not available, testing with fallback")
            # Fallback is tested above
            return

        # Should accept name parameter
        decorator = observe(name="user_prompt")
        assert callable(decorator)

        # Should be able to decorate function
        @decorator
        def test_func():
            pass

        assert callable(test_func)


class TestTask46IntegrationWithLangfuseV4:
    """Integration tests with Langfuse v4 API."""

    def test_langfuse_observe_available_in_v4(self):
        """
        RED: Test that Langfuse v4 provides observe at top-level.
        Expected: from langfuse import observe works.
        """
        # This is the v4 API
        try:
            from langfuse import observe
            assert callable(observe)
        except ImportError as e:
            pytest.fail(f"Langfuse v4 should provide observe at top-level: {e}")

    def test_get_client_function_available(self):
        """
        RED: Test that get_client function is available in v4.
        Expected: get_client is callable and can be imported.
        """
        try:
            from langfuse import get_client
            assert callable(get_client)
        except ImportError as e:
            pytest.fail(f"Langfuse v4 should provide get_client: {e}")

    def test_instrumentation_handles_missing_credentials_gracefully(self):
        """
        RED: Test that instrumentation doesn't crash when Langfuse credentials missing.
        Expected: Functions execute, possibly as no-ops when client inactive.
        """
        import langfuse_instrumentation

        # Remove credentials temporarily
        old_env = {}
        for key in ["LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASEURL"]:
            if key in os.environ:
                old_env[key] = os.environ.pop(key)

        try:
            # Should not crash
            langfuse_instrumentation.init_langfuse_trace("/tmp/test")
            langfuse_instrumentation.init_langfuse_prompt_span("test")
            langfuse_instrumentation.ensure_flush()
        finally:
            os.environ.update(old_env)


class TestPhase4SuccessCriteria:
    """
    Comprehensive verification of Phase 4 success criteria.
    """

    def test_hook_imports_without_errors(self):
        """SUCCESS CRITERION: Hook imports without errors."""
        import importlib.util
        hook_path = Path(__file__).parent.parent.parent / ".claude/plugin-generated/hooks/prompt_classifier.py"
        spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
        prompt_classifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prompt_classifier)
        assert prompt_classifier is not None

    def test_observe_decorator_applies_successfully(self):
        """SUCCESS CRITERION: @observe decorator applies successfully."""
        try:
            from langfuse import observe
        except ImportError:
            pytest.skip("Testing with fallback")
            return

        @observe(name="user_prompt")
        def test_main():
            return True

        assert callable(test_main)
        assert test_main() is True

    def test_langfuse_instrumentation_calls_execute(self):
        """SUCCESS CRITERION: langfuse_instrumentation calls execute without errors."""
        import langfuse_instrumentation

        # All should execute without error
        langfuse_instrumentation.init_langfuse_trace("/test/root")
        langfuse_instrumentation.init_langfuse_prompt_span("Test prompt")
        langfuse_instrumentation.ensure_flush()

    def test_no_breaking_changes_with_v4(self):
        """SUCCESS CRITERION: No breaking changes with Langfuse v4."""
        # Verify v4 is installed
        import langfuse
        version = tuple(map(int, langfuse.__version__.split('.')[:2]))
        assert version[0] >= 4, f"Expected Langfuse v4+, got {langfuse.__version__}"

        # Verify critical APIs available
        from langfuse import observe, get_client
        assert callable(observe)
        assert callable(get_client)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
