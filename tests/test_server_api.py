import pytest
from fastapi.testclient import TestClient
from src.api.server import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "RoadFit-X" in data.get("message", "")

def test_brain_status_endpoint(client):
    response = client.get("/brain/status")
    assert response.status_code == 200
    data = response.json()
    assert "episodic" in data
    assert "semantic" in data
    assert "working" in data
    assert "total_experiences" in data["episodic"]
    assert "trained" in data["semantic"]
    assert "active_hazards_count" in data["working"]

def test_roadblock_endpoint(client):
    payload = {
        "lat": 12.9345,
        "lon": 77.6220,
        "severity": 0.9
    }
    response = client.post("/brain/roadblock", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Working Memory" in data.get("message", "")

def test_route_plan_same_node_error(client):
    payload = {
        "orig_lat": 12.9345,
        "orig_lon": 77.6220,
        "dest_lat": 12.9345,
        "dest_lon": 77.6220
    }
    response = client.post("/route/plan", json=payload)
    assert response.status_code == 400
    assert "same node" in response.json().get("detail", "").lower()

def test_route_plan_valid_trip(client):
    payload = {
        "orig_lat": 12.9345,
        "orig_lon": 77.6220,
        "dest_lat": 12.9416,
        "dest_lon": 77.6285,
        "vehicle_width": 1.8,
        "vehicle_height": 1.6,
        "vehicle_weight": 1.2,
        "rain_level": "none",
        "traffic_level": "normal",
        "unknown_data_policy": "exploratory"
    }
    response = client.post("/route/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "selected_route" in data
    assert "baseline_route" in data
    sr = data["selected_route"]
    assert "geometry" in sr
    assert "eta_p50_min" in sr
    assert "academic_metrics" in sr
    assert "completion_probability" in sr
    metrics = sr["academic_metrics"]
    assert "ISER_%" in metrics
    assert "TRR" in metrics
