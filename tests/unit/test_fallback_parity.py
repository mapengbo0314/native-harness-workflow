"""Phase 6a Group 3: one keyword table for every fallback classifier.

The 2026-06-11 review (finding #1) confirmed the tool-plane dispatcher
fast-path and the deployed prompt_classifier fallback contradict each other
(implement/build/create/new → B in one, D in the other). The repair: a single
table in src/harness/runtime/fallback_keywords.py (runtime slice — copied
into minted plugins), consumed by both, with this corpus pinning parity:
drift fails CI.

Precedence is part of the contract: A → B → C → D → E, first match wins
('fix the typo' → A because A's 'fix' outranks D — review finding #9 removes
the dead 'fix the' D-entry rather than pretending it routes).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from harness.runtime.fallback_keywords import classify
from harness.runtime.dispatcher import keyword_fast_path

HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)


@pytest.fixture(scope="module")
def fallback_classify():
    """The deployed hook's fallback with the shared-table import BLOCKED —
    deterministically exercises its inline last-resort copy (the real drift
    risk).  Without the block, earlier tests that put a plugin src/ on
    sys.path leak a stale `fallback_keywords` into this test."""
    spec = importlib.util.spec_from_file_location(
        "prompt_classifier_parity_test", HOOKS_DIR / "prompt_classifier.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(HOOKS_DIR))

    def _inline_only(prompt):
        saved = sys.modules.get("fallback_keywords", "absent")
        sys.modules["fallback_keywords"] = None  # forces ImportError inside
        try:
            return mod.fallback_classify(prompt)
        finally:
            if saved == "absent":
                sys.modules.pop("fallback_keywords", None)
            else:
                sys.modules["fallback_keywords"] = saved

    return _inline_only


# (prompt, expected branch) — covers every branch + the precedence cases.
CORPUS = [
    # A — bugs/diagnosis
    ("fix the broken login", "A"),
    ("there's a stack trace in the error log", "A"),
    ("the app crashes on startup", "A"),
    ("tests are failing with an exception", "A"),
    ("fix the typo in the comment", "A"),          # precedence: A's 'fix' outranks D
    # B — genuinely open design work
    ("design a new architecture for the billing system", "B"),
    ("brainstorm approaches for multi-tenant isolation", "B"),
    ("spec out the migration roadmap", "B"),
    ("let's plan the next quarter's refactor", "B"),
    # C — questions / knowledge retrieval
    ("how does the session store work", "C"),
    ("where is the config loaded", "C"),
    ("explain the update pipeline", "C"),
    ("what does the dispatcher do", "C"),
    ("which file handles authentication", "C"),
    ("which approach should I use for caching", "C"),  # review finding #2: bare 'which'
    ("walk me through the mint flow", "C"),
    # D — concrete implementation (bias-to-D)
    ("implement the CSV export feature", "D"),
    ("build a retry wrapper around the client", "D"),
    ("create a helper for date parsing", "D"),
    ("add a new endpoint for health checks", "D"),
    ("rename the variable across the module", "D"),
    ("update the README install section", "D"),
    # E — no technical intent
    ("tell me a joke", "E"),
    ("good morning", "E"),
    # word-boundary guards (review 2026-06-12): substrings must not over-trigger
    ("renew the subscription reminder", "E"),     # 'new' inside 'renew' must not hit D
    ("however, looks good to me", "E"),           # 'how' inside 'however' must not hit C
    ("they went somewhere else", "E"),            # 'where' inside 'somewhere' must not hit C
    ("a new endpoint for health checks", "D"),    # \bnew\b still routes D
    ("how do I run the suite", "C"),              # \bhow\b still routes C
]


class TestSharedTable:
    @pytest.mark.parametrize("prompt,expected", CORPUS)
    def test_corpus_classification(self, prompt, expected):
        assert classify(prompt) == expected, f"{prompt!r} → expected {expected}"

    def test_no_dead_fix_the_in_d(self):
        """Review finding #9: 'fix the' in D was unreachable (A's 'fix' wins).
        The table must not carry it."""
        from harness.runtime.fallback_keywords import KEYWORDS
        assert "fix the" not in KEYWORDS["D"]

    def test_bare_which_routes_c_with_word_boundary(self):
        from harness.runtime.fallback_keywords import REGEX
        assert REGEX["C"].search("which approach wins"), "bare 'which' must route C"
        assert not REGEX["C"].search("sandwiches are great"), "word boundary required"


class TestParity:
    @pytest.mark.parametrize("prompt,expected", CORPUS)
    def test_dispatcher_fast_path_matches_table(self, prompt, expected):
        result = keyword_fast_path(prompt)
        assert result["branch"] == expected, (
            f"dispatcher fast-path diverged on {prompt!r}: "
            f"{result['branch']} != {expected}"
        )

    @pytest.mark.parametrize("prompt,expected", CORPUS)
    def test_deployed_fallback_matches_table(self, fallback_classify, prompt, expected):
        got = fallback_classify(prompt)
        assert got == expected, (
            f"deployed fallback diverged on {prompt!r}: {got} != {expected}"
        )
