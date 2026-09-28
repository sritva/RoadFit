import pytest
from src.data.official_rule_rag import query_irc_rule, enrich_edge_metadata
from src.data.provenance_store import ProvenanceStore

def test_query_irc_rule():
    rule_primary = query_irc_rule("primary")
    assert rule_primary["carriageway_width"] >= 7.0
    assert "IRC:86-1983" in rule_primary["standard"]

    # When lanes=4, primary road width should scale
    rule_4lanes = query_irc_rule("primary", lanes=4)
    assert rule_4lanes["carriageway_width"] == 14.0

    # Fallback for unknown road classes
    rule_unknown = query_irc_rule("non_existent_highway_type")
    assert rule_unknown["carriageway_width"] > 0

def test_enrich_edge_metadata_with_rag():
    provenance = ProvenanceStore()
    edge_data = {"highway": "secondary", "length": 150.0}
    edge_id = (101, 102, 0)

    # Edge has no width initially
    assert "width" not in edge_data

    enrich_edge_metadata(edge_data, provenance, edge_id)

    # Now edge has width and provenance entry
    assert "width" in edge_data
    assert edge_data["width"] == 6.0
    assert edge_data["width_source"] == "inferred_irc_rag"

    evidence = provenance.get_evidence(edge_id, "width")
    assert evidence is not None
    assert evidence.value == 6.0
    assert "IRC:86-1983" in evidence.source
