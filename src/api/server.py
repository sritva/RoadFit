"""
RoadFit-X: API Server (Refactored)
------------------------------------
Wires the refactored routing engine, Poisson survival model, and
catastrophic CVaR into the FastAPI endpoint.

FIXES applied:
  - Handles new router return type: (path_nodes, path_edges, stats)
  - Uses exact edge keys from path_edges for geometry extraction
    (no more MultiDiGraph edge collapse in coordinate extraction)
  - Completion probability comes from the Poisson survival model
  - CVaR reports catastrophic tail-risk, not just travel-time variance
"""
import sys
import os
import math
import numpy as np
from scipy.spatial import KDTree
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Tuple, Dict, Any
import uvicorn
import osmnx as ox
import shapely.wkt

# Ensure src modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from routing.risk_aware_router import route_risk_aware
from routing.cvar_optimizer import optimize_cvar_route
from models.scenario_generator import generate_scenarios
from vehicle.vehicle_digital_twin import VehicleDigitalTwin
from data.provenance_store import ProvenanceStore
from brain.cognitive_core import CognitiveCore

def _build_kd_tree(graph):
    nodes_data = list(graph.nodes(data=True))
    coords = np.array([[d['y'], d['x']] for _, d in nodes_data])
    node_ids = np.array([n for n, _ in nodes_data])
    return KDTree(coords), node_ids


app = FastAPI(title="RoadFit-X API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
MASTER_GRAPH = None
KD_TREE = None
NODE_IDS = None
PROVENANCE = ProvenanceStore()
BRAIN = CognitiveCore()

print("Loading enriched master graph into memory for API...")
try:
    MASTER_GRAPH = ox.load_graphml("data/koramangala_enriched_v2.graphml")
    print("Graph loaded successfully.")
    KD_TREE, NODE_IDS = _build_kd_tree(MASTER_GRAPH)
    print(f"KD-Tree built with {len(NODE_IDS)} nodes.")
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
    unknown_data_policy: str = "exploratory"
    simulate_congestion: bool = False
    rain_level: str = "none"      # none, light, moderate, heavy, extreme
    traffic_level: str = "normal"  # low, normal, heavy, gridlock


@app.get("/")
def read_root():
    return {"message": "RoadFit-X World Model API v3.0 is online"}

@app.post("/brain/train")
def train_brain(iterations: int = 1000):
    if MASTER_GRAPH is None:
        raise HTTPException(status_code=500, detail="Master graph not loaded.")
    
    import threading
    # Run in background to avoid blocking FastAPI
    def _train():
        BRAIN.train_brain(MASTER_GRAPH, iterations)
    
    thread = threading.Thread(target=_train)
    thread.start()
    return {"message": f"Brain training initiated with {iterations} simulated scenarios in the background."}

def _extract_route_coords_from_edges(
    graph,
    path_nodes: List[int],
    path_edges: List[Tuple[int, int, Any, Dict[str, Any]]],
) -> List[List[float]]:
    """Extract [lon, lat] coordinates using exact edge keys from path_edges.

    This avoids the old MultiDiGraph collapse bug: we use the precise edge
    key that was selected by the router, not an arbitrary parallel edge.
    """
    coords = []
    for u, v, key, data in path_edges:
        geom = data.get('geometry')
        if geom is not None:
            try:
                if isinstance(geom, str):
                    geom = shapely.wkt.loads(geom)
                if hasattr(geom, 'coords'):
                    for lon, lat in geom.coords:
                        coords.append([lon, lat])
                    continue
            except Exception:
                pass
        # Fallback to node coordinates
        u_data = graph.nodes[u]
        coords.append([float(u_data['x']), float(u_data['y'])])

    # Always append destination
    last_node = path_nodes[-1]
    last = graph.nodes[last_node]
    coords.append([float(last['x']), float(last['y'])])
    return coords


@app.post("/route/plan")
def route_plan(request: CoordinateRequest):
    # Determine active graph: dynamic download if outside Koramangala bounds
    distance_to_center = (
        (request.orig_lat - 12.9352)**2 + (request.orig_lon - 77.6245)**2
    )**0.5

    if distance_to_center > 0.05:
        # Prevent massive inter-city requests from hanging the OSM Overpass API
        # Haversine approximation in degrees (1 deg ~ 111km)
        trip_distance_deg = ((request.orig_lat - request.dest_lat)**2 + (request.orig_lon - request.dest_lon)**2)**0.5
        if trip_distance_deg > 0.5: # ~50km
            raise HTTPException(
                status_code=400,
                detail="Trip too long for dynamic graph generation. Please select points within 50km of each other."
            )
            
        print("Coordinates outside Koramangala. Dynamically fetching OSM graph...")
        try:
            padding = 0.015  # ~1.5km padding
            north = max(request.orig_lat, request.dest_lat) + padding
            south = min(request.orig_lat, request.dest_lat) - padding
            east = max(request.orig_lon, request.dest_lon) + padding
            west = min(request.orig_lon, request.dest_lon) - padding

            active_graph = ox.graph_from_bbox(
                bbox=(west, south, east, north),
                network_type='drive'
            )
            temp_kd, temp_ids = _build_kd_tree(active_graph)

            _, oi = temp_kd.query([request.orig_lat, request.orig_lon])
            _, di = temp_kd.query([request.dest_lat, request.dest_lon])
            orig_node = int(temp_ids[oi])
            dest_node = int(temp_ids[di])
            print(f"Dynamic graph loaded: {active_graph.number_of_nodes()} nodes")
        except Exception as e:
            print(f"Dynamic graph fetch failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Could not fetch map data: {e}"
            )
    else:
        if MASTER_GRAPH is None:
            raise HTTPException(
                status_code=500, detail="Master graph not loaded."
            )
        _, oi = KD_TREE.query([request.orig_lat, request.orig_lon])
        _, di = KD_TREE.query([request.dest_lat, request.dest_lon])
        orig_node = int(NODE_IDS[oi])
        dest_node = int(NODE_IDS[di])
        active_graph = MASTER_GRAPH

    if orig_node == dest_node:
        raise HTTPException(
            status_code=400,
            detail="Origin and destination resolve to the same node. "
                   "Please move them further apart."
        )

    vehicle = VehicleDigitalTwin(
        vehicle_type="custom",
        width_m=request.vehicle_width,
        height_m=request.vehicle_height,
        gross_weight_t=request.vehicle_weight,
        axle_load_t=request.vehicle_weight / 2.0,
        wheelbase_m=3.0,
        turning_radius_m=6.0,
        ground_clearance_m=0.2,
        max_grade_pct=15.0,
        surface_tolerance=["asphalt", "concrete", "paved", "compacted"],
        rain_tolerance="medium",
        cargo_class="standard",
        risk_preference="moderate",
        unknown_data_policy=request.unknown_data_policy
    )

    rain = request.rain_level
    traffic = request.traffic_level

    # ── Baseline B0 Route for Trade-off Comparison ──
    from evaluation.baseline_routes import route_shortest_eta
    from evaluation.metrics_engine import MetricsEngine
    from routing.risk_aware_router import _compute_path_stats
    
    b0_nodes = route_shortest_eta(active_graph, orig_node, dest_node)
    b0_edges = []
    b0_coords = []
    b0_time = 0.0
    
    if b0_nodes and len(b0_nodes) >= 2:
        for i in range(len(b0_nodes)-1):
            u = b0_nodes[i]
            v = b0_nodes[i+1]
            edge_data = active_graph.get_edge_data(u, v)
            if edge_data:
                key = list(edge_data.keys())[0]
                b0_edges.append((u, v, key, edge_data[key]))
        
        b0_coords = _extract_route_coords_from_edges(active_graph, b0_nodes, b0_edges)
        
        # Calculate B0 baseline physical time
        for _, _, _, data in b0_edges:
            length_m = float(data.get('length', 10.0))
            speed_raw = data.get('speed_kph', data.get('maxspeed', 25.0))
            if isinstance(speed_raw, list):
                speed_raw = speed_raw[0]
            try:
                speed_kph = float(speed_raw)
            except (ValueError, TypeError):
                speed_kph = 25.0
            speed_mps = max(speed_kph * (1000.0 / 3600.0), 1.0)
            b0_time += (length_m / speed_mps)

    # ── Route using the refactored engine ──
    if request.simulate_congestion:
        print(f"CVaR mode: rain={rain}, traffic={traffic}")
        scenarios = generate_scenarios(active_graph, num_scenarios=5)
        rf_nodes, rf_edges, rf_stats = optimize_cvar_route(
            base_graph=active_graph,
            scenarios=scenarios,
            orig_node=orig_node,
            dest_node=dest_node,
            vehicle=vehicle,
            provenance=PROVENANCE,
            rain_level=rain,
            traffic_level=traffic,
        )
    else:
        print(f"Ensemble A* mode: rain={rain}, traffic={traffic}, policy={request.unknown_data_policy}")
        
        # Mechanism 1: Pure Heuristics (No Memory)
        h_nodes, h_edges, h_stats = route_risk_aware(
            G=active_graph, orig_node=orig_node, dest_node=dest_node,
            vehicle=vehicle, provenance=PROVENANCE, rain_level=rain, traffic_level=traffic
        )
        
        # Mechanism 2: Cognitive Bias (Episodic Memory)
        biased_graph = BRAIN.apply_cognitive_bias(active_graph, rain, traffic, vehicle.vehicle_type)
        b_nodes, b_edges, b_stats = route_risk_aware(
            G=biased_graph, orig_node=orig_node, dest_node=dest_node,
            vehicle=vehicle, provenance=PROVENANCE, rain_level=rain, traffic_level=traffic
        )
        
        # Ensemble Selection Logic:
        # Compare expected travel time adjusted by survival probability (ETA / P_survival)
        # Lower is better.
        def _score(stats):
            if not stats: return float('inf')
            p = stats.get('completion_probability', 0.001)
            eta = stats.get('eta_seconds', 999999)
            return eta / max(p, 0.001)

        score_h = _score(h_stats)
        score_b = _score(b_stats)

        ensemble_winner = ""
        if b_nodes and score_b <= score_h:
            rf_nodes, rf_edges, rf_stats = b_nodes, b_edges, b_stats
            ensemble_winner = "Cognitive Core (Brain Memory)"
        elif h_nodes:
            rf_nodes, rf_edges, rf_stats = h_nodes, h_edges, h_stats
            ensemble_winner = "Pure Physics Heuristics"
        else:
            rf_nodes, rf_edges, rf_stats = None, None, None

    if rf_nodes is None or rf_edges is None or len(rf_nodes) < 2:
        raise HTTPException(
            status_code=404,
            detail=f"No viable route found under '{request.unknown_data_policy}' policy. Try a more relaxed policy.",
        )

    # ── Geometry extraction using exact edge keys ──
    coords = _extract_route_coords_from_edges(active_graph, rf_nodes, rf_edges)

    if len(coords) < 2:
        raise HTTPException(
            status_code=500,
            detail="Route found but geometry extraction failed.",
        )

    # Calculate true physical time for RoadFit-X to ensure accurate ETTP
    rf_time = 0.0
    for _, _, _, data in rf_edges:
        length_m = float(data.get('length', 10.0))
        speed_raw = data.get('speed_kph', data.get('maxspeed', 25.0))
        if isinstance(speed_raw, list):
            speed_raw = speed_raw[0]
        try:
            speed_kph = float(speed_raw)
        except (ValueError, TypeError):
            speed_kph = 25.0
        speed_mps = max(speed_kph * (1000.0 / 3600.0), 1.0)
        rf_time += (length_m / speed_mps)
        
    if b0_time <= 0:
        b0_time = rf_time

    # Evaluate Academic Metrics
    metrics_engine = MetricsEngine(vehicle)
    academic_metrics = metrics_engine.evaluate_route(
        G=active_graph, 
        path_nodes=rf_nodes, 
        path_edges=rf_edges, 
        median_eta=rf_time, 
        baseline_b0_time=b0_time
    )

    # Counterfactual explanations
    from routing.counterfactual_router import generate_route_explanation
    explanations = generate_route_explanation(rf_stats, rf_nodes)

    dist_km = rf_stats.get('distance_m', 0) / 1000.0

    return {
        "selected_route": {
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "eta_p50_min": round(rf_time / 60.0, 1),
            "eta_p90_min": round((rf_time / 60.0) * 1.3, 1),
            "completion_probability": round(
                rf_stats.get('completion_probability', 0.9), 4
            ),
            "cvar_risk": round(rf_stats.get('cvar_risk', rf_time * 0.2), 1),
            "distance_km": round(dist_km, 2),
            "avg_speed_kmh": round(rf_stats.get('avg_speed_kmh', 25.0), 1),
            "rain_level": rain,
            "traffic_level": traffic,
            "ensemble_winner": ensemble_winner if not request.simulate_congestion else "CVaR Optimiser",
            "academic_metrics": academic_metrics
        },
        "baseline_route": {
            "geometry": {
                "type": "LineString",
                "coordinates": b0_coords,
            },
            "eta_p50_min": round(b0_time / 60.0, 1)
        },
        "warnings": (
            explanations
            if explanations
            else [f"Route optimised. {len(rf_nodes)} nodes traversed."]
        )
    }


if __name__ == "__main__":
    print("Starting RoadFit-X API Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
