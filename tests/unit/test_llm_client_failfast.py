"""C1 (review 2026-06-12): deterministic LLM errors (404 / model-not-found)
must NOT be retried — retrying a misconfigured model pin is pure latency waste
in the UserPromptSubmit hot path. Transient errors still retry.
"""
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
import tenacity.nap

from harness.runtime import llm_client
from harness.runtime.llm_client import LLMConfigError, query_llm


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    # Neutralise tenacity's backoff so the retry test doesn't actually wait.
    monkeypatch.setattr(tenacity.nap.time, "sleep", lambda *a, **k: None)
    monkeypatch.delenv("HARNESS_MOCK_LLM", raising=False)


def _cpe(stderr: str) -> subprocess.CalledProcessError:
    return subprocess.CalledProcessError(returncode=1, cmd=["claude"], output="", stderr=stderr)


def test_model_not_found_raises_config_error_without_retry():
    with patch.object(
        llm_client.subprocess, "run", side_effect=_cpe("API Error 404: model not found")
    ) as run:
        with pytest.raises(LLMConfigError):
            query_llm("hi", "claude")
    assert run.call_count == 1


def test_transient_error_still_retries_three_times():
    with patch.object(
        llm_client.subprocess, "run", side_effect=_cpe("connection reset by peer")
    ) as run:
        with pytest.raises(RuntimeError):
            query_llm("hi", "claude")
    assert run.call_count == 3


def test_config_error_is_not_a_runtimeerror():
    # The retry predicate keys on RuntimeError; LLMConfigError must sit outside
    # that hierarchy so tenacity never retries it.
    assert not issubclass(LLMConfigError, RuntimeError)
