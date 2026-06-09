"""Oracle grader for B-implementation-001: Add CSV export feature.

Runs pytest against test_data_table.py only — the auth tests are intentionally
excluded because the fixture carries a pre-existing auth bug (that's A_bug_fix's
subject, not this task's).

Scoring:
  1.0  — all data_table tests pass (feature implemented, no regressions)
  0.5  — export_csv test passes but other data_table tests regressed
  0.0  — export_csv test does not pass
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = workspace.resolve()

    try:
        # Run only test_data_table.py — isolates this task from the auth bug fixture
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_data_table.py", "-v",
             "--tb=short", "--no-header"],
            cwd=str(w),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return _failed(w, "pytest timed out")
    except Exception as exc:
        return _failed(w, f"could not run pytest: {exc}")

    stdout = result.stdout + result.stderr
    # -v output: "tests/test_data_table.py::test_export_csv_returns_string PASSED"
    export_test_passed = "test_export_csv_returns_string PASSED" in stdout
    all_passed = result.returncode == 0

    if all_passed:
        score = 1.0
    elif export_test_passed:
        score = 0.5  # feature works but agent broke something else
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
    }


def _failed(w: Path, reason: str) -> dict[str, Any]:
    return {
        "task": "B-implementation-001",
        "workspace": str(w),
        "outcome_score": 0.0,
        "passed": False,
        "export_test_passed": False,
        "details": reason,
    }
