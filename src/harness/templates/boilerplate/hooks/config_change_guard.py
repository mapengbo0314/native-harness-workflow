import sys
import json

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        # State management removed, config changes always allowed
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in config_change_guard: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
