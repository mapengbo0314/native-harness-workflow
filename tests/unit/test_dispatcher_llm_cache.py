"""C1 (review 2026-06-12): once the LLM is found misconfigured, the dispatcher
caches that verdict so subsequent prompts skip straight to the keyword fallback
instead of re-spawning a doomed subprocess every prompt.
"""
from __future__ import annotations

from harness.runtime.dispatcher import OrchestratorDispatcher
from harness.runtime.llm_client import LLMConfigError


def _dispatcher(tmp_path) -> OrchestratorDispatcher:
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    return OrchestratorDispatcher(str(config_dir))


def test_broken_llm_verdict_is_cached(tmp_path, monkeypatch):
    dispatcher = _dispatcher(tmp_path)
    monkeypatch.setenv("HARNESS_PLATFORM_CLI", "claude")

    calls = {"n": 0}

    def fake_query(*_args, **_kwargs):
        calls["n"] += 1
        raise LLMConfigError("model not found")

    monkeypatch.setattr("harness.runtime.dispatcher.query_llm", fake_query)

    # First prompt: attempts the LLM once, records the broken verdict, falls back.
    first = dispatcher.classify_intent("implement feature X")
    assert calls["n"] == 1
    assert first["branch"]  # keyword fallback still returns a usable branch

    # Second prompt within TTL: cached verdict → no further subprocess spawn.
    dispatcher.classify_intent("add another thing")
    assert calls["n"] == 1
