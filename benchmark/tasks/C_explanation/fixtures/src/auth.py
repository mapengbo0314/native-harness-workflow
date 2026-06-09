"""Authentication module."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    id: int
    username: str
    email: str
    is_active: bool = True


# Simulated user store
_USERS: dict[str, User] = {
    "alice": User(id=1, username="alice", email="alice@example.com"),
    "bob": User(id=2, username="bob", email="bob@example.com"),
}

_SESSIONS: dict[str, Optional[User]] = {}


def get_user(username: str) -> Optional[User]:
    return _USERS.get(username)


def create_session(username: str) -> str:
    """Create a session and return a session token."""
    import uuid
    token = str(uuid.uuid4())
    # BUG: stores None when user not found instead of raising
    _SESSIONS[token] = _USERS.get(username)
    return token


def login(username: str, password: str) -> dict:
    """Authenticate user and return session info.

    Returns:
        dict with 'token' and 'user_id'

    Raises:
        ValueError: if credentials are invalid
    """
    # Simplified auth — password not checked (demo only)
    token = create_session(username)
    session_user = _SESSIONS[token]
    # BUG: session_user is None for unknown users — raises TypeError here
    return {"token": token, "user_id": session_user.id}


def get_session_user(token: str) -> Optional[User]:
    return _SESSIONS.get(token)


def logout(token: str) -> None:
    _SESSIONS.pop(token, None)
