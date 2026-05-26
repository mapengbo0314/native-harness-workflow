import sys
import os
from pathlib import Path

sys.path.append(str(Path("src")))
from harness.runtime.dispatcher import OrchestratorDispatcher

def test():
    # Setup dummy environment
    os.environ["LANGFUSE_TRACE_ID"] = "dummy"
    os.environ["LANGFUSE_SESSION_ID"] = "dummy"
    
    dispatcher = OrchestratorDispatcher(config_dir=".gemini/config")
    
    # We will just test the assemble_branch_context and dispatch_agent
    res = dispatcher.assemble_branch_context("implementer", "A")
    print("assemble_branch_context output:")
    print(res)
    
    # Also dispatch agent
    try:
        context = {"prompt": "Fix the bug", "files": []}
        res2 = dispatcher.dispatch_agent("implementer", context)
        print("\ndispatch_agent output:")
        print(res2.get("context", {}).get("branch_context_pointers"))
    except Exception as e:
        print("dispatch failed:", e)

if __name__ == "__main__":
    test()
