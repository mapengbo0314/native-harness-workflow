#!/usr/bin/env python3
"""Deterministic session-state CLI for skills (F4 ECC port R2; Phase 6a).

Skills are markdown — they cannot mutate the session store directly.  This
script is the invocable they call:

  session_phase.py set-phase <phase> [--session <id>]
  session_phase.py clear-phase [--artifact <path>] [--session <id>]
  session_phase.py set-research-done [--note <txt>] [--session <id>]
  session_phase.py arm-budget [--max-tool-calls N] [--max-file-reads M] [--session <id>]
  session_phase.py disarm-budget [--session <id>]

Session resolution (Phase 6a): pass --session with the id shown in the
SYSTEM STATE block for precision; without it, the pointer file published by
the hooks (state/current_session) is used, so the script writes to the same
store the enforcing hooks read.  The legacy env/ppid fallback remains last.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# hook_common lives in the sibling hooks/ directory of the deployed plugin.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from hook_common import (  # noqa: E402
    budget_sidecar_path,
    clear_phase,
    get_session_id,
    resolve_plugin_root,
    set_phase,
    set_research_done,
)

_BUDGET_DEFAULT_MAX_TOOL_CALLS = 30
_BUDGET_DEFAULT_MAX_FILE_READS = 12


def _budget_sidecar(plugin_root: Path, session_id: str) -> Path:
    sidecar = budget_sidecar_path(plugin_root, session_id)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    return sidecar


def _arm_budget(plugin_root: Path, session_id: str, max_tool_calls: int, max_file_reads: int) -> Path:
    sidecar = _budget_sidecar(plugin_root, session_id)
    tmp = sidecar.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "max_tool_calls": max_tool_calls,
        "max_file_reads": max_file_reads,
        "tool_calls": 0,
        "file_reads": 0,
    }), encoding="utf-8")
    tmp.replace(sidecar)
    return sidecar


def main() -> int:
    parser = argparse.ArgumentParser(prog="session_phase.py")
    sub = parser.add_subparsers(dest="command", required=True)

    def _add(name: str, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--session", default=None,
                       help="Explicit session id (from SYSTEM STATE); default: hooks' pointer file")
        return p

    p_set = _add("set-phase", "Persist the session phase (e.g. planning)")
    p_set.add_argument("phase")

    p_clear = _add("clear-phase", "Clear the persisted phase")
    p_clear.add_argument("--artifact", default=None, help="Exit artifact (e.g. the design doc path)")

    p_rd = _add("set-research-done", "Record the search-first research pass or its waiver")
    p_rd.add_argument("--note", default=None, help="One-line research summary or waiver")

    p_arm = _add("arm-budget", "Write the dispatch-budget sidecar pre_tool_use enforces (R5)")
    p_arm.add_argument("--max-tool-calls", type=int, default=_BUDGET_DEFAULT_MAX_TOOL_CALLS)
    p_arm.add_argument("--max-file-reads", type=int, default=_BUDGET_DEFAULT_MAX_FILE_READS)

    _add("disarm-budget", "Remove the dispatch-budget sidecar (no-op when absent)")

    args = parser.parse_args()
    plugin_root = resolve_plugin_root()
    session_id = args.session or get_session_id()

    if args.command == "set-phase":
        set_phase(plugin_root, session_id, args.phase)
        print(f"[HARNESS] phase={args.phase} recorded for session {session_id}")
    elif args.command == "clear-phase":
        clear_phase(plugin_root, session_id, exit_artifact=args.artifact)
        print(f"[HARNESS] phase cleared for session {session_id}")
    elif args.command == "set-research-done":
        set_research_done(plugin_root, session_id, note=args.note)
        print(f"[HARNESS] research_done recorded for session {session_id}")
    elif args.command == "arm-budget":
        sidecar = _arm_budget(plugin_root, session_id, args.max_tool_calls, args.max_file_reads)
        print(f"[HARNESS] budget sidecar armed: {sidecar}")
    elif args.command == "disarm-budget":
        _budget_sidecar(plugin_root, session_id).unlink(missing_ok=True)
        print(f"[HARNESS] budget sidecar disarmed for session {session_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
