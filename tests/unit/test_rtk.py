import json
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.init.rtk import RTK_HOOK_COMMAND, configure_rtk, install_rtk, setup_rtk


def compatible_rtk(*args, **kwargs):
    return True


def test_configure_rtk_merges_claude_settings_idempotently(tmp_path):
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir()
    settings_path.write_text(
        json.dumps({"permissions": {"allow": ["Read"]}}),
        encoding="utf-8",
    )

    with patch("harness.init.rtk._has_compatible_rtk", side_effect=compatible_rtk):
        assert configure_rtk(tmp_path, "claude") is True
        assert configure_rtk(tmp_path, "claude") is True

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["permissions"] == {"allow": ["Read"]}
    hooks = settings["hooks"]["PreToolUse"]
    commands = [
        hook["command"]
        for entry in hooks
        for hook in entry["hooks"]
    ]
    assert commands.count(RTK_HOOK_COMMAND) == 1


def test_configure_rtk_skips_claude_hook_when_binary_is_missing(tmp_path):
    with patch("harness.init.rtk._has_compatible_rtk", return_value=False):
        assert configure_rtk(tmp_path, "claude") is False

    assert not (tmp_path / ".claude" / "settings.json").exists()


def test_configure_rtk_rejects_invalid_existing_settings(tmp_path):
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir()
    settings_path.write_text("{broken", encoding="utf-8")

    with patch("harness.init.rtk._has_compatible_rtk", side_effect=compatible_rtk):
        with pytest.raises(ValueError, match="not valid JSON"):
            configure_rtk(tmp_path, "claude")


def test_configure_rtk_uses_rules_only_for_codex(tmp_path):
    with patch("harness.init.rtk._has_compatible_rtk", side_effect=compatible_rtk):
        assert configure_rtk(tmp_path, "codex") is True
    assert not (tmp_path / ".codex").exists()


def test_setup_rtk_without_install_permission_warns_and_continues(tmp_path):
    with (
        patch("harness.init.rtk._has_compatible_rtk", return_value=False),
        patch("harness.init.rtk.install_rtk") as mock_install,
    ):
        assert setup_rtk(tmp_path, "claude") is False

    mock_install.assert_not_called()


def test_setup_rtk_interactive_accepts_install(tmp_path):
    with (
        patch(
            "harness.init.rtk._has_compatible_rtk",
            side_effect=[False, True],
        ),
        patch("harness.init.rtk.install_rtk", return_value=True) as mock_install,
    ):
        assert setup_rtk(
            tmp_path,
            "codex",
            interactive=True,
            input_fn=lambda prompt: "yes",
        ) is True

    mock_install.assert_called_once_with()


def test_setup_rtk_install_failure_is_non_fatal(tmp_path):
    with (
        patch("harness.init.rtk._has_compatible_rtk", return_value=False),
        patch("harness.init.rtk.install_rtk", return_value=False),
    ):
        assert setup_rtk(
            tmp_path,
            "claude",
            install_if_missing=True,
        ) is False


def test_install_rtk_runs_downloaded_script_and_verifies(tmp_path):
    response = patch("harness.init.rtk.urllib.request.urlopen")
    with (
        response as mock_urlopen,
        patch("harness.init.rtk.subprocess.run") as mock_run,
        patch("harness.init.rtk._has_compatible_rtk", return_value=True),
    ):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = (
            b"#!/bin/sh\nexit 0\n"
        )
        mock_run.return_value.returncode = 0
        assert install_rtk() is True

    command = mock_run.call_args.args[0]
    assert command[0] == "sh"
    assert not Path(command[1]).exists()
