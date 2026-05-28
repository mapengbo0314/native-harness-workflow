import re
import os

file_path = "tests/sandbox/runner.py"

with open(file_path, "r") as f:
    content = f.read()

# Remove api_key argument definition
content = re.sub(r'parser\.add_argument\("--api-key", help="API key.*"\n', '', content)

with open(file_path, "w") as f:
    f.write(content)

print("Updated runner.py args")
