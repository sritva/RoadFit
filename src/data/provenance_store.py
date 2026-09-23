"""
RoadFit-X: Provenance Store
Defines the schema and storage for edge evidence and uncertainty.
"""

from typing import Any, Optional
from pydantic import BaseModel

class EdgeEvidence(BaseModel):
    attribute: str
    value: Any
    uncertainty_std: float
    source: str
    source_timestamp: str
    verification_state: str = "unverified"
    evidence_quality: float = 0.5
    
class ProvenanceStore:
    def __init__(self):
        self._store = {}
        
    def add_evidence(self, edge_id: tuple, evidence: EdgeEvidence):
        if edge_id not in self._store:
            self._store[edge_id] = []
        self._store[edge_id].append(evidence)
        
    def get_evidence(self, edge_id: tuple, attribute: str) -> Optional[EdgeEvidence]:
        if edge_id not in self._store:
            return None
        # Return the highest quality evidence for this attribute
        relevant = [e for e in self._store[edge_id] if e.attribute == attribute]
        if not relevant:
            return None
        return max(relevant, key=lambda e: e.evidence_quality)
