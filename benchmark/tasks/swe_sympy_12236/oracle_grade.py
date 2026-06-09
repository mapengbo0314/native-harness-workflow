"""Oracle grader for swe-sympy-12236.

Fail-to-pass: test_div must pass (including the new domain assertion for symbolic params).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FAIL_TO_PASS = [
    "sympy/polys/tests/test_polytools.py::test_div",
]

PASS_TO_PASS_SAMPLE = [
    "sympy/polys/tests/test_polytools.py::test_poly",
    "sympy/polys/tests/test_polytools.py::test_gcdex",
]


def score_workspace(workspace: Path) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *FAIL_TO_PASS, "-v", "--tb=short", "--no-header"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=180,
    )
    stdout = result.stdout + result.stderr
    passed = result.returncode == 0

    regression_result = subprocess.run(
        [sys.executable, "-m", "pytest", *PASS_TO_PASS_SAMPLE, "-v", "--tb=short", "--no-header"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=180,
    )
    no_regression = regression_result.returncode == 0

    if passed and no_regression:
        score = 1.0
    elif passed:
        score = 0.75
    else:
        score = 0.0

    return {
        "outcome_score": score,
        "fail_to_pass_passed": passed,
        "no_regression": no_regression,
        "stdout": stdout[:2000],
    }


if __name__ == "__main__":
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    result = score_workspace(workspace)
    print(result)
    sys.exit(0 if result["outcome_score"] >= 1.0 else 1)
