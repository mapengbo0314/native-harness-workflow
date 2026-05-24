import pytest
import threading
import json
from pathlib import Path
from harness.templates.boilerplate.hooks.hook_common import atomic_write_json, read_json

def test_atomic_write_concurrency(tmp_path):
    state_file = tmp_path / "state.json"
    
    def writer(thread_id):
        data = {"thread": thread_id, "payload": "A" * 1000}
        atomic_write_json(state_file, data)

    threads = []
    for i in range(100):
        t = threading.Thread(target=writer, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    final_data = read_json(state_file)
    assert "thread" in final_data
    assert "payload" in final_data
    assert final_data["payload"] == "A" * 1000
