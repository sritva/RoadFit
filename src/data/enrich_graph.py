import osmnx as ox
import networkx as nx
import numpy as np
import random
import os

def enrich_graph_widths(input_path: str, output_path: str, drop_rate: float = 0.3):
    print(f"Loading GraphML from {input_path}...")
    G = ox.load_graphml(input_path)
    
    # Statistical parameters for width generation
    # format: (mean, std_dev, min_width)
    hw_distributions = {
        'primary': (8.0, 1.5, 6.0),
        'primary_link': (8.0, 1.5, 6.0),
        'secondary': (7.0, 1.2, 5.0),
        'secondary_link': (7.0, 1.2, 5.0),
        'tertiary': (6.0, 1.0, 4.0),
        'tertiary_link': (6.0, 1.0, 4.0),
        'trunk': (9.0, 1.5, 7.0),
        'trunk_link': (9.0, 1.5, 7.0),
        'residential': (3.5, 1.0, 2.0),
        'living_street': (3.0, 0.8, 1.8),
        'unclassified': (3.5, 1.0, 2.0)
    }
    
    fallback_dist = (4.0, 1.0, 2.5)
    
    np.random.seed(42)
    random.seed(42)
    
    total_edges = 0
    enriched_edges = 0
    dropped_edges = 0
    
    print("Enriching edges with statistical widths...")
    for u, v, key, data in G.edges(keys=True, data=True):
        total_edges += 1
        
        # If it already has a width, skip or overwrite?
        # Since MDEF was 100%, we'll just overwrite/fill everything then drop some
        hw = data.get('highway')
        if isinstance(hw, list):
            hw = hw[0]
            
        dist = hw_distributions.get(hw, fallback_dist)
        
        # Randomly decide if this edge will have a missing tag
        if random.random() < drop_rate:
            if 'width' in data:
                del data['width']
            dropped_edges += 1
            continue
            
        # Generate synthetic width
        synthetic_width = max(np.random.normal(dist[0], dist[1]), dist[2])
        
        # Add a tiny bit of noise to make it look realistic
        synthetic_width = round(synthetic_width, 1)
        
        # Inject tag
        data['width'] = str(synthetic_width)
        enriched_edges += 1
        
    print(f"Total Edges: {total_edges}")
    print(f"Enriched Edges (Simulated Data): {enriched_edges} ({(enriched_edges/total_edges)*100:.1f}%)")
    print(f"Dropped Edges (Simulated Missing Data): {dropped_edges} ({(dropped_edges/total_edges)*100:.1f}%)")
    
    print(f"Saving enriched graph to {output_path}...")
    ox.save_graphml(G, output_path)
    print("Done!")

if __name__ == "__main__":
    in_path = "data/koramangala_enhanced.graphml"
    out_path = "data/koramangala_enriched_v2.graphml"
    
    if not os.path.exists(in_path):
        print(f"Error: {in_path} not found.")
    else:
        enrich_graph_widths(in_path, out_path, drop_rate=0.3)
