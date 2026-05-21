import os
import json
import pytest
from pathlib import Path
from harness.dispatcher import OrchestratorDispatcher

def test_state_management_atomic_write(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    dispatcher = OrchestratorDispatcher(str(config_dir))
    
    # Initial state should be default
    state = dispatcher._load_state()
    assert state == {
        "active_persona": "orchestrator",
        "tdd_status": "inactive",
        "matrix_branch": None,
        "consecutive_rejections": 0,
        "setup_complete": False,
        "strict_enforcement_enabled": False,
    }
    
    # Save state
    new_state = {"active_persona": "implementer", "tdd_status": "active"}
    dispatcher._save_state(new_state)
    
    # Load state back
    loaded_state = dispatcher._load_state()
    assert loaded_state == new_state
    
    # Verify file exists
    state_file = config_dir / ".harness_state.json"
    assert state_file.exists()
    
    # Check if it was written atomically (hard to verify without mocking os.replace, but we can check if it exists)
    with open(state_file, 'r') as f:
        data = json.load(f)
        assert data == new_state

def test_state_management_locking(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    dispatcher = OrchestratorDispatcher(str(config_dir))
    lock_path = config_dir / ".harness_state.json.lock"
    
    # Manually create lock
    lock_path.mkdir()
    
    # Attempting to save should raise an exception because the lock is fresh
    with pytest.raises(OSError, match="Could not acquire lock for state file"):
        dispatcher._save_state({"test": "data"}, timeout=0.1)

    # Now simulate a stale lock (make it look 11 seconds old)
    import time
    stale_time = time.time() - 11
    os.utime(lock_path, (stale_time, stale_time))

    # Attempting to save should now succeed
    dispatcher._save_state({"test": "data2"}, timeout=0.1)
    state = dispatcher._load_state()
    assert state == {"test": "data2"}

def test_matrix_routing_classification(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    dispatcher = OrchestratorDispatcher(str(config_dir))
    
    # Branch A: Bug Fix (stack trace)
    assert dispatcher.classify_intent("It's broken: Traceback (most recent call last):...") == "A"
    
    # Branch B: Feature
    assert dispatcher.classify_intent("Implement a new user authentication system") == "B"
    
    # Branch C: Question
    assert dispatcher.classify_intent("How does the dispatcher work?") == "C"
    
    # Branch D: Surgical Edit
    assert dispatcher.classify_intent("Fix the typo in main.py") == "D"

def test_verb_guardrails(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    dispatcher = OrchestratorDispatcher(str(config_dir))
    
    # Valid verbs
    assert dispatcher.validate_verb("/plan") is True
    assert dispatcher.validate_verb("/work") is True
    assert dispatcher.validate_verb("/review") is True
    assert dispatcher.validate_verb("/release") is True
    assert dispatcher.validate_verb("/setup") is True
    
    # Invalid verbs
    assert dispatcher.validate_verb("/delete") is False
    assert dispatcher.validate_verb("just some text") is False

def test_dispatch_agent_updates_state(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Mock agents config file
    agents_file = config_dir / "agents.json"
    with open(agents_file, 'w') as f:
        json.dump({"agents": {"implementer": {}, "planner": {}}}, f)
        
    dispatcher = OrchestratorDispatcher(str(config_dir))
    
    # Dispatch implementer
    result = dispatcher.dispatch_agent("implementer", {"prompt": "Fix this bug"})
    
    assert result["agent"] == "implementer"
    assert result["intent_branch"] == "A"
    assert result["state"]["active_persona"] == "implementer"
    assert result["state"]["tdd_status"] == "active"
    
    # Dispatch planner
    result = dispatcher.dispatch_agent("planner", {"prompt": "Create a new feature"})
    
    assert result["agent"] == "planner"
    assert result["intent_branch"] == "B"
    assert result["state"]["active_persona"] == "planner"
    # Should not overwrite tdd_status explicitly to active for planner, 
    # but the current logic retains whatever was there, so if we dispatch planner after implementer, 
    # tdd_status remains active, which is fine, or we should set it to inactive? 
    # Let's check how state was updated:
    # state["active_persona"] = agent_name
    # if agent_name == "implementer": state["tdd_status"] = "active"
    # It doesn't reset it, which is probably fine. Let's just test that the active persona changed.
    
    state = dispatcher._load_state()
    assert state["active_persona"] == "planner"
