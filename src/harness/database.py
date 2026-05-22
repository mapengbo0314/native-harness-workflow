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
        conn = sqlite3.connect(self.db_path)
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
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

    def get_state(self) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT value FROM state WHERE key = 'current_state'")
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return {}
        finally:
            conn.close()

    def set_state(self, state: Dict[str, Any]):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO state (key, value) VALUES ('current_state', ?)",
                    (json.dumps(state),)
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
        finally:
            conn.close()

    def release_lease(self, agent_name: str):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM leases WHERE agent_name = ?", (agent_name,))
        finally:
            conn.close()
