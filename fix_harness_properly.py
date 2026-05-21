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
content = re.sub(r'(print\([^)]+)', r'\1, file=sys.stderr', content)

with open("harness/plugin_generator.py", "w") as f:
    f.write(content)

print("Fixed generator properly")
