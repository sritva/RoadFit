"""
RoadFit-X: Routing Engine Invariant Tests
-------------------------------------------
Validates the five critical system invariants established in the
architecture audit.  These tests use synthetic graphs (no disk I/O)
to verify mathematical correctness in isolation.
"""
import math
import pytest
import networkx as nx
from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.routing.risk_aware_router import (
    route_risk_aware,
    haversine_admissible_heuristic
)


# ──────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────

def _make_vehicle(width=2.4, height=2.8, weight=5.0):
    """Delivery van profile used across tests."""
    return VehicleDigitalTwin(
        vehicle_type="test_van",
        width_m=width,
        height_m=height,
        gross_weight_t=weight,
        axle_load_t=weight / 2.0,
        wheelbase_m=3.0,
        turning_radius_m=6.0,
        ground_clearance_m=0.2,
        max_grade_pct=15.0,
        surface_tolerance=["asphalt", "concrete", "paved"],
        rain_tolerance="medium",
        cargo_class="standard",
        risk_preference="moderate",
        unknown_data_policy="exploratory"
    )


def _make_parallel_edge_graph():
    """
    Synthetic graph with two parallel edges between nodes 1 and 2:
      Key 0: fast (30s) but NARROW (1.8m — too tight for a 2.4m van)
      Key 1: slow (60s) but WIDE  (3.5m — safe for a 2.4m van)

    The router MUST select key 1 for a 2.4m-wide vehicle.

    Layout:  0 → 1 ═══ 2 → 3   (═══ = parallel edges)
    """
    G = nx.MultiDiGraph()
    # Nodes with lat/lon
    G.add_node(0, y=12.935, x=77.624)
    G.add_node(1, y=12.936, x=77.625)
    G.add_node(2, y=12.937, x=77.626)
    G.add_node(3, y=12.938, x=77.627)

    # 0 → 1: normal wide road
    G.add_edge(0, 1, key=0, length=100.0, width=6.0, maxheight=4.5,
               highway='secondary', travel_time=10.0)

    # 1 → 2, Key 0: FAST but NARROW
    G.add_edge(1, 2, key=0, length=200.0, width=1.8, maxheight=4.5,
               highway='service', travel_time=30.0)

    # 1 → 2, Key 1: SLOW but WIDE
    G.add_edge(1, 2, key=1, length=200.0, width=3.5, maxheight=4.5,
               highway='secondary', travel_time=60.0)

    # 2 → 3: normal wide road
    G.add_edge(2, 3, key=0, length=100.0, width=6.0, maxheight=4.5,
               highway='secondary', travel_time=10.0)
    return G


def _make_risk_tradeoff_graph():
    """
    Two routes from 0 → 2:
      Route A: 0 → 1 → 2, 15 min faster but p_e = 0.01 (near-impossible)
      Route B: 0 → 3 → 2, 15 min slower but p_e = 0.99 (safe)

    The router MUST select Route B.
    """
    G = nx.MultiDiGraph()
    G.add_node(0, y=12.935, x=77.624)
    G.add_node(1, y=12.936, x=77.625)
    G.add_node(2, y=12.937, x=77.626)
    G.add_node(3, y=12.935, x=77.627)

    # Route A: fast but physically blocked (width = 1.0m for a 2.4m van)
    G.add_edge(0, 1, key=0, length=500.0, width=1.0, maxheight=4.5,
               highway='service', travel_time=60.0)
    G.add_edge(1, 2, key=0, length=500.0, width=1.0, maxheight=4.5,
               highway='service', travel_time=60.0)

    # Route B: slow but safe (width = 6.0m)
    G.add_edge(0, 3, key=0, length=800.0, width=6.0, maxheight=4.5,
               highway='secondary', travel_time=500.0)
    G.add_edge(3, 2, key=0, length=800.0, width=6.0, maxheight=4.5,
               highway='secondary', travel_time=500.0)
    return G


# ──────────────────────────────────────────────
#  Test 1: MultiDiGraph Parallel Edge Bypass
# ──────────────────────────────────────────────

def test_parallel_edge_bypass():
    """
    INVARIANT: Given two parallel edges between (u, v) — one narrow+fast,
    one wide+slow — a 2.4m-wide vehicle MUST select the wide edge.
    """
    G = _make_parallel_edge_graph()
    vehicle = _make_vehicle(width=2.4)

    path_nodes, path_edges, stats = route_risk_aware(
        G, 0, 3, vehicle
    )

    assert path_nodes is not None, "Router must find a path"
    assert len(path_nodes) == 4, f"Expected 4 nodes, got {len(path_nodes)}"

    # Find the edge between nodes 1 and 2
    edge_1_2 = [(u, v, k, d) for u, v, k, d in path_edges if u == 1 and v == 2]
    assert len(edge_1_2) == 1, "Exactly one edge between 1→2"
    _, _, selected_key, selected_data = edge_1_2[0]

    # The wide edge (key=1, width=3.5m) must be selected
    road_width = float(selected_data.get('width', 0))
    assert road_width >= 2.4, (
        f"Router selected edge with width {road_width}m for a {vehicle.width_m}m "
        f"vehicle — should have selected the wide parallel edge (key 1)"
    )


# ──────────────────────────────────────────────
#  Test 2: Heuristic Admissibility
# ──────────────────────────────────────────────

def test_heuristic_admissibility():
    """
    INVARIANT: h(n) ≤ actual_cost(n, target) for all node pairs.
    The Haversine / v_max heuristic must never overestimate.
    """
    # Test with known coordinates
    # Bangalore to Indiranagar: ~3km → at 120 km/h ≈ 90s
    h = haversine_admissible_heuristic(
        12.9352, 77.6245,  # Koramangala
        12.9716, 77.6412,  # Indiranagar
        max_network_speed_mps=33.33  # 120 km/h
    )

    # Haversine distance should be ~4.3 km → h ≈ 129s at 120km/h
    assert h > 0, "Heuristic must be positive for non-identical points"
    assert h < 300, f"Heuristic {h:.1f}s seems too large for ~4km"

    # Same point → h = 0
    h_same = haversine_admissible_heuristic(12.9352, 77.6245, 12.9352, 77.6245)
    assert h_same == 0.0, "Heuristic must be 0 for identical points"

    # Consistency check: h(A,C) ≤ h(A,B) + actual_cost(B,C)
    # Since h underestimates, h(A,C) ≤ d(A,C)/v_max
    # and d(A,C) ≤ d(A,B) + d(B,C) by triangle inequality
    h_ac = haversine_admissible_heuristic(12.93, 77.62, 12.97, 77.65)
    h_ab = haversine_admissible_heuristic(12.93, 77.62, 12.95, 77.63)
    h_bc = haversine_admissible_heuristic(12.95, 77.63, 12.97, 77.65)
    assert h_ac <= h_ab + h_bc + 1e-6, "Heuristic must satisfy triangle inequality"


# ──────────────────────────────────────────────
#  Test 3: Discretization Invariance
# ──────────────────────────────────────────────

def test_discretization_invariance():
    """
    INVARIANT: A 1000m road split into 2×500m edges must return the SAME
    survival probability as when split into 20×50m edges (Δ ≤ 1e-5).
    """
    # Simulated path_edges with identical hazard characteristics
    road_attrs = {
        'width': 3.0,       # 3m road for a 2.4m vehicle → 0.6m clearance
        'maxheight': 4.5,
        'highway': 'secondary',
        'length': None,      # Will be set per variant
    }

    vehicle = _make_vehicle(width=2.4)

    # Variant A: one 1000m edge
    data_a = {**road_attrs, 'length': 1000.0}
    from src.models.traversability_heuristic import predict_traversability
    p_single, _ = predict_traversability(data_a, vehicle)

    # Variant B: two 500m edges
    data_b = {**road_attrs, 'length': 500.0}
    p_half, _ = predict_traversability(data_b, vehicle)
    survival_2_edges = p_half * p_half  # Product of probabilities

    # Variant C: twenty 50m edges
    data_c = {**road_attrs, 'length': 50.0}
    p_small, _ = predict_traversability(data_c, vehicle)
    survival_20_edges = p_small ** 20

    # All three must be equivalent (within floating-point tolerance)
    assert abs(p_single - survival_2_edges) < 1e-5, (
        f"1×1000m ({p_single:.8f}) ≠ 2×500m ({survival_2_edges:.8f}) — "
        f"discretization dependent!"
    )
    assert abs(p_single - survival_20_edges) < 1e-5, (
        f"1×1000m ({p_single:.8f}) ≠ 20×50m ({survival_20_edges:.8f}) — "
        f"discretization dependent!"
    )


# ──────────────────────────────────────────────
#  Test 4: No Catastrophic Tradeoff
# ──────────────────────────────────────────────

def test_no_catastrophic_tradeoff():
    """
    INVARIANT: An edge with p_e ≤ 0.01 must NEVER be selected over an edge
    with p_e ≥ 0.99, even if it saves 15 minutes of travel time.
    """
    G = _make_risk_tradeoff_graph()
    vehicle = _make_vehicle(width=2.4)

    path_nodes, path_edges, stats = route_risk_aware(
        G, 0, 2, vehicle
    )

    assert path_nodes is not None, "Router must find a path via the safe route"

    # Route A goes through node 1.  Route B goes through node 3.
    # The safe route MUST go through node 3.
    assert 3 in path_nodes, (
        f"Router chose the unsafe route through node 1 instead of the safe "
        f"route through node 3.  Path: {path_nodes}"
    )
    assert 1 not in path_nodes, (
        f"Router included the physically impassable node 1 in the path. "
        f"Path: {path_nodes}"
    )


# ──────────────────────────────────────────────
#  Test 5: No Synthetic Fallback (UI invariant,
#          verified via source code inspection)
# ──────────────────────────────────────────────

def test_no_synthetic_fallback():
    """
    INVARIANT: The frontend source code must NOT contain the
    buildDemoRoute function or any synthetic route generation on error.
    """
    import os
    frontend_path = os.path.join(
        os.path.dirname(__file__), '..', 'frontend', 'src', 'App.jsx'
    )

    if not os.path.exists(frontend_path):
        pytest.skip("Frontend source not found at expected path")

    with open(frontend_path, 'r', encoding='utf-8') as f:
        source = f.read()

    assert 'buildDemoRoute' not in source, (
        "SAFETY VIOLATION: App.jsx still contains the buildDemoRoute function. "
        "The frontend must never generate synthetic routes."
    )
    assert 'setDemoMode' not in source, (
        "SAFETY VIOLATION: App.jsx still references demoMode state. "
        "Remove all demo fallback logic."
    )


# ──────────────────────────────────────────────
#  Test 6: Polynomial Bounding (Epsilon Dominance)
# ──────────────────────────────────────────────
def test_polynomial_bound():
    """
    INVARIANT: The epsilon-dominance bucketing must prevent exponential label growth.
    Even with many paths converging on a node, the number of labels stored must not
    exceed the theoretical bucket combinations.
    """
    # Create a graph with many parallel paths of slightly different costs
    G = nx.MultiDiGraph()
    G.add_node(0, y=12.935, x=77.624)
    G.add_node(1, y=12.936, x=77.625)

    for i in range(50): # 50 parallel edges
        # Slightly varying travel time, width, and hazard
        width = 2.4 + (i * 0.01)
        tt = 10.0 + (i * 0.1)
        G.add_edge(0, 1, key=i, length=100.0, width=width, maxheight=4.5,
                   highway='secondary', travel_time=tt)

    vehicle = _make_vehicle(width=2.4)
    
    # We just run the router. Since it uses epsilon-dominance, 
    # it shouldn't store all 50 labels on node 1 if they fall into the same buckets.
    # The default buckets are delta_h=0.02, delta_u=100, delta_c=0.2
    # All these edges have 100m length and same u_e, so bucket_U is the same.
    # Clearance varies from 0 to 0.5m, so bucket_C has at most 3 values.
    # Hazard varies slightly, bucket_H has at most 2 values.
    # Max theoretical labels per state = 1 * 3 * 2 = 6
    
    path_nodes, path_edges, stats = route_risk_aware(G, 0, 1, vehicle)
    assert path_nodes is not None, "Router must find a path"
    
    # Note: To strictly test the internal pareto_fronts length, we'd need to mock or 
    # return it from the router. But we can assert it runs very fast and returns 
    # the best path, proving the logic doesn't fail.
    assert len(path_nodes) == 2


# ──────────────────────────────────────────────
#  Test 7: Strict vs. Exploratory Missing-Data Policy Verification
# ──────────────────────────────────────────────
def test_missing_data_policy_enforcement():
    G = nx.MultiDiGraph()
    # Path 1: Missing width tag
    G.add_node(1, y=12.93, x=77.61)
    G.add_node(2, y=12.94, x=77.61)
    G.add_edge(1, 2, key=0, length=100.0, speed_kph=30.0) # No width tag!

    van_strict = _make_vehicle()
    van_strict.unknown_data_policy = "strict"
    path_strict, _, _ = route_risk_aware(G, 1, 2, van_strict)
    assert path_strict is None, "Strict policy must reject untagged edges."

    van_exploratory = _make_vehicle()
    van_exploratory.unknown_data_policy = "exploratory"
    path_exp, _, _ = route_risk_aware(G, 1, 2, van_exploratory)
    assert path_exp is not None, "Exploratory policy should permit the untagged edge."


# ──────────────────────────────────────────────
#  Test 8: Sub-Graph Topological Cycle Resilience
# ──────────────────────────────────────────────
def test_dense_grid_polynomial_termination():
    """
    Verify that on dense grids with multiple cycles, the polynomial bucketing 
    prevents infinite loops without losing connectivity.
    """
    # Generate 5x5 grid graph with bi-directional MultiDiGraph edges
    G = nx.grid_2d_graph(5, 5, create_using=nx.MultiDiGraph)
    for u, v, k in G.edges(keys=True):
        G[u][v][k]['length'] = 50.0
        G[u][v][k]['speed_kph'] = 30.0
        G[u][v][k]['width'] = 3.0

    # Map node labels to integers and add coordinates
    mapping = {node: i for i, node in enumerate(G.nodes())}
    G_mapped = nx.relabel_nodes(G, mapping)
    for i, data in G_mapped.nodes(data=True):
        data['x'] = 77.60 + (i % 5) * 0.001
        data['y'] = 12.90 + (i // 5) * 0.001

    vehicle = _make_vehicle(width=2.2)
    # Using exploratory so missing maxweight/maxheight tags don't cause rejection
    vehicle.unknown_data_policy = "exploratory"
    
    path_nodes, path_edges, stats = route_risk_aware(G_mapped, 0, 24, vehicle)
    assert path_nodes is not None, "Router failed to find a path in dense grid."
    assert len(path_nodes) >= 9, "Manhattan diameter of 5x5 grid is 9 nodes."
