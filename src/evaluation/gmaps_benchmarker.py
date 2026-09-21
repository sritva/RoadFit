import os
import random
import googlemaps
from datetime import datetime
import osmnx as ox
from dotenv import load_dotenv

# Ensure we can import our routing
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from routing.baseline_astar import run_astar_routing, get_edge_data
from graph_engine.traffic_updater import update_graph_traffic

load_dotenv()

GMAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def benchmark_against_google(graph_path, num_samples=10):
    if not GMAPS_API_KEY or GMAPS_API_KEY == "your_google_maps_api_key_here":
        print("Warning: Google Maps API key not set in .env. Using mock Google Maps response.")
        gmaps = None
    else:
        gmaps = googlemaps.Client(key=GMAPS_API_KEY)
        
    print(f"Loading graph for benchmarking from {graph_path}...")
    G = ox.load_graphml(graph_path)
    
    # Update graph with traffic
    G = update_graph_traffic(G)
    
    # Save the traffic graph to be used by the router
    traffic_graph_path = graph_path.replace(".graphml", "_traffic.graphml")
    ox.save_graphml(G, traffic_graph_path)
    
    nodes = list(G.nodes(data=True))
    
    results = []
    
    for i in range(num_samples):
        # Pick random origin and destination
        orig = random.choice(nodes)
        dest = random.choice(nodes)
        
        orig_id, orig_data = orig
        dest_id, dest_data = dest
        
        orig_coords = (orig_data['y'], orig_data['x'])
        dest_coords = (dest_data['y'], dest_data['x'])
        
        # 1. RoadFit Route
        route = run_astar_routing(orig_id, dest_id, G=G)
        if route is None:
            continue
            
        # Calculate simulated RoadFit ETA based on sum of travel_time edges
        roadfit_eta = 0
        roadfit_dist = 0
        for u, v in zip(route[:-1], route[1:]):
            edge_data = get_edge_data(G, u, v)
            roadfit_eta += float(edge_data.get('travel_time', 10))
            roadfit_dist += float(edge_data.get('length', 10))
            
        # 2. Google Maps Route
        if gmaps:
            now = datetime.now()
            try:
                directions_result = gmaps.directions(
                    orig_coords,
                    dest_coords,
                    mode="driving",
                    departure_time=now
                )
                
                if directions_result:
                    leg = directions_result[0]['legs'][0]
                    gmaps_eta = leg['duration_in_traffic']['value'] if 'duration_in_traffic' in leg else leg['duration']['value']
                    gmaps_dist = leg['distance']['value']
                else:
                    gmaps_eta, gmaps_dist = 0, 0
            except Exception as e:
                print(f"Google Maps API error: {e}")
                gmaps_eta, gmaps_dist = 0, 0
        else:
            # Mock Google Maps values
            # Google is generally faster as it ignores vehicle constraints (e.g. narrow roads)
            gmaps_eta = roadfit_eta * random.uniform(0.7, 0.95)
            gmaps_dist = roadfit_dist * random.uniform(0.8, 1.0)
            
        results.append({
            'orig': orig_coords,
            'dest': dest_coords,
            'roadfit_eta': roadfit_eta,
            'gmaps_eta': gmaps_eta,
            'roadfit_dist': roadfit_dist,
            'gmaps_dist': gmaps_dist
        })
        print(f"[{i+1}/{num_samples}] RF: {roadfit_eta/60:.1f}m | GMaps: {gmaps_eta/60:.1f}m | Delta: {abs(roadfit_eta - gmaps_eta)/60:.1f}m")
        
    print(f"\nBenchmarking complete. Evaluated {len(results)} routes.")
    return results

if __name__ == "__main__":
    benchmark_against_google("data/koramangala_enhanced.graphml", num_samples=5)
