"""
RoadFit-X: Hard Constraint Router (Fixed)
-------------------------------------------
Baseline A* router using hard physics constraints.

FIXES applied:
  - Heuristic uses Haversine great-circle distance (not Euclidean on lat/lon
    degrees), divided by max network speed for admissibility.
  - MultiDiGraph edge selection evaluates all parallel keys and picks the
    best viable one for the vehicle, instead of blindly taking min-length.
"""
import networkx as nx
import osmnx as ox
import argparse
import time

from src.routing.risk_aware_router import haversine_admissible_heuristic


def get_edge_data(G, u, v, vehicle_width=2.0, vehicle_height=2.0):
    """Return the most relevant edge payload for a node pair.

    For MultiDiGraphs, evaluates ALL parallel edge keys and returns the one
    with the lowest travel time that still satisfies vehicle hard constraints.
    Falls back to the shortest-length edge if no travel_time is available.
    """
    edge_data = G.get_edge_data(u, v)
    if edge_data is None:
        return {}

    if G.is_multigraph():
        if not edge_data:
            return {}

        # Evaluate all parallel keys — prefer the fastest that fits the vehicle
        viable = []
        for key, data in edge_data.items():
            edge_width = float(data.get('width', 10.0))
            edge_height = float(data.get('maxheight', 10.0))
            if vehicle_width <= edge_width and vehicle_height <= edge_height:
                viable.append(data)

        if viable:
            return min(viable, key=lambda d: float(d.get('travel_time', d.get('length', 0.0) or 0.0)))

        # No viable edge — return the least-bad option (for error reporting)
        return min(edge_data.values(),
                   key=lambda d: float(d.get('length', 0.0) or 0.0))

    return edge_data


def custom_weight_function(u, v, d, vehicle_width=2.0, vehicle_height=2.0, alpha=0.5, beta=0.5):
    """
    Custom weight function combining distance/time with difficulty/risk.
    """
    # ---------------------------------------------------------
    # 1. HARD PHYSICS CONSTRAINTS (Enterprise Level)
    # ---------------------------------------------------------
    edge_width = float(d.get('width', 10.0))
    edge_height = float(d.get('maxheight', 10.0))

    # If the vehicle is physically wider or taller than the road,
    # it mathematically cannot pass.  Return infinity.
    if vehicle_width > edge_width or vehicle_height > edge_height:
        return float('inf')

    # ---------------------------------------------------------
    # 2. DYNAMIC TRAFFIC OVERLAY (Time-based Weight)
    # ---------------------------------------------------------
    travel_time = float(d.get('travel_time', d.get('length', 10.0) / 10.0))
    risk = float(d.get('obstruction_risk', 0.1))

    # Penalize routes that have high obstruction risk
    weight = travel_time * (1.0 + (risk * 2.0))
    return weight


def run_astar_routing(orig_node: int, dest_node: int, G=None,
                      graph_path: str = None,
                      vehicle_width=2.0, vehicle_height=2.0,
                      vehicle_weight=2.0,
                      max_network_speed_mps=33.33):
    if G is None and graph_path is not None:
        print(f"Loading pruned graph from {graph_path}")
        G = ox.load_graphml(graph_path)
    elif G is None:
        raise ValueError("Must provide either a pre-loaded Graph G or a graph_path.")

    start_time = time.time()

    # Pre-fetch target coordinates for the heuristic
    target_lat = G.nodes[dest_node]['y']
    target_lon = G.nodes[dest_node]['x']

    try:
        # Weight function injected with vehicle constraints
        weight = lambda u, v, d: custom_weight_function(
            u, v, d, vehicle_width, vehicle_height
        )

        # Haversine admissible heuristic (FIXED — no more Euclidean on degrees)
        def h(u, _v):
            return haversine_admissible_heuristic(
                G.nodes[u]['y'], G.nodes[u]['x'],
                target_lat, target_lon,
                max_network_speed_mps
            )

        route = nx.astar_path(
            G,
            source=orig_node,
            target=dest_node,
            heuristic=h,
            weight=weight
        )

        end_time = time.time()

        # Calculate stats
        route_length = 0.0
        for u, v in zip(route[:-1], route[1:]):
            edge_data = get_edge_data(G, u, v, vehicle_width, vehicle_height)
            route_length += float(edge_data.get('length', 0))

        print(f"Route found in {end_time - start_time:.4f} seconds.")
        print(f"Route stops (nodes): {len(route)}")
        print(f"Total distance: {route_length:.2f} meters")

        return route

    except nx.NetworkXNoPath:
        print(f"No path found between {orig_node} and {dest_node} for this vehicle.")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Baseline A* Routing on Pruned Graph")
    parser.add_argument("--graph", type=str, required=True, help="Path to pruned GraphML")
    parser.add_argument("--orig", type=int, required=True, help="Origin Node ID")
    parser.add_argument("--dest", type=int, required=True, help="Destination Node ID")

    args = parser.parse_args()
    run_astar_routing(args.orig, args.dest, graph_path=args.graph)
