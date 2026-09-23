import random
import time
import hashlib
import networkx as nx
from typing import Optional, Dict, Any, Tuple

from src.brain.episodic_memory import EpisodicMemoryBank
from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.routing.risk_aware_router import route_risk_aware

class CognitiveCore:
    def __init__(self, db_path="brain_memory.db"):
        self.memory = EpisodicMemoryBank(db_path)

    def _deterministic_env_hazard(self, edge_id: str, weather: str, traffic: str, data: dict) -> bool:
        """
        An oracle that defines the 'real world' physics. 
        Instead of a separate ground-truth graph, we deterministically generate
        real-world hazards based on the context and edge properties.
        Returns True if the hazard causes a route failure (e.g. flooded and blocked).
        """
        # Base failure rate
        fail_prob = 0.0
        
        road_type = data.get('highway', 'unknown')
        width = float(data.get('width', data.get('_width_mean', 3.0)))
        
        # 1. Weather hazards
        if weather == "rain":
            # Narrow residential/service roads flood easily
            if road_type in ['service', 'residential'] and width < 4.0:
                # Use hash to make flooding consistent per edge in rain
                h = int(hashlib.md5(f"{edge_id}_rain_flood".encode()).hexdigest(), 16)
                if h % 100 < 40: # 40% chance this specific edge is a permanent flood zone
                    fail_prob += 1.0

        if weather == "storm":
            if road_type in ['tertiary', 'residential']:
                h = int(hashlib.md5(f"{edge_id}_storm_tree".encode()).hexdigest(), 16)
                if h % 100 < 15: # 15% chance of downed tree
                    fail_prob += 1.0

        # 2. Traffic hazards
        if traffic == "peak":
            # Very narrow roads get completely gridlocked by parked cars during peak
            if width < 3.5:
                h = int(hashlib.md5(f"{edge_id}_peak_gridlock".encode()).hexdigest(), 16)
                if h % 100 < 60: # 60% chance of impossible gridlock
                    fail_prob += 1.0

        return fail_prob >= 1.0

    def train_brain(self, G: nx.MultiDiGraph, iterations: int = 1000):
        """
        Simulates 1000 random routing tasks under various contexts.
        Learns which edges historically fail.
        """
        nodes = list(G.nodes)
        weathers = ["clear", "rain", "storm"]
        traffics = ["low", "peak"]
        vehicle = VehicleDigitalTwin(
            vehicle_type="training_van",
            width_m=2.4, height_m=2.8, gross_weight_t=5.0,
            axle_load_t=2.5, wheelbase_m=3.0, turning_radius_m=6.0,
            ground_clearance_m=0.2, max_grade_pct=15.0,
            surface_tolerance=["asphalt", "concrete"],
            rain_tolerance="medium", risk_preference="moderate",
            unknown_data_policy="exploratory"
        )
        
        print(f"🧠 Brain entering REM sleep... dreaming {iterations} scenarios.")
        for i in range(iterations):
            orig = random.choice(nodes)
            dest = random.choice(nodes)
            if orig == dest: continue
            
            weather = random.choice(weathers)
            traffic = random.choice(traffics)
            
            # Route with no prior knowledge
            path_nodes, path_edges, stats = route_risk_aware(G, orig, dest, vehicle)
            
            if path_nodes and path_edges:
                # Simulate traversing the route in the "real world"
                failed_edge = None
                time_taken = 0.0
                for (u, v, k, data) in path_edges:
                    edge_id = f"{u}_{v}_{k}"
                    
                    # Did we hit a hazard?
                    if self._deterministic_env_hazard(edge_id, weather, traffic, data):
                        failed_edge = edge_id
                        break
                    
                    # Accumulate time
                    time_taken += data.get('travel_time', 10.0)
                
                # Commit memories
                # For simplicity, we commit success for edges we passed, and failure for the one that blocked us
                for (u, v, k, data) in path_edges:
                    edge_id = f"{u}_{v}_{k}"
                    if edge_id == failed_edge:
                        self.memory.commit_experience(edge_id, weather, traffic, vehicle.vehicle_type, False, time_taken)
                        break # Route ends here
                    else:
                        self.memory.commit_experience(edge_id, weather, traffic, vehicle.vehicle_type, True, data.get('travel_time', 10.0))
            
            if i % 100 == 0:
                print(f"  [{i}/{iterations}] Memories consolidated...")
                
        print("🧠 Waking up. Learning complete.")

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
