import re
import os

hooks = [
    (".claude/harness-wf-plugin/src/hooks/prompt_interceptor.py", "prompt_interceptor", """if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(intercept(sys.argv[1]))"""),
        
    (".claude/harness-wf-plugin/src/hooks/pre_tool_guard.py", "pre_tool_guard", """if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        check_tool_use(sys.argv[1], sys.argv[2])"""),
        
    (".claude/harness-wf-plugin/src/hooks/stop_monitor.py", "stop_monitor", """if __name__ == "__main__":
    import sys
    reason = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    on_stop(reason)""")
]

for path, name, old_main in hooks:
    if not os.path.exists(path):
        continue
    
    with open(path, 'r') as f:
        content = f.read()
        
    if "import traceback" not in content:
        content = content.replace("import datetime", "import datetime\nimport traceback")
        
    new_main = f"""if __name__ == "__main__":
    import sys
    try:
        {old_main.split('import sys')[1].strip()}
    except Exception as e:
        print(f"[HOOK CRASH]: {name} failed: {{e}}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)"""
        
    if "[HOOK CRASH]" not in content:
        content = content.replace(old_main, new_main)
        with open(path, 'w') as f:
            f.write(content)
        print(f"Patched {path}")

