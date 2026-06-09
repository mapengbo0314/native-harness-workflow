"""Workspace setup for swe-pylint-6506."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/pylint-dev/pylint"
BASE_COMMIT = "0a4204fd7555cfedd43f43017c94d24ef48244a5"

TEST_PATCH = """\
diff --git a/tests/config/test_config.py b/tests/config/test_config.py
--- a/tests/config/test_config.py
+++ b/tests/config/test_config.py
@@ -10,7 +10,6 @@
 import pytest
 from pytest import CaptureFixture

-from pylint.config.exceptions import _UnrecognizedOptionError
 from pylint.lint import Run as LintRun
 from pylint.testutils._run import _Run as Run
 from pylint.testutils.configuration_test import run_using_a_configuration_file
@@ -65,18 +64,20 @@ def test_unknown_message_id(capsys: CaptureFixture) -> None:

 def test_unknown_option_name(capsys: CaptureFixture) -> None:
     \"\"\"Check that we correctly raise a message on an unknown option.\"\"\"
-    with pytest.raises(_UnrecognizedOptionError):
+    with pytest.raises(SystemExit):
         Run([str(EMPTY_MODULE), "--unknown-option=yes"], exit=False)
     output = capsys.readouterr()
-    assert "E0015: Unrecognized option found: unknown-option=yes" in output.out
+    assert "usage: pylint" in output.err
+    assert "Unrecognized option" in output.err


 def test_unknown_short_option_name(capsys: CaptureFixture) -> None:
     \"\"\"Check that we correctly raise a message on an unknown short option.\"\"\"
-    with pytest.raises(_UnrecognizedOptionError):
+    with pytest.raises(SystemExit):
         Run([str(EMPTY_MODULE), "-Q"], exit=False)
     output = capsys.readouterr()
-    assert "E0015: Unrecognized option found: Q" in output.out
+    assert "usage: pylint" in output.err
+    assert "Unrecognized option" in output.err


 def test_unknown_confidence(capsys: CaptureFixture) -> None:
"""


def prepare_runtime(state: dict) -> dict:
    workspace = Path(state["workspace"])
    for item in list(workspace.iterdir()):
        shutil.rmtree(item) if item.is_dir() else item.unlink()

    print(f"  [swe-setup] cloning {REPO_URL} …")
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
