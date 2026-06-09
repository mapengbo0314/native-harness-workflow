"""Workspace setup for swe-sympy-12236."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/sympy/sympy"
BASE_COMMIT = "d60497958f6dea7f5e25bc41e9107a6a63694d01"

TEST_PATCH = """\
diff --git a/sympy/polys/tests/test_polytools.py b/sympy/polys/tests/test_polytools.py
--- a/sympy/polys/tests/test_polytools.py
+++ b/sympy/polys/tests/test_polytools.py
@@ -1700,6 +1700,10 @@ def test_div():
     q = f.exquo(g)
     assert q.get_domain().is_ZZ

+    f, g = Poly(x+y, x), Poly(2*x+y, x)
+    q, r = f.div(g)
+    assert q.get_domain().is_Frac and r.get_domain().is_Frac
+

 def test_gcdex():
     f, g = 2*x, x**2 - 16
"""


def prepare_runtime(state: dict) -> dict:
    workspace = Path(state["workspace"])
    for item in list(workspace.iterdir()):
        shutil.rmtree(item) if item.is_dir() else item.unlink()

    print(f"  [swe-setup] cloning {REPO_URL} (sympy is large, ~1 min) …")
    subprocess.run(["git", "clone", "--quiet", REPO_URL, str(workspace)], check=True)
    subprocess.run(["git", "checkout", "--quiet", BASE_COMMIT], cwd=str(workspace), check=True)
    subprocess.run(["git", "apply", "-"], input=TEST_PATCH, text=True, cwd=str(workspace), check=True)
    print("  [swe-setup] installing package …")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet", "--disable-pip-version-check"],
        cwd=str(workspace), check=True,
    )
    print("  [swe-setup] done")
    return {}
