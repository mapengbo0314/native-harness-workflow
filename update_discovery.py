import re
import os

files_to_update = [
    "src/harness/init/discovery_engine.py",
    "tests/sandbox/runner.py"
]

for file_path in files_to_update:
    if not os.path.exists(file_path):
        continue
    with open(file_path, "r") as f:
        content = f.read()

    # If it's runner.py, it calls query_llm with self.llm_provider, self.api_key
    if "runner.py" in file_path:
        content = re.sub(r'query_llm\(full_prompt, self.llm_provider, self.api_key, model=self.model\)',
                         r'query_llm(full_prompt, self.cli_name, model=self.model)', content)
        content = re.sub(r'query_llm\(full_prompt, self\.llm_provider, self\.api_key, model=self\.model\)',
                         r'query_llm(full_prompt, self.cli_name, model=self.model)', content)

    with open(file_path, "w") as f:
        f.write(content)

print("Done runner update")
