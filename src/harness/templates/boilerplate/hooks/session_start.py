#!/usr/bin/env python3
"""session_start.py — SessionStart hook.

Emits a digest of recent session-memory entries as ``additionalContext`` so
Claude Code can surface prior decisions/blockers/patterns at the start of a
new session.  Also prunes session_memory_*.json files older than 30 days.

Output shape (Claude Code SessionStart contract):
  {
    "hookSpecificOutput": {
      "hookEventName": "SessionStart",
      "additionalContext": "<markdown digest string>"
    }
  }

The shape was verified against the prompt_classifier.py degraded-response path
in this repo, which uses the same ``hookSpecificOutput.additionalContext``
envelope — and against the Claude Code hook documentation structure (the
additionalContext field is injected into the system prompt for SessionStart
hooks).

Toggle: ``services.session_memory`` in features.json (fail-open: missing =>
enabled).  Opt-out env: ``HARNESS_SESSION_CONTEXT=off``.

Fail-open: any unhandled exception exits 0 with empty output.
"""
import json
import os
import sys
from pathlib import Path


def main() -> None:
    try:
        # Opt-out env check (fast path)
        if os.environ.get("HARNESS_SESSION_CONTEXT", "").lower() == "off":
            sys.exit(0)

        try:
            input_data = json.load(sys.stdin)
        except Exception:
            input_data = {}

        hooks_dir = Path(__file__).parent
        sys.path.insert(0, str(hooks_dir))

        from hook_common import (
            resolve_plugin_root,
            feature_enabled,
            build_session_digest,
            prune_old_session_files,
        )

        plugin_root = resolve_plugin_root()

        if not feature_enabled("services.session_memory", plugin_root):
            sys.exit(0)

        # Prune stale session files (retention enforcement)
        prune_old_session_files(plugin_root)

        # Build the digest from all surviving session files
        digest = build_session_digest(plugin_root)

        if digest:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": digest,
                }
            }
            print(json.dumps(output))

        sys.exit(0)

    except SystemExit:
        raise
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
