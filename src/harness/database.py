import sqlite3
import time
import os
import json
from typing import Optional, Dict, Any

class HarnessDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_connection()
        try:
            # Enable WAL mode for better concurrency. 
            # This is persistent for file-based databases.
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS leases (
                        agent_name TEXT PRIMARY KEY,
                        expires_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS state (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
        finally:
            conn.close()

    def get_state(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            key = f"state_{session_id}" if session_id else "current_state"
            cursor = conn.execute("SELECT value FROM state WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            
            # Fallback for migration
            if session_id:
                cursor = conn.execute("SELECT value FROM state WHERE key = 'current_state'")
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
            return {}
        finally:
            conn.close()

    def set_state(self, state: Dict[str, Any], session_id: Optional[str] = None):
        conn = self._get_connection()
        try:
            key = f"state_{session_id}" if session_id else "current_state"
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
                    (key, json.dumps(state))
                )
        finally:
            conn.close()

    def acquire_lease(self, agent_name: str, ttl_seconds: int) -> bool:
        now = time.time()
        conn = self._get_connection()
        try:
            with conn:
                # Clean up expired leases first
                conn.execute("DELETE FROM leases WHERE expires_at < ?", (now,))
                
                # Try to insert new lease
                try:
                    conn.execute(
                        "INSERT INTO leases (agent_name, expires_at) VALUES (?, ?)",
                        (agent_name, now + ttl_seconds)
                    )
                    return True
                except sqlite3.IntegrityError:
                    # Lease already exists and is not expired
                    return False
        except sqlite3.OperationalError:
            # Database might be locked or other operational issues
            return False
        finally:
            conn.close()

    def release_lease(self, agent_name: str):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM leases WHERE agent_name = ?", (agent_name,))
        finally:
            conn.close()
