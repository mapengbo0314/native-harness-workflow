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
import errno
import time
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

        # 5. Verify 10-turn session length threshold BEFORE lock creation
        transcript = input_data.get("transcript") or input_data.get("turns") or []
        if not isinstance(transcript, list) or len(transcript) < 10:
            sys.exit(0)

        # 6. Lockfile check and creation
        state_dir = plugin_root / "state"
        state_dir.mkdir(exist_ok=True)
        lockfile = state_dir / "learning.lock"
        session_id = get_session_id()

        acquired = False
        try:
            # Atomic creation using os.open with O_CREAT | O_EXCL
            fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(f"session_id={session_id}\npid=PENDING\n")
            acquired = True
        except FileExistsError:
            # Handle stale or dead lockfile
            stale = False
            try:
                st = lockfile.stat()
                # If modified > 5 minutes ago, count as stale
                if time.time() - st.st_mtime > 300:
                    stale = True
                else:
                    # Parse PID and check if process is alive
                    content = lockfile.read_text(encoding="utf-8")
                    pid = None
                    for line in content.splitlines():
                        if line.startswith("pid="):
                            val = line.split("=", 1)[1].strip()
                            if val != "PENDING":
                                try:
                                    pid = int(val)
                                except ValueError:
                                    pass
                            break
                    if pid is not None:
                        try:
                            os.kill(pid, 0)
                        except OSError as e:
                            if e.errno == errno.ESRCH:
                                stale = True
            except Exception:
                pass

            if stale:
                try:
                    lockfile.unlink(missing_ok=True)
                    # Retry atomic creation once
                    fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        f.write(f"session_id={session_id}\npid=PENDING\n")
                    acquired = True
                except Exception:
                    pass

        if not acquired:
            sys.exit(0)

        # 7. Write input data payload to a temporary file for extract_skills.py to consume
        input_payload_file = state_dir / f"learning_input_{session_id}.json"
        input_payload_file.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")

        # 8. Determine log file path (Redirect output to .claude/state/learning_extraction.log or .gemini/state/)
        if plugin_root.parent.name == ".claude":
            log_dir = plugin_root.parent / "state"
        else:
            log_dir = plugin_root / "state"
        log_dir.mkdir(exist_ok=True, parents=True)
        log_file = log_dir / "learning_extraction.log"

        # 9. Detached spawn of extract_skills.py
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
        log_fh = open(log_file, "a", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=log_fh,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        log_fh.close()

        # Update lockfile with the background process PID
        lockfile.write_text(f"session_id={session_id}\npid={proc.pid}\n", encoding="utf-8")

        sys.exit(0)

    except SystemExit:
        raise
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
