import pytest
import threading
import json
from pathlib import Path
from harness.templates.boilerplate.hooks.hook_common import atomic_write_json, read_json, update_state

def test_atomic_write_concurrency(tmp_path):
    state_file = tmp_path / "state.json"

    # Initialize state
    atomic_write_json(state_file, {"count": 0})

    def worker():
        def increment(state):
            state["count"] = state.get("count", 0) + 1
        update_state(state_file, increment)

    threads = []
    for i in range(100):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    final_data = read_json(state_file)
    assert "count" in final_data
    assert final_data["count"] == 100
