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

def test_acquire_lease_handles_operational_error():
    """Test that acquire_lease returns False when an OperationalError (like database lock) occurs."""
    from unittest.mock import MagicMock, patch
    import sqlite3
    db = HarnessDB(":memory:")
    
    # Mock _get_connection to return a connection that raises OperationalError on execute
    mock_conn = MagicMock()
    # DELETE in acquire_lease
    mock_conn.execute.side_effect = [
        sqlite3.OperationalError("database is locked")
    ]
    
    with patch.object(HarnessDB, '_get_connection', return_value=mock_conn):
        result = db.acquire_lease("test_agent", 10)
        assert result is False

def test_acquire_lease_handles_operational_error_on_insert():
    """Test that acquire_lease returns False when an OperationalError occurs during INSERT."""
    from unittest.mock import MagicMock, patch
    import sqlite3
    db = HarnessDB(":memory:")
    
    mock_conn = MagicMock()
    # 1. DELETE in acquire_lease
    # 2. INSERT in acquire_lease
    mock_conn.execute.side_effect = [
        MagicMock(), # DELETE
        sqlite3.OperationalError("database is locked")
    ]
    
    with patch.object(HarnessDB, '_get_connection', return_value=mock_conn):
        result = db.acquire_lease("test_agent", 10)
        assert result is False
