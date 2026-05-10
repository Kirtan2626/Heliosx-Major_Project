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

class TimeSeriesEntry(BaseModel):
    time: str
    sun_alt: float
    shadow: float
    action: str
    energy_ai: float
    energy_tracker: float
    temp_c: float
    dni: float
    aqi: float
    wind_speed: float

class DailyTotals(BaseModel):
    fixed_wh: float
    tracker_wh: float
    ai_wh: float

class CommercialImpact(BaseModel):
    kwh_loss: float
    financial_loss_usd: float
    urgency: str

class FaultEntry(BaseModel):
    type: str
    severity: str
    message: str

class ObstacleEntry(BaseModel):
    type: str
    z_height: float
    polygon: Optional[list[tuple[float, float]]] = None
    point: Optional[tuple[float, float]] = None
    radius: Optional[float] = None

class SimulationResult(BaseModel):
    lat: float
    lon: float
    daily_totals: DailyTotals
    timeseries: list[TimeSeriesEntry]
    faults: list[FaultEntry]
    commercial_impact: CommercialImpact
    obstacles: list[ObstacleEntry]
