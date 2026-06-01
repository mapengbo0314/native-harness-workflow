"""A7 — `harness-wf update --check` is read-only and reports verdicts.

Setup uses the manifest API against the REAL package source; the command is
exercised via subprocess (faithful CLI path). Asserts zero disk mutation.
"""
import subprocess
import sys
from pathlib import Path

import pytest

import harness
from harness.update.manifest import write_manifest

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


def _run(project: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "harness.init.cli", "update",
         "--project-path", str(project), *args],
        capture_output=True, text=True,
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
