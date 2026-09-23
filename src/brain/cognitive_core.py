import random
import time
import hashlib
import networkx as nx
from typing import Optional, Dict, Any, Tuple, List
import concurrent.futures

from src.brain.episodic_memory import EpisodicMemoryBank
from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.routing.risk_aware_router import route_risk_aware

def deterministic_env_hazard(edge_id: str, weather: str, traffic: str, data: dict) -> bool:
    """
    An oracle that defines the 'real world' physics. 
    Returns True if the hazard causes a route failure.
    """
    fail_prob = 0.0
    
    road_type = data.get('highway', 'unknown')
    width = float(data.get('width', data.get('_width_mean', 3.0)))
    
    if weather == "rain":
        if road_type in ['service', 'residential'] and width < 4.0:
            h = int(hashlib.md5(f"{edge_id}_rain_flood".encode()).hexdigest(), 16)
            if h % 100 < 40: 
                fail_prob += 1.0

    if weather == "storm":
        if road_type in ['tertiary', 'residential']:
            h = int(hashlib.md5(f"{edge_id}_storm_tree".encode()).hexdigest(), 16)
            if h % 100 < 15: 
                fail_prob += 1.0

    if traffic == "peak":
        if width < 3.5:
            h = int(hashlib.md5(f"{edge_id}_peak_gridlock".encode()).hexdigest(), 16)
            if h % 100 < 60: 
                fail_prob += 1.0

    return fail_prob >= 1.0

def simulate_routes_chunk(G: nx.MultiDiGraph, iterations: int, vehicle: VehicleDigitalTwin) -> List[Tuple]:
    """
    Worker function to simulate a chunk of routes in parallel.
    Returns a list of experience tuples ready for batch DB insertion.
    """
    nodes = list(G.nodes)
    weathers = ["clear", "rain", "storm"]
    traffics = ["low", "peak"]
    experiences = []
    
    for _ in range(iterations):
        orig = random.choice(nodes)
        dest = random.choice(nodes)
        if orig == dest: continue
        
        weather = random.choice(weathers)
        traffic = random.choice(traffics)
        
        path_nodes, path_edges, stats = route_risk_aware(G, orig, dest, vehicle)
        
        if path_nodes and path_edges:
            failed_edge = None
            time_taken = 0.0
            for (u, v, k, data) in path_edges:
                edge_id = f"{u}_{v}_{k}"
                if deterministic_env_hazard(edge_id, weather, traffic, data):
                    failed_edge = edge_id
                    break
                time_taken += data.get('travel_time', 10.0)
            
            for (u, v, k, data) in path_edges:
                edge_id = f"{u}_{v}_{k}"
                if edge_id == failed_edge:
                    experiences.append((edge_id, weather, traffic, vehicle.vehicle_type, False, time_taken))
                    break
                else:
                    experiences.append((edge_id, weather, traffic, vehicle.vehicle_type, True, data.get('travel_time', 10.0)))
    
    return experiences

class CognitiveCore:
    def __init__(self, db_path="brain_memory.db"):
        self.memory = EpisodicMemoryBank(db_path)

    def train_brain(self, G: nx.MultiDiGraph, iterations: int = 20000):
        """
        Simulates 20,000 random routing tasks across all available CPU cores.
        """
        import os
        num_cores = max(1, os.cpu_count() - 1)
        chunk_size = max(1, iterations // num_cores)
        chunks = [chunk_size] * num_cores
        
        # Handle remainder if not perfectly divisible
        if sum(chunks) < iterations:
            chunks[0] += (iterations - sum(chunks))

        vehicle = VehicleDigitalTwin(
            vehicle_type="training_van",
            width_m=2.4, height_m=2.8, gross_weight_t=5.0,
            axle_load_t=2.5, wheelbase_m=3.0, turning_radius_m=6.0,
            ground_clearance_m=0.2, max_grade_pct=15.0,
            surface_tolerance=["asphalt", "concrete"],
            rain_tolerance="medium", risk_preference="moderate",
            unknown_data_policy="exploratory"
        )
        
        print(f"🧠 Brain entering REM sleep... scaling out {iterations} scenarios across {num_cores} cores.")
        
        start_t = time.time()
        total_experiences = 0
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_cores) as executor:
            futures = [executor.submit(simulate_routes_chunk, G, c, vehicle) for c in chunks]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    experiences = future.result()
                    if experiences:
                        self.memory.commit_experiences_batch(experiences)
                        total_experiences += len(experiences)
                        print(f"  [+] Consolidated {len(experiences)} memories into SQLite...")
                except Exception as e:
                    print(f"  [!] Core simulation failed: {e}")
                
        print(f"🧠 Learning complete in {time.time() - start_t:.1f}s. {total_experiences} edge experiences memorized.")

    def apply_cognitive_bias(self, G: nx.MultiDiGraph, weather: str, traffic: str, vehicle_type: str) -> nx.MultiDiGraph:
        """
        Injects historical failure probabilities directly into the graph.
        The risk_aware_router will pick up '_history_penalty'.
        """
        G_biased = G.copy()
        
        # Recall penalties from episodic memory
        penalties = self.memory.recall_edge_penalties(weather, traffic, vehicle_type)
        
        for u, v, k, data in G_biased.edges(keys=True, data=True):
            edge_id = f"{u}_{v}_{k}"
            if edge_id in penalties:
                # Store the historical failure rate (0.0 to 1.0)
                data['_history_penalty'] = penalties[edge_id]
            else:
                data['_history_penalty'] = 0.0
                
        return G_biased
