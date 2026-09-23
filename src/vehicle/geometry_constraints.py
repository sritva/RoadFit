"""
RoadFit-X: Geometry Constraints
Calculates compatibility margins (e.g., clearance buffers) between a vehicle and a road edge.
Robust OSM tag parsing - handles strings like "3.5 m", "3 4", None, lists, etc.
"""
import re
from typing import Dict, Any
from .vehicle_digital_twin import VehicleDigitalTwin


def _parse_osm_float(value, default: float) -> float:
    """Safely parse OSM numeric tags which can be messy strings."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    # Handle string values: strip units, take first numeric token
    s = str(value).strip().lower()
    # Remove units like 'm', 't', 'tons', 'ft'
    s = re.sub(r'[a-zA-Z\'\"]+', ' ', s).strip()
    # If there are multiple numbers (e.g. "3 4"), take the min for safety
    nums = re.findall(r'\d+\.?\d*', s)
    if not nums:
        return default
    return min(float(n) for n in nums)


def compute_geometry_margins(edge_data: Dict[str, Any], vehicle: VehicleDigitalTwin) -> Dict[str, float]:
    """
    Computes physical clearance margins. A negative margin implies a hard physical block.
    Uses safe OSM parsing with an explicit missing data policy.
    If a critical attribute is missing and the policy forbids it, the margin is returned as None,
    indicating an unverified/infeasible state.
    """
    margins = {}
    policy = getattr(vehicle, 'unknown_data_policy', 'conservative')

    # --- Width ---
    raw_width = edge_data.get('width')
    if raw_width is None:
        if policy == "strict":
            margins['width_clearance_m'] = None # Explicitly unknown/forbidden
        elif policy == "conservative":
            margins['width_clearance_m'] = None # Defer to traversability model for uncertainty check
        else: # exploratory
            margins['width_clearance_m'] = 6.5 - vehicle.width_m
    else:
        margins['width_clearance_m'] = _parse_osm_float(raw_width, 6.5) - vehicle.width_m

    # --- Height ---
    raw_height = edge_data.get('maxheight')
    if raw_height is None:
        if policy == "strict":
            margins['height_clearance_m'] = None
        elif policy == "conservative":
            margins['height_clearance_m'] = None
        else: # exploratory
            margins['height_clearance_m'] = 4.5 - vehicle.height_m
    else:
        margins['height_clearance_m'] = _parse_osm_float(raw_height, 4.5) - vehicle.height_m

    # --- Weight ---
    raw_weight = edge_data.get('maxweight', edge_data.get('max_weight'))
    highway_type = edge_data.get('highway', 'residential')
    default_weight = 20.0 if highway_type in ('motorway', 'trunk', 'primary') else 10.0
    
    if raw_weight is None:
        if policy == "strict":
            margins['weight_margin_t'] = None
        elif policy == "conservative":
            margins['weight_margin_t'] = None
        else: # exploratory
            margins['weight_margin_t'] = default_weight - vehicle.gross_weight_t
    else:
        margins['weight_margin_t'] = _parse_osm_float(raw_weight, default_weight) - vehicle.gross_weight_t

    # Turn radius: approximated by road category
    highway_radii = {
        'motorway': 50.0, 'trunk': 40.0, 'primary': 30.0,
        'secondary': 20.0, 'tertiary': 15.0, 'residential': 10.0, 'service': 8.0
    }
    road_radius = highway_radii.get(str(highway_type), 12.0)
    margins['turning_radius_margin_m'] = road_radius - vehicle.turning_radius_m

    return margins
