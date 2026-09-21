import os
import random
import networkx as nx
from dotenv import load_dotenv

load_dotenv()
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

def update_graph_traffic(G):
    """
    Simulates or fetches real-time traffic data to update edge travel times.
    This dynamically alters the routing cost structure.
    """
    print("Updating graph with live traffic data...")
    
    # In a real scenario, we would iterate through major bounding boxes of the graph,
    # query the TomTom Traffic Flow API (or Google Maps Routes), and map-match the speeds 
    # to the specific OSM node edges.
    
    # Here, we simulate a 'traffic incident' layer. 
    # We will randomly select 5% of edges and drastically increase their travel time to simulate congestion.
    
    edges_to_update = list(G.edges(data=True, keys=True))
    incident_count = int(len(edges_to_update) * 0.05)
    
    # Reset all edges to their free-flow speed first (from feature extractor)
    for u, v, k, data in edges_to_update:
        if 'length' in data and 'speed_kph' in data:
            # Base travel time in seconds
            base_time = (data['length'] / 1000) / data['speed_kph'] * 3600
            data['travel_time'] = base_time
            data['traffic_multiplier'] = 1.0 # Free flow
            
    # Apply synthetic congestion
    congested_edges = random.sample(edges_to_update, incident_count)
    for u, v, k, data in congested_edges:
        if 'travel_time' in data:
            # Multiplier between 2x and 5x slower
            multiplier = random.uniform(2.0, 5.0)
            data['travel_time'] *= multiplier
            data['traffic_multiplier'] = multiplier
            
    print(f"Traffic update complete. {incident_count} edges are congested.")
    return G

if __name__ == "__main__":
    # Test
    import osmnx as ox
    try:
        G = ox.load_graphml("data/koramangala_enhanced.graphml")
        G_traffic = update_graph_traffic(G)
        ox.save_graphml(G_traffic, "data/koramangala_traffic.graphml")
        print("Saved traffic-enhanced graph.")
    except Exception as e:
        print(f"Error: {e}")
