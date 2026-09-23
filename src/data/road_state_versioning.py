"""
RoadFit-X: Road State Versioning
Provides versioned, inspectable road-state memory, allowing replayable experiments.
"""
import uuid
import time
from typing import Dict, Any, List

class RoadStateVersion:
    def __init__(self, description: str):
        self.version_id = str(uuid.uuid4())
        self.timestamp = time.time()
        self.description = description
        self.edge_updates = {}
        
    def log_update(self, edge_id: tuple, key: str, old_val: Any, new_val: Any):
        if edge_id not in self.edge_updates:
            self.edge_updates[edge_id] = []
        self.edge_updates[edge_id].append({
            'key': key,
            'old': old_val,
            'new': new_val
        })

class RoadStateMemory:
    def __init__(self):
        self.history: List[RoadStateVersion] = []
        self.current_version = None
        
    def start_new_version(self, description: str) -> RoadStateVersion:
        v = RoadStateVersion(description)
        self.history.append(v)
        self.current_version = v
        return v
