import re

with open("harness/plugin_generator.py", "r") as f:
    content = f.read()

# 1. PYTHONPATH and python3
content = content.replace('"command": "python -m src', '"command": "PYTHONPATH=.claude/plugin-generated python3 -m src')

# 2. Tool names
content = content.replace('tool_name == \\"Bash\\"', 'tool_name in {\\"Bash\\", \\"run_shell_command\\"}')
content = content.replace('tool_name in {\\"Bash\\", \\"Edit\\", \\"Write\\", \\"MultiEdit\\"}', 'tool_name in {\\"Bash\\", \\"run_shell_command\\", \\"Edit\\", \\"Write\\", \\"MultiEdit\\", \\"replace\\", \\"write_file\\", \\"write_to_file\\", \\"replace_file_content\\"}')
content = content.replace('tool_name in {\\"Edit\\", \\"Write\\", \\"MultiEdit\\"}', 'tool_name in {\\"Edit\\", \\"Write\\", \\"MultiEdit\\", \\"replace\\", \\"write_file\\", \\"write_to_file\\", \\"replace_file_content\\"}')
content = content.replace('tool_name == \\"Read\\"', 'tool_name in {\\"Read\\", \\"read_file\\"}')

# 3. Proper stderr replacements
replacements = [
    ('print("[ACTION REQUIRED]: Run sh {{HARNESS_DIR}}/scripts/setup_harness.sh before strict harness enforcement.")', 'print("[ACTION REQUIRED]: Run sh {{HARNESS_DIR}}/scripts/setup_harness.sh before strict harness enforcement.", file=sys.stderr)'),
    ('print("[QA REQUIRED]: You cannot exit. Dispatch Task(\\"@verifier\\") to perform robustness checks.")', 'print("[QA REQUIRED]: You cannot exit. Dispatch Task(\\"@verifier\\") to perform robustness checks.", file=sys.stderr)'),
    ('print(f"[GATEKEEPER ERROR]: {result.stderr or result.stdout}")', 'print(f"[GATEKEEPER ERROR]: {result.stderr or result.stdout}", file=sys.stderr)'),
    ('print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.")', 'print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.", file=sys.stderr)'),
    ('print(message)', 'print(message, file=sys.stderr)')
]

for old, new in replacements:
    content = content.replace(old, new)

with open("harness/plugin_generator.py", "w") as f:
    f.write(content)

print("Fixed generator properly")
