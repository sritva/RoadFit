"""
RoadFit-X: Official Rule RAG
Enriches OSM road attributes by retrieving structural rules from official manuals (e.g. Indian Roads Congress).
"""
from typing import Dict, Any, Optional
from .provenance_store import EdgeEvidence, ProvenanceStore

# Indian Roads Congress (IRC) Structural Standards Knowledge Base
IRC_STANDARDS: Dict[str, Dict[str, Any]] = {
    'motorway': {'carriageway_width': 14.0, 'lane_width': 3.5, 'min_width': 10.5, 'std_dev': 1.0, 'speed_kph': 80.0, 'standard': 'IRC:SP:84-2019 (Expressway)'},
    'trunk': {'carriageway_width': 9.0, 'lane_width': 3.5, 'min_width': 7.0, 'std_dev': 1.0, 'speed_kph': 60.0, 'standard': 'IRC:SP:73-2018 (National/State Highway)'},
    'trunk_link': {'carriageway_width': 7.0, 'lane_width': 3.5, 'min_width': 5.5, 'std_dev': 0.8, 'speed_kph': 40.0, 'standard': 'IRC:SP:73-2018'},
    'primary': {'carriageway_width': 7.0, 'lane_width': 3.5, 'min_width': 6.0, 'std_dev': 0.8, 'speed_kph': 50.0, 'standard': 'IRC:86-1983 (Arterial)'},
    'primary_link': {'carriageway_width': 6.0, 'lane_width': 3.5, 'min_width': 5.0, 'std_dev': 0.6, 'speed_kph': 35.0, 'standard': 'IRC:86-1983'},
    'secondary': {'carriageway_width': 6.0, 'lane_width': 3.0, 'min_width': 5.0, 'std_dev': 0.7, 'speed_kph': 40.0, 'standard': 'IRC:86-1983 (Sub-Arterial)'},
    'secondary_link': {'carriageway_width': 5.5, 'lane_width': 3.0, 'min_width': 4.5, 'std_dev': 0.5, 'speed_kph': 30.0, 'standard': 'IRC:86-1983'},
    'tertiary': {'carriageway_width': 5.5, 'lane_width': 3.0, 'min_width': 4.0, 'std_dev': 0.6, 'speed_kph': 30.0, 'standard': 'IRC:86-1983 (Collector)'},
    'tertiary_link': {'carriageway_width': 4.5, 'lane_width': 3.0, 'min_width': 3.5, 'std_dev': 0.5, 'speed_kph': 25.0, 'standard': 'IRC:86-1983'},
    'residential': {'carriageway_width': 4.0, 'lane_width': 2.75, 'min_width': 2.5, 'std_dev': 0.5, 'speed_kph': 25.0, 'standard': 'IRC:86-1983 (Local Street)'},
    'living_street': {'carriageway_width': 3.0, 'lane_width': 2.5, 'min_width': 2.0, 'std_dev': 0.4, 'speed_kph': 15.0, 'standard': 'IRC:86-1983 (Shared/Pedestrian)'},
    'service': {'carriageway_width': 3.0, 'lane_width': 2.5, 'min_width': 2.0, 'std_dev': 0.4, 'speed_kph': 15.0, 'standard': 'IRC:86-1983 (Access Lane)'},
    'unclassified': {'carriageway_width': 3.5, 'lane_width': 2.75, 'min_width': 2.5, 'std_dev': 0.6, 'speed_kph': 25.0, 'standard': 'IRC:86-1983'}
}

FALLBACK_RULE = {
    'carriageway_width': 3.5,
    'lane_width': 2.75,
    'min_width': 2.5,
    'std_dev': 0.8,
    'speed_kph': 25.0,
    'standard': 'IRC:86-1983 (Default Fallback)'
}


def query_irc_rule(highway_class: str, lanes: Optional[int] = None) -> Dict[str, Any]:
    """
    Retrieves structural rules from the Indian Roads Congress (IRC) codex.
    If number of lanes is known, scales width accordingly.
    """
    rule = IRC_STANDARDS.get(highway_class, FALLBACK_RULE).copy()
    if lanes is not None and lanes > 0:
        rule['carriageway_width'] = max(rule['min_width'], lanes * rule['lane_width'])
    return rule


def enrich_edge_metadata(osm_edge: Dict[str, Any], provenance: ProvenanceStore, edge_id: tuple):
    """
    Retrieval-Augmented Generation (RAG) process.
    If OSM is missing width, infers it based on road classification, lane counts,
    and authoritative Indian Roads Congress (IRC) geometric design standards.
    """
    if 'width' not in osm_edge:
        hw = osm_edge.get('highway', 'residential')
        if isinstance(hw, list):
            hw = hw[0]
            
        lanes_raw = osm_edge.get('lanes')
        lanes = None
        if lanes_raw is not None:
            try:
                lanes = int(float(lanes_raw[0] if isinstance(lanes_raw, list) else lanes_raw))
            except (ValueError, TypeError):
                lanes = None

        rule = query_irc_rule(hw, lanes)
        inferred_width = round(rule['carriageway_width'], 1)

        # Add to provenance store as inferred with IRC citation
        evidence = EdgeEvidence(
            attribute="width",
            value=inferred_width,
            uncertainty_std=rule['std_dev'],
            source=f"LLM_RAG_{rule['standard']}",
            source_timestamp="2026-09-28",
            verification_state="unverified",
            evidence_quality=0.55 if lanes is not None else 0.45
        )
        provenance.add_evidence(edge_id, evidence)
        osm_edge['width'] = inferred_width
        osm_edge['width_source'] = 'inferred_irc_rag'
