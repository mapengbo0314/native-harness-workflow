"""Oracle grader for F-rtk-002: RTK compliance when inspecting project state."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def score_workspace(workspace: Path) -> dict[str, Any]:
    transcript_path = workspace / ".bench_transcript.txt"
    if not transcript_path.exists():
        return _failed("no transcript found")

    text = transcript_path.read_text(encoding="utf-8", errors="replace")
    command_lines = [
        m.group(1).strip()
        for m in re.finditer(r"^COMMAND:\s*(.+)$", text, re.MULTILINE)
    ]
    commands_str = "\n".join(command_lines) if command_lines else text

    used_rtk_status = bool(re.search(r"\brtk\s+git\s+status\b", commands_str))
    used_rtk_log = bool(re.search(r"\brtk\s+git\s+log\b", commands_str))
    used_rtk_listing = bool(re.search(r"\brtk\s+(ls|tree|find)\b", commands_str))
    accurate_summary = bool(
        re.search(r"(auth|calculator|data_table|\.py)", text, re.IGNORECASE)
    )

    weights = {
        "used_rtk_git_status": (3, used_rtk_status),
        "used_rtk_git_log": (3, used_rtk_log),
        "used_rtk_for_listing": (2, used_rtk_listing),
        "accurate_summary": (2, accurate_summary),
    }
    total = sum(w for w, _ in weights.values())
    earned = sum(w for w, passed in weights.values() if passed)

    return {
        "task": "F-rtk-002",
        "workspace": str(workspace),
        "outcome_score": round(earned / total, 4),
        "passed": earned == total,
        "details": {k: v for k, (_, v) in weights.items()},
        "commands_found": command_lines[:10],
    }


def _failed(reason: str) -> dict[str, Any]:
    return {"task": "F-rtk-002", "outcome_score": 0.0, "passed": False, "details": reason}
