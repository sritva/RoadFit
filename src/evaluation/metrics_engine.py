"""
RoadFit-X: Evaluation Metrics Engine
------------------------------------
Computes standard academic spatial and statistical metrics across route baselines.
Metrics calculated:
  - ISER: Infeasible Segment Encroachment Rate
  - CNME: Critical Narrow Margin Exposure
  - MDEF: Missing-Data Exposure Fraction
  - TRR: Tail-Risk Ratio (CVaR-90 / Median ETA)
  - ETTP: Excess Travel Time Penalty
"""
from typing import List, Dict, Any, Tuple
import numpy as np
from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.vehicle.geometry_constraints import _parse_osm_float
from src.routing.cvar_optimizer import compute_catastrophic_cvar

class MetricsEngine:
    def __init__(self, vehicle: VehicleDigitalTwin):
        self.vehicle = vehicle

    def compute_iser(self, path_edges: List[tuple]) -> float:
        """Infeasible Segment Encroachment Rate (Percentage)"""
        if not path_edges: return 0.0
        total_length = 0.0
        violation_length = 0.0
        
        for _, _, _, data in path_edges:
            length = float(data.get('length', 50.0))
            total_length += length
            
            w_e_raw = data.get('width')
            if w_e_raw is not None:
                w_e = _parse_osm_float(w_e_raw, 6.5)
                if w_e < self.vehicle.width_m:
                    violation_length += length
                    
        return (violation_length / total_length) * 100.0 if total_length > 0 else 0.0

    def compute_cnme(self, path_edges: List[tuple]) -> float:
        """Critical Narrow Margin Exposure (Percentage)"""
        if not path_edges: return 0.0
        total_length = 0.0
        narrow_length = 0.0
        
        for _, _, _, data in path_edges:
            length = float(data.get('length', 50.0))
            total_length += length
            
            w_e_raw = data.get('width')
            if w_e_raw is not None:
                w_e = _parse_osm_float(w_e_raw, 6.5)
                clearance = w_e - self.vehicle.width_m
                if 0 < clearance <= 0.20:
                    narrow_length += length
                    
        return (narrow_length / total_length) * 100.0 if total_length > 0 else 0.0

    def compute_mdef(self, path_edges: List[tuple]) -> float:
        """Missing-Data Exposure Fraction (Percentage)
        Must check the ORIGINAL provenance or raw OSM tag, not the imputed value.
        """
        if not path_edges: return 0.0
        total_length = 0.0
        missing_length = 0.0
        
        for _, _, _, data in path_edges:
            length = float(data.get('length', 50.0))
            total_length += length
            
            # Check if the width was actually measured or if it came from raw OSM tag
            is_inferred = data.get('width_source') == 'inferred' or 'width' not in data
            has_original_tag = not is_inferred
            
            if not has_original_tag:
                missing_length += length
                
        return (missing_length / total_length) * 100.0 if total_length > 0 else 0.0

    def compute_trr(self, G, path_nodes: List[int], path_edges: List[tuple], median_eta: float) -> float:
        """Tail-Risk Ratio (CVaR-90 / Median ETA)"""
        if not path_nodes or not path_edges or median_eta <= 0:
            return 1.0
            
        # Using existing CVaR optimizer to calculate CVaR at tau=0.90
        cvar_result = compute_catastrophic_cvar(
            path_edges, self.vehicle,
            num_scenarios=50, tau=0.90
        )
        cvar_90 = cvar_result['cvar_90_sec']
        return float(cvar_90) / median_eta

    def compute_ettp(self, route_time: float, baseline_b0_time: float) -> float:
        """Excess Travel Time Penalty (Percentage)"""
        if baseline_b0_time <= 0:
            return 0.0
        return ((route_time - baseline_b0_time) / baseline_b0_time) * 100.0

    def compute_min_clearance(self, path_edges: List[tuple]) -> float:
        """Absolute minimum lateral clearance across the route."""
        if not path_edges: return 0.0
        min_c = float('inf')
        for _, _, _, data in path_edges:
            w_e_raw = data.get('width')
            if w_e_raw is not None:
                w_e = _parse_osm_float(w_e_raw, 6.5)
            else:
                w_e = 6.5  # fallback assumption for untagged when forced
            clearance = max(w_e - self.vehicle.width_m, -0.5) # Allow slightly negative
            if clearance < min_c:
                min_c = clearance
        return float(min_c) if min_c != float('inf') else 2.0

    def evaluate_route(self, G, path_nodes: List[int], path_edges: List[tuple], 
                       median_eta: float, baseline_b0_time: float) -> Dict[str, float]:
        """Runs all metrics on a given route."""
        return {
            'ISER_%': round(self.compute_iser(path_edges), 2),
            'CNME_%': round(self.compute_cnme(path_edges), 2),
            'MDEF_%': round(self.compute_mdef(path_edges), 2),
            'TRR': round(self.compute_trr(G, path_nodes, path_edges, median_eta), 2),
            'ETTP_%': round(self.compute_ettp(median_eta, baseline_b0_time), 2),
            'MinClearance_m': round(self.compute_min_clearance(path_edges), 2)
        }
