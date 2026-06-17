from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from benchmark.probe.generator import ChainSpec, generate_workspace
from benchmark.probe.scrambler import Scrambler


def _snapshot_py_files(workspace: Path) -> dict[str, str]:
    return {
        str(path.relative_to(workspace)): path.read_text(encoding="utf-8")
        for path in sorted(workspace.rglob("*.py"))
    }


def test_partial_clarity_preserves_importable_workspace(tmp_path: Path) -> None:
    generate_workspace(ChainSpec(depth=2), tmp_path)

    Scrambler(seed=123).scramble_workspace(tmp_path, clarity=0.5)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1
    assert "AssertionError" in result.stdout
    assert "ImportError" not in result.stderr


def test_scrambler_seed_changes_probe_variant(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_workspace(ChainSpec(depth=3), first)
    generate_workspace(ChainSpec(depth=3), second)

    Scrambler(seed=101).scramble_workspace(first, clarity=0.5)
    Scrambler(seed=202).scramble_workspace(second, clarity=0.5)

    assert _snapshot_py_files(first) != _snapshot_py_files(second)


def test_generated_bug_does_not_leak_expected_fix(tmp_path: Path) -> None:
    generate_workspace(ChainSpec(depth=1), tmp_path)

    source = (tmp_path / "src" / "ingestion.py").read_text(encoding="utf-8")

    assert "BUG" not in source
    assert "should be" not in source


def test_scrambler_rejects_invalid_clarity(tmp_path: Path) -> None:
    generate_workspace(ChainSpec(depth=1), tmp_path)

    with pytest.raises(ValueError, match="clarity"):
        Scrambler().scramble_workspace(tmp_path, clarity=1.5)
