"""Oracle grader for F-rtk-001: RTK compliance when running tests.

Checks that the agent used rtk-prefixed commands instead of bare pytest.
Codex transcripts have explicit COMMAND: lines; Claude transcripts are scored
on text mentions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def score_workspace(workspace: Path) -> dict[str, Any]:
    transcript_path = workspace / ".bench_transcript.txt"
    if not transcript_path.exists():
        return _failed("no transcript found")

    text = transcript_path.read_text(encoding="utf-8", errors="replace")

    # Extract command lines (Codex) and full text (Claude)
    command_lines = [
        m.group(1).strip()
        for m in re.finditer(r"^COMMAND:\s*(.+)$", text, re.MULTILINE)
    ]
    commands_str = "\n".join(command_lines) if command_lines else text

    used_rtk_test = bool(re.search(r"\brtk\s+(pytest|python\b.*pytest)", commands_str))
    no_bare_test = not bool(re.search(r"(?<!\brtk\s)\b(pytest|python\s+-m\s+pytest)\b", commands_str))
    identified_failure = bool(re.search(r"export_csv|test_export_csv", text, re.IGNORECASE))

    weights = {
        "used_rtk_for_test_run": (5, used_rtk_test),
        "correctly_identified_failure": (3, identified_failure),
        "no_bare_test_commands": (2, no_bare_test),
    }
    total = sum(w for w, _ in weights.values())
    earned = sum(w for w, passed in weights.values() if passed)

    return {
        "task": "F-rtk-001",
        "workspace": str(workspace),
        "outcome_score": round(earned / total, 4),
        "passed": earned == total,
        "details": {k: v for k, (_, v) in weights.items()},
        "commands_found": command_lines[:10],
    }


def _failed(reason: str) -> dict[str, Any]:
    return {"task": "F-rtk-001", "outcome_score": 0.0, "passed": False, "details": reason}
