from harness.discovery_engine import detect_tech_stack
import os
import tempfile

with tempfile.TemporaryDirectory() as temp_dir:
    with open(os.path.join(temp_dir, "package.json"), "w") as f:
        f.write('{"name": "test"}')
    stack = detect_tech_stack(temp_dir)
    print("Detected Stack:", stack)
