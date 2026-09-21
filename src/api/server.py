import sys
import os
import numpy as np
from scipy.spatial import KDTree
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import osmnx as ox

# Ensure src modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from routing.baseline_astar import run_astar_routing
from routing.k_shortest_paths import get_k_shortest_paths


def _get_edge_data(graph, u, v):
    data = graph.get_edge_data(u, v)
    if data is None:
        return {}
    if isinstance(data, dict):
        return next(iter(data.values()), {})
    return data


app = FastAPI()

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global states
MASTER_GRAPH = None
KD_TREE = None
NODE_IDS = None

print("Loading master graph into memory for API...")
try:
    MASTER_GRAPH = ox.load_graphml("data/koramangala_enhanced_traffic.graphml")
    print("Graph loaded successfully.")
    
    print("Building KD-Tree for O(log N) spatial indexing...")
    nodes_data = list(MASTER_GRAPH.nodes(data=True))
    coords = np.array([[data['y'], data['x']] for node_id, data in nodes_data]) # [lat, lon]
    NODE_IDS = np.array([node_id for node_id, data in nodes_data])
    KD_TREE = KDTree(coords)
    print("KD-Tree built successfully.")
    
except Exception as e:
    print(f"Warning: Could not load master graph. {e}")
    MASTER_GRAPH = None

class CoordinateRequest(BaseModel):
    orig_lat: float
    orig_lon: float
    dest_lat: float
    dest_lon: float
    vehicle_width: float = 2.0
    vehicle_height: float = 2.0
    vehicle_weight: float = 2.0
    graph_path: str = "data/koramangala_enhanced_traffic.graphml"

@app.get("/")
def read_root():
    return {"message": "RoadFit Hyperlocal Routing API is online"}

@app.post("/route/compare")
def route_compare(request: CoordinateRequest):
    if MASTER_GRAPH is None or KD_TREE is None:
        raise HTTPException(status_code=500, detail="Master graph or spatial index not loaded.")
        
    # 1. Resolve coordinates to nearest graph nodes in O(log N)
    # Using KD-Tree for [lat, lon]
    _, orig_idx = KD_TREE.query([request.orig_lat, request.orig_lon])
    _, dest_idx = KD_TREE.query([request.dest_lat, request.dest_lon])
    orig_node = int(NODE_IDS[orig_idx])
    dest_node = int(NODE_IDS[dest_idx])
    
    # 2. RoadFit route (hard-constrained, traffic-aware)
    # Pass G via dependency injection to avoid disk I/O
    rf_route = run_astar_routing(
        orig_node=orig_node, 
        dest_node=dest_node, 
        G=MASTER_GRAPH, 
        vehicle_width=request.vehicle_width, 
        vehicle_height=request.vehicle_height, 
        vehicle_weight=request.vehicle_weight
    )
    
    if rf_route is None:
        raise HTTPException(status_code=404, detail="No route found for this vehicle. Hard physics constraints blocked passage.")
        
    import shapely.wkt
    
    # 3. Extract path coordinates for RoadFit route
    rf_coords = []
    rf_distance = 0
    rf_eta = 0
    
    for u, v in zip(rf_route[:-1], rf_route[1:]):
        edge_data = _get_edge_data(MASTER_GRAPH, u, v)
        rf_distance += float(edge_data.get('length', 10))
        rf_eta += float(edge_data.get('travel_time', 10))

        geom = edge_data.get('geometry')
        if geom is not None:
            if isinstance(geom, str):
                geom = shapely.wkt.loads(geom)
            if hasattr(geom, 'coords'):
                for lon, lat in geom.coords:
                    rf_coords.append([lon, lat])
                continue

        u_data = MASTER_GRAPH.nodes[u]
        rf_coords.append([u_data['x'], u_data['y']])
            
    # Always append the final destination node
    final_node = MASTER_GRAPH.nodes[rf_route[-1]]
    rf_coords.append([final_node['x'], final_node['y']])
        
    # Mocking Google Maps route for now by perturbing the RoadFit route slightly
    gmaps_coords = rf_coords.copy()
    
    return {
        "roadfit_geometry": {
            "type": "LineString",
            "coordinates": rf_coords
        },
        "gmaps_geometry": {
            "type": "LineString",
            "coordinates": gmaps_coords
        },
        "roadfit_stats": {
            "distance_km": rf_distance / 1000,
            "eta_mins": rf_eta / 60
        },
        "gmaps_stats": {
            "distance_km": (rf_distance * 0.9) / 1000,
            "eta_mins": max(1, (rf_eta / 60) - 2)
        }
    }

if __name__ == "__main__":
    print("Starting RoadFit API Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
