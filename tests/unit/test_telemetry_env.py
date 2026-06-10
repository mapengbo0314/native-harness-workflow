"""Telemetry must never fire from test subprocesses or credential-less CLI runs.

Background: langfuse v3+/v4 renamed the kill-switch from LANGFUSE_ENABLED to
LANGFUSE_TRACING_ENABLED, so the old guards silently stopped working after the
langfuse>=4 bump — every pytest run exported synthetic "user_prompt" traces
(e.g. "explain how the login feature works") to the real Langfuse project via
credentials inherited from .env."""
from __future__ import annotations

from harness.init import cli
from tests._env_utils import telemetry_safe_env


class TestCliLangfuseGuard:
    def test_sets_both_kill_switches_without_creds(self):
        env: dict = {}
        cli._disable_langfuse_unless_configured(env)
        assert env["LANGFUSE_ENABLED"] == "false"           # harness compat gate
        assert env["LANGFUSE_TRACING_ENABLED"] == "false"   # langfuse v3+/v4 SDK

    def test_leaves_env_alone_when_creds_present(self):
        env = {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}
        cli._disable_langfuse_unless_configured(env)
        assert "LANGFUSE_ENABLED" not in env
        assert "LANGFUSE_TRACING_ENABLED" not in env

    def test_does_not_override_explicit_opt_in(self):
        env = {"LANGFUSE_TRACING_ENABLED": "true"}
        cli._disable_langfuse_unless_configured(env)
        assert env["LANGFUSE_TRACING_ENABLED"] == "true"    # setdefault semantics


class TestTelemetrySafeEnv:
    def test_strips_creds_and_disables_tracing(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
        monkeypatch.setenv("HARNESS_GLOBAL_INGESTION_BASE64", "abc")
        env = telemetry_safe_env()
        assert "LANGFUSE_PUBLIC_KEY" not in env
        assert "LANGFUSE_SECRET_KEY" not in env
        assert "HARNESS_GLOBAL_INGESTION_BASE64" not in env
        assert env["LANGFUSE_ENABLED"] == "false"
        assert env["LANGFUSE_TRACING_ENABLED"] == "false"

    def test_preserves_unrelated_vars(self, monkeypatch):
        monkeypatch.setenv("SOME_OTHER_VAR", "keep-me")
        assert telemetry_safe_env()["SOME_OTHER_VAR"] == "keep-me"
