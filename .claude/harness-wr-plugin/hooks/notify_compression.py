#!/usr/bin/env python3
import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        
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
