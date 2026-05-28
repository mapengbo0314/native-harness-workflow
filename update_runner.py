import re
import os

file_path = "tests/sandbox/runner.py"

with open(file_path, "r") as f:
    content = f.read()

# Fix the SandboxRunner init
content = content.replace("def __init__(self, harness_dir: Path, llm_provider: str, api_key: str, model: str = None):", "def __init__(self, harness_dir: Path, cli_name: str, model: str = None):")
content = content.replace("self.llm_provider = llm_provider", "self.cli_name = cli_name")
content = content.replace("self.api_key = api_key\n", "")

# Fix the instantiation
content = content.replace("runner = SandboxRunner(harness_dir, provider, api_key, model=args.model)", "runner = SandboxRunner(harness_dir, provider, model=args.model)")

with open(file_path, "w") as f:
    f.write(content)

print("Updated runner.py")
