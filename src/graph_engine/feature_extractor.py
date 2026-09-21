import osmnx as ox
import networkx as nx
import argparse
import os
import math

def calculate_turn_angle(u_coord, v_coord, w_coord):
    """Calculate angle between three points (u->v->w) in degrees."""
    # Simplified planar calculation for local areas
    dx1, dy1 = v_coord[0] - u_coord[0], v_coord[1] - u_coord[1]
    dx2, dy2 = w_coord[0] - v_coord[0], w_coord[1] - v_coord[1]
    
    dot = dx1*dx2 + dy1*dy2
    det = dx1*dy2 - dy1*dx2
    angle = math.atan2(det, dot)
    return math.degrees(angle)

def enhance_graph_features(input_path: str, output_path: str):
    print(f"Loading graph from {input_path}")
    G = ox.load_graphml(input_path)
    
    # 1. Fill missing widths with proxies based on highway type
    # OSM highway types and typical widths in meters (proxies)
    highway_widths = {
        'motorway': 15.0,
        'trunk': 12.0,
        'primary': 10.0,
        'secondary': 8.0,
        'tertiary': 6.0,
        'unclassified': 5.0,
        'residential': 4.5,
        'living_street': 3.5,
        'service': 3.0,
        'track': 2.5
    }
    
    print("Enhancing edge features...")
    for u, v, k, data in G.edges(keys=True, data=True):
        highway = data.get('highway', 'unclassified')
        if isinstance(highway, list):
            highway = highway[0]
            
        # Add estimated width if missing
        if 'width' not in data or data['width'] == 'NaN':
            data['est_width'] = highway_widths.get(highway, 4.0)
        else:
            try:
                # Some widths are strings like '4.5', some are lists
                w = data['width']
                if isinstance(w, list): w = w[0]
                data['est_width'] = float(w.replace('m', '').strip())
            except:
                data['est_width'] = highway_widths.get(highway, 4.0)
                
        # Add a placeholder for local congestion / building density
        # In a real pipeline, we'd query building footprints near this edge
        if highway in ['residential', 'living_street']:
            data['obstruction_risk'] = 0.8
        elif highway in ['primary', 'motorway']:
            data['obstruction_risk'] = 0.2
        else:
            data['obstruction_risk'] = 0.5
            
        # Hard constraints placeholder (if maxheight/maxweight exist in OSM, use them)
        data['max_height'] = float(data.get('maxheight', 99.0)) if isinstance(data.get('maxheight'), (int, float, str)) and str(data.get('maxheight')).replace('.','').isdigit() else 99.0
        data['max_weight'] = float(data.get('maxweight', 99.0)) if isinstance(data.get('maxweight'), (int, float, str)) and str(data.get('maxweight')).replace('.','').isdigit() else 99.0

    print("Saving enhanced graph...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ox.save_graphml(G, output_path)
    print(f"Enhanced graph saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance OSM graph with physical features")
    parser.add_argument("--input", type=str, required=True, help="Input GraphML file path")
    parser.add_argument("--output", type=str, required=True, help="Output GraphML file path")
    
    args = parser.parse_args()
    enhance_graph_features(args.input, args.output)
