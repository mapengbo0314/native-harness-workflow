import os
from unittest.mock import patch

import pytest

from harness.init.minting_engine import handle_code_conflicts


@pytest.fixture(autouse=True)
def clear_headless_mode():
    previous = os.environ.pop("HARNESS_HEADLESS", None)
    yield
    if previous is not None:
        os.environ["HARNESS_HEADLESS"] = previous


def test_handle_code_conflicts_headless(capsys):
    """Test that in headless mode, the function returns the new content automatically."""
    with patch.dict(os.environ, {"HARNESS_HEADLESS": "1"}):
        existing = "def old(): pass"
        new = "def new(): pass"
        result = handle_code_conflicts(existing, new, "test.py")
        assert result == new
        captured = capsys.readouterr()
        assert "[HARNESS] Headless mode: Auto-overwriting test.py" in captured.out

def test_handle_code_conflicts_identical():
    """Test that if files are identical, it returns the new content without prompting."""
    existing = "print('hello')"
    new = "print('hello')"
    # Even in non-headless mode, if identical, it should just return new
    result = handle_code_conflicts(existing, new, "test.py")
    assert result == new

@patch("builtins.input", side_effect=["O"])
def test_handle_code_conflicts_user_overwrite(mock_input, capsys):
    """Test user choosing to overwrite with new boilerplate."""
    existing = "old_code()"
    new = "new_code()"
    result = handle_code_conflicts(existing, new, "test.py")
    assert result == new
    captured = capsys.readouterr()
    assert "--- CONFLICT: test.py ---" in captured.out
    assert "-old_code()" in captured.out
    assert "+new_code()" in captured.out

@patch("builtins.input", side_effect=["K"])
def test_handle_code_conflicts_user_keep(mock_input):
    """Test user choosing to keep existing version."""
    existing = "old_code()"
    new = "new_code()"
    result = handle_code_conflicts(existing, new, "test.py")
    assert result == existing
