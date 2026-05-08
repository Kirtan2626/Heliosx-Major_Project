from enum import Enum
from typing import Dict, Union

class MaintenanceUrgency(Enum):
    """Enumeration of maintenance urgency levels."""
    CRITICAL = "Schedule within 48 hours"
    MONITOR = "Monitor performance"
    HEALTHY = "System Healthy"

# Constants for impact calculation
HIGH_IMPACT_THRESHOLD = 10.0
LOW_IMPACT_THRESHOLD = 1.0
WH_TO_KWH_DIVISOR = 1000.0

def calculate_impact(wh_loss: float, tariff: float) -> Dict[str, Union[float, str]]:
    """
    Calculates the commercial impact of energy loss.

    Args:
        wh_loss: Energy loss in Watt-hours. Must be non-negative.
        tariff: Energy tariff in USD/kWh. Must be non-negative.

    Returns:
        A dictionary containing:
            - kwh_loss: Loss converted to kilowatt-hours.
            - financial_loss_usd: Loss in USD.
            - urgency: Maintenance urgency as a string.

    Raises:
        ValueError: If wh_loss or tariff are negative.
    """
    if wh_loss < 0:
        raise ValueError("wh_loss cannot be negative")
    if tariff < 0:
        raise ValueError("tariff cannot be negative")

    kwh_loss = wh_loss / WH_TO_KWH_DIVISOR
    financial_loss = kwh_loss * tariff
    
    if financial_loss >= HIGH_IMPACT_THRESHOLD:
        urgency = MaintenanceUrgency.CRITICAL.value
    elif financial_loss >= LOW_IMPACT_THRESHOLD:
        urgency = MaintenanceUrgency.MONITOR.value
    else:
        urgency = MaintenanceUrgency.HEALTHY.value
        
    return {
        "kwh_loss": round(kwh_loss, 4),
        "financial_loss_usd": round(financial_loss, 2),
        "urgency": urgency
    }
