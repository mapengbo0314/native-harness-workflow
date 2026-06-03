"""3-way merge and interactive resolver for `harness-wf update` conflicts.

Uses `git merge-file` — a battle-tested diff3 engine that operates on loose
files (no repo required) and emits standard conflict markers.  This replaces
the lossy section-union of `merge_markdown`, which has no conflict detection.

three_way(ours, base, theirs) -> (merged_text, had_conflict)
  had_conflict is True when git reports overlapping (unmergeable) hunks.
"""
from __future__ import annotations

import difflib
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Callable


class ConflictResolutionAborted(RuntimeError):
    """Raised when interactive conflict resolution is aborted cleanly."""


class ConflictResolutionNeedsHuman(RuntimeError):
    """Raised when conflict resolution cannot proceed without a human."""


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


InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
EditorFn = Callable[[Path], int | None]


def resolve(
    path: str | Path,
    base: str,
    ours: str,
    theirs: str,
    *,
    headless: bool = False,
    input_fn: InputFn = input,
    editor: str | EditorFn | None = None,
    output_fn: OutputFn = print,
) -> str:
    """Resolve a conflict and return the chosen/merged content.

    The resolver only writes temporary files. Headless callers fail closed by
    raising ConflictResolutionNeedsHuman instead of making an implicit choice.
    """
    if headless:
        raise ConflictResolutionNeedsHuman(f"{path} requires interactive conflict resolution")

    while True:
        try:
            choice = input_fn(
                f"Conflict in {path}. [K]eep local, [O]verwrite, [D]iff, [M]erge: "
            )
        except (EOFError, KeyboardInterrupt) as exc:
            raise ConflictResolutionAborted(f"conflict resolution aborted for {path}") from exc

        normalized = choice.strip().lower()
        if normalized in {"k", "keep"}:
            return ours
        if normalized in {"o", "overwrite"}:
            return theirs
        if normalized in {"d", "diff"}:
            output_fn(_unified_diff(path, ours, theirs))
            continue
        if normalized in {"m", "merge"}:
            merged, had_conflict = three_way(ours, base, theirs)
            if not had_conflict:
                return merged

            active_editor = editor if editor is not None else os.environ.get("EDITOR")
            if not active_editor:
                output_fn("Manual merge is unavailable because no editor is configured.")
                continue

            try:
                edited = _edit_conflict_file(merged, active_editor)
            except KeyboardInterrupt as exc:
                raise ConflictResolutionAborted(f"conflict resolution aborted for {path}") from exc
            if edited is None:
                output_fn("Manual merge editor exited unsuccessfully.")
                continue
            return edited

        output_fn("Choose K, O, D, or M.")


def _unified_diff(path: str | Path, ours: str, theirs: str) -> str:
    return "".join(
        difflib.unified_diff(
            ours.splitlines(keepends=True),
            theirs.splitlines(keepends=True),
            fromfile=f"{path} (ours)",
            tofile=f"{path} (theirs)",
        )
    )


def _edit_conflict_file(merged: str, editor: str | EditorFn) -> str | None:
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".merge", delete=False) as f:
        temp_path = Path(f.name)
        f.write(merged)

    try:
        if callable(editor):
            returncode = editor(temp_path)
        else:
            try:
                command = [*shlex.split(editor), str(temp_path)]
                returncode = subprocess.run(command, check=False).returncode
            except (OSError, ValueError):
                return None

        if returncode not in (0, None):
            return None
        return temp_path.read_text(encoding="utf-8")
    finally:
        temp_path.unlink(missing_ok=True)
