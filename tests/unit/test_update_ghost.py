"""B4 — split implementer.md at the ghost-injection marker (R4).

Harness owns everything ABOVE the marker; the marker + invariants below are
project-owned and never touched by update.
"""
from harness.update.ghost import split_ghost_injection, GHOST_MARKER


def test_split_separates_harness_and_project_tail():
    text = "# Implementer\nrole stuff\n\n" + GHOST_MARKER + "\ninv1\ninv2\n"
    harness_part, tail = split_ghost_injection(text)
    assert "role stuff" in harness_part
    assert GHOST_MARKER not in harness_part
    assert "inv1" in tail and "inv2" in tail


def test_split_no_marker_is_all_harness():
    text = "# Implementer\nrole\n"
    harness_part, tail = split_ghost_injection(text)
    assert harness_part == text
    assert tail == ""


def test_marker_string_matches_minting_engine():
    # Guard against drift from minting_engine.py:210
    assert GHOST_MARKER == "### STRICT INVARIANTS (Ghost Injection)"
