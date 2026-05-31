import sys
import os
import json
import subprocess
from pathlib import Path

plugin_dir = Path(".claude/harness-wr-plugin")
if not plugin_dir.exists():
    print("Plugin dir not found")
    sys.exit(1)

# Ensure PYTHONPATH behaves exactly as Claude Code would inject it
env = os.environ.copy()
env["PYTHONPATH"] = str(plugin_dir)

print("--- Running Prompt Interceptor ---")
proc1 = subprocess.run(
    ["python3", "-m", "src.hooks.prompt_interceptor"],
    env=env,
    input=json.dumps({"prompt": "sandbox test"}).encode('utf-8'),
    capture_output=True
)
print("Return code:", proc1.returncode)
print("Stdout:", proc1.stdout.decode('utf-8'))
if proc1.stderr:
    print("Stderr:", proc1.stderr.decode('utf-8'))

print("--- Running PreTool Guard ---")
proc2 = subprocess.run(
    ["python3", "-m", "src.hooks.pre_tool_guard"],
    env=env,
    input=json.dumps({"toolName": "Bash", "input": {"command": "echo test"}}).encode('utf-8'),
    capture_output=True
)
print("Return code:", proc2.returncode)
print("Stdout:", proc2.stdout.decode('utf-8'))
if proc2.stderr:
    print("Stderr:", proc2.stderr.decode('utf-8'))

print("--- Environment Check Complete ---")
