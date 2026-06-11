"""Phase 0 (ECC feature port): CLI `features sync` subcommand tests.

TDD — written BEFORE the subcommand exists in cli.py.
Verifies:
  - `harness-wf features sync` calls compile_features on the resolved plugin root
  - domain-refresh also triggers compile_features
  - FeaturesValidationError in either path prints [HARNESS] ERROR and exits 1
  - run_domain_refresh_with_sync prints the same success line as run_features_sync
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
    # domain.json lives at .claude/harness-wf-plugin/domain/domain.json (default platform)
    domain_dir = tmp_path / ".claude" / "harness-wf-plugin" / "domain"
    domain_dir.mkdir(parents=True, exist_ok=True)
    domain_json = domain_dir / "domain.json"
    domain_json.write_text('{"stack": []}', encoding="utf-8")

    with (
        patch("harness.domain.seed.detect.detect_stack", return_value=[]),
        patch("harness.init.cli.compile_features") as mock_cf,
    ):
        from harness.init.cli import run_domain_refresh_with_sync
        run_domain_refresh_with_sync(str(tmp_path))

    mock_cf.assert_called_once_with(Path(tmp_path))


# ---------------------------------------------------------------------------
# FeaturesValidationError -> exit code 1, no traceback (Finding 3)
# ---------------------------------------------------------------------------


def test_features_sync_validation_error_exits_1(tmp_path, capsys):
    """Invalid features.yaml must produce exit code 1 and print [HARNESS] ERROR."""
    from harness.init.cli import run_features_sync
    from harness.init.features import FeaturesValidationError

    with patch(
        "harness.init.cli.compile_features",
        side_effect=FeaturesValidationError("root must be a mapping"),
    ):
        with pytest.raises(SystemExit) as exc_info:
            run_features_sync(str(tmp_path))

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "[HARNESS] ERROR:" in captured.out
    assert "root must be a mapping" in captured.out
    # No traceback in stdout
    assert "Traceback" not in captured.out


def test_domain_refresh_validation_error_exits_1(tmp_path, capsys):
    """FeaturesValidationError during domain-refresh must also exit 1."""
    # domain.json lives at .claude/harness-wf-plugin/domain/domain.json (default platform)
    domain_dir = tmp_path / ".claude" / "harness-wf-plugin" / "domain"
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "domain.json").write_text('{"stack": []}', encoding="utf-8")

    from harness.init.features import FeaturesValidationError

    with (
        patch("harness.domain.seed.detect.detect_stack", return_value=[]),
        patch(
            "harness.init.cli.compile_features",
            side_effect=FeaturesValidationError("bad yaml root"),
        ),
    ):
        from harness.init.cli import run_domain_refresh_with_sync

        with pytest.raises(SystemExit) as exc_info:
            run_domain_refresh_with_sync(str(tmp_path))

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "[HARNESS] ERROR:" in captured.out
    assert "bad yaml root" in captured.out
    assert "Traceback" not in captured.out


# ---------------------------------------------------------------------------
# run_domain_refresh_with_sync prints success line (Finding 4)
# ---------------------------------------------------------------------------


def test_domain_refresh_prints_success_line(tmp_path, capsys):
    """run_domain_refresh_with_sync must print the features.json compiled line on success."""
    # domain.json lives at .claude/harness-wf-plugin/domain/domain.json (default platform)
    domain_dir = tmp_path / ".claude" / "harness-wf-plugin" / "domain"
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "domain.json").write_text('{"stack": []}', encoding="utf-8")
    fake_json_path = tmp_path / "features.json"

    with (
        patch("harness.domain.seed.detect.detect_stack", return_value=[]),
        patch("harness.init.cli.compile_features", return_value=fake_json_path),
    ):
        from harness.init.cli import run_domain_refresh_with_sync
        run_domain_refresh_with_sync(str(tmp_path))

    captured = capsys.readouterr()
    assert "features.json compiled" in captured.out
    assert str(fake_json_path) in captured.out
