"""C3 (review 2026-06-12): `claude plugin validate` must run exactly once.

The previous implementation retried by re-running an identical command (no flag
was ever degraded), so a validation failure spawned the subprocess twice for no
benefit. We pin single-run behaviour.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from harness.init import cli
from harness.init.cli import HarnessSetupError


def test_run_plugin_validate_runs_once_on_success(tmp_path):
    fake = MagicMock(returncode=0, stdout="", stderr="")
    with patch.object(cli.subprocess, "run", return_value=fake) as run:
        cli._run_plugin_validate("claude", tmp_path)
    assert run.call_count == 1


def test_run_plugin_validate_raises_without_retry_on_failure(tmp_path):
    fake = MagicMock(returncode=1, stdout="boom", stderr="bad flag")
    with patch.object(cli.subprocess, "run", return_value=fake) as run:
        with pytest.raises(HarnessSetupError):
            cli._run_plugin_validate("claude", tmp_path)
    # No second attempt — the old retry was a no-op and is gone.
    assert run.call_count == 1
