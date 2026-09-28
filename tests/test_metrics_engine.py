import pytest
import networkx as nx
from src.vehicle.vehicle_digital_twin import VehicleDigitalTwin
from src.evaluation.metrics_engine import MetricsEngine

@pytest.fixture
def test_vehicle():
    return VehicleDigitalTwin(
        vehicle_type="hatchback",
        width_m=1.8,
        height_m=1.5,
        gross_weight_t=1.2,
        axle_load_t=0.6,
        wheelbase_m=2.5,
        turning_radius_m=5.0,
        ground_clearance_m=0.17,
        max_grade_pct=15.0,
        surface_tolerance=["asphalt", "concrete"],
        rain_tolerance="medium",
        risk_preference="moderate",
        unknown_data_policy="exploratory"
    )

def test_iser_calculation(test_vehicle):
    engine = MetricsEngine(test_vehicle)
    # Edge 1: width 2.5m (ok, > 1.8m), length 100m
    # Edge 2: width 1.5m (violation, < 1.8m), length 100m
    edges = [
        (0, 1, 0, {"length": 100.0, "width": "2.5"}),
        (1, 2, 0, {"length": 100.0, "width": "1.5"})
    ]
    iser = engine.compute_iser(edges)
    # 100m violation out of 200m total = 50.0%
    assert iser == 50.0

def test_cnme_calculation(test_vehicle):
    engine = MetricsEngine(test_vehicle)
    # Vehicle width = 1.8m. Critical margin: 0 < clearance <= 0.20m, i.e., width in (1.8, 2.0]
    # Edge 1: width 1.9m -> clearance = 0.1m (critical margin!), length 100m
    # Edge 2: width 3.0m -> clearance = 1.2m (safe), length 100m
    edges = [
        (0, 1, 0, {"length": 100.0, "width": "1.9"}),
        (1, 2, 0, {"length": 100.0, "width": "3.0"})
    ]
    cnme = engine.compute_cnme(edges)
    # 100m out of 200m = 50.0%
    assert cnme == 50.0

def test_mdef_calculation(test_vehicle):
    engine = MetricsEngine(test_vehicle)
    # Edge 1: has measured width, length 100m
    # Edge 2: has inferred width ('width_source': 'inferred'), length 100m
    edges = [
        (0, 1, 0, {"length": 100.0, "width": "3.5"}),
        (1, 2, 0, {"length": 100.0, "width": "3.5", "width_source": "inferred"})
    ]
    mdef = engine.compute_mdef(edges)
    assert mdef == 50.0

def test_ettp_calculation(test_vehicle):
    engine = MetricsEngine(test_vehicle)
    # Route time 120s, baseline time 100s -> +20% excess
    ettp = engine.compute_ettp(120.0, 100.0)
    assert round(ettp, 1) == 20.0

def test_min_clearance(test_vehicle):
    engine = MetricsEngine(test_vehicle)
    # Vehicle width = 1.8m
    # Edge 1: width 3.0m -> clearance 1.2m
    # Edge 2: width 2.2m -> clearance 0.4m
    edges = [
        (0, 1, 0, {"length": 100.0, "width": "3.0"}),
        (1, 2, 0, {"length": 100.0, "width": "2.2"})
    ]
    min_c = engine.compute_min_clearance(edges)
    assert round(min_c, 2) == 0.40
