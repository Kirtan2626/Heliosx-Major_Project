import pytest
from src.physics_engine.fault_diagnosis import classify_faults

def test_thermal_fault():
    # Simulate high temp, AI yield < Tracker yield
    # Needs > 4 occurrences for medium severity
    results = [
        {"temp_c": 55.0, "energy_tracker": 100.0, "energy_ai": 90.0, "sun_alt": 45.0, "aqi": 20}
    ] * 5
    faults = classify_faults(results)
    assert any(f["type"] == "thermal_derating" for f in faults)

def test_soiling_fault():
    # Simulate high AQI, low wind, significant loss
    # Needs > 8 occurrences for high severity
    results = [
        {"temp_c": 25.0, "energy_tracker": 100.0, "energy_ai": 85.0, "sun_alt": 45.0, "aqi": 300, "wind_speed": 1.0}
    ] * 9
    faults = classify_faults(results)
    assert any(f["type"] == "dust_soiling" for f in faults)

def test_shading_fault():
    # Simulate low sun alt (< 20) and high loss (> 30%)
    results = [
        {"temp_c": 25.0, "energy_tracker": 100.0, "energy_ai": 60.0, "sun_alt": 15.0, "aqi": 20}
    ]
    faults = classify_faults(results)
    assert any(f["type"] == "shading_anomaly" for f in faults)

def test_empty_results():
    # Ensure empty input returns empty list and doesn't crash
    assert classify_faults([]) == []

def test_negative_loss():
    # Ensure negative loss (AI > Tracker) doesn't trigger faults
    results = [
        {"temp_c": 55.0, "energy_tracker": 100.0, "energy_ai": 110.0, "sun_alt": 45.0, "aqi": 20}
    ] * 10
    faults = classify_faults(results)
    assert faults == []
