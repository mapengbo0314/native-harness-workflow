"""3-way merge for `harness-wf update` conflict resolution.

Uses `git merge-file` — a battle-tested diff3 engine that operates on loose
files (no repo required) and emits standard conflict markers.  This replaces
the lossy section-union of `merge_markdown`, which has no conflict detection.

three_way(ours, base, theirs) -> (merged_text, had_conflict)
  had_conflict is True when git reports overlapping (unmergeable) hunks.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def three_way(ours: str, base: str, theirs: str) -> tuple[str, bool]:
    """Run a diff3 merge. Returns the merged text (with conflict markers if
    any) and whether a conflict occurred.

    Failure mode: if `git merge-file` errors (returncode < 0), raises
    RuntimeError — callers should fall back to interactive keep/overwrite.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        ours_f = d / "ours"
        base_f = d / "base"
        theirs_f = d / "theirs"
        ours_f.write_text(ours, encoding="utf-8")
        base_f.write_text(base, encoding="utf-8")
        theirs_f.write_text(theirs, encoding="utf-8")

        # -p: write result to stdout, leave inputs untouched.
        # arg order: <current/ours> <base> <other/theirs>
        result = subprocess.run(
            ["git", "merge-file", "-p", str(ours_f), str(base_f), str(theirs_f)],
            capture_output=True,
            text=True,
        )

    # returncode: 0 = clean, >0 = number of conflicts, <0 = error.
    if result.returncode < 0:
        raise RuntimeError(f"git merge-file failed: {result.stderr}")
    return result.stdout, result.returncode > 0
