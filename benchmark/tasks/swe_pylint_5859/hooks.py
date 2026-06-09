"""Workspace setup for swe-pylint-5859.

Clones pylint at the exact base commit from SWE-bench Lite, applies the
verification test patch, and installs the package so the agent can run tests.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/pylint-dev/pylint"
BASE_COMMIT = "182cc539b8154c0710fcea7e522267e42eba8899"

TEST_PATCH = """\
diff --git a/tests/checkers/unittest_misc.py b/tests/checkers/unittest_misc.py
--- a/tests/checkers/unittest_misc.py
+++ b/tests/checkers/unittest_misc.py
@@ -68,6 +68,16 @@ def test_without_space_fixme(self) -> None:
         ):
             self.checker.process_tokens(_tokenize_str(code))

+    @set_config(notes=["???"])
+    def test_non_alphanumeric_codetag(self) -> None:
+        code = \"\"\"a = 1
+                #???
+                \"\"\"
+        with self.assertAddsMessages(
+            MessageTest(msg_id="fixme", line=2, args="???", col_offset=17)
+        ):
+            self.checker.process_tokens(_tokenize_str(code))
+
     @set_config(notes=[])
     def test_absent_codetag(self) -> None:
         code = \"\"\"a = 1
"""


def prepare_runtime(state: dict) -> dict:
    workspace = Path(state["workspace"])
    _setup(workspace)
    return {}


def _setup(workspace: Path) -> None:
    # Clear anything harness-bench copied (no fixtures, but be safe)
    for item in list(workspace.iterdir()):
        shutil.rmtree(item) if item.is_dir() else item.unlink()

    print(f"  [swe-setup] cloning {REPO_URL} …")
    subprocess.run(
        ["git", "clone", "--quiet", REPO_URL, str(workspace)],
        check=True,
    )
    subprocess.run(
        ["git", "checkout", "--quiet", BASE_COMMIT],
        cwd=str(workspace), check=True,
    )
    subprocess.run(
        ["git", "apply", "-"],
        input=TEST_PATCH, text=True,
        cwd=str(workspace), check=True,
    )
    print("  [swe-setup] installing package …")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet",
         "--disable-pip-version-check"],
        cwd=str(workspace), check=True,
    )
    print("  [swe-setup] done")
