"""Phase 1a (ECC feature port): language alias map for rules-pack selection.

Maps Linguist / cdxgen display names (as found in domain.json ``stack``) to
the pack directory names used under ``rules/packs/``.

Only LANGUAGE entries are mapped.  Framework/tool names (Django, FastAPI,
React, …) are deliberately absent — they are not substring-matched and will
return nothing.

Public API
----------
PACK_ALIASES : dict[str, str]
    Case-insensitive lookup key (lowercase) → pack dir name.

stack_to_packs(stack: list[str]) -> set[str]
    Return the set of pack-dir names for recognised language entries in
    *stack*.  Unrecognised or framework entries are silently skipped.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Alias map  (key = lowercase Linguist display name, value = pack dir name)
# ---------------------------------------------------------------------------

PACK_ALIASES: dict[str, str] = {
    "python": "python",
    "go": "golang",
    "golang": "golang",       # cdxgen sometimes emits "Golang"
    "typescript": "typescript",
    "javascript": "javascript",
}


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def stack_to_packs(stack: list[str]) -> set[str]:
    """Return pack-dir names for the recognised language entries in *stack*.

    Lookup is case-insensitive.  Framework names and unknown entries are
    ignored (NOT substring-matched).

    Parameters
    ----------
    stack:
        List of display-name strings from ``domain.json`` (e.g.
        ``["Python", "Go", "Django"]``).

    Returns
    -------
    set[str]
        Set of pack directory names (e.g. ``{"python", "golang"}``).
    """
    result: set[str] = set()
    for entry in stack:
        pack = PACK_ALIASES.get(entry.lower())
        if pack is not None:
            result.add(pack)
    return result
