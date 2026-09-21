import networkx as nx
import osmnx as ox
import argparse
import time
from itertools import islice

from .baseline_astar import custom_weight_function

def get_k_shortest_paths(graph_path: str, orig_node: int, dest_node: int, k: int = 3):
    print(f"Loading pruned graph from {graph_path}")
    G = ox.load_graphml(graph_path)
    
    print(f"Finding {k} shortest simple paths from {orig_node} to {dest_node} using Yen's Algorithm...")
    
    start_time = time.time()
    
    try:
        # Define weight function
        # NetworkX's shortest_simple_paths requires a weight function or string.
        # It accepts a weight function in newer versions (NX 3+), but string edge attributes are safer.
        # We will iterate through edges and add a pre-computed 'combined_weight' attribute
        
        print("Pre-computing edge weights for Yen's algorithm...")
        for u, v, d in G.edges(data=True):
            d['combined_weight'] = custom_weight_function(u, v, d)
            
        # Convert multi-graph to DiGraph if needed for shortest_simple_paths 
        # (Yen's algorithm implementation in nx works best on simple directed graphs)
        if G.is_multigraph():
            # Simplest approach: keep the shortest edge between nodes
            G_simple = nx.DiGraph()
            for u, v, data in G.edges(data=True):
                w = data['combined_weight']
                if G_simple.has_edge(u, v):
                    if w < G_simple[u][v]['combined_weight']:
                        G_simple.add_edge(u, v, **data)
                else:
                    G_simple.add_edge(u, v, **data)
        else:
            G_simple = G
        
        # Calculate K shortest paths
        k_paths = list(islice(nx.shortest_simple_paths(G_simple, orig_node, dest_node, weight='combined_weight'), k))
        
        end_time = time.time()
        
        print(f"Found {len(k_paths)} paths in {end_time - start_time:.4f} seconds.")
        
        for i, path in enumerate(k_paths):
            route_length = sum(G_simple[u][v].get('length', 1.0) for u, v in zip(path[:-1], path[1:]))
            route_weight = sum(G_simple[u][v].get('combined_weight', 1.0) for u, v in zip(path[:-1], path[1:]))
            print(f"Path {i+1}: Stops: {len(path)}, Distance: {route_length:.2f}m, Custom Weight: {route_weight:.2f}")
            
        return k_paths
        
    except nx.NetworkXNoPath:
        print(f"No path found between {orig_node} and {dest_node}.")
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find K-Shortest Paths on Pruned Graph")
    parser.add_argument("--graph", type=str, required=True, help="Path to pruned GraphML")
    parser.add_argument("--orig", type=int, required=True, help="Origin Node ID")
    parser.add_argument("--dest", type=int, required=True, help="Destination Node ID")
    parser.add_argument("--k", type=int, default=3, help="Number of alternative routes to find")
    
    args = parser.parse_args()
    get_k_shortest_paths(args.graph, args.orig, args.dest, args.k)
