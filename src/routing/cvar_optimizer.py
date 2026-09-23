"""
RoadFit-X: CVaR Optimizer (Refactored)
---------------------------------------
Catastrophic-Risk CVaR: Monte Carlo evaluation over combined travel delay
AND physical edge-failure events (Bernoulli sampling per edge).

FIXES applied:
  - CVaR is computed over *generalized loss* that includes vehicle entrapment,
    not just travel-time variance during traffic jams.
  - Removed incommensurable objective (old: base_eta + cvar*1.5 + (1-p)*10000).
  - Each Monte Carlo scenario samples edge passability from Bernoulli(p_e) and
    applies a catastrophic penalty if any edge fails.
"""
import math
from typing import List, Tuple, Dict, Any, Optional
import networkx as nx
import numpy as np

from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.routing.risk_aware_router import (
    _compute_path_stats,
    _physics_travel_time,
)
from src.routing.pareto_candidates import get_k_shortest_paths
from src.models.traversability_heuristic import predict_traversability
from src.data.provenance_store import ProvenanceStore


def compute_catastrophic_cvar(
    path_edges: List[Tuple[int, int, Any, Dict[str, Any]]],
    vehicle: VehicleDigitalTwin,
    provenance: ProvenanceStore = None,
    rain_level: str = 'none',
    traffic_level: str = 'normal',
    num_scenarios: int = 100,
    tau: float = 0.90,
    c_catastrophic_seconds: float = 14400.0,  # 4-hour entrapment penalty
) -> Dict[str, float]:
    """
    Evaluates CVaR over combined travel delay AND catastrophic physical failures.

    For each Monte Carlo scenario:
      1. Sample a lognormal traffic multiplier for dynamic speed variation.
      2. Sample physical passability per edge from Bernoulli(p_e).
      3. If any edge fails, loss = elapsed_time + catastrophic_penalty.
      4. If all edges pass, loss = simulated_travel_time.

    Returns dict with expected_loss_sec, var_90_sec, cvar_90_sec,
    sample_failure_rate.
    """
    edge_probs = []
    base_times = []

    for u, v, key, data in path_edges:
        p_e, _ = predict_traversability(
            data, vehicle, provenance, (u, v), rain_level, traffic_level
        )
        t_e = _physics_travel_time(data, rain_level, traffic_level)
        base_times.append(t_e)
        edge_probs.append(p_e)

    base_times = np.array(base_times)
    edge_probs = np.array(edge_probs)

    scenario_losses = np.zeros(num_scenarios)

    for s in range(num_scenarios):
        # 1. Sample dynamic traffic multiplier (lognormal — heavy-tailed)
        traffic_multiplier = np.random.lognormal(mean=0.0, sigma=0.25)
        simulated_times = base_times * traffic_multiplier

        # 2. Sample physical passability per edge
        sampled_passes = np.random.binomial(n=1, p=np.clip(edge_probs, 0, 1))
        passed_all = np.all(sampled_passes == 1)

        if passed_all:
            scenario_losses[s] = np.sum(simulated_times)
        else:
            # Vehicle is trapped: loss = time elapsed before failure + penalty
            failed_at_idx = np.where(sampled_passes == 0)[0][0]
            elapsed_before_failure = np.sum(simulated_times[:failed_at_idx])
            scenario_losses[s] = elapsed_before_failure + c_catastrophic_seconds

    # Sort and extract tail losses
    scenario_losses.sort()
    cutoff_idx = int(math.floor(tau * num_scenarios))
    var_tau = float(scenario_losses[cutoff_idx])
    cvar_tau = float(np.mean(scenario_losses[cutoff_idx:]))

    return {
        'expected_loss_sec': float(np.mean(scenario_losses)),
        'var_90_sec': var_tau,
        'cvar_90_sec': cvar_tau,
        'sample_failure_rate': float(
            np.mean(scenario_losses >= c_catastrophic_seconds)
        ),
    }


def optimize_cvar_route(
    base_graph: nx.MultiDiGraph,
    scenarios: List[nx.MultiDiGraph],
    orig_node: int,
    dest_node: int,
    vehicle: VehicleDigitalTwin,
    provenance: ProvenanceStore = None,
    rain_level: str = 'none',
    traffic_level: str = 'normal',
    tau: float = 0.90,
    k: int = 4,
    c_catastrophic_seconds: float = 14400.0,
) -> Tuple[Optional[List[int]], Optional[List[tuple]], dict]:
    """
    1. Find K shortest physically feasible routes on the base graph.
    2. Evaluate each candidate's catastrophic CVaR across Monte Carlo futures.
    3. Select the route with the lowest CVaR score.

    Returns (path_nodes, path_edges, stats) — same contract as route_risk_aware.
    """
    k_paths = get_k_shortest_paths(
        base_graph, orig_node, dest_node, vehicle, provenance, k,
        rain_level, traffic_level,
    )

    if not k_paths:
        return None, None, {}

    best_route_nodes = None
    best_route_edges = None
    best_cvar_score = float('inf')
    best_stats = {}

    for path in k_paths:
        # Reconstruct path_edges with exact edge data from the base graph
        path_edges = []
        for u, v in zip(path[:-1], path[1:]):
            edge_dict = base_graph[u][v]
            # Pick the best edge key (lowest cost)
            best_key = None
            best_cost = float('inf')
            for key, data in edge_dict.items():
                p_e, u_e = predict_traversability(
                    data, vehicle, provenance, (u, v),
                    rain_level, traffic_level,
                )
                t_e = _physics_travel_time(data, rain_level, traffic_level)
                
                # We want to pick the edge that has the lowest combination of travel time and hazard
                # This approximates the old calibrated edge cost.
                p_clamped = max(min(p_e, 0.99999), 1e-6)
                cost = t_e + (-math.log(p_clamped)) * 1000.0  # Scale hazard appropriately
                
                if cost < best_cost:
                    best_cost = cost
                    best_key = key
            if best_key is not None:
                edata = dict(base_graph[u][v][best_key])
                path_edges.append((u, v, best_key, edata))
            else:
                # Edge not traversable — skip this candidate
                path_edges = None
                break

        if path_edges is None:
            continue

        # Compute base stats
        base_stats = _compute_path_stats(
            base_graph, path_edges, vehicle, provenance, rain_level, traffic_level
        )

        if base_stats.get('completion_probability', 1.0) < 0.01:
            continue

        # Compute catastrophic CVaR
        cvar_result = compute_catastrophic_cvar(
            path_edges, vehicle, provenance,
            rain_level, traffic_level,
            num_scenarios=max(len(scenarios) * 20, 100),
            tau=tau,
            c_catastrophic_seconds=c_catastrophic_seconds,
        )

        # Single objective: CVaR score (lower is better)
        cvar_score = cvar_result['cvar_90_sec']

        if cvar_score < best_cvar_score:
            best_cvar_score = cvar_score
            best_route_nodes = path
            best_route_edges = path_edges
            best_stats = base_stats
            best_stats['cvar_risk'] = cvar_result['cvar_90_sec']
            best_stats['expected_loss_sec'] = cvar_result['expected_loss_sec']
            best_stats['sample_failure_rate'] = cvar_result['sample_failure_rate']

    return best_route_nodes, best_route_edges, best_stats
