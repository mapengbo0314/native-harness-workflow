import pytest
import os
from harness.database import HarnessDB

def test_sqlite_lease(tmp_path):
    db_path = tmp_path / "state.db"
    db = HarnessDB(str(db_path))
    
    # Acquire lock
    assert db.acquire_lease("implementer", ttl_seconds=5) == True
    
    # Cannot acquire same active lock
    assert db.acquire_lease("implementer", ttl_seconds=5) == False
    
    # Release lock
    db.release_lease("implementer")
    
    # Can acquire again
    assert db.acquire_lease("implementer", ttl_seconds=5) == True

def test_lease_expiration(tmp_path):
    db_path = tmp_path / "state.db"
    db = HarnessDB(str(db_path))
    
    # Acquire lock with short TTL
    assert db.acquire_lease("short_lived", ttl_seconds=1) == True
    
    # Wait for expiration
    import time
    time.sleep(1.1)
    
    # Should be able to acquire again because it expired
    assert db.acquire_lease("short_lived", ttl_seconds=5) == True

def test_state_management(tmp_path):
    db_path = tmp_path / "state.db"
    db = HarnessDB(str(db_path))
    
    initial_state = db.get_state()
    assert initial_state == {}
    
    test_state = {"active_persona": "implementer", "tdd_status": "active"}
    db.set_state(test_state)
    
    assert db.get_state() == test_state
