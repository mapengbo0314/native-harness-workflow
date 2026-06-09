"""Optional RTK integration for minted harness workspaces."""

from __future__ import annotations

import json
import os
import subprocess
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable


RTK_HOOK_COMMAND = "rtk hook claude"
RTK_RULES = """**RTK output compression:** When `rtk` is available, use it for supported shell commands (for example, `rtk git status`, `rtk pytest`, and `rtk ls`). Fall back to the original command when RTK does not support it."""
RTK_INSTALL_URL = "https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh"


def setup_rtk(
    project_path: Path,
    platform: str,
    *,
    install_if_missing: bool = False,
    interactive: bool = False,
    input_fn: Callable[[str], str] = input,
) -> bool:
    """Ensure RTK is available, then configure the selected platform.

    Installation is always best-effort. A missing or failed installation emits
    a warning and leaves the rest of harness setup unaffected.
    """
    if not _has_compatible_rtk():
        should_install = install_if_missing
        if interactive and not install_if_missing:
            answer = input_fn(
                "RTK is not installed. Install it now using the official "
                "rtk-ai installer? [y/N]: "
            )
            should_install = answer.strip().lower() in {"y", "yes"}

        if should_install and not install_rtk():
            return False
        if not should_install:
            print(
                "[HARNESS] Warning: RTK was requested but a compatible 'rtk' "
                "binary is not available. Continuing without RTK."
            )
            return False

    return configure_rtk(project_path, platform)


def configure_rtk(project_path: Path, platform: str) -> bool:
    """Configure RTK after its binary has been verified."""
    if not _has_compatible_rtk():
        print(
            "[HARNESS] Warning: RTK configuration skipped because a compatible "
            "'rtk' binary is not available."
        )
        return False

    if platform != "claude":
        print(
            f"[HARNESS] RTK enabled for {platform} through the generated rules "
            "instruction (native command hooks are unavailable)."
        )
        return True

    settings_path = project_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = _read_settings(settings_path)
    pre_tool_use = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])

    already_present = any(
        any(
            hook.get("command") == RTK_HOOK_COMMAND
            for hook in entry.get("hooks", [])
        )
        for entry in pre_tool_use
    )
    if not already_present:
        pre_tool_use.append(
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": RTK_HOOK_COMMAND}],
            }
        )
        settings_path.write_text(
            json.dumps(settings, indent=2) + "\n",
            encoding="utf-8",
        )

    print("[HARNESS] RTK Claude PreToolUse hook configured.")
    return True


def install_rtk() -> bool:
    """Install RTK with its official installer on supported platforms."""
    if sys.platform == "win32":
        print(
            "[HARNESS] Warning: Automatic RTK installation is not supported "
            "on Windows. Continuing without RTK."
        )
        return False

    script_path: Path | None = None
    try:
        with urllib.request.urlopen(RTK_INSTALL_URL, timeout=30) as response:
            script = response.read()
        with tempfile.NamedTemporaryFile(
            prefix="harness-rtk-install-",
            suffix=".sh",
            delete=False,
        ) as script_file:
            script_file.write(script)
            script_path = Path(script_file.name)

        result = subprocess.run(
            ["sh", str(script_path)],
            check=False,
            text=True,
        )
        if result.returncode != 0:
            print(
                "[HARNESS] Warning: RTK installation failed. "
                "Continuing without RTK."
            )
            return False
    except (OSError, urllib.error.URLError) as exc:
        print(
            f"[HARNESS] Warning: Could not install RTK: {exc}. "
            "Continuing without RTK."
        )
        return False
    finally:
        if script_path:
            script_path.unlink(missing_ok=True)

    if not _has_compatible_rtk():
        print(
            "[HARNESS] Warning: RTK installer completed, but a compatible "
            "'rtk' binary is not available on PATH. Continuing without RTK."
        )
        return False

    print("[HARNESS] RTK installed successfully.")
    return True


def _has_compatible_rtk() -> bool:
    candidates = [
        shutil.which("rtk"),
        str(Path.home() / ".local" / "bin" / "rtk"),
        str(Path.home() / ".cargo" / "bin" / "rtk"),
    ]
    seen = set()
    for executable in candidates:
        if not executable or executable in seen:
            continue
        seen.add(executable)
        if not Path(executable).is_file():
            continue
        try:
            result = subprocess.run(
                [executable, "gain"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            executable_dir = str(Path(executable).parent)
            path_entries = os.environ.get("PATH", "").split(os.pathsep)
            if executable_dir not in path_entries:
                os.environ["PATH"] = (
                    executable_dir
                    + os.pathsep
                    + os.environ.get("PATH", "")
                )
            return True
    return False


def _read_settings(settings_path: Path) -> dict:
    if not settings_path.exists():
        return {}

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Cannot configure RTK because {settings_path} is not valid JSON: {exc}"
        ) from exc

    if not isinstance(settings, dict):
        raise ValueError(
            f"Cannot configure RTK because {settings_path} must contain a JSON object."
        )
    return settings
