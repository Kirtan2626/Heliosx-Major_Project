import pytest
from src.heliosx_sim_server import run_simulation

def test_run_simulation_basic():
    lat, lon = 28.61, 77.23 # New Delhi
    weather = {
        "temperatureC": 30.0,
        "cloudCoverPercent": 10.0,
        "windSpeed": 5.0
    }
    context = {
        "buildings": [
            {"tags": {"height": "15"}}
        ]
    }
    
    result = run_simulation(lat, lon, weather, context)
    
    assert "daily_totals" in result
    assert "timeseries" in result
    assert len(result["timeseries"]) == 48
    
    totals = result["daily_totals"]
    assert totals["fixed_wh"] >= 0
    assert totals["tracker_wh"] >= 0
    assert totals["ai_wh"] >= 0
    
    # Check a few timeseries entries
    for entry in result["timeseries"]:
        assert "time" in entry
        assert "sun_alt" in entry
        assert "shadow" in entry
        assert "action" in entry
        assert "energy_ai" in entry
        assert "energy_tracker" in entry
        assert "temp_c" in entry
        assert "dni" in entry
        assert "aqi" in entry
        assert "wind_speed" in entry

    assert "faults" in result
    assert "commercial_impact" in result

if __name__ == "__main__":
    # Manual run
    lat, lon = 28.61, 77.23
    weather = {
        "temperatureC": 30.0,
        "cloudCoverPercent": 10.0,
        "windSpeed": 5.0
    }
    context = {
        "buildings": [
            {"tags": {"height": "15"}}
        ]
    }
    res = run_simulation(lat, lon, weather, context)
    print(f"Daily Totals: {res['daily_totals']}")
    print(f"First 3 steps: {res['timeseries'][:3]}")
