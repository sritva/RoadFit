import pytest
import networkx as nx
import os
import hashlib
from src.brain.cognitive_core import CognitiveCore
from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.routing.risk_aware_router import route_risk_aware

@pytest.fixture
def test_graph():
    G = nx.MultiDiGraph()
    G.add_node(0, y=12.935, x=77.624)
    G.add_node(1, y=12.936, x=77.625) # Hazard node (narrow road)
    G.add_node(2, y=12.937, x=77.626)
    G.add_node(3, y=12.935, x=77.627) # Safe detour
    
    # Path A: Fast but floods in rain
    G.add_edge(0, 1, key=0, length=500.0, width=3.5, maxheight=4.5, highway='service', travel_time=60.0)
    G.add_edge(1, 2, key=0, length=500.0, width=3.5, maxheight=4.5, highway='service', travel_time=60.0)
    
    # Path B: Slow but wide (no flood)
    G.add_edge(0, 3, key=0, length=800.0, width=6.0, maxheight=4.5, highway='secondary', travel_time=200.0)
    G.add_edge(3, 2, key=0, length=800.0, width=6.0, maxheight=4.5, highway='secondary', travel_time=200.0)
    
    return G

def test_cognitive_learning(test_graph):
    # Use in-memory DB for tests
    brain = CognitiveCore(db_path=":memory:")
    
    vehicle = VehicleDigitalTwin(
        vehicle_type="training_van",
        width_m=2.4, height_m=2.8, gross_weight_t=5.0,
        axle_load_t=2.5, wheelbase_m=3.0, turning_radius_m=6.0,
        ground_clearance_m=0.2, max_grade_pct=15.0,
        surface_tolerance=["asphalt", "concrete"],
        rain_tolerance="medium", risk_preference="moderate",
        unknown_data_policy="exploratory"
    )
    
    # 1. Simulate failure
    # We manually commit a massive failure to episodic memory for edge (0, 1, 0)
    edge_id = "0_1_0"
    for _ in range(5):
        brain.memory.commit_experience(edge_id, "rain", "low", "training_van", False, 999.0)
        
    # 2. Apply Cognitive Bias
    biased_graph = brain.apply_cognitive_bias(test_graph, "rain", "low", "training_van")
    
    assert biased_graph[0][1][0]['_history_penalty'] == 1.0, "Brain should have injected a 100% failure penalty."
    
    # 3. Route again on the biased graph
    path_nodes_after, _, _ = route_risk_aware(biased_graph, 0, 2, vehicle, rain_level="rain", traffic_level="low")
    
    # The brain should detour around node 1 and take the safe node 3
    assert 1 not in path_nodes_after, "After training, router should avoid the historically failed Path A."
    assert 3 in path_nodes_after, "After training, router must detour to the safe Path B."
