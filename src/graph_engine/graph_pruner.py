import osmnx as ox
import networkx as nx
import argparse
import os

def prune_graph_for_vehicle(input_path: str, output_path: str, 
                            vehicle_width: float, vehicle_height: float, vehicle_weight: float):
    print(f"Loading graph from {input_path}")
    G = ox.load_graphml(input_path)
    
    print(f"Pruning for vehicle: width={vehicle_width}m, height={vehicle_height}m, weight={vehicle_weight}t")
    
    edges_to_remove = []
    
    for u, v, k, data in G.edges(keys=True, data=True):
        # Check width (add a small safety margin, e.g., 0.5m total)
        if 'est_width' in data:
            if float(data['est_width']) < (vehicle_width + 0.5):
                edges_to_remove.append((u, v, k))
                continue
                
        # Check height
        if 'max_height' in data:
            if float(data['max_height']) < vehicle_height:
                edges_to_remove.append((u, v, k))
                continue
                
        # Check weight
        if 'max_weight' in data:
            if float(data['max_weight']) < vehicle_weight:
                edges_to_remove.append((u, v, k))
                continue
                
    print(f"Removing {len(edges_to_remove)} edges that violate constraints...")
    G.remove_edges_from(edges_to_remove)
    
    # Remove isolated nodes
    isolated_nodes = list(nx.isolates(G))
    G.remove_nodes_from(isolated_nodes)
    
    print(f"Pruned graph. Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")
    
    # Save graph
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ox.save_graphml(G, output_path)
    print(f"Pruned graph saved to {output_path}")
    
    return G

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prune OSM graph for specific vehicle constraints")
    parser.add_argument("--input", type=str, required=True, help="Input enhanced GraphML file path")
    parser.add_argument("--output", type=str, required=True, help="Output GraphML file path")
    parser.add_argument("--width", type=float, default=2.0, help="Vehicle width in meters")
    parser.add_argument("--height", type=float, default=2.0, help="Vehicle height in meters")
    parser.add_argument("--weight", type=float, default=2.0, help="Vehicle weight in tonnes")
    
    args = parser.parse_args()
    prune_graph_for_vehicle(args.input, args.output, args.width, args.height, args.weight)
