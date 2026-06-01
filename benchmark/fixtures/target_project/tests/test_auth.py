"""Tests for auth module."""
import pytest
from src.auth import login, get_user, create_session, logout


def test_login_known_user():
    result = login("alice", "any")
    assert "token" in result
    assert result["user_id"] == 1


def test_login_unknown_user_raises():
    # This test documents the bug — login should raise ValueError, not TypeError
    with pytest.raises(ValueError, match="Invalid credentials"):
        login("nobody", "any")


def test_logout_clears_session():
    token = create_session("alice")
    logout(token)
    from src.auth import get_session_user
    assert get_session_user(token) is None
