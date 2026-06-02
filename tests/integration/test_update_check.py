"""A7 — `harness-wf update --check` is read-only and reports verdicts.

Setup uses the manifest API against the REAL package source; the command is
exercised via subprocess (faithful CLI path). Asserts zero disk mutation.
"""
import subprocess
import sys
import json
import os
from pathlib import Path

import pytest

import harness
from harness.init.runtime_slice import reproduce_runtime_file
from harness.update.manifest import normalize_and_hash, write_base_sidecar, write_manifest

PACKAGE_ROOT = Path(harness.__file__).parent


def _snapshot(root: Path) -> dict[str, float]:
    return {str(p): p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def minted_project(tmp_path):
    """A minimal deployed plugin with a real runtime file + a manifest."""
    plug = tmp_path / ".claude" / "harness-wf-plugin"
    (plug / "src").mkdir(parents=True)
    # Copy a real runtime source so it compares as 'current'.
    disp_src = PACKAGE_ROOT / "runtime" / "dispatcher.py"
    (plug / "src" / "dispatcher.py").write_text(disp_src.read_text())
    write_manifest(plug, PACKAGE_ROOT, render_context={"platform": "claude"})
    return tmp_path


def _run(project: Path, *args, input_text: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "harness.init.cli", "update",
         "--project-path", str(project), *args],
        capture_output=True, text=True, input=input_text, env=env,
    )


def test_check_runs_read_only_and_reports(minted_project):
    before = _snapshot(minted_project)
    result = _run(minted_project, "--check")
    after = _snapshot(minted_project)

    assert result.returncode == 0, result.stderr
    # dispatcher copied verbatim from upstream -> current
    assert "current" in result.stdout.lower()
    assert "src/dispatcher.py" in result.stdout
    # nothing written
    assert before == after, "update --check must not mutate any file"


def test_check_detects_user_edit(minted_project):
    plug = minted_project / ".claude" / "harness-wf-plugin"
    (plug / "src" / "dispatcher.py").write_text("# locally hacked\n")
    result = _run(minted_project, "--check")
    assert result.returncode == 0, result.stderr
    assert "keep-yours" in result.stdout.lower()


def test_missing_manifest_exits_nonzero(tmp_path):
    (tmp_path / ".claude" / "harness-wf-plugin").mkdir(parents=True)
    result = _run(tmp_path, "--check")
    assert result.returncode != 0


def test_update_apply_refreshes_merges_and_preserves_user_files(tmp_path):
    plug = tmp_path / ".claude" / "harness-wf-plugin"
    (plug / "src").mkdir(parents=True)
    (plug / "agents").mkdir(parents=True)
    skill_rel = "skills/harness-systematic-debugging/SKILL.md"
    (plug / Path(skill_rel).parent).mkdir(parents=True)
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "settings.json").write_text('{"user": true}\n')
    custom_skill = tmp_path / ".claude" / "user-skills" / "custom" / "SKILL.md"
    custom_skill.parent.mkdir(parents=True)
    custom_skill.write_text("custom skill\n")

    dispatcher = plug / "src" / "dispatcher.py"
    agent = plug / "agents" / "implementer.md"
    skill = plug / skill_rel
    dispatcher.write_text("old dispatcher\n")
    agent.write_text("base agent\n")
    skill.write_text((PACKAGE_ROOT / "templates" / "boilerplate" / skill_rel).read_text())
    (plug / "agents.json").write_text("{}\n")

    manifest = write_manifest(
        plug,
        PACKAGE_ROOT,
        render_context={"platform": "claude", "harness_dir_name": ".claude", "selected_agents": []},
    )
    manifest["owned"]["src/dispatcher.py"]["source_hash"] = normalize_and_hash("old dispatcher\n")
    manifest["owned"]["agents/implementer.md"]["source_hash"] = normalize_and_hash("base agent\n")
    manifest["owned"]["agents/implementer.md"]["rendered_hash"] = normalize_and_hash("base agent\n")
    (plug / ".harness-meta.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_base_sidecar(plug, manifest)

    agent.write_text("local agent edit\n")
    skill.write_text("local skill edit\n")

    result = _run(tmp_path, input_text="O\n")

    assert result.returncode == 0, result.stderr
    assert dispatcher.read_text() == reproduce_runtime_file("dispatcher.py", platform="claude", package_root=PACKAGE_ROOT)
    assert agent.read_text() != "local agent edit\n"
    assert skill.read_text() == "local skill edit\n"
    agents_json = json.loads((plug / "agents.json").read_text())
    assert agents_json["agents"]["implementer"]["source"] == agent.read_text()
    assert (tmp_path / ".claude" / "settings.json").read_text() == '{"user": true}\n'
    assert custom_skill.read_text() == "custom skill\n"


def test_update_apply_headless_conflict_applies_nothing(tmp_path):
    plug = tmp_path / ".claude" / "harness-wf-plugin"
    (plug / "agents").mkdir(parents=True)
    agent = plug / "agents" / "implementer.md"
    agent.write_text("base agent\n")
    manifest = write_manifest(
        plug,
        PACKAGE_ROOT,
        render_context={"platform": "claude", "harness_dir_name": ".claude", "selected_agents": []},
    )
    manifest["owned"]["agents/implementer.md"]["source_hash"] = normalize_and_hash("base agent\n")
    manifest["owned"]["agents/implementer.md"]["rendered_hash"] = normalize_and_hash("base agent\n")
    (plug / ".harness-meta.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_base_sidecar(plug, manifest)
    agent.write_text("local agent edit\n")

    env = os.environ.copy()
    env["HARNESS_HEADLESS"] = "1"
    result = _run(tmp_path, env=env)

    assert result.returncode != 0
    assert agent.read_text() == "local agent edit\n"
