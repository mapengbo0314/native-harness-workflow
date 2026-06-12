"""Single source of truth for keyword fallback intent classification.

Phase 6a Group 3 (review finding #1): the tool-plane dispatcher fast-path and
the deployed prompt_classifier fallback drifted into contradiction
(implement/build/create/new → B in one, D in the other). Both now consume this
table — it ships in the runtime slice, so minted plugins carry the same copy
the tool plane imports. tests/unit/test_fallback_parity.py pins a fixed
corpus across all consumers; drift fails CI.

Precedence is part of the contract: first match wins in BRANCH_ORDER.
- A before D: 'fix the typo' → A (A's 'fix' outranks any D phrasing; the old
  dead 'fix the' D-entry is gone — review finding #9).
- B before C/D: design language marks genuinely open work.
- Bias-to-D (F4 proportionality): implement-style verbs without design
  language route to D, never B.
- No match → E (no technical intent).
"""
from __future__ import annotations

import re

BRANCH_ORDER = ("A", "B", "C", "D")

KEYWORDS = {
    "A": ["broken", "bug", "error", "fix", "stack trace", "failing",
          "exception", "traceback", "crash"],
    "B": ["design", "architecture", "brainstorm", "spec out", "roadmap"],
    "C": ["how", "where", "explain", "what does", "walk me through",
          "which file", "which"],
    "D": ["typo", "change color", "minor update", "rename", "refactor",
          "add", "create", "write", "build", "set up", "update", "new"],
}

# Word-boundary patterns that substring matching would over-trigger on.
REGEX = {
    "B": re.compile(r"\bplan\b"),
    "D": re.compile(r"\bimplement\b"),
}

DEFAULT_BRANCH = "E"


def classify(prompt: str) -> str:
    """Classify a prompt into routing branch A/B/C/D/E by keyword precedence."""
    p = (prompt or "").lower()
    for branch in BRANCH_ORDER:
        if any(k in p for k in KEYWORDS[branch]):
            return branch
        pattern = REGEX.get(branch)
        if pattern and pattern.search(p):
            return branch
    return DEFAULT_BRANCH
