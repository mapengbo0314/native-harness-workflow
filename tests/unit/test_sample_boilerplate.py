import os
import subprocess
import pytest

BOILERPLATE_PATH = "tests/fixtures/boilerplates/sample-py-app"

def test_boilerplate_files_exist():
    expected_files = [
        "requirements.txt",
        "pyproject.toml",
        "src/app.py",
        "tests/test_app.py",
    ]
    for rel_path in expected_files:
        full_path = os.path.join(BOILERPLATE_PATH, rel_path)
        assert os.path.exists(full_path), f"Missing {rel_path}"

def test_boilerplate_is_runnable():
    # Try to run pytest on the boilerplate from within its directory
    result = subprocess.run(
        ["pytest"],
        cwd=BOILERPLATE_PATH,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Pytest failed on boilerplate:\n{result.stdout}\n{result.stderr}"
