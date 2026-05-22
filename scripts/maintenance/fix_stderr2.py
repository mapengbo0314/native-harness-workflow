import re

files = [
    ".claude/plugin-generated/src/hooks/stop_monitor.py",
    ".claude/plugin-generated/src/hooks/pre_tool_guard.py",
    "harness/plugin_generator.py"
]

for filepath in files:
    with open(filepath, 'r') as f:
        content = f.read()

    # Revert my bad python attempt
    content = re.sub(r'sys\.stderr\.write\((.*?)\s*\+\s*"\\n"\)', r'print(\1)', content)
    # Revert the broken one specifically
    content = content.replace('sys.stderr.write("[QA REQUIRED]: You cannot exit. Dispatch Task(\\"@verifier\\" + "\\n") to perform robustness checks.")', 'print("[QA REQUIRED]: You cannot exit. Dispatch Task(\\"@verifier\\") to perform robustness checks.")')
    
    # Just do a clean text replace for known prints
    content = content.replace('print("[ACTION REQUIRED]', 'print("[ACTION REQUIRED]", file=sys.stderr)')
    content = content.replace('print("[QA REQUIRED]', 'print("[QA REQUIRED]", file=sys.stderr)')
    content = content.replace('print(f"[GATEKEEPER ERROR]', 'print(f"[GATEKEEPER ERROR]", file=sys.stderr)')
    content = content.replace('print("[ESCALATION]', 'print("[ESCALATION]", file=sys.stderr)')
    content = content.replace('print(message)', 'print(message, file=sys.stderr)')

    with open(filepath, 'w') as f:
        f.write(content)

print("Fixed prints to stderr using file=sys.stderr")
