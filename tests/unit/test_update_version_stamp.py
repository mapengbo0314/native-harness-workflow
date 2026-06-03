"""S1 — lock the two version planes: manifest version == pyproject version."""
import tomllib
from pathlib import Path

import harness
from harness.update.manifest import _read_harness_version


def test_manifest_version_matches_pyproject():
    pkg = Path(harness.__file__).parent
    repo_root = pkg.parent.parent
    with open(repo_root / "pyproject.toml", "rb") as f:
        expected = tomllib.load(f)["project"]["version"]
    assert _read_harness_version(pkg) == expected
