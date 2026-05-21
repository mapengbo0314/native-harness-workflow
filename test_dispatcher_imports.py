import sys
import os
plugin_dir = ".claude/plugin-generated"
sys.path.insert(0, plugin_dir)
try:
    from src.dispatcher import OrchestratorDispatcher
    d = OrchestratorDispatcher(os.path.join(plugin_dir, "config"))
    d._save_state({"test": 1})
    print("Dispatcher OK")
except Exception as e:
    print(f"Dispatcher Error: {e}")
