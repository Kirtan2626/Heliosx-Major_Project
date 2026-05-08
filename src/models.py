from pydantic import BaseModel
from typing import Optional

class CoordinatesRequest(BaseModel):
    lat: float
    lon: float

class UnifiedEnvironmentalPayload(BaseModel):
    temperatureC: float
    roundedTemperatureC: int
    humidityPercent: float
    windSpeed: float
    windSpeedUnit: str = "m/s"
    cloudCoverPercent: float
    source: str
    sourceLabel: str
    fetchedAt: str
