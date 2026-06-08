"""Oracle grader for B-implementation-001: Add CSV export feature.

Runs pytest on the workspace — specifically the test_export_csv_returns_string
test which validates the new feature, plus the full suite to catch regressions.
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
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short", "--no-header"],
            cwd=str(w),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {
            "task": "B-implementation-001",
            "workspace": str(w),
            "outcome_score": 0.0,
            "passed": False,
            "details": "pytest timed out",
        }
    except Exception as exc:
        return {
            "task": "B-implementation-001",
            "workspace": str(w),
            "outcome_score": 0.0,
            "passed": False,
            "details": f"could not run pytest: {exc}",
        }

    stdout = result.stdout + result.stderr
    passed_count, failed_count = _parse_pytest_counts(stdout)
    all_passed = result.returncode == 0 and failed_count == 0

    # Check specifically whether the export_csv test passed
    export_test_passed = "test_export_csv_returns_string" in stdout and "PASSED" in stdout
    # Fallback: if all tests passed, the export test must have passed too
    if all_passed:
        export_test_passed = True

    # Scoring: full credit requires all tests to pass (including the new feature)
    if all_passed:
        score = 1.0
    elif export_test_passed and passed_count > 0:
        # Feature implemented but some other test broke — partial credit
        total = passed_count + failed_count
        score = round(0.5 + 0.5 * passed_count / total, 4) if total > 0 else 0.5
    elif passed_count > 0:
        # Some tests pass but the feature isn't there
        total = passed_count + failed_count
        score = round(0.3 * passed_count / total, 4) if total > 0 else 0.0
    else:
        score = 0.0

    return {
        "task": "B-implementation-001",
        "workspace": str(w),
        "outcome_score": score,
        "passed": all_passed,
        "export_test_passed": export_test_passed,
        "details": stdout.strip()[:2000],
        "pytest_returncode": result.returncode,
        "tests_passed": passed_count,
        "tests_failed": failed_count,
    }


def _parse_pytest_counts(output: str) -> tuple[int, int]:
    """Extract (passed, failed) counts from pytest -q output."""
    import re

    passed = 0
    failed = 0
    m = re.search(r"(\d+)\s+passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", output)
    if m:
        failed = int(m.group(1))
    return passed, failed
