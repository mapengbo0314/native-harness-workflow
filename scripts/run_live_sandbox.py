import os
import subprocess
from pathlib import Path

def get_gemini_key():
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1]
    return None

key = get_gemini_key()
if not key:
    print("GEMINI_API_KEY not found in .env")
    exit(1)

cmd = [
    "python3", "tests/sandbox/runner.py",
    "--scenario", "docstring",
    "--provider", "gemini",
    "--api-key", key
]

print(f"Running: {' '.join(cmd[:6])} [KEY REDACTED]")
subprocess.run(cmd)
