"""
ScenarioScorer — evaluates a completed sandbox run against expected_behavior.

Deterministic checks (no LLM required):
  routing_correct  — did sandbox_events.json record the expected routing branch?
  tdd_adherence    — did a test file write precede a source file write?
  task_complete    — does pytest pass in the workspace?
  no_loop          — were there no repeated identical (tool, args) pairs?

Each check returns a float 0.0–1.0 or None if it cannot be applied (no expected
value specified, or no relevant events captured). None checks are excluded from
the weighted aggregate so partial scenarios score fairly.

The aggregate passes at >= 0.7 by default.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# Weights must sum to 1.0 across all checks that can be applied.
# When a check is skipped (returns None), remaining weights are renormalised.
_WEIGHTS = {
    "routing_correct": 0.35,
    "tdd_adherence":   0.25,
    "task_complete":   0.30,
    "no_loop":         0.10,
}

PASS_THRESHOLD = 0.7


class ScenarioScorer:
    def __init__(
        self,
        workspace: Path,
        events_file: Path,
        expected_behavior: Optional[Dict[str, Any]] = None,
    ):
        self.workspace = workspace
        self.events_file = events_file
        self.expected = expected_behavior or {}
        self._events: Optional[List[Dict]] = None

    @property
    def events(self) -> List[Dict]:
        if self._events is None:
            self._events = _load_events(self.events_file)
        return self._events

    def _tool_events(self) -> List[Dict]:
        return [e for e in self.events if e.get("event") == "TOOL"]

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def score_routing_correct(self) -> Optional[float]:
        """1.0 if the recorded branch matches expected_behavior.branch."""
        expected_branch = self.expected.get("branch")
        if not expected_branch:
            return None

        for event in self.events:
            payload = event.get("payload", {})
            branch = payload.get("intent_branch") or payload.get("branch")
            if branch:
                return 1.0 if branch.upper() == expected_branch.upper() else 0.0

        return 0.0  # routing event never appeared

    def score_tdd_adherence(self) -> Optional[float]:
        """
        1.0  — first write was a test file, followed by a source write.
        0.5  — tests were written but no source write followed (incomplete, not wrong).
        0.0  — source was written before tests, or only source was written.
        None — no writes at all (cannot judge).
        """
        writes = _collect_writes(self._tool_events())
        if not writes:
            return None

        first_test = next((i for i, w in enumerate(writes) if w["is_test"]), None)
        first_src = next((i for i, w in enumerate(writes) if not w["is_test"]), None)

        if first_test is None:
            return 0.0   # only source writes
        if first_src is None:
            return 0.5   # only test writes — incomplete but not a TDD violation
        return 1.0 if first_test < first_src else 0.0

    def score_task_complete(self) -> float:
        """1.0 if pytest exits 0 in the workspace, 0.0 otherwise."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--tb=no", "-q"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        return 1.0 if result.returncode == 0 else 0.0

    def score_no_loop(self) -> float:
        """1.0 if no identical (tool_name, args) pair repeats; 0.0 if a loop is detected."""
        seen: List[tuple] = []
        for event in self._tool_events():
            p = event.get("payload", {})
            key = (
                p.get("tool_name", ""),
                json.dumps(p.get("tool_args") or {}, sort_keys=True),
            )
            if key in seen:
                return 0.0
            seen.append(key)
        return 1.0

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    def score_all(self) -> Dict[str, Any]:
        """
        Run all checks and return:
          {
            "scores":    {check_name: float},
            "skipped":   [check_name, ...],
            "aggregate": float | None,
            "passed":    bool,
          }
        """
        checks = {
            "routing_correct": self.score_routing_correct,
            "tdd_adherence":   self.score_tdd_adherence,
            "task_complete":   self.score_task_complete,
            "no_loop":         self.score_no_loop,
        }

        scores: Dict[str, float] = {}
        skipped: List[str] = []

        for name, fn in checks.items():
            value = fn()
            if value is None:
                skipped.append(name)
            else:
                scores[name] = round(value, 4)

        total_weight = sum(_WEIGHTS[k] for k in scores)
        if total_weight > 0:
            aggregate = round(
                sum(scores[k] * _WEIGHTS[k] for k in scores) / total_weight,
                4,
            )
        else:
            aggregate = None

        return {
            "scores":    scores,
            "skipped":   skipped,
            "aggregate": aggregate,
            "passed":    aggregate is not None and aggregate >= PASS_THRESHOLD,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _load_events(events_file: Path) -> List[Dict]:
    if not events_file.exists():
        return []
    events = []
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


def _collect_writes(tool_events: List[Dict]) -> List[Dict]:
    writes = []
    for event in tool_events:
        p = event.get("payload", {})
        tool_name = p.get("tool_name", "").lower()
        if tool_name not in ("write_file", "write", "edit", "replace", "multiedit"):
            continue
        args = p.get("tool_args") or p.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        path = args.get("file_path") or args.get("path") or ""
        is_test = "test" in path.lower() or path.startswith("tests/")
        writes.append({"path": path, "is_test": is_test})
    return writes
