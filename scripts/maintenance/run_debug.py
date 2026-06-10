from harness.domain.detect import detect_stack
import os
import tempfile

with tempfile.TemporaryDirectory() as temp_dir:
    with open(os.path.join(temp_dir, "package.json"), "w") as f:
        f.write('{"name": "test"}')
    stack = detect_stack(temp_dir)
    print("Detected Stack:", stack)
