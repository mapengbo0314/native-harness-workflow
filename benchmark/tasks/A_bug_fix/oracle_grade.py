"""Oracle grader for A-bug-fix-001: Fix login error.

Runs pytest on the workspace to verify the bug is fixed.  The test suite
already contains test_login_unknown_user_raises which documents the correct
behaviour — if that passes, the bug is fixed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = workspace.resolve()

    # Use the same Python interpreter that's running the oracle so we get
    # the right venv / installed packages (including pytest).
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_auth.py", "-q", "--tb=short", "--no-header"],
            cwd=str(w),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {
            "task": "A-bug-fix-001",
            "workspace": str(w),
            "outcome_score": 0.0,
            "passed": False,
            "details": "pytest timed out",
        }
    except Exception as exc:
        return {
            "task": "A-bug-fix-001",
            "workspace": str(w),
            "outcome_score": 0.0,
            "passed": False,
            "details": f"could not run pytest: {exc}",
        }

    stdout = result.stdout + result.stderr
    passed_count, failed_count = _parse_pytest_counts(stdout)
    all_passed = result.returncode == 0 and failed_count == 0

    # Full credit if all tests pass; partial credit if some pass
    if all_passed:
        score = 1.0
    elif passed_count > 0:
        total = passed_count + failed_count
        score = round(passed_count / total, 4) if total > 0 else 0.0
    else:
        score = 0.0

    return {
        "task": "A-bug-fix-001",
        "workspace": str(w),
        "outcome_score": score,
        "passed": all_passed,
        "details": stdout.strip()[:2000],
        "pytest_returncode": result.returncode,
        "tests_passed": passed_count,
        "tests_failed": failed_count,
    }


def _parse_pytest_counts(output: str) -> tuple[int, int]:
    """Extract (passed, failed) counts from pytest -q output."""
    import re

    # Look for summary line like "3 passed" or "1 failed, 2 passed"
    passed = 0
    failed = 0
    m = re.search(r"(\d+)\s+passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", output)
    if m:
        failed = int(m.group(1))
    return passed, failed
