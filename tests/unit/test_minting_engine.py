
import os
import json
import shutil
from pathlib import Path
from unittest.mock import patch
from harness.init.minting_engine import mint_workspace

def test_mint_workspace_does_not_generate_setup_script(tmp_path):
    # Setup mock project
    project_path = tmp_path / "project_abs_path_test"
    project_path.mkdir()

    # Path to real boilerplate in the repo
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"

    target_dir = project_path / ".gemini"

    # We call mint_workspace
    mint_workspace(
        target_dir=str(target_dir),
        selected_agents=[],
        project_path=str(project_path),
        platform_choice="1", # Gemini
        boilerplate_dir=str(boilerplate_dir)
    )    


def test_mint_workspace_adds_rtk_rules_when_enabled(tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"

    mint_workspace(
        target_dir=str(project_path / ".codex"),
        selected_agents=[],
        project_path=str(project_path),
        platform_choice="5",
        boilerplate_dir=str(boilerplate_dir),
        enable_rtk=True,
    )

    staged_root = project_path / ".codex" / "root_staging"
    staged_rules = next(
        path
        for path in (staged_root / "AGENTS.md", staged_root / "CODEX.md")
        if path.exists()
    )
    assert "**RTK output compression:**" in staged_rules.read_text(encoding="utf-8")


def test_rules_pointer_domain_path_is_platform_neutral(tmp_path):
    """The project-ops rules pointer must not say "the plugin's" — only Claude
    deploys domain.json under a plugin; for gemini/codex/cursor it lives directly
    under the config dir (e.g. .gemini/domain/domain.json), so the wording must be
    platform-neutral and not claim a non-existent "plugin"."""
    project_path = tmp_path / "neutral"
    project_path.mkdir()
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"

    mint_workspace(
        target_dir=str(project_path / ".gemini"),
        selected_agents=[],
        project_path=str(project_path),
        platform_choice="1",  # gemini — no plugin
        boilerplate_dir=str(boilerplate_dir),
    )

    rules = (project_path / ".gemini" / "root_staging" / "GEMINI.md")
    if not rules.exists():
        rules = project_path / "GEMINI.md"
    text = rules.read_text(encoding="utf-8")
    assert "the plugin's `domain/domain.json`" not in text, (
        "rules pointer leaks plugin-only wording into a non-plugin platform"
    )
    # Still references the manifest, just neutrally.
    assert "domain/domain.json" in text
