#!/usr/bin/env python3
"""session_memory_save.py — Stop + PreCompact hook.

Heartbeat that touches updated_at and prunes stale entries for the current
session.  Skills and other hooks record entries via
``hook_common.record_session_entry``; this hook is the persistence heartbeat:
it ensures the file exists and enforces entry-count caps / retention.

Toggle: ``services.session_memory`` in features.json (fail-open: missing =>
enabled).  Opt-out env: ``HARNESS_SESSION_CONTEXT=off``.

Fail-open everywhere: any unhandled exception exits 0.
"""
import json
import os
import sys
from pathlib import Path


def main() -> None:
    try:
        # Opt-out env check first (fast path, no I/O)
        if os.environ.get("HARNESS_SESSION_CONTEXT", "").lower() == "off":
            sys.exit(0)

        try:
            input_data = json.load(sys.stdin)
        except Exception:
            input_data = {}

        # Resolve plugin root
        hooks_dir = Path(__file__).parent
        plugin_root = hooks_dir.parent
        sys.path.insert(0, str(hooks_dir))

        from hook_common import (
            resolve_plugin_root,
            get_session_id,
            publish_session_pointer,
            feature_enabled,
            _load_session,
            _save_session,
            _SUMMARY_MAX,
            capped_text,
        )

        plugin_root = resolve_plugin_root()

        # Feature toggle check
        if not feature_enabled("services.session_memory", plugin_root):
            sys.exit(0)

        # Resolve session id (Phase 6a M1 order: override > payload > env > pointer)
        session_id = get_session_id(input_data)
        publish_session_pointer(plugin_root, session_id)

        # Load (or initialise) the session file
        data = _load_session(plugin_root, session_id)

        # Cap entry summaries (defensive — record_session_entry already caps, but
        # files written by earlier versions or external tools may not be capped)
        for entry in data.get("entries", []):
            if isinstance(entry.get("summary"), str):
                entry["summary"] = capped_text(entry["summary"], _SUMMARY_MAX)

        # Persist (updates updated_at)
        _save_session(plugin_root, session_id, data)

        sys.exit(0)

    except SystemExit:
        raise
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()