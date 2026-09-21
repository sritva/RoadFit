import networkx as nx
import osmnx as ox
import argparse
import time


def get_edge_data(G, u, v):
    """Return the most relevant edge payload for a node pair across both DiGraph and MultiDiGraph graphs."""
    edge_data = G.get_edge_data(u, v)
    if edge_data is None:
        return {}

    if G.is_multigraph():
        if not edge_data:
            return {}
        return min(edge_data.values(), key=lambda item: float(item.get('length', 0.0) or 0.0))

    return edge_data


def calculate_heuristic(u, v, G, target_node):
    """
    Euclidean distance heuristic for A* on spatial graphs.
    """
    u_data = G.nodes[u]
    target_data = G.nodes[target_node]
    
    # Calculate great-circle distance as heuristic
    # ox.distance.great_circle_vec(lat1, lng1, lat2, lng2) could be used
    # Simplified Euclidean for small city scale if projected, 
    # but lat/lon requires Haversine or great_circle.
    
    # Simple Euclidean for unprojected lat/lon as a fast proxy
    dx = u_data['x'] - target_data['x']
    dy = u_data['y'] - target_data['y']
    return (dx**2 + dy**2)**0.5

def custom_weight_function(u, v, d, vehicle_width=2.0, vehicle_height=2.0, alpha=0.5, beta=0.5):
    """
    Custom weight function combining distance/time with difficulty/risk.
    d: edge data dictionary
    vehicle_width: physical width of the vehicle in meters
    vehicle_height: physical height of the vehicle in meters
    """
    
    # ---------------------------------------------------------
    # 1. HARD PHYSICS CONSTRAINTS (Enterprise Level)
    # ---------------------------------------------------------
    edge_width = float(d.get('width', 10.0))
    edge_height = float(d.get('maxheight', 10.0))
    
    # If the vehicle is physically wider or taller than the road, 
    # it mathematically cannot pass. Return infinity.
    if vehicle_width > edge_width or vehicle_height > edge_height:
        return float('inf')
        
    # ---------------------------------------------------------
    # 2. DYNAMIC TRAFFIC OVERLAY (Time-based Weight)
    # ---------------------------------------------------------
    # Base weight is length (or travel time if we calculated it)
    length = float(d.get('length', 1.0))
    
    # Dynamic Weight Function: Uses live traffic travel time and applies obstruction risk penalties
    travel_time = float(d.get('travel_time', d.get('length', 10.0) / 10.0)) # Fallback if traffic missing
    risk = float(d.get('obstruction_risk', 0.1))
    
    # Penalize routes that have high obstruction risk even more heavily to ensure 
    # physical safety is prioritized over just traffic speed for large vehicles
    weight = travel_time * (1.0 + (risk * 2.0))
    return weight

def run_astar_routing(orig_node: int, dest_node: int, G=None, graph_path: str = None, vehicle_width=2.0, vehicle_height=2.0, vehicle_weight=2.0):
    if G is None and graph_path is not None:
        print(f"Loading pruned graph from {graph_path}")
        G = ox.load_graphml(graph_path)
    elif G is None:
        raise ValueError("Must provide either a pre-loaded Graph G or a graph_path.")
    
    start_time = time.time()
    
    try:
        # Define weight function injected with vehicle constraints
        weight = lambda u, v, d: custom_weight_function(u, v, d, vehicle_width, vehicle_height)
        
        # A* Search
        route = nx.astar_path(
            G, 
            source=orig_node, 
            target=dest_node, 
            heuristic=lambda u, v: calculate_heuristic(u, v, G, dest_node),
            weight=weight
        )
        
        end_time = time.time()
        
        # Calculate stats
        # Use networkx directly to calculate route length
        route_length = 0.0
        for u, v in zip(route[:-1], route[1:]):
            edge_data = get_edge_data(G, u, v)
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
