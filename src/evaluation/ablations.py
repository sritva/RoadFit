"""
RoadFit-X Evaluation: Ablations and Benchmarks
----------------------------------------------
Runs the validation protocol baselines (B0 to B3 and RoadFit-X) 
and computes academic metrics (ISER, CNME, MDEF, TRR, ETTP).
"""
import networkx as nx
import math
import random
import csv
import time
import sys
import argparse
import osmnx as ox

from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.evaluation.baseline_routes import (
    route_shortest_eta,
    route_hard_constrained_astar
)
from src.routing.pareto_candidates import get_k_shortest_paths
from src.routing.risk_aware_router import route_risk_aware, _compute_path_stats
from src.evaluation.metrics_engine import MetricsEngine
from src.brain.cognitive_core import CognitiveCore

def extract_path_edges(G, path_nodes):
    path_edges = []
    if not path_nodes: return []
    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
        # Taking the first key just for baselines that don't track keys
        edge_dict = G[u][v]
        key = list(edge_dict.keys())[0]
        data = edge_dict[key]
        path_edges.append((u, v, key, data))
    return path_edges

def get_path_travel_time(path_edges) -> float:
    """Calculates true physical traversal duration in seconds."""
    total_seconds = 0.0
    if not path_edges: return 0.0
    for _, _, _, data in path_edges:
        length_m = float(data.get('length', 10.0))
        speed_raw = data.get('speed_kph', data.get('maxspeed', 25.0))
        if isinstance(speed_raw, list):
            speed_raw = speed_raw[0]
        try:
            speed_kph = float(speed_raw)
        except (ValueError, TypeError):
            speed_kph = 25.0
            
        speed_mps = max(speed_kph * (1000.0 / 3600.0), 1.0)
        total_seconds += (length_m / speed_mps)
    return total_seconds

def run_all_ablations(G: nx.MultiDiGraph, vehicle: VehicleDigitalTwin, orig_node: int, dest_node: int):
    print("Running Academic Ablations & Metrics Engine...\n")
    
    engine = MetricsEngine(vehicle)
    results = {}
    
    # ---------------------------------------------------------
    # Baseline B0: Unconstrained Dijkstra (ETA only)
    # ---------------------------------------------------------
    path_b0 = route_shortest_eta(G, orig_node, dest_node)
    edges_b0 = extract_path_edges(G, path_b0)
    t_b0 = get_path_travel_time(edges_b0)
    
    if t_b0 <= 0:
        print("B0 found no feasible route! Cannot compute relative metrics.")
        return {}
        
    res_b0 = engine.evaluate_route(G, path_b0, edges_b0, t_b0, t_b0)
    results["B0 (Unconstrained)"] = res_b0
    
    # ---------------------------------------------------------
    # Baseline B1: Hard Constrained A*
    # ---------------------------------------------------------
    path_b1 = route_hard_constrained_astar(G, orig_node, dest_node, vehicle)
    edges_b1 = extract_path_edges(G, path_b1)
    t_b1 = get_path_travel_time(edges_b1)
    
    res_b1 = engine.evaluate_route(G, path_b1, edges_b1, t_b1, t_b0)
    results["B1 (Hard Constrained)"] = res_b1
    
    # ---------------------------------------------------------
    # RoadFit-X: Multi-Label Constrained A* (Phase 3)
    # ---------------------------------------------------------
    vehicle.unknown_data_policy = "strict"
    path_rf_strict, edges_rf_strict, _ = route_risk_aware(G, orig_node, dest_node, vehicle)
    t_rf_strict = get_path_travel_time(edges_rf_strict)
    if edges_rf_strict:
        res_rfs = engine.evaluate_route(G, path_rf_strict, edges_rf_strict, t_rf_strict, t_b0)
        results["RoadFit-X (Strict)"] = res_rfs
    else:
        # If strict policy completely fails
        results["RoadFit-X (Strict)"] = {'ISER_%': 0.0, 'CNME_%': 0.0, 'MDEF_%': 0.0, 'TRR': 0.0, 'ETTP_%': 0.0}

    vehicle.unknown_data_policy = "conservative"
    path_rf_cons, edges_rf_cons, _ = route_risk_aware(G, orig_node, dest_node, vehicle)
    t_rf_cons = get_path_travel_time(edges_rf_cons)
    if edges_rf_cons:
        res_rfc = engine.evaluate_route(G, path_rf_cons, edges_rf_cons, t_rf_cons, t_b0)
        results["RoadFit-X (Conservative)"] = res_rfc
        
    vehicle.unknown_data_policy = "exploratory"
    path_rf_exp, edges_rf_exp, _ = route_risk_aware(G, orig_node, dest_node, vehicle)
    t_rf_exp = get_path_travel_time(edges_rf_exp)
    if edges_rf_exp:
        res_rfe = engine.evaluate_route(G, path_rf_exp, edges_rf_exp, t_rf_exp, t_b0)
        results["RoadFit-X (Exploratory)"] = res_rfe
        
    # ---------------------------------------------------------
    # RoadFit-X: Cognitive Brain (Episodic Memory + Exploratory)
    # ---------------------------------------------------------
    # Assuming brain is already trained, we inject its bias for a 'rain' and 'peak' context
    brain = CognitiveCore()
    biased_graph = brain.apply_cognitive_bias(G, weather="rain", traffic="peak", vehicle_type=vehicle.vehicle_type)
    
    path_rf_brain, edges_rf_brain, _ = route_risk_aware(biased_graph, orig_node, dest_node, vehicle)
    t_rf_brain = get_path_travel_time(edges_rf_brain)
    if edges_rf_brain:
        res_rfb = engine.evaluate_route(biased_graph, path_rf_brain, edges_rf_brain, t_rf_brain, t_b0)
        results["RoadFit-X (Cognitive Brain)"] = res_rfb
    
    # Print Results Matrix
    print(f"{'Router':<25} | {'ISER %':<8} | {'CNME %':<8} | {'MDEF %':<8} | {'TRR':<6} | {'ETTP %':<8}")
    print("-" * 75)
    for name, r in results.items():
        if r.get('ETTP_%', 0) == 0 and name != "B0 (Unconstrained)" and not r.get('TRR'):
            print(f"{name:<25} | {'NO PATH':<8} | {'-':<8} | {'-':<8} | {'-':<6} | {'-':<8}")
        else:
            ettp = f"+{r.get('ETTP_%'):.2f}" if r.get('ETTP_%', 0) > 0 else f"{r.get('ETTP_%', 0):.2f}"
            print(f"{name:<25} | {r.get('ISER_%', 0):<8.2f} | {r.get('CNME_%', 0):<8.2f} | {r.get('MDEF_%', 0):<8.2f} | {r.get('TRR', 0):<6.2f} | {ettp:<8}")
    
    # We will just return the results dict to the caller
    return results

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000.0  # return meters

def categorize_nodes(G):
    arterial_nodes = set()
    residential_nodes = set()
    arterial_tags = {'primary', 'secondary', 'tertiary', 'trunk', 'primary_link', 'secondary_link', 'tertiary_link', 'trunk_link'}
    residential_tags = {'residential', 'living_street', 'unclassified'}
    
    for u, v, data in G.edges(data=True):
        hw = data.get('highway')
        if isinstance(hw, list):
            hw = hw[0]
        if hw in arterial_tags:
            arterial_nodes.add(u)
            arterial_nodes.add(v)
        elif hw in residential_tags:
            residential_nodes.add(u)
            residential_nodes.add(v)
            
    # Pure residential nodes shouldn't also be arterial junctions
    pure_residential = residential_nodes - arterial_nodes
    return list(arterial_nodes), list(pure_residential)

def sample_stratified_od_pairs(G, n_art_res=40, n_res_res=40, n_art_art=20):
    arterial_nodes, pure_res_nodes = categorize_nodes(G)
    sampled_pairs = []
    
    def get_coords(n):
        return G.nodes[n].get('y', 0), G.nodes[n].get('x', 0)
    
    print("Sampling Arterial -> Residential...")
    while len(sampled_pairs) < n_art_res:
        u = random.choice(arterial_nodes)
        v = random.choice(pure_res_nodes)
        if nx.has_path(G, u, v):
            sampled_pairs.append((u, v, "Arterial->Residential"))
            
    print("Sampling Residential -> Residential (>= 1.5km)...")
    res_pairs = 0
    while res_pairs < n_res_res:
        u = random.choice(pure_res_nodes)
        v = random.choice(pure_res_nodes)
        if u != v:
            lat1, lon1 = get_coords(u)
            lat2, lon2 = get_coords(v)
            if haversine(lat1, lon1, lat2, lon2) >= 1500.0:
                if nx.has_path(G, u, v):
                    sampled_pairs.append((u, v, "Residential->Residential"))
                    res_pairs += 1

    print("Sampling Arterial -> Arterial...")
    art_pairs = 0
    while art_pairs < n_art_art:
        u = random.choice(arterial_nodes)
        v = random.choice(arterial_nodes)
        if u != v and nx.has_path(G, u, v):
            sampled_pairs.append((u, v, "Arterial->Arterial"))
            art_pairs += 1
            
    random.shuffle(sampled_pairs)
    return sampled_pairs

def run_experiment(G, vehicle, num_pairs, output_csv):
    # Determine split based on requested num_pairs
    n_art_res = int(0.4 * num_pairs)
    n_res_res = int(0.4 * num_pairs)
    n_art_art = num_pairs - n_art_res - n_res_res
    
    pairs = sample_stratified_od_pairs(G, n_art_res, n_res_res, n_art_art)
    
    records = []
    models = ["B0 (Unconstrained)", "B1 (Hard Constrained)", "RoadFit-X (Strict)", "RoadFit-X (Conservative)", "RoadFit-X (Exploratory)", "RoadFit-X (Cognitive Brain)"]
    
    print(f"Executing {num_pairs} pairs and saving to {output_csv}...\n")
    
    for i, (orig, dest, category) in enumerate(pairs, 1):
        print(f"Evaluating Pair {i}/{num_pairs} ({category}): {orig} -> {dest}")
        results = run_all_ablations(G, vehicle, orig, dest)
        
        for model in models:
            metrics = results.get(model, {})
            # If router completely failed or NO PATH
            if not metrics or metrics.get('ETTP_%') == 0 and not metrics.get('TRR') and model != "B0 (Unconstrained)":
                feasibility = 0
                iser, cnme, mdef, trr, ettp, min_c = None, None, None, None, None, None
            else:
                feasibility = 1
                iser = metrics.get('ISER_%', 0)
                cnme = metrics.get('CNME_%', 0)
                mdef = metrics.get('MDEF_%', 0)
                trr = metrics.get('TRR', 0)
                ettp = metrics.get('ETTP_%', 0)
                min_c = metrics.get('MinClearance_m', 0)
                
            records.append({
                'PairID': i,
                'Category': category,
                'Model': model,
                'Feasible': feasibility,
                'ISER_%': iser,
                'CNME_%': cnme,
                'MDEF_%': mdef,
                'TRR': trr,
                'ETTP_%': ettp,
                'MinClearance_m': min_c
            })
            
    # Write to CSV
    fields = ['PairID', 'Category', 'Model', 'Feasible', 'ISER_%', 'CNME_%', 'MDEF_%', 'TRR', 'ETTP_%', 'MinClearance_m']
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
        
    print(f"\nExperiment complete. Data saved to {output_csv}")
    
    # Calculate Aggregate FSR and Conditional ETTP/TRR
    print("\n" + "="*80)
    print("FINAL AGGREGATE RESULTS")
    print("="*80)
    
    print(f"{'Model':<25} | {'FSR %':<8} | {'Avg TRR':<10} | {'Avg ETTP %':<10} | {'Valid N'}")
    print("-" * 75)
    for model in models:
        model_records = [r for r in records if r['Model'] == model]
        feasible_records = [r for r in model_records if r['Feasible'] == 1]
        
        fsr = (len(feasible_records) / len(model_records)) * 100.0 if model_records else 0.0
        
        if feasible_records:
            avg_trr = sum(r['TRR'] for r in feasible_records) / len(feasible_records)
            avg_ettp = sum(r['ETTP_%'] for r in feasible_records) / len(feasible_records)
        else:
            avg_trr, avg_ettp = 0.0, 0.0
            
        print(f"{model:<25} | {fsr:<8.1f} | {avg_trr:<10.2f} | +{avg_ettp:<9.2f} | N={len(feasible_records)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RoadFit-X: Run Validation Protocol Baselines")
    parser.add_argument("--graph", type=str, required=True, help="Path to GraphML file")
    parser.add_argument("--orig-node", type=int, required=False, help="Origin OSM Node ID")
    parser.add_argument("--dest-node", type=int, required=False, help="Destination OSM Node ID")
    parser.add_argument("--num-pairs", type=int, default=100, help="Number of random OD pairs to sample")
    parser.add_argument("--output", type=str, default="results_100_od.csv", help="CSV output path")
    args = parser.parse_args()

    print(f"Loading GraphML from {args.graph}...")
    try:
        G = ox.load_graphml(args.graph)
    except Exception as e:
        print(f"Error loading graph: {e}", file=sys.stderr)
        sys.exit(1)

    # Instantiate Delivery Van
    vehicle = VehicleDigitalTwin(
        vehicle_type="delivery_van",
        width_m=2.4,
        height_m=2.6,
        gross_weight_t=3.5,
        axle_load_t=1.75,
        wheelbase_m=3.0,
        turning_radius_m=6.0,
        ground_clearance_m=0.2,
        max_grade_pct=15.0,
        surface_tolerance=["asphalt", "concrete", "paved"],
        rain_tolerance="medium",
        cargo_class="standard",
        risk_preference="moderate",
        unknown_data_policy="conservative"
    )

    if args.orig_node and args.dest_node:
        run_all_ablations(G, vehicle, args.orig_node, args.dest_node)
    else:
        run_experiment(G, vehicle, args.num_pairs, args.output)
