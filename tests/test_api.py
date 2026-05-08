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
