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
