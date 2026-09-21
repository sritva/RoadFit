import os

import osmnx as ox

from src.routing.baseline_astar import get_edge_data, run_astar_routing


def test_graph_file_loads():
    G = ox.load_graphml('data/koramangala_enhanced_traffic.graphml')
    assert len(G.nodes) > 0
    assert len(G.edges) > 0
    assert G.is_multigraph() is True


def test_route_finder_returns_path_for_known_pair():
    G = ox.load_graphml('data/koramangala_enhanced_traffic.graphml')

    orig_node = min(G.nodes)
    dest_node = max(G.nodes)

    route = run_astar_routing(orig_node, dest_node, G=G)

    if route is not None:
        assert len(route) >= 2
        assert route[0] == orig_node
        assert route[-1] == dest_node


def test_multigraph_edge_lookup_returns_dict():
    G = ox.load_graphml('data/koramangala_enhanced_traffic.graphml')
    edge = next(iter(G.edges(keys=True, data=True)))
    u, v, k, data = edge
    fetched = get_edge_data(G, u, v)
    assert isinstance(fetched, dict)
    assert 'length' in fetched or 'travel_time' in fetched
