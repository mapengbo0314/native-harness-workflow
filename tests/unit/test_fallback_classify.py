"""Tests for fallback_classify keyword coverage.

Uses the same exec()-based extraction as run_routing.py to avoid module-level
side effects in prompt_classifier.py (stdout manipulation, langfuse imports).
"""
from __future__ import annotations

from pathlib import Path

import pytest

BOILERPLATE_HOOK = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks/prompt_classifier.py"
)


def _load_fallback_classify():
    source = BOILERPLATE_HOOK.read_text()
    start = source.find("def fallback_classify(")
    end = source.find("\n@", start)
    fn_source = source[start:end].strip()
    ns: dict = {}
    exec(fn_source, ns)
    return ns["fallback_classify"]


@pytest.fixture(scope="module")
def classify():
    return _load_fallback_classify()


# --- Category A: Bug fix / diagnosis ---

@pytest.mark.parametrize("prompt", [
    "fix the broken login",
    "there's a stack trace in the error log",
    "users are getting a 500 error on checkout",
    "why is the test failing?",
    "there's a NullPointerException in production",
    "the build is broken",
    "debug this crash",
])
def test_category_A(classify, prompt):
    assert classify(prompt) == "A", f"Expected A for: {prompt!r}"


# --- Category B: genuinely open design work (F4 bias-to-D: B is reserved) ---

@pytest.mark.parametrize("prompt", [
    "design the database schema for the new invoicing module",
    "plan the migration strategy for the user data move",
    "what architecture should the new billing system use",
    "brainstorm approaches to caching the search results",
])
def test_category_B(classify, prompt):
    assert classify(prompt) == "B", f"Expected B for: {prompt!r}"


# --- Category D: implement-style prompts (F4 proportionality: bias-to-D) ---
# These previously classified B; the search-first proportionality guard sends
# concrete, scoped implementation requests to D so they are not dragged
# through the research/planning pipeline.  D's pre-flight asks 1-2 clarifying
# questions when context is missing instead of escalating to B.

@pytest.mark.parametrize("prompt", [
    "implement the CSV export feature",
    "add a dark mode toggle to the settings page",
    "build a rate limiter for the API",
    "write a script to migrate user data to the new format",
    "create a webhook handler for Stripe events",
    "add pagination to the repos endpoint",
    "rename the helper module",
])
def test_category_D_bias(classify, prompt):
    assert classify(prompt) == "D", f"Expected D for: {prompt!r}"


# --- Category C: Explanation / navigation ---

@pytest.mark.parametrize("prompt", [
    "how does the dispatcher work?",
    "where is the auth middleware defined?",
    "explain the difference between the planner and implementer agents",
    "what does the prompt_classifier hook do?",
    "walk me through the minting pipeline",
    "which file handles the GitHub API calls?",
])
def test_category_C(classify, prompt):
    assert classify(prompt) == "C", f"Expected C for: {prompt!r}"


# --- Category E: Misc / off-topic ---

@pytest.mark.parametrize("prompt", [
    "tell me a joke",
    "what's the weather like?",
    "summarize what we've done today",
    "who invented Python?",
])
def test_category_E(classify, prompt):
    assert classify(prompt) == "E", f"Expected E for: {prompt!r}"
