from fastapi.testclient import TestClient
import pytest
from src.serve_dashboard import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_weather_endpoint(client):
    response = client.get("/weather?lat=28.61&lon=77.21")
    assert response.status_code == 200
    data = response.json()
    assert "temperatureC" in data

def test_context_endpoint(client):
    response = client.get("/site-context?lat=28.61&lon=77.21")
    assert response.status_code == 200
    data = response.json()
    assert "buildings" in data

def test_validation_error(client):
    # Latitude out of range
    response = client.get("/weather?lat=100&lon=77.21")
    assert response.status_code == 422
    
    # Longitude out of range
    response = client.get("/weather?lat=28.61&lon=200")
    assert response.status_code == 422

def test_simulate_endpoint(client):
    response = client.post("/simulate?lat=28.61&lon=77.21&tariff=0.25")
    assert response.status_code == 200
    data = response.json()
    assert "daily_totals" in data
    assert "faults" in data
    assert "commercial_impact" in data
    assert data["commercial_impact"]["financial_loss_usd"] >= 0

def test_export_matlab_endpoint(client):
    # First get simulation data
    sim_resp = client.post("/simulate?lat=28.61&lon=77.21")
    sim_data = sim_resp.json()
    
    # Then test export
    response = client.post("/export-matlab", json=sim_data)
    assert response.status_code == 200
    data = response.json()
    assert "Metadata" in data
    assert "Environment" in data
    assert "PhysicsResults" in data
    assert "AILog" in data
    assert data["Metadata"]["coords"] == [28.61, 77.21]
