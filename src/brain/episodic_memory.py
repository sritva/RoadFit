import os
import sqlite3
import json
import threading
from typing import Dict, Any, List, Tuple

class EpisodicMemoryBank:
    """
    The Hippocampus of RoadFit-X.
    Stores historical route traversal successes/failures under varying contexts.
    """
    def __init__(self, db_path="brain_memory.db"):
        self.db_path = db_path
        self._local = threading.local()
        # For disk-based DBs, we can init once. For in-memory, we must init per connection.
        if db_path != ":memory:":
            self._init_db(sqlite3.connect(self.db_path))

    def _get_conn(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path)
            if self.db_path == ":memory:":
                self._init_db(self._local.conn)
        return self._local.conn

    def _init_db(self, conn):
        c = conn.cursor()
        c.execute('PRAGMA journal_mode=WAL;') # Enable concurrent reads/writes
        c.execute('PRAGMA synchronous=NORMAL;')
        # edge_id is stored as string: f"{u}_{v}_{k}"
        c.execute('''
            CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edge_id TEXT,
                weather TEXT,
                traffic TEXT,
                vehicle_type TEXT,
                success INTEGER,
                actual_time REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Index for fast associative recall
        c.execute('CREATE INDEX IF NOT EXISTS idx_recall ON experiences (edge_id, weather, traffic, vehicle_type)')
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

    def commit_experience(
        self, 
        edge_id: str, 
        weather: str, 
        traffic: str, 
        vehicle_type: str, 
        success: bool, 
        actual_time: float
    ):
        """Records a single edge traversal outcome in episodic memory."""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('''
            INSERT INTO experiences (edge_id, weather, traffic, vehicle_type, success, actual_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (edge_id, weather, traffic, vehicle_type, int(success), actual_time))
        conn.commit()

    def commit_experiences_batch(self, experiences: List[Tuple]):
        """
        Records multiple edge traversal outcomes in episodic memory efficiently.
        experiences is a list of tuples: (edge_id, weather, traffic, vehicle_type, success, actual_time)
        """
        conn = self._get_conn()
        c = conn.cursor()
        c.executemany('''
            INSERT INTO experiences (edge_id, weather, traffic, vehicle_type, success, actual_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', experiences)
        conn.commit()

    def recall_edge_penalties(self, weather: str, traffic: str, vehicle_type: str) -> Dict[str, float]:
        """
        Recalls historical failure rates for all edges under a specific context.
        Returns a dict mapping edge_id -> penalty_multiplier (0.0 to 1.0).
        A penalty of 1.0 means 100% failure historically.
        """
        conn = self._get_conn()
        c = conn.cursor()
        # Calculate failure rate per edge for this context
        # If an edge failed 3 times out of 4 under Rain, penalty = 0.75
        c.execute('''
            SELECT edge_id, 
                   COUNT(*) as total_attempts,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures
            FROM experiences
            WHERE weather = ? AND traffic = ? AND vehicle_type = ?
            GROUP BY edge_id
        ''', (weather, traffic, vehicle_type))
        
        penalties = {}
        for row in c.fetchall():
            edge_id, attempts, failures = row
            if attempts > 0:
                penalties[edge_id] = failures / float(attempts)
        return penalties

    def clear_memories(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('DELETE FROM experiences')
        conn.commit()
