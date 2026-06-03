"""Ghost-injection split (R4).

`mint_workspace` appends the target project's CONTEXT.md "Strict Invariants"
to agents/implementer.md at mint time (minting_engine.py:210). That tail is
project-owned, not harness-owned, and must be preserved verbatim across
updates. The harness owns only the portion ABOVE the marker.
"""
from __future__ import annotations

GHOST_MARKER = "### STRICT INVARIANTS (Ghost Injection)"


def split_ghost_injection(text: str) -> tuple[str, str]:
    """Return (harness_part, project_tail).

    project_tail is "" when the marker is absent (whole file is harness-owned).
    When present, project_tail starts at the marker and runs to end of file.
    """
    idx = text.find(GHOST_MARKER)
    if idx == -1:
        return text, ""
    return text[:idx], text[idx:]
