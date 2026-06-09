"""Oracle grader for C-explanation-001: Explain dispatcher routing.

Scores the agent's explanation against four criteria using transcript
pattern matching (deterministic) plus a word-count check. No LLM judge needed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


_DISPATCHER_TERMS = [
    "dispatcher", "prompt_classifier", "classify", "classification",
    "route", "routing", "router",
]
_CATEGORY_TERMS = [
    "A_bug", "B_impl", "C_exp", "E_misc",
    "bug_fix", "implementation", "explanation",
    "category", " A ", " B ", " C ", " E ",
    "A-", "B-", "C-", "E-",
]
_FILE_TERMS = [
    "dispatcher.py", "prompt_classifier.py", "classifier.py",
    "hook_common", "pre_tool_use",
]


def score_workspace(workspace: Path) -> dict[str, Any]:
    transcript_path = workspace / ".bench_transcript.txt"
    if not transcript_path.exists():
        return _failed("no transcript found")

    text = transcript_path.read_text(encoding="utf-8", errors="replace").lower()
    word_count = len(text.split())

    referenced_file = any(t.lower() in text for t in _FILE_TERMS)
    explained_classification = (
        any(t.lower() in text for t in _DISPATCHER_TERMS)
        and any(t.lower() in text for t in _CATEGORY_TERMS)
    )
    concise = word_count <= 500  # generous limit; original asked for 300 but JSON adds overhead

    # Hallucination heuristic: penalise only if the text confidently asserts
    # specific non-existent file paths we know are wrong
    hallucination_markers = ["router.py", "agent_router.py", "dispatch_table.py"]
    no_hallucination = not any(m in text for m in hallucination_markers)

    weights = {
        "referenced_correct_file": (2, referenced_file),
        "explained_classification": (2, explained_classification),
        "no_hallucination": (2, no_hallucination),
        "concise": (1, concise),
    }
    total = sum(w for w, _ in weights.values())
    earned = sum(w for w, passed in weights.values() if passed)

    return {
        "task": "C-explanation-001",
        "workspace": str(workspace),
        "outcome_score": round(earned / total, 4),
        "passed": earned == total,
        "word_count": word_count,
        "details": {k: v for k, (_, v) in weights.items()},
    }


def _failed(reason: str) -> dict[str, Any]:
    return {
        "task": "C-explanation-001",
        "outcome_score": 0.0,
        "passed": False,
        "details": reason,
    }
