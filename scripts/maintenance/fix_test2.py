import re

with open("tests/integration/test_dynamic_manifest.py", "r") as f:
    content = f.read()

content = content.replace('python3 -m src.hooks', 'PYTHONPATH=.claude/plugin-generated python3 -m src.hooks')

with open("tests/integration/test_dynamic_manifest.py", "w") as f:
    f.write(content)
print("Updated test file.")
