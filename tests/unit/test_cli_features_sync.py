"""Phase 0 (ECC feature port): CLI `features sync` subcommand tests.

TDD — written BEFORE the subcommand exists in cli.py.
Verifies:
  - `harness-wf features sync` calls compile_features on the resolved plugin root
  - domain-refresh also triggers compile_features
"""
from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helper: build a minimal args namespace that run_features_sync expects
# ---------------------------------------------------------------------------

def _make_args(project_path: str, **kwargs) -> types.SimpleNamespace:
    ns = types.SimpleNamespace(
        command="features",
        subcommand="sync",
        project_path=project_path,
    )
    ns.__dict__.update(kwargs)
    return ns


# ---------------------------------------------------------------------------
# features sync -> compile_features called on plugin root
# ---------------------------------------------------------------------------


def test_features_sync_calls_compile_features(tmp_path):
    """run_features_sync must call compile_features with the plugin root."""
    from harness.init.cli import run_features_sync

    with patch("harness.init.cli.compile_features") as mock_cf:
        run_features_sync(str(tmp_path))

    mock_cf.assert_called_once_with(Path(tmp_path))


# ---------------------------------------------------------------------------
# domain-refresh -> compile_features also called
# ---------------------------------------------------------------------------


def test_domain_refresh_triggers_compile_features(tmp_path):
    """run_domain_refresh (via seed) must trigger a compile_features call."""
    # Create a minimal domain.json so refresh doesn't bail early
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    domain_json = tmp_path / ".claude" / "domain.json"
    domain_json.write_text('{"stack": []}', encoding="utf-8")

    with (
        patch("harness.domain.seed.detect.detect_stack", return_value=[]),
        patch("harness.init.cli.compile_features") as mock_cf,
    ):
        from harness.init.cli import run_domain_refresh_with_sync
        run_domain_refresh_with_sync(str(tmp_path))

    mock_cf.assert_called_once_with(Path(tmp_path))
