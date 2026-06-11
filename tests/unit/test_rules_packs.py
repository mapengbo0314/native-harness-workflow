"""Phase 1a (ECC feature port): rules-pack selection tests.

TDD: tests written BEFORE implementation.
Covers:
  1. lang_aliases.stack_to_packs — language alias map lookups
  2. minting_engine.select_rules_packs — pack dir resolution
  3. mint_workspace pack install behavior — namespaced install + pruning
  4. domain-refresh re-sync of pack selection
  5. toggle rules_packs.enabled: false => no install
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# 1. lang_aliases.stack_to_packs
# ---------------------------------------------------------------------------


class TestStackToPacks:
    def test_python_maps_to_python(self):
        from harness.init.lang_aliases import stack_to_packs
        assert stack_to_packs(["Python"]) == {"python"}

    def test_go_maps_to_golang(self):
        from harness.init.lang_aliases import stack_to_packs
        assert stack_to_packs(["Go"]) == {"golang"}

    def test_typescript_maps_to_typescript(self):
        from harness.init.lang_aliases import stack_to_packs
        assert stack_to_packs(["TypeScript"]) == {"typescript"}

    def test_javascript_maps_to_javascript(self):
        from harness.init.lang_aliases import stack_to_packs
        assert stack_to_packs(["JavaScript"]) == {"javascript"}

    def test_go_with_framework_ignored(self):
        from harness.init.lang_aliases import stack_to_packs
        # Django is a framework, NOT a language — must be ignored
        assert stack_to_packs(["Go", "Django"]) == {"golang"}

    def test_lowercase_go_maps_to_golang(self):
        from harness.init.lang_aliases import stack_to_packs
        assert stack_to_packs(["go"]) == {"golang"}

    def test_unknown_entry_returns_empty(self):
        from harness.init.lang_aliases import stack_to_packs
        assert stack_to_packs(["Brainfuck", "COBOL"]) == set()

    def test_empty_stack_returns_empty(self):
        from harness.init.lang_aliases import stack_to_packs
        assert stack_to_packs([]) == set()

    def test_mixed_case_python(self):
        from harness.init.lang_aliases import stack_to_packs
        assert stack_to_packs(["PYTHON"]) == {"python"}

    def test_framework_names_ignored(self):
        from harness.init.lang_aliases import stack_to_packs
        # None of these should match — they are framework names
        assert stack_to_packs(["Django", "FastAPI", "React", "Express"]) == set()


# ---------------------------------------------------------------------------
# 2. select_rules_packs — pack dir resolution (requires packs on disk)
# ---------------------------------------------------------------------------


@pytest.fixture()
def packs_root(tmp_path):
    """Create a minimal placeholder packs_root with common/, python/, golang/."""
    root = tmp_path / "packs"
    (root / "common").mkdir(parents=True)
    (root / "common" / "baseline.md").write_text("# baseline\n<!-- placeholder -->\n")
    (root / "python").mkdir()
    (root / "python" / "placeholder.md").write_text(
        "---\npaths: [\"**/*.py\"]\n---\n<!-- placeholder -->\n"
    )
    (root / "golang").mkdir()
    (root / "golang" / "placeholder.md").write_text(
        "---\npaths: [\"**/*.go\"]\n---\n<!-- placeholder -->\n"
    )
    (root / "typescript").mkdir()
    (root / "typescript" / "placeholder.md").write_text(
        "---\npaths: [\"**/*.ts\", \"**/*.tsx\"]\n---\n<!-- placeholder -->\n"
    )
    return root


class TestSelectRulesPacks:
    def test_python_stack_selects_common_and_python(self, packs_root):
        from harness.init.minting_engine import select_rules_packs
        result = select_rules_packs(["Python"], packs_root)
        names = {p.name for p in result}
        assert "common" in names
        assert "python" in names
        assert "golang" not in names

    def test_go_stack_selects_common_and_golang(self, packs_root):
        from harness.init.minting_engine import select_rules_packs
        result = select_rules_packs(["Go"], packs_root)
        names = {p.name for p in result}
        assert "common" in names
        assert "golang" in names
        assert "python" not in names

    def test_empty_stack_selects_common_only(self, packs_root):
        from harness.init.minting_engine import select_rules_packs
        result = select_rules_packs([], packs_root)
        names = {p.name for p in result}
        assert names == {"common"}

    def test_unknown_language_selects_common_only(self, packs_root):
        from harness.init.minting_engine import select_rules_packs
        result = select_rules_packs(["Brainfuck"], packs_root)
        names = {p.name for p in result}
        assert names == {"common"}

    def test_missing_pack_dir_on_disk_skipped(self, packs_root):
        """JavaScript is in PACK_ALIASES but has no dir in packs_root => skip it."""
        from harness.init.minting_engine import select_rules_packs
        result = select_rules_packs(["JavaScript"], packs_root)
        names = {p.name for p in result}
        # javascript dir doesn't exist in our packs_root fixture — common only
        assert names == {"common"}


# ---------------------------------------------------------------------------
# 3. mint_workspace — namespaced install + pruning
# ---------------------------------------------------------------------------


def _make_boilerplate(tmp_path: Path) -> Path:
    """Create a minimal boilerplate dir with packs/ subtree for minting tests."""
    bp = tmp_path / "boilerplate"
    bp.mkdir()
    # Minimal required files so mint_workspace doesn't crash
    (bp / "features.yaml").write_text("rules_packs:\n  enabled: true\n")
    # packs tree
    packs = bp / "rules" / "packs"
    (packs / "common").mkdir(parents=True)
    (packs / "common" / "baseline.md").write_text("# baseline\n<!-- placeholder -->\n")
    (packs / "python").mkdir()
    (packs / "python" / "placeholder.md").write_text(
        "---\npaths: [\"**/*.py\"]\n---\n<!-- placeholder -->\n"
    )
    (packs / "golang").mkdir()
    (packs / "golang" / "placeholder.md").write_text(
        "---\npaths: [\"**/*.go\"]\n---\n<!-- placeholder -->\n"
    )
    (packs / "typescript").mkdir()
    (packs / "typescript" / "placeholder.md").write_text(
        "---\npaths: [\"**/*.ts\", \"**/*.tsx\"]\n---\n<!-- placeholder -->\n"
    )
    return bp


def _write_domain_json(project_path: Path, stack: list[str]) -> None:
    """Write domain.json for the project, mirroring the deployed path."""
    domain_dir = project_path / ".claude" / "harness-wf-plugin" / "domain"
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "domain.json").write_text(
        json.dumps({"stack": stack}), encoding="utf-8"
    )


class TestMintWorkspacePackInstall:
    """Integration-lite tests: call install_rules_packs directly (lighter than full mint)."""

    def test_python_stack_installs_common_and_python(self, tmp_path):
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Python"])

        target = tmp_path / "target_plugin"
        target.mkdir()
        # Copy packs to the "deployed plugin" location
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},  # default-enabled
        )

        install_root = project / ".claude" / "rules" / "harness"
        assert (install_root / "common" / "baseline.md").exists()
        assert (install_root / "python" / "placeholder.md").exists()
        assert not (install_root / "golang").exists()

    def test_golang_excluded_from_deployed_packs_when_not_in_stack(self, tmp_path):
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Python"])

        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
        )

        # golang dir should be pruned from the deployed plugin packs tree
        assert not (target / "rules" / "packs" / "golang").exists()
        # python dir should remain
        assert (target / "rules" / "packs" / "python").exists()
        # common always remains
        assert (target / "rules" / "packs" / "common").exists()

    def test_rules_packs_disabled_installs_nothing(self, tmp_path):
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Python"])

        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        features = {"rules_packs": {"enabled": False}}

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features=features,
        )

        install_root = project / ".claude" / "rules" / "harness"
        assert not install_root.exists()
        # All packs pruned from deployed plugin
        assert not (target / "rules" / "packs" / "python").exists()
        assert not (target / "rules" / "packs" / "golang").exists()
        assert not (target / "rules" / "packs" / "common").exists()

    def test_language_flag_false_excludes_language(self, tmp_path):
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Go", "Python"])

        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        # golang explicitly disabled in features
        features = {"rules_packs": {"enabled": True, "languages": {"golang": False}}}

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features=features,
        )

        install_root = project / ".claude" / "rules" / "harness"
        assert (install_root / "common").exists()
        assert (install_root / "python").exists()
        assert not (install_root / "golang").exists()

    def test_missing_domain_json_installs_common_only(self, tmp_path):
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        # No domain.json written

        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
        )

        install_root = project / ".claude" / "rules" / "harness"
        assert (install_root / "common").exists()
        assert not (install_root / "python").exists()
        assert not (install_root / "golang").exists()


# ---------------------------------------------------------------------------
# 3b. mint_workspace calls install_rules_packs once with correct args
# ---------------------------------------------------------------------------


def test_mint_workspace_calls_install_rules_packs(tmp_path):
    """mint_workspace must call install_rules_packs once after compile_features."""
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"
    project_path = tmp_path / "project"
    project_path.mkdir()
    target_dir = project_path / ".gemini"

    with (
        patch("harness.init.minting_engine.compile_features") as mock_cf,
        patch("harness.init.minting_engine.install_rules_packs") as mock_irp,
    ):
        mock_cf.return_value = target_dir / "features.json"
        mock_irp.return_value = None

        from harness.init.minting_engine import mint_workspace
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="1",  # gemini
            boilerplate_dir=str(boilerplate_dir),
        )

    mock_irp.assert_called_once()
    # Verify it was called with project_path as a Path
    call_kwargs = mock_irp.call_args
    assert call_kwargs is not None, "install_rules_packs was never called"
    # project_path should be the project dir
    passed_project = call_kwargs.kwargs.get("project_path") or call_kwargs.args[0]
    assert Path(passed_project) == project_path


# ---------------------------------------------------------------------------
# 4. domain-refresh re-triggers pack sync
# ---------------------------------------------------------------------------


def test_domain_refresh_triggers_pack_sync(tmp_path):
    """run_domain_refresh_with_sync must call sync_rules_packs after refresh."""
    domain_dir = tmp_path / ".claude" / "harness-wf-plugin" / "domain"
    domain_dir.mkdir(parents=True)
    (domain_dir / "domain.json").write_text('{"stack": ["Python"]}', encoding="utf-8")

    with (
        patch("harness.domain.seed.detect.detect_stack", return_value=["Python"]),
        patch("harness.init.cli.compile_features", return_value=None),
        patch("harness.init.cli.sync_rules_packs") as mock_sync,
    ):
        from harness.init.cli import run_domain_refresh_with_sync
        run_domain_refresh_with_sync(str(tmp_path))

    mock_sync.assert_called_once()


# ---------------------------------------------------------------------------
# 5. Integration: template tree ships packs with frontmatter on language packs
# ---------------------------------------------------------------------------


class TestTemplatePacks:
    def test_packs_dir_exists_in_boilerplate(self):
        from pathlib import Path
        repo_root = Path(__file__).parent.parent.parent
        packs_root = repo_root / "src" / "harness" / "templates" / "boilerplate" / "rules" / "packs"
        assert packs_root.exists(), f"packs dir missing: {packs_root}"

    def test_common_pack_has_no_paths_frontmatter(self):
        from pathlib import Path
        repo_root = Path(__file__).parent.parent.parent
        common_baseline = repo_root / "src" / "harness" / "templates" / "boilerplate" / "rules" / "packs" / "common" / "baseline.md"
        assert common_baseline.exists()
        content = common_baseline.read_text()
        # common should NOT have a paths: frontmatter (it's un-scoped)
        if content.startswith("---"):
            import re
            fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if fm_match:
                fm_text = fm_match.group(1)
                assert "paths:" not in fm_text, "common/baseline.md must NOT have paths: frontmatter"

    def test_language_packs_have_paths_frontmatter(self):
        from pathlib import Path
        import re
        repo_root = Path(__file__).parent.parent.parent
        packs_root = repo_root / "src" / "harness" / "templates" / "boilerplate" / "rules" / "packs"
        lang_packs = ["python", "typescript", "golang"]
        for lang in lang_packs:
            lang_dir = packs_root / lang
            assert lang_dir.exists(), f"language pack dir missing: {lang_dir}"
            md_files = list(lang_dir.glob("*.md"))
            assert md_files, f"no .md files in {lang_dir}"
            for md_file in md_files:
                content = md_file.read_text()
                assert content.startswith("---"), f"{md_file} must start with YAML frontmatter"
                fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                assert fm_match, f"{md_file} has malformed frontmatter"
                fm_text = fm_match.group(1)
                assert "paths:" in fm_text, f"{md_file} must have paths: in frontmatter"


# ---------------------------------------------------------------------------
# New behavioral tests (TDD — written before implementation)
# ---------------------------------------------------------------------------


class TestStaleDirPruneOnRefresh:
    """Issue 1: stale language dirs in install_root must be pruned on re-install."""

    def test_stale_lang_dir_removed_on_refresh(self, tmp_path):
        """Install Python+Go, then re-install Python only — golang/ must be gone."""
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        # First install: Python + Go
        _write_domain_json(project, ["Python", "Go"])
        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
        )

        install_root = project / ".claude" / "rules" / "harness"
        assert (install_root / "golang").exists(), "golang must be present after first install"
        assert (install_root / "python").exists(), "python must be present after first install"

        # Rebuild packs_root so golang is available again (simulates a fresh plugin deploy)
        shutil.rmtree(target / "rules" / "packs")
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        # Second install: Python only
        _write_domain_json(project, ["Python"])
        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
        )

        assert (install_root / "python").exists(), "python must remain after refresh"
        assert (install_root / "common").exists(), "common must remain after refresh"
        assert not (install_root / "golang").exists(), "golang must be pruned after refresh"


class TestCleanRecopyRemovesStaleFiles:
    """Issue 2: copytree must clean-recreate dest subdir so removed pack files disappear."""

    def test_stale_file_removed_on_reinstall(self, tmp_path):
        """Pre-create stale.md in install_root/python/, run install, assert it's gone."""
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        _write_domain_json(project, ["Python"])

        # Pre-create a stale file in the destination python dir
        install_root = project / ".claude" / "rules" / "harness"
        stale_file = install_root / "python" / "stale.md"
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_text("stale content\n")
        assert stale_file.exists()

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
        )

        assert not stale_file.exists(), "stale.md must be removed by clean re-copy"
        assert (install_root / "python" / "placeholder.md").exists(), "real pack files must be present"


class TestLanguageStringBoolGuard:
    """Issue 3: _features_language_enabled must treat non-bool values as enabled (fail-open)."""

    def test_string_false_treated_as_enabled(self, tmp_path):
        """languages: {golang: 'false'} (string) => golang still installed."""
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        _write_domain_json(project, ["Go"])

        # String "false" should NOT disable the pack (only bool False disables)
        features = {"rules_packs": {"enabled": True, "languages": {"golang": "false"}}}

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features=features,
        )

        install_root = project / ".claude" / "rules" / "harness"
        assert (install_root / "golang").exists(), "golang must be installed when flag is string 'false' (fail-open)"


# ---------------------------------------------------------------------------
# New: scope install_root prune to harness-managed pack names only
# ---------------------------------------------------------------------------


class TestPruneSpareUserDirs:
    """install_root prune must not delete user-created dirs (e.g. team-conventions/).

    Only children whose names are in known_pack_dirs (PACK_ALIASES values +
    packs_root child names) should ever be removed.  Unknown dirs are left
    intact as defense-in-depth.
    """

    def test_user_dir_survives_stale_pack_pruned(self, tmp_path):
        """Create .claude/rules/harness/team-conventions/custom.md and a stale
        golang/ dir; run install with stack=["Python"]; assert:
        - team-conventions/ SURVIVES (not a known pack name)
        - golang/ is REMOVED (known pack name, not in matched set)
        - python/ and common/ are INSTALLED
        """
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Python"])

        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        # Pre-populate install_root with a user dir AND a stale harness-managed dir
        install_root = project / ".claude" / "rules" / "harness"
        user_dir = install_root / "team-conventions"
        user_dir.mkdir(parents=True)
        (user_dir / "custom.md").write_text("# Team conventions\n")

        stale_dir = install_root / "golang"
        stale_dir.mkdir(parents=True)
        (stale_dir / "placeholder.md").write_text("stale golang content\n")

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
        )

        # User content must survive
        assert (install_root / "team-conventions" / "custom.md").exists(), (
            "team-conventions/custom.md must survive — it is not a harness-managed pack dir"
        )
        # Stale known pack dir must be pruned
        assert not (install_root / "golang").exists(), (
            "golang/ must be pruned — it is a known pack dir not in the matched set"
        )
        # Expected packs installed
        assert (install_root / "python" / "placeholder.md").exists()
        assert (install_root / "common" / "baseline.md").exists()


# ---------------------------------------------------------------------------
# Phase 1c: persona inlining for non-Claude platforms (design M3)
# ---------------------------------------------------------------------------


def _make_boilerplate_with_agents(tmp_path: Path) -> Path:
    """Create a boilerplate dir with packs subtree AND an agents/ dir for inlining tests."""
    bp = _make_boilerplate(tmp_path)
    agents_dir = bp / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / "implementer.md").write_text(
        "---\nname: implementer\n---\n# Implementer\n\nDo implementation work.\n"
    )
    (agents_dir / "reviewer.md").write_text(
        "---\nname: reviewer\n---\n# Reviewer\n\nDo code review.\n"
    )
    return bp


class TestPersonaInliningNonClaude:
    """Phase 1c: non-Claude platforms get pack content inlined into agent personas."""

    def test_gemini_platform_inlines_python_pack_into_personas(self, tmp_path):
        """Minting with platform=gemini + Python stack → each agent persona contains python pack content."""
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate_with_agents(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Python"])

        # The deployed plugin is a copy of the boilerplate
        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")
        shutil.copytree(bp / "agents", target / "agents")

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
            platform="gemini",
        )

        # Each agent persona must contain the python pack content marker
        for persona_name in ["implementer.md", "reviewer.md"]:
            persona = target / "agents" / persona_name
            assert persona.exists(), f"{persona_name} should exist"
            content = persona.read_text(encoding="utf-8")
            assert "## Stack Rules (auto-included)" in content, (
                f"{persona_name}: expected '## Stack Rules (auto-included)' section for gemini"
            )
            assert "<!-- harness:rules-packs:start -->" in content, (
                f"{persona_name}: expected rules-packs marker"
            )
            # Python pack content (placeholder text) must be present
            assert "placeholder" in content or "# Python" in content or "**/*.py" not in content, (
                f"{persona_name}: expected python pack content in persona"
            )

    def test_claude_platform_does_not_inline_personas(self, tmp_path):
        """Minting with platform=claude → agent personas are NOT modified (Claude loads rules natively)."""
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate_with_agents(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Python"])

        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")
        shutil.copytree(bp / "agents", target / "agents")

        original_content = (target / "agents" / "implementer.md").read_text(encoding="utf-8")

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
            platform="claude",
        )

        after_content = (target / "agents" / "implementer.md").read_text(encoding="utf-8")
        assert after_content == original_content, (
            "claude platform must NOT modify agent persona files — Claude auto-loads .claude/rules/"
        )

    def test_inline_is_idempotent_on_re_mint(self, tmp_path):
        """Running install_rules_packs twice on gemini → marker section appears exactly once."""
        from harness.init.minting_engine import install_rules_packs

        bp = _make_boilerplate_with_agents(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Python"])

        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")
        shutil.copytree(bp / "agents", target / "agents")

        kwargs = dict(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
            platform="gemini",
        )

        # First install
        install_rules_packs(**kwargs)
        # Rebuild packs_root for second run (packs get pruned after first install)
        shutil.rmtree(target / "rules" / "packs")
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        # Second install
        install_rules_packs(**kwargs)

        persona = target / "agents" / "implementer.md"
        content = persona.read_text(encoding="utf-8")
        # Marker must appear exactly once
        assert content.count("<!-- harness:rules-packs:start -->") == 1, (
            "harness:rules-packs:start marker must appear exactly once after two installs (idempotent)"
        )

    def test_dynamically_generated_agent_gets_inlined_non_claude(self, tmp_path):
        """Dynamically generated agent files (created after install_rules_packs) must also
        receive the '## Stack Rules (auto-included)' section on non-Claude platforms.

        Reproduces the sequencing bug: install_rules_packs inlines into existing agents,
        but dynamic agents are written AFTER that call.  The fix is that mint_workspace
        must call _inline_packs_into_personas again at the end, after all agents exist.

        This test directly exercises the re-inline step: call install (agents_dir empty),
        then add a new agent file, then call _inline_packs_into_personas, assert it gets
        the section.
        """
        from harness.init.minting_engine import install_rules_packs, _inline_packs_into_personas

        bp = _make_boilerplate(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        _write_domain_json(project, ["Python"])

        target = tmp_path / "target_plugin"
        target.mkdir()
        shutil.copytree(bp / "rules" / "packs", target / "rules" / "packs")

        # agents_dir starts EMPTY — simulates that no static agents exist at install time
        agents_dir = target / "agents"
        agents_dir.mkdir()

        install_rules_packs(
            project_path=project,
            deployed_plugin_path=target,
            packs_root=target / "rules" / "packs",
            features={},
            platform="gemini",
        )

        # Verify: existing (empty) agents_dir was processed — no agents means nothing to inline yet
        assert len(list(agents_dir.glob("*.md"))) == 0

        # Now simulate dynamic agent generation: write a new agent file AFTER install
        dynamic_agent = agents_dir / "dynamic-researcher.md"
        dynamic_agent.write_text(
            "---\nname: dynamic-researcher\n---\n# Dynamic Researcher\n\nDo research.\n"
        )

        # Without the fix, the dynamic agent would NOT have the inline section at this point.
        content_before_reinline = dynamic_agent.read_text(encoding="utf-8")
        assert "## Stack Rules (auto-included)" not in content_before_reinline, (
            "precondition: dynamic agent must NOT have the section before re-inline"
        )

        # The fix: call _inline_packs_into_personas again after all agents are generated.
        install_root = project / ".claude" / "rules" / "harness"
        from harness.init.lang_aliases import stack_to_packs
        matched_lang_packs = stack_to_packs(["Python"])
        _inline_packs_into_personas(
            install_root=install_root,
            agents_dir=agents_dir,
            matched_lang_packs=matched_lang_packs,
        )

        # After re-inline, the dynamic agent must have the section
        content_after = dynamic_agent.read_text(encoding="utf-8")
        assert "## Stack Rules (auto-included)" in content_after, (
            "dynamic agent must have '## Stack Rules (auto-included)' after _inline_packs_into_personas re-run"
        )
        assert "<!-- harness:rules-packs:start -->" in content_after, (
            "dynamic agent must have harness:rules-packs:start marker after re-inline"
        )
