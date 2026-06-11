#!/usr/bin/env python3
"""Deterministic session-phase CLI for skills (F4 ECC port, R2).

Skills are markdown — they cannot mutate the session store directly.  This
script is the invocable they call:

  session_phase.py set-phase <phase>                 # e.g. brainstorming entry
  session_phase.py clear-phase [--artifact <path>]   # e.g. design sign-off
  session_phase.py set-research-done [--note <txt>]  # search-first / waiver

Resolves the plugin root and session id exactly like the hooks do
(CLAUDE_PLUGIN_ROOT / HARNESS_SESSION_ID etc. via hook_common).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# hook_common lives in the sibling hooks/ directory of the deployed plugin.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from hook_common import (  # noqa: E402
    clear_phase,
    get_session_id,
    resolve_plugin_root,
    set_phase,
    set_research_done,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="session_phase.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_set = sub.add_parser("set-phase", help="Persist the session phase (e.g. planning)")
    p_set.add_argument("phase")

    p_clear = sub.add_parser("clear-phase", help="Clear the persisted phase")
    p_clear.add_argument("--artifact", default=None, help="Exit artifact (e.g. the design doc path)")

    p_rd = sub.add_parser("set-research-done", help="Record the search-first research pass or its waiver")
    p_rd.add_argument("--note", default=None, help="One-line research summary or waiver")

    args = parser.parse_args()
    plugin_root = resolve_plugin_root()
    session_id = get_session_id()

    if args.command == "set-phase":
        set_phase(plugin_root, session_id, args.phase)
        print(f"[HARNESS] phase={args.phase} recorded for session {session_id}")
    elif args.command == "clear-phase":
        clear_phase(plugin_root, session_id, exit_artifact=args.artifact)
        print(f"[HARNESS] phase cleared for session {session_id}")
    elif args.command == "set-research-done":
        set_research_done(plugin_root, session_id, note=args.note)
        print(f"[HARNESS] research_done recorded for session {session_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())