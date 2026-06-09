"""Oracle grader for F-rtk-003: RTK compliance — fix and verify.

Combines executable verification (pytest) with transcript analysis for RTK compliance.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def score_workspace(workspace: Path) -> dict[str, Any]:
    # --- Outcome: did the implementation actually pass? ---
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_data_table.py", "-q", "--tb=short", "--no-header"],
            cwd=str(workspace.resolve()),
            capture_output=True,
            text=True,
            timeout=60,
        )
        pytest_passed = result.returncode == 0
        pytest_output = (result.stdout + result.stderr).strip()[:1000]
    except Exception as exc:
        pytest_passed = False
        pytest_output = str(exc)

    # --- Process: did the agent use RTK? ---
    transcript_path = workspace / ".bench_transcript.txt"
    if transcript_path.exists():
        text = transcript_path.read_text(encoding="utf-8", errors="replace")
        command_lines = [
            m.group(1).strip()
            for m in re.finditer(r"^COMMAND:\s*(.+)$", text, re.MULTILINE)
        ]
        commands_str = "\n".join(command_lines) if command_lines else text

        used_rtk_pytest = bool(re.search(r"\brtk\s+(pytest|python\b.*pytest)", commands_str))
        used_rtk_status = bool(re.search(r"\brtk\s+git\s+status\b", commands_str))
        ran_tests_to_verify = pytest_passed or bool(
            re.search(r"(passed|failed|error)", commands_str, re.IGNORECASE)
        )
    else:
        used_rtk_pytest = False
        used_rtk_status = False
        ran_tests_to_verify = False

    weights = {
        "used_rtk_pytest": (4, used_rtk_pytest),
        "used_rtk_git_status": (2, used_rtk_status),
        "implementation_correct": (3, pytest_passed),
        "ran_tests_to_verify": (1, ran_tests_to_verify),
    }
    total = sum(w for w, _ in weights.values())
    earned = sum(w for w, passed in weights.values() if passed)

    return {
        "task": "F-rtk-003",
        "workspace": str(workspace),
        "outcome_score": round(earned / total, 4),
        "passed": earned == total,
        "pytest_passed": pytest_passed,
        "pytest_output": pytest_output,
        "details": {k: v for k, (_, v) in weights.items()},
    }
