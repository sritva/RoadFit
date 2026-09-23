"""
RoadFit-X: Baseline Routing Algorithms
Provides classic implementations for comparison against RoadFit-X risk-aware routing.
"""
import networkx as nx

def route_shortest_distance(G, orig_node, dest_node):
    """Standard unconstrained shortest distance (Dijkstra)"""
    try:
        return nx.shortest_path(G, orig_node, dest_node, weight='length')
    except nx.NetworkXNoPath:
        return None

def route_shortest_eta(G, orig_node, dest_node):
    """Standard unconstrained fastest time (Dijkstra)"""
    try:
        return nx.shortest_path(G, orig_node, dest_node, weight='travel_time')
    except nx.NetworkXNoPath:
        return None

def route_hard_constrained_astar(G, orig_node, dest_node, vehicle_profile):
    """
    Hard-constrained A* routing. 
    This uses the updated hard_constraint_router internally.
    """
    from src.routing.hard_constraint_router import run_astar_routing
    return run_astar_routing(
        orig_node=orig_node, 
        dest_node=dest_node, 
        G=G, 
        vehicle_width=vehicle_profile.width_m, 
        vehicle_height=vehicle_profile.height_m, 
        vehicle_weight=vehicle_profile.gross_weight_t
    )
