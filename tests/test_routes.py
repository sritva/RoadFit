import os

import osmnx as ox

from src.evaluation.baseline_routes import route_shortest_eta


def test_graph_file_loads():
    G = ox.load_graphml('data/koramangala_enriched_v2.graphml')
    assert len(G.nodes) > 0
    assert len(G.edges) > 0
    assert G.is_multigraph() is True


def test_route_finder_returns_path_for_known_pair():
    G = ox.load_graphml('data/koramangala_enriched_v2.graphml')

    orig_node = min(G.nodes)
    dest_node = max(G.nodes)

    route = route_shortest_eta(G, orig_node, dest_node)

    if route is not None:
        assert len(route) >= 2
        assert route[0] == orig_node
        assert route[-1] == dest_node


def test_multigraph_edge_lookup_returns_dict():
    G = ox.load_graphml('data/koramangala_enriched_v2.graphml')
    edge = next(iter(G.edges(keys=True, data=True)))
    u, v, k, data = edge
    fetched = G.get_edge_data(u, v)
    assert isinstance(fetched, dict)
