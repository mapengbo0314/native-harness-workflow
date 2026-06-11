#!/usr/bin/env python3
"""session_end.py — SessionEnd hook.

Triggers skill learning/extraction at the end of a session by spawning
extract_skills.py in the background.

Guards:
  - HARNESS_INTERNAL_LLM_CALL=1 (recursion guard) => exit immediately.
  - feature_enabled("hooks.session_end.learning_extraction") => exit if disabled.
  - lockfile state/learning.lock => exit if exists (prevent overlapping runs).
  - turn threshold: transcript/turns count >= 10 => exit if less.

Fail-open: any unhandled exception exits 0.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        # 1. Recursion guard check
        if os.environ.get("HARNESS_INTERNAL_LLM_CALL") == "1":
            sys.exit(0)

        # 2. Parse stdin
        try:
            input_data = json.load(sys.stdin)
        except Exception:
            input_data = {}

        # 3. Setup paths and imports
        hooks_dir = Path(__file__).parent.resolve()
        sys.path.insert(0, str(hooks_dir))

        from hook_common import (
            resolve_plugin_root,
            feature_enabled,
            get_session_id,
        )

        plugin_root = resolve_plugin_root()

        # 4. Check feature toggle
        if not feature_enabled("hooks.session_end.learning_extraction", plugin_root):
            sys.exit(0)

        # 5. Lockfile check and creation
        state_dir = plugin_root / "state"
        state_dir.mkdir(exist_ok=True)
        lockfile = state_dir / "learning.lock"
        if lockfile.exists():
            sys.exit(0)

        # 6. Verify 10-turn session length threshold
        transcript = input_data.get("transcript") or input_data.get("turns") or []
        if not isinstance(transcript, list) or len(transcript) < 10:
            sys.exit(0)

        # Create lockfile now to prevent concurrent extractions
        session_id = get_session_id()
        lockfile.write_text(f"session_id={session_id}\npid={os.getpid()}\n", encoding="utf-8")

        # 7. Write input data payload to a temporary file for extract_skills.py to consume
        input_payload_file = state_dir / f"learning_input_{session_id}.json"
        input_payload_file.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")

        # 8. Detached spawn of extract_skills.py
        scripts_dir = plugin_root / "scripts"
        extract_script = scripts_dir / "extract_skills.py"

        cmd = [
            sys.executable,
            str(extract_script),
            "--plugin-root",
            str(plugin_root),
            "--input-file",
            str(input_payload_file),
            "--session-id",
            str(session_id),
        ]

        # Standard Python 3 way to spawn detached on UNIX-like platforms
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        sys.exit(0)

    except SystemExit:
        raise
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
