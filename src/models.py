from pydantic import BaseModel, Field
from typing import Optional, Annotated
from datetime import datetime
from fastapi import Query

# Validated coordinates types for reuse
LatQuery = Annotated[float, Query(description="Latitude (-90 to 90)", ge=-90, le=90)]
LonQuery = Annotated[float, Query(description="Longitude (-180 to 180)", ge=-180, le=180)]

class CoordinatesRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

class UnifiedEnvironmentalPayload(BaseModel):
    temperatureC: float
    roundedTemperatureC: int
    humidityPercent: float
    windSpeed: float
    windSpeedUnit: str = "m/s"
    cloudCoverPercent: float
    source: str
    sourceLabel: str
    fetchedAt: datetime
