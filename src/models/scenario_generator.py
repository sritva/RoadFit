"""
RoadFit-X: Scenario Generator (Refactored)
--------------------------------------------
Generates multiple plausible future road states for Monte Carlo CVaR.

FIXES applied:
  - Travel time perturbation uses lognormal distribution (heavy-tailed,
    realistic for congestion bursts) instead of uniform noise.
  - Adds edge-level traversability perturbation via Beta noise to simulate
    uncertain road conditions (partial closures, waterlogging, etc.).
"""
import copy
from typing import List, Dict, Any
import networkx as nx
import numpy as np


def generate_scenarios(
    base_graph: nx.MultiDiGraph,
    num_scenarios: int = 5,
    travel_time_sigma: float = 0.25,
    traversability_noise_alpha: float = 20.0,
) -> List[nx.MultiDiGraph]:
    """
    Generates Monte Carlo future scenarios for CVaR optimization.

    Each scenario applies:
      1. Lognormal travel-time perturbation to model heavy-tailed congestion.
      2. Beta-distributed traversability noise to model uncertain road passability.

    Parameters:
      travel_time_sigma:  σ of lognormal (0.25 ≈ ±30% typical, occasional 2-3×)
      traversability_noise_alpha:  concentration of Beta noise; higher = less noise.
    """
    scenarios = []

    for _ in range(num_scenarios):
        scenario_graph = base_graph.copy()

        for u, v, k, data in scenario_graph.edges(data=True, keys=True):
            # 1. Lognormal travel-time perturbation
            base_time = float(data.get('travel_time', 10.0))
            congestion_multiplier = np.random.lognormal(
                mean=0.0, sigma=travel_time_sigma
            )
            data['travel_time'] = base_time * congestion_multiplier

            # 2. Beta-distributed traversability noise
            # If the edge has a stored traversability_prob, perturb it
            base_prob = float(data.get('_traversability_prob', 0.95))
            base_prob = max(min(base_prob, 0.999), 0.001)
            # Beta(α·p, α·(1-p)) has mean p and decreasing variance with α
            alpha_param = traversability_noise_alpha * base_prob
            beta_param = traversability_noise_alpha * (1.0 - base_prob)
            perturbed_prob = np.random.beta(
                max(alpha_param, 0.01), max(beta_param, 0.01)
            )
            data['_traversability_prob'] = float(perturbed_prob)

        scenarios.append(scenario_graph)

    return scenarios
