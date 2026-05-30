"""
Headless-mint fixture reused by all S1 matrix tests.

mint_platform(tmp_path, platform) -> Path
  Runs the full headless mint pipeline into a fresh subdirectory of tmp_path,
  then returns the directory that actually contains the canonical wiring
  artifacts (hooks.json, agents/, skills/).

Verified plugin-root conventions from real mint runs (2026-05-29):
  - "claude"  →  <project>/.claude/plugin-generated/
                 (hooks/hooks.json, agents.json, agents/, skills/ live here)
  - "gemini"  →  <project>/.gemini/
                 (hooks/hooks.json, agents/, skills/ live here)

selected_agents shape: list[dict] — each dict has at minimum a "name" key
  and optionally "role", "zone", "system_prompt".  All existing tests pass []
  for a bare mint, so we do the same here.

platform must be one of: "claude", "gemini".
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Platform choice strings used by mint_workspace / cli.py
_PLATFORM_CHOICES: dict[str, str] = {
    "gemini": "1",
    "claude": "2",
}

# Where the wiring artifacts land after a full headless mint for each platform
_PLUGIN_ROOT_SUBPATH: dict[str, str] = {
    "gemini": ".gemini",
    "claude": ".claude/plugin-generated",
}


def mint_platform(tmp_path: Path, platform: str) -> Path:
    """Run a headless mint for *platform* into a fresh sub-dir of *tmp_path*.

    Args:
        tmp_path: A writable temporary directory (e.g. pytest's ``tmp_path``
                  fixture).  A dedicated project sub-directory is created
                  inside it so multiple calls with the same ``tmp_path`` do
                  not collide.
        platform: ``"claude"`` or ``"gemini"``.

    Returns:
        The Path to the plugin root — the directory that contains the canonical
        wiring artifacts for the platform:

        - claude  →  ``<project>/.claude/plugin-generated/``
        - gemini  →  ``<project>/.gemini/``

    Raises:
        ValueError: If *platform* is not recognised.
    """
    if platform not in _PLATFORM_CHOICES:
        raise ValueError(
            f"Unknown platform {platform!r}. "
            f"Supported: {sorted(_PLATFORM_CHOICES)}"
        )

    from harness.init.cli import main  # local import keeps module-level cheap

    platform_choice = _PLATFORM_CHOICES[platform]

    # Use a platform-specific subdirectory so callers can mint both platforms
    # into the same tmp_path without conflicts.
    project_path = tmp_path / f"{platform}_project"
    project_path.mkdir(parents=True, exist_ok=True)
    # Minimal file so tech-stack detection has something to look at
    (project_path / "app.py").write_text('print("hello")\n')

    # LLM response: include orchestrator-plugin skill for claude so the plugin
    # stack is generated (which is what exposes plugin-generated/).
    skills = []
    if platform == "claude":
        skills = [
            {
                "name": "orchestrator-plugin",
                "url": "https://github.com/example/plugin",
                "type": "extension",
            }
        ]

    llm_response = json.dumps(
        {
            "sme_name": "test-sme",
            "core_domain_value": "test",
            "invariants": [],
            "glossary": {},
            "domain_events": [],
            "skills": skills,
            "mcps": [],
        }
    )

    llm_choice = "anthropic" if platform == "claude" else "gemini"

    with (
        patch("harness.init.discovery_engine.query_llm") as mock_llm,
        patch("subprocess.run") as mock_run,
        patch("urllib.request.urlopen") as mock_url,
        patch("harness.init.cli.parse_args") as mock_args,
        patch("sys.exit"),
    ):
        mock_llm.return_value = llm_response
        mock_run.return_value = MagicMock(returncode=0)
        mock_url.return_value.__enter__.return_value.read.return_value = b""

        args = MagicMock()
        args.command = "init"
        args.project_path = str(project_path)
        args.llm = llm_choice
        args.model = None
        args.bundle = None
        mock_args.return_value = args

        env = {
            "HARNESS_HEADLESS": "1",
            "HARNESS_PLATFORM": platform_choice,
            "GEMINI_API_KEY": "fake-key",
            "ANTHROPIC_API_KEY": "fake-key",
            "PATH": os.environ.get("PATH", ""),
        }
        with patch.dict(os.environ, env):
            try:
                main()
            except SystemExit:
                pass

    plugin_root = project_path / _PLUGIN_ROOT_SUBPATH[platform]
    return plugin_root
