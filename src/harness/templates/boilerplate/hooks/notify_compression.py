#!/usr/bin/env python3
import sys
import json
from pathlib import Path

def main():
    try:
        input_data = json.load(sys.stdin)

        # Increment 4: honour the hooks.notify_compression toggle (fail-open).
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from hook_common import hook_enabled
            if not hook_enabled("notify_compression", Path(__file__).resolve().parent.parent):
                print(json.dumps({}))
                sys.exit(0)
        except SystemExit:
            raise
        except Exception:
            pass

        # Why is it compressing?
        trigger = input_data.get("trigger", "auto")
        
        message = "⚠️ SYSTEM ALERT: Context window limit reached. The CLI is auto-compressing conversation history. You may want to consider using `/clear` soon to reset your context."
        
        if trigger == "manual":
             message = "ℹ️ Manual context compression initiated. Reminder: you can use `/clear` for a full reset."

        # Send the notification to the terminal
        print(json.dumps({
            "systemMessage": message
        }))
        sys.exit(0)
        
    except Exception:
        print(json.dumps({}))
        sys.exit(0)

if __name__ == "__main__":
    main()
