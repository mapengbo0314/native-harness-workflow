import re

with open('harness/plugin_generator.py', 'r') as f:
    content = f.read()

# 1. Update hook_header to include traceback
if "import traceback" not in content:
    content = content.replace("import datetime", "import datetime\nimport traceback")

# 2. Update prompt_interceptor.py main block
old_pi_main = """if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(intercept(sys.argv[1]))"""
new_pi_main = """if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) > 1:
            print(intercept(sys.argv[1]))
    except Exception as e:
        print(f"[HOOK CRASH]: prompt_interceptor failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)"""
content = content.replace(old_pi_main, new_pi_main)

# 3. Update pre_tool_guard.py main block
old_pt_main = """if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        check_tool_use(sys.argv[1], sys.argv[2])"""
new_pt_main = """if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) > 2:
            check_tool_use(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"[HOOK CRASH]: pre_tool_guard failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)"""
content = content.replace(old_pt_main, new_pt_main)

# 4. Update stop_monitor.py main block
old_sm_main = """if __name__ == "__main__":
    import sys
    reason = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    on_stop(reason)"""
new_sm_main = """if __name__ == "__main__":
    import sys
    try:
        reason = sys.argv[1] if len(sys.argv) > 1 else "unknown"
        on_stop(reason)
    except Exception as e:
        print(f"[HOOK CRASH]: stop_monitor failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)"""
content = content.replace(old_sm_main, new_sm_main)

with open('harness/plugin_generator.py', 'w') as f:
    f.write(content)

print("Patched plugin_generator.py")
