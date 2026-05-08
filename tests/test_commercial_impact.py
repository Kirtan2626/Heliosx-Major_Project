import pytest
from src.services.commercial_impact import calculate_impact, MaintenanceUrgency

def test_high_impact():
    # Loss of 100kWh at $0.15/kWh = $15.0
    impact = calculate_impact(wh_loss=100000, tariff=0.15)
    assert impact["financial_loss_usd"] == 15.0
    assert impact["urgency"] == MaintenanceUrgency.CRITICAL.value

def test_boundary_high():
    # $10.0 boundary
    impact = calculate_impact(wh_loss=100000, tariff=0.10)
    assert impact["financial_loss_usd"] == 10.0
    assert impact["urgency"] == MaintenanceUrgency.CRITICAL.value

def test_boundary_low():
    # $1.0 boundary
    impact = calculate_impact(wh_loss=10000, tariff=0.10)
    assert impact["financial_loss_usd"] == 1.0
    assert impact["urgency"] == MaintenanceUrgency.MONITOR.value

def test_healthy_impact():
    impact = calculate_impact(wh_loss=10, tariff=0.15)
    assert impact["urgency"] == MaintenanceUrgency.HEALTHY.value

def test_zero_loss():
    impact = calculate_impact(wh_loss=0, tariff=0.15)
    assert impact["financial_loss_usd"] == 0.0
    assert impact["urgency"] == MaintenanceUrgency.HEALTHY.value

def test_negative_wh_loss():
    with pytest.raises(ValueError, match="wh_loss cannot be negative"):
        calculate_impact(wh_loss=-1, tariff=0.15)

def test_negative_tariff():
    with pytest.raises(ValueError, match="tariff cannot be negative"):
        calculate_impact(wh_loss=100, tariff=-0.1)
