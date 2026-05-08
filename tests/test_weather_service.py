import pytest
import asyncio
from src.weather_service import WeatherService
from src.models import CoordinatesRequest

@pytest.mark.asyncio
async def test_fetch_weather_default():
    service = WeatherService()
    req = CoordinatesRequest(lat=28.61, lon=77.21)
    
    # Force error to test fallback
    service._fail_next = True
    
    payload = await service.get_weather(req)
    assert payload.temperatureC == 35.0 # safe physics default
    assert payload.windSpeed == 3.0
    assert payload.cloudCoverPercent == 0.0
