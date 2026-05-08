from src.services.commercial_impact import calculate_impact

def test_high_impact():
    # Loss of 100kWh (huge) at $0.15/kWh
    impact = calculate_impact(wh_loss=100000, tariff=0.15)
    assert impact["financial_loss_usd"] == 15.0
    assert "Schedule within 48 hours" in impact["urgency"]

def test_healthy_impact():
    impact = calculate_impact(wh_loss=10, tariff=0.15)
    assert impact["urgency"] == "System Healthy"
