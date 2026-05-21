import re

files_to_fix = [
    "harness/plugin_generator.py"
]

replacements = {
    'tool_name == "Bash"': 'tool_name in {"Bash", "run_shell_command"}',
    'tool_name in {"Bash", "Edit", "Write", "MultiEdit"}': 'tool_name in {"Bash", "run_shell_command", "Edit", "Write", "MultiEdit", "replace", "write_file", "write_to_file", "replace_file_content"}',
    'tool_name in {"Edit", "Write", "MultiEdit"}': 'tool_name in {"Edit", "Write", "MultiEdit", "replace", "write_file", "write_to_file", "replace_file_content"}',
    'tool_name == "Read"': 'tool_name in {"Read", "read_file"}',
    'print("[ACTION REQUIRED]': 'print("[ACTION REQUIRED]", file=sys.stderr',
    'print("[QA REQUIRED]': 'print("[QA REQUIRED]", file=sys.stderr',
    'print(f"[GATEKEEPER ERROR]': 'print(f"[GATEKEEPER ERROR]", file=sys.stderr',
    'print("[ESCALATION]': 'print("[ESCALATION]", file=sys.stderr',
    'print(message)': 'print(message, file=sys.stderr)',
}

for filepath in files_to_fix:
    with open(filepath, "r") as f:
        content = f.read()
    
    for old_str, new_str in replacements.items():
        content = content.replace(old_str, new_str)
        
    with open(filepath, "w") as f:
        f.write(content)

print("Fixed harness/plugin_generator.py")
