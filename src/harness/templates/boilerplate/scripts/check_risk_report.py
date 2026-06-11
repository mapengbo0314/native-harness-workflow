#!/usr/bin/env python3
"""Risk-report staleness checker for the adversary exit gate (F2 ECC port, C3).

There is no dispatcher insertion point for a "design complete" gate, so the
gate lives in skill text: `harness-brainstorming-plans` and
`harness-requesting-code-review` invoke this script before sign-off when
`pipeline.dispatcher.gates.adversary_exit` is on.

  check_risk_report.py <design-doc> [--reports-dir docs/adversary]

Exit 0: gate satisfied — a risk report matching the design doc's <topic>
exists and is newer than the design doc (or the gate toggle is off).
Exit 1: gate not satisfied — report missing or stale (message on stderr).
Exit 2: bad input (design doc does not exist).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# hook_common lives in the sibling hooks/ directory of the deployed plugin.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from hook_common import feature_enabled, resolve_plugin_root  # noqa: E402

_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_GATE_KEY = "pipeline.dispatcher.gates.adversary_exit"


def extract_topic(design_doc: Path) -> str:
    """`2026-06-10-widget-sync-design.md` → `widget-sync` (date optional)."""
    stem = design_doc.name
    if stem.endswith(".md"):
        stem = stem[: -len(".md")]
    stem = _DATE_PREFIX.sub("", stem)
    if stem.endswith("-design"):
        stem = stem[: -len("-design")]
    return stem


def find_fresh_report(design_doc: Path, reports_dir: Path) -> tuple[Path, str]:
    """Return (newest matching report or None, failure reason or '')."""
    topic = extract_topic(design_doc)
    candidates = sorted(
        reports_dir.glob(f"*{topic}-risk-report.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    # Exact topic match: strip optional date prefix and the suffix.
    candidates = [
        c for c in candidates
        if _DATE_PREFIX.sub("", c.name) == f"{topic}-risk-report.md"
    ]
    if not candidates:
        return None, (
            f"no risk report found for topic '{topic}' in {reports_dir} — "
            "run the adversary-pipeline skill against the design doc first"
        )
    newest = candidates[0]
    if newest.stat().st_mtime <= design_doc.stat().st_mtime:
        return None, (
            f"risk report {newest} is stale (older than the design doc) — "
            "the design changed after the last adversary review; re-run the "
            "adversary-pipeline skill"
        )
    return newest, ""


def main() -> int:
    parser = argparse.ArgumentParser(prog="check_risk_report.py")
    parser.add_argument("design_doc", help="Path to the design doc under review")
    parser.add_argument(
        "--reports-dir",
        default="docs/adversary",
        help="Directory holding *-risk-report.md files (default: docs/adversary)",
    )
    args = parser.parse_args()

    plugin_root = resolve_plugin_root()
    if not feature_enabled(_GATE_KEY, plugin_root):
        print(f"[HARNESS] adversary exit gate off ({_GATE_KEY}=false) — pass")
        return 0

    design_doc = Path(args.design_doc)
    if not design_doc.is_file():
        print(f"[HARNESS] design doc not found: {design_doc}", file=sys.stderr)
        return 2

    report, reason = find_fresh_report(design_doc, Path(args.reports_dir))
    if report is None:
        print(f"[HARNESS] adversary exit gate: {reason}", file=sys.stderr)
        return 1

    print(f"[HARNESS] adversary exit gate: risk report {report} is fresh — pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
