"""
RoadFit-X: Risk-Aware Router (Refactored Phase 2)
---------------------------------------------------
True Multi-Label Constrained A* router with:
  1. Edge-state representation: state = (node, incoming_edge_key)
  2. Pareto dominance tracking: Maintains non-dominated paths over
     [travel_time, hazard, uncertainty, -min_clearance].
  3. Explicit missing data constraints via geometry margins.
  4. Returns a Pareto candidate set directly, bypassing the need for Yen's K-shortest.
"""
import math
import heapq
import networkx as nx
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.models.traversability_heuristic import predict_traversability
from src.vehicle.operational_constraints import get_physics_speed, get_car_density
from src.vehicle.geometry_constraints import compute_geometry_margins
from src.data.provenance_store import ProvenanceStore


@dataclass
class Label:
    travel_time_s: float
    integrated_hazard: float
    uncertainty_penalty: float
    min_clearance_m: float
    node: int
    edge_key: Any
    predecessor: Optional['Label'] = field(repr=False)
    f_score: float = 0.0  # travel_time + heuristic

    def dominates(self, other: 'Label') -> bool:
        """
        Returns True if self strictly dominates other across all objectives.
        We want to minimize time, hazard, and uncertainty, and maximize clearance.
        """
        # "No worse in all tracked resources"
        no_worse = (
            self.travel_time_s <= other.travel_time_s + 1e-5 and
            self.integrated_hazard <= other.integrated_hazard + 1e-5 and
            self.uncertainty_penalty <= other.uncertainty_penalty + 1e-5 and
            self.min_clearance_m >= other.min_clearance_m - 1e-5
        )
        if not no_worse:
            return False
            
        # "Strictly better on at least one"
        strictly_better = (
            self.travel_time_s < other.travel_time_s - 1e-5 or
            self.integrated_hazard < other.integrated_hazard - 1e-5 or
            self.uncertainty_penalty < other.uncertainty_penalty - 1e-5 or
            self.min_clearance_m > other.min_clearance_m + 1e-5
        )
        return strictly_better

    def __lt__(self, other):
        # Priority queue ordering by f_score (time lower bound)
        return self.f_score < other.f_score


# ────────────────────────────────────────────────────
#  Admissible & Consistent Haversine Heuristic
# ────────────────────────────────────────────────────
def haversine_admissible_heuristic(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    max_network_speed_mps: float = 33.33  # 120 km/h
) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance_m = R * c

    return distance_m / max_network_speed_mps


# ────────────────────────────────────────────────────
#  Physics-Based Travel Time
# ────────────────────────────────────────────────────
def _physics_travel_time(edge_data: dict, rain_level: str = 'none', traffic_level: str = 'normal') -> float:
    length_m = float(edge_data.get('length', 50.0))
    if 'travel_time' in edge_data and rain_level == 'none' and traffic_level == 'normal':
        try:
            return max(1.0, float(edge_data['travel_time']))
        except (TypeError, ValueError):
            pass

    speed_kmh = get_physics_speed(edge_data, rain_level, traffic_level)
    speed_ms = speed_kmh / 3.6
    return max(1.0, length_m / speed_ms)


# ────────────────────────────────────────────────────
#  Main Multi-Label A* Router
# ────────────────────────────────────────────────────
def route_risk_aware_multilabel(
    G: nx.MultiDiGraph,
    orig_node: int,
    dest_node: int,
    vehicle: VehicleDigitalTwin,
    provenance: ProvenanceStore = None,
    rain_level: str = 'none',
    traffic_level: str = 'normal',
    max_network_speed_mps: float = 33.33,
    max_candidates_to_find: int = 10
) -> List[Tuple[List[int], List[tuple], dict]]:
    """
    Multi-label constrained A* finding Pareto-optimal candidate paths.
    
    Returns a list of candidate routes, each as:
       (path_nodes, path_edges, stats_dict)
    """
    target_lat = G.nodes[dest_node]['y']
    target_lon = G.nodes[dest_node]['x']

    h0 = haversine_admissible_heuristic(
        G.nodes[orig_node]['y'], G.nodes[orig_node]['x'],
        target_lat, target_lon, max_network_speed_mps
    )

    # Initial label
    start_label = Label(
        travel_time_s=0.0,
        integrated_hazard=0.0,
        uncertainty_penalty=0.0,
        min_clearance_m=float('inf'),
        node=orig_node,
        edge_key=None,
        predecessor=None,
        f_score=h0
    )

    # Priority queue: (f_score, tiebreaker, label)
    pq: List[Tuple[float, int, Label]] = []
    heapq.heappush(pq, (h0, 0, start_label))
    counter = 1

    # Pareto frontiers per state: state is (node, incoming_edge_key)
    # The value is now a dictionary mapping buckets to the label with the minimum travel time.
    # Bucket tuple: (bucket_H, bucket_U, bucket_C)
    pareto_fronts: Dict[Tuple[int, Any], Dict[Tuple[int, int, int], Label]] = {}
    
    # Store complete valid paths
    completed_paths = []

    # Risk preference thresholds
    max_hazard = {
        "aggressive": 0.51,    # ~60% survival min
        "moderate": 0.22,      # ~80% survival min
        "conservative": 0.051  # ~95% survival min
    }.get(vehicle.risk_preference, 0.22)
    
    # Discretization parameters for epsilon-dominance bucketing
    delta_h = 0.02
    delta_u = 100.0
    delta_c = 0.2

    while pq and len(completed_paths) < max_candidates_to_find:
        _, _, current_label = heapq.heappop(pq)
        u = current_label.node

        # Check if we reached the destination
        if u == dest_node:
            completed_paths.append(current_label)
            continue

        # Expand neighbors
        for v in G.neighbors(u):
            edge_dict = G[u][v]
            
            for key, data in edge_dict.items():
                # 1. Hard physics constraints filter (Policy-aware)
                margins = compute_geometry_margins(data, vehicle)
                
                # If any margin is None, the explicit missing data policy rejected it
                if any(val is None for val in margins.values()):
                    continue
                
                # If any margin is strictly negative by >10cm, physically blocked
                if any(val < -0.10 for val in margins.values()):
                    continue
                
                clearance = margins.get('width_clearance_m', 10.0)
                
                # 2. Extract hazard and uncertainty
                p_e, u_e = predict_traversability(
                    data, vehicle, provenance, (u, v), rain_level, traffic_level
                )
                
                # Apply Cognitive Bias (Episodic Memory override)
                if '_history_penalty' in data and data['_history_penalty'] > 0.0:
                    penalty_factor = 1.0 - (data['_history_penalty'] * 0.99)
                    p_e *= penalty_factor
                    u_e += (data['_history_penalty'] * 1000.0)
                    
                if p_e < 0.01:
                    continue  # Untraversable
                
                length_m = max(float(data.get('length', 50.0)), 1.0)
                p_clamped = max(min(p_e, 0.99999), 1e-6)
                nll_hazard = -math.log(p_clamped)
                
                # 3. Create new label
                new_t = current_label.travel_time_s + _physics_travel_time(data, rain_level, traffic_level)
                new_h = current_label.integrated_hazard + nll_hazard
                new_u = current_label.uncertainty_penalty + (u_e * length_m)
                new_c = min(current_label.min_clearance_m, clearance)
                
                # Prune if exceeding risk preference thresholds
                if new_h > max_hazard:
                    continue
                
                h_val = haversine_admissible_heuristic(
                    G.nodes[v]['y'], G.nodes[v]['x'],
                    target_lat, target_lon, max_network_speed_mps
                )
                
                new_label = Label(
                    travel_time_s=new_t,
                    integrated_hazard=new_h,
                    uncertainty_penalty=new_u,
                    min_clearance_m=new_c,
                    node=v,
                    edge_key=key,
                    predecessor=current_label,
                    f_score=new_t + h_val
                )
                
                state = (v, key)
                front_buckets = pareto_fronts.setdefault(state, {})
                
                # 4. Epsilon-Dominance Bucketing
                b_h = math.floor(new_h / delta_h)
                b_u = math.floor(new_u / delta_u)
                b_c = math.floor(new_c / delta_c)
                bucket_key = (b_h, b_u, b_c)
                
                # Check if this new label is dominated by any existing bucket
                is_dominated = False
                for ex_b_key, ex_label in front_buckets.items():
                    # If an existing bucket is strictly better or equal in all dimensions,
                    # AND its travel time is better or equal, it dominates the new label.
                    if (ex_b_key[0] <= b_h and 
                        ex_b_key[1] <= b_u and 
                        ex_b_key[2] >= b_c and 
                        ex_label.travel_time_s <= new_label.travel_time_s):
                        is_dominated = True
                        break
                        
                if not is_dominated:
                    # The new label is valid. Let's see if it dominates any existing buckets.
                    buckets_to_remove = []
                    for ex_b_key, ex_label in front_buckets.items():
                        if (b_h <= ex_b_key[0] and 
                            b_u <= ex_b_key[1] and 
                            b_c >= ex_b_key[2] and 
                            new_label.travel_time_s <= ex_label.travel_time_s):
                            buckets_to_remove.append(ex_b_key)
                            
                    for b_rem in buckets_to_remove:
                        del front_buckets[b_rem]
                        
                    front_buckets[bucket_key] = new_label
                    heapq.heappush(pq, (new_label.f_score, counter, new_label))
                    counter += 1

    # Reconstruct all completed paths
    results = []
    for final_label in completed_paths:
        path_nodes = []
        path_edges = []
        
        curr = final_label
        while curr.predecessor is not None:
            prev = curr.predecessor
            edge_data = dict(G[prev.node][curr.node][curr.edge_key])
            path_edges.append((prev.node, curr.node, curr.edge_key, edge_data))
            path_nodes.append(curr.node)
            curr = prev
            
        path_nodes.append(orig_node)
        
        path_nodes.reverse()
        path_edges.reverse()
        
        stats = _compute_path_stats(G, path_edges, vehicle, provenance, rain_level, traffic_level)
        results.append((path_nodes, path_edges, stats))

    # Return candidates sorted by primary objective (travel time)
    results.sort(key=lambda x: x[2].get('travel_time_s', float('inf')))
    return results


# ────────────────────────────────────────────────────
#  Compatibility wrapper for single-route calls
# ────────────────────────────────────────────────────
def route_risk_aware(
    G: nx.MultiDiGraph,
    orig_node: int,
    dest_node: int,
    vehicle: VehicleDigitalTwin,
    provenance: ProvenanceStore = None,
    rain_level: str = 'none',
    traffic_level: str = 'normal'
) -> Tuple[Optional[List[int]], Optional[List[tuple]], dict]:
    candidates = route_risk_aware_multilabel(
        G, orig_node, dest_node, vehicle, provenance, rain_level, traffic_level,
        max_candidates_to_find=1
    )
    if candidates:
        return candidates[0]
    return None, None, {}


# ────────────────────────────────────────────────────
#  Path Statistics
# ────────────────────────────────────────────────────
def _compute_path_stats(G, path_edges, vehicle, provenance,
                        rain_level='none', traffic_level='normal'):
    total_time_s = 0.0
    total_dist_m = 0.0
    total_integrated_hazard = 0.0
    total_uncertainty = 0.0
    min_clearance = 999.0
    total_car_density_weighted = 0.0

    for u, v, key, data in path_edges:
        p_e, u_e = predict_traversability(
            data, vehicle, provenance, (u, v), rain_level, traffic_level
        )
        data['_traversability_prob'] = p_e

        length = float(data.get('length', 50.0))
        total_dist_m += length
        total_time_s += _physics_travel_time(data, rain_level, traffic_level)

        p_clamped = max(min(p_e, 0.99999), 1e-6)
        total_integrated_hazard += -math.log(p_clamped)
        total_uncertainty += u_e * length

        margins = compute_geometry_margins(data, vehicle)
        if margins.get('width_clearance_m') is not None:
            min_clearance = min(min_clearance, margins['width_clearance_m'])

        try:
            cars = get_car_density(data, traffic_level)
            total_car_density_weighted += cars * (length / 1000.0)
        except Exception:
            pass

    completion_probability = math.exp(-total_integrated_hazard)
    avg_cars_per_km = total_car_density_weighted / max(total_dist_m / 1000.0, 0.001)

    stats = {
        'distance_m': total_dist_m,
        'travel_time_s': total_time_s,
        'completion_probability': completion_probability,
        'uncertainty_penalty': total_uncertainty,
        'min_clearance_m': min_clearance if min_clearance < 900 else 5.0,
        'avg_speed_kmh': (total_dist_m / max(total_time_s, 1.0)) * 3.6,
        'avg_cars_per_km': avg_cars_per_km,
        'rain_level': rain_level,
        'traffic_level': traffic_level,
        'edge_count': len(path_edges),
    }
    return stats
