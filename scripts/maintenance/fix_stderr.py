import re

files = [
    ".claude/harness-wr-plugin/src/hooks/stop_monitor.py",
    ".claude/harness-wr-plugin/src/hooks/pre_tool_guard.py",
    "harness/plugin_generator.py"
]

for filepath in files:
    with open(filepath, 'r') as f:
        content = f.read()

    # Revert my bad sed attempt first if needed, though they might be broken now
    content = content.replace('sys.stderr.write("[ACTION REQUIRED]', 'print("[ACTION REQUIRED]')
    content = content.replace('sys.stderr.write("[QA REQUIRED]', 'print("[QA REQUIRED]')
    content = content.replace('sys.stderr.write(f"[GATEKEEPER ERROR]', 'print(f"[GATEKEEPER ERROR]')
    content = content.replace('sys.stderr.write("[ESCALATION]', 'print("[ESCALATION]')
    content = content.replace('sys.stderr.write(message)', 'print(message)')
    content = content.replace('sys.stderr.write("[VIOLATION]', 'print("[VIOLATION]')
    content = content.replace('sys.stderr.write("[TDD VIOLATION]', 'print("[TDD VIOLATION]')
    content = content.replace('sys.stderr.write("[EFFICIENCY VIOLATION]', 'print("[EFFICIENCY VIOLATION]')
    
    # Strip any dangling \n" I accidentally added
    content = re.sub(r'print\((.*?)\)\\n"', r'print(\1)', content)
    
    # Now cleanly convert to sys.stderr.write
    content = re.sub(r'print\((.*?)\)', r'sys.stderr.write(\1 + "\\n")', content)

    with open(filepath, 'w') as f:
        f.write(content)

print("Fixed prints to stderr")
