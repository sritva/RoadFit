import osmnx as ox
import argparse
import os

def download_and_save_graph(place_name: str, network_type: str = "drive", output_dir: str = "data"):
    print(f"Downloading OSM graph for: {place_name} (network_type: {network_type})")
    
    # Configure osmnx
    ox.settings.use_cache = True
    ox.settings.log_console = True
    
    # Download graph
    try:
        G = ox.graph_from_place(place_name, network_type=network_type, simplify=True)
    except Exception as e:
        print(f"Place boundary not found, falling back to address with 2km radius... ({e})")
        G = ox.graph_from_address(place_name, dist=2000, network_type=network_type, simplify=True)
    
    print(f"Graph downloaded. Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")
    
    # Save graph to GraphML format
    os.makedirs(output_dir, exist_ok=True)
    
    # Clean up place name for filename
    safe_place_name = place_name.replace(' ', '_').replace(',', '').lower()
    output_path = os.path.join(output_dir, f"{safe_place_name}_{network_type}.graphml")
    
    ox.save_graphml(G, output_path)
    print(f"Graph saved to {output_path}")
    
    return G

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download OSM graph for a city")
    parser.add_argument("--place", type=str, default="Bengaluru, Karnataka, India", help="Place name (e.g., 'Bengaluru, India')")
    parser.add_argument("--network", type=str, default="drive", choices=["drive", "bike", "walk", "all"], help="Network type")
    parser.add_argument("--output", type=str, default="data", help="Output directory relative to project root")
    
    args = parser.parse_args()
    
    # Ensure output dir is relative to project root (assuming script is run from project root)
    download_and_save_graph(args.place, args.network, args.output)
