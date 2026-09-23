"""
RoadFit-X: Vehicle Digital Twin
Defines a comprehensive physical-operational profile for routing vehicles.
"""
from typing import List, Literal
from pydantic import BaseModel

class VehicleDigitalTwin(BaseModel):
    vehicle_type: str
    width_m: float
    height_m: float
    gross_weight_t: float
    axle_load_t: float
    wheelbase_m: float
    turning_radius_m: float
    ground_clearance_m: float
    max_grade_pct: float
    surface_tolerance: List[str]
    rain_tolerance: Literal["low", "medium", "high"]
    risk_preference: Literal["aggressive", "moderate", "conservative"]
    unknown_data_policy: Literal["strict", "conservative", "exploratory"] = "conservative"

    def __str__(self):
        return f"{self.vehicle_type} (W:{self.width_m}m, H:{self.height_m}m, Wgt:{self.gross_weight_t}t)"
