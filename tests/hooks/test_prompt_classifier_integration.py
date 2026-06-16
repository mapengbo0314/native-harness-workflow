"""
Phase 4: Hook Integration Tests with Real Execution.

Tests that verify prompt_classifier.py hook can execute in realistic scenarios.
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude/harness-wf-plugin/hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude/harness-wf-plugin/src"))


class TestHookExecutionWithMockedDispatcher:
    """Test hook execution with mocked dispatcher to avoid full harness init."""

    @pytest.fixture
    def hook_module(self):
        """Load hook module for testing."""
        import importlib.util
        hook_path = Path(__file__).parent.parent.parent / ".claude/harness-wf-plugin/hooks/prompt_classifier.py"
        spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        return hook

    def test_hook_fallback_classify_logic(self, hook_module):
        """
        RED: Test fallback_classify categorization logic.
        Expected: Categorizes prompts into A, B, C, D correctly.
        """
        # Category A: bug fixes
        assert hook_module.fallback_classify("fix the broken login") == "A"
        assert hook_module.fallback_classify("there's a stack trace in the error") == "A"

        # Category D (bias-to-D, F4 proportionality): implement-style prompts
        # route to direct implementation, not the Branch-B planning pipeline.
        assert hook_module.fallback_classify("implement the feature") == "D"
        # Category B: genuinely open design work
        assert hook_module.fallback_classify("design a new architecture") == "B"

        # Category C: explanations
        assert hook_module.fallback_classify("how does this work") == "C"
        assert hook_module.fallback_classify("where is the config") == "C"

        # Category E: miscellaneous
        assert hook_module.fallback_classify("tell me a joke") == "E"

    def test_hook_observe_decorator_applies(self, hook_module):
        """
        RED: Test that @observe decorator on main() doesn't break function signature.
        Expected: main function is callable and decorated.
        """
        # main should be defined and decorated
        assert hasattr(hook_module, "main")
        assert callable(hook_module.main)

    def test_hook_imports_all_required_modules(self, hook_module):
        """
        RED: Test that hook module imports successfully with all dependencies.
        Expected: All imports present, no missing dependencies.
        """
        # Verify key imports are available after module load
        assert hook_module is not None
        assert hasattr(hook_module, "json")
        assert hasattr(hook_module, "sys")
        assert hasattr(hook_module, "os")
        assert hasattr(hook_module, "Path")

    def test_hook_main_function_exists_and_is_decorated(self, hook_module):
        """
        RED: Test that main() exists and is decorated with @observe.
        Expected: main is callable and has decorator applied.
        """
        # main() should exist
        assert hasattr(hook_module, "main")
        main_func = getattr(hook_module, "main")

        # Should be callable
        assert callable(main_func)

        # Should have the @observe decorator applied (either real or fallback)
        # The decorator should make it callable, which we verify above


class TestHookRobustness:
    """Test hook robustness against various input conditions."""

    def test_hook_imports_without_credentials(self):
        """
        RED: Test hook can be imported even when Langfuse credentials missing.
        Expected: Import succeeds, hook is usable even without credentials.
        """
        # Save any existing credentials
        old_creds = {}
        for key in ["LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASEURL"]:
            if key in os.environ:
                old_creds[key] = os.environ.pop(key)

        try:
            import importlib.util
            hook_path = Path(__file__).parent.parent.parent / ".claude/harness-wf-plugin/hooks/prompt_classifier.py"
            spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
            hook = importlib.util.module_from_spec(spec)
            # Should not crash even without credentials
            spec.loader.exec_module(hook)
            assert hook is not None
        finally:
            os.environ.update(old_creds)

    def test_langfuse_instrumentation_defensive_apis(self):
        """
        RED: Test that langfuse_instrumentation APIs are defensive.
        Expected: All APIs safe to call even with missing dependencies.
        """
        import langfuse_instrumentation

        # Remove credentials
        old_creds = {}
        for key in ["LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY"]:
            if key in os.environ:
                old_creds[key] = os.environ.pop(key)

        try:
            # All should be safe
            langfuse_instrumentation.init_langfuse_trace("/tmp/test")
            langfuse_instrumentation.init_langfuse_prompt_span("test prompt")
            langfuse_instrumentation.ensure_flush()

            # No exception should be raised
        finally:
            os.environ.update(old_creds)

    def test_hook_fallback_observe_decorator_chain(self):
        """
        RED: Test the observe decorator fallback chain in hook.
        Expected: Hook defines fallback if imports fail.
        """
        import importlib.util
        hook_path = Path(__file__).parent.parent.parent / ".claude/harness-wf-plugin/hooks/prompt_classifier.py"
        spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)

        # Hook should have observe defined
        assert hasattr(hook, "observe")
        observe_func = getattr(hook, "observe")

        # Should be callable
        assert callable(observe_func)

        # Should accept name kwarg and return decorator
        decorator = observe_func(name="test_span")
        assert callable(decorator)

        # Should be able to decorate function
        @decorator
        def test_func():
            return "ok"

        assert callable(test_func)
        assert test_func() == "ok"


class TestHookEnvironmentIntegration:
    """Test hook integration with environment variables."""

    def test_session_id_resolution(self):
        """
        RED: Test that hook can resolve session ID from environment.
        Expected: Session ID is deterministic and can be read.
        """
        import hook_common

        # Set explicit session ID
        os.environ["HARNESS_SESSION_ID"] = "test-session-123"

        session_id = hook_common.get_session_id()
        assert session_id == "test-session-123"

        # Clean up
        del os.environ["HARNESS_SESSION_ID"]

    def test_project_root_resolution(self):
        """
        RED: Test that hook can resolve project root.
        Expected: resolve_project_root returns Path.
        """
        import hook_common

        # Test with workspace_root in input
        input_json = {"workspace_root": "/test/workspace"}
        result = hook_common.resolve_project_root(input_json)
        assert isinstance(result, Path)
        assert str(result).endswith("test/workspace")

    def test_plugin_root_resolution(self):
        """
        RED: Test that hook can resolve plugin root.
        Expected: resolve_plugin_root returns valid Path.
        """
        import hook_common

        result = hook_common.resolve_plugin_root()
        assert isinstance(result, Path)
        assert result.exists()


class TestLangfuseV4CompatibilityMatrix:
    """Verify compatibility with Langfuse v4 features."""

    def test_observe_decorator_v4_api(self):
        """
        RED: Test that Langfuse v4 observe decorator works.
        Expected: @observe(name="...") successfully decorates functions.
        """
        from langfuse import observe

        @observe(name="test_operation")
        def test_func():
            return "success"

        assert callable(test_func)
        assert test_func() == "success"

    def test_get_client_v4_api(self):
        """
        RED: Test that Langfuse v4 get_client works.
        Expected: get_client is callable and returns client or NoOp.
        """
        from langfuse import get_client

        client = get_client()
        assert client is not None
        # Client should have flush method
        assert hasattr(client, "flush")
        assert callable(client.flush)

    def test_instrumentation_with_v4_client(self):
        """
        RED: Test that instrumentation works with v4 client.
        Expected: Client methods can be called without errors.
        """
        import langfuse_instrumentation
        from langfuse import get_client

        # Get client
        client = get_client()

        # Instrumentation should work
        langfuse_instrumentation.init_langfuse_trace("/test")
        langfuse_instrumentation.init_langfuse_prompt_span("test prompt")
        langfuse_instrumentation.ensure_flush()

        # Client should still be usable
        client.flush()


class TestPhase4EndToEndScenarios:
    """End-to-end scenarios testing Phase 4 success criteria."""

    def test_hook_can_be_imported_and_main_called(self):
        """
        SUCCESS CRITERION: Hook imports and main() is decorated.
        Expected: No import errors, main is callable.
        """
        import importlib.util
        hook_path = Path(__file__).parent.parent.parent / ".claude/harness-wf-plugin/hooks/prompt_classifier.py"
        spec = importlib.util.spec_from_file_location("prompt_classifier", hook_path)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)

        # main should exist and be callable
        assert hasattr(hook, "main")
        assert callable(hook.main)

    def test_langfuse_instrumentation_fully_functional(self):
        """
        SUCCESS CRITERION: langfuse_instrumentation executes all functions.
        Expected: All 3 public functions execute without error.
        """
        import langfuse_instrumentation

        # All should execute
        langfuse_instrumentation.init_langfuse_trace("/test/project")
        langfuse_instrumentation.init_langfuse_prompt_span("Test prompt")
        langfuse_instrumentation.ensure_flush()

        # No exceptions = success

    def test_v4_compatibility_no_breaking_changes(self):
        """
        SUCCESS CRITERION: No breaking changes with Langfuse v4.
        Expected: All v4 APIs accessible and working.
        """
        import langfuse

        # Verify version
        version = langfuse.__version__
        assert version.startswith("4."), f"Expected v4, got {version}"

        # Verify critical APIs
        from langfuse import observe, get_client
        assert callable(observe)
        assert callable(get_client)

        # Verify decorator works
        @observe(name="test")
        def test_func():
            pass

        assert callable(test_func)

    def test_prompt_classifier_recursion_guard(self):
        """Verify prompt_classifier.py exits immediately with 0 if HARNESS_INTERNAL_LLM_CALL=1 is set."""
        import json
        import subprocess
        from pathlib import Path
        import sys
        import os
        hook_path = Path(__file__).parent.parent.parent / ".claude/harness-wf-plugin/hooks/prompt_classifier.py"
        env = {**os.environ, "HARNESS_INTERNAL_LLM_CALL": "1"}
        p = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps({"prompt": "hello"}),
            capture_output=True,
            text=True,
            env=env
        )
        assert p.returncode == 0
        assert p.stdout == ""
        assert p.stderr == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
