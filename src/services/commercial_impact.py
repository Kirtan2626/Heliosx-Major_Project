def calculate_impact(wh_loss: float, tariff: float) -> dict:
    kwh_loss = wh_loss / 1000.0
    financial_loss = kwh_loss * tariff
    
    if financial_loss > 10.0:
        urgency = "Schedule within 48 hours"
    elif financial_loss > 1.0:
        urgency = "Monitor performance"
    else:
        urgency = "System Healthy"
        
    return {
        "kwh_loss": round(kwh_loss, 4),
        "financial_loss_usd": round(financial_loss, 2),
        "urgency": urgency
    }
