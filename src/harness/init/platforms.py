"""Single source of truth for the CLI platform-choice digit map.

The mint flow accepts a numeric platform choice ("1".."5"); both ``cli`` and
``minting_engine`` need to turn that into a canonical platform name and a
deployment folder. This module owns the mapping so it cannot drift across call
sites (review 2026-06-12 H4). Intentionally has ZERO harness.* imports — it is a
leaf so any module can import it without a cycle.
"""
from __future__ import annotations

PLATFORM_BY_DIGIT = {
    "1": "gemini",
    "2": "claude",
    "3": "cursor",
    "4": "agents",
    "5": "codex",
}

_KNOWN_PLATFORMS = frozenset(PLATFORM_BY_DIGIT.values())


def platform_name_from_choice(choice: str) -> str:
    """Map a platform digit ("1".."5") to its canonical name; an unrecognized
    value passes through lowercased (callers may pass a name directly)."""
    return PLATFORM_BY_DIGIT.get(choice, choice).lower()


def harness_folder_from_choice(choice: str) -> str:
    """Deployment folder for a platform choice (``.claude``/``.gemini``/…).

    Equivalent to the legacy if/elif: known platforms map to ``"." + name``;
    anything unrecognized falls back to the embedded ``.agents`` layout.
    """
    name = platform_name_from_choice(choice)
    return "." + (name if name in _KNOWN_PLATFORMS else "agents")
