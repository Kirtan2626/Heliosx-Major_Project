import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.weather_service import WeatherService
from src.models import CoordinatesRequest, UnifiedEnvironmentalPayload
from datetime import datetime

@pytest.mark.asyncio
async def test_fetch_weather_happy_path():
    service = WeatherService()
    req = CoordinatesRequest(lat=28.61, lon=77.21)
    
    mock_response_data = {
        "current": {
            "temperature_2m": 25.5,
            "relative_humidity_2m": 60,
            "wind_speed_10m": 5.2,
            "cloud_cover": 20
        }
    }
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        payload = await service.get_weather(req)
        
        assert payload.temperatureC == 25.5
        assert payload.humidityPercent == 60
        assert payload.windSpeed == 5.2
        assert payload.cloudCoverPercent == 20
        assert payload.source == "Open-Meteo"
        assert isinstance(payload.fetchedAt, datetime)

@pytest.mark.asyncio
async def test_fetch_weather_fallback_on_error():
    service = WeatherService()
    req = CoordinatesRequest(lat=28.61, lon=77.21)
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")
        
        payload = await service.get_weather(req)
        
        assert payload.source == "Fallback"
        assert payload.temperatureC == 35.0
        assert isinstance(payload.fetchedAt, datetime)

@pytest.mark.asyncio
async def test_fetch_weather_cache_usage():
    service = WeatherService()
    req = CoordinatesRequest(lat=28.61, lon=77.21)
    
    mock_response_data = {
        "current": {
            "temperature_2m": 25.5,
            "relative_humidity_2m": 60,
            "wind_speed_10m": 5.2,
            "cloud_cover": 20
        }
    }
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        # First call - should hit mock
        payload1 = await service.get_weather(req)
        assert mock_get.call_count == 1
        
        # Second call - should hit cache
        payload2 = await service.get_weather(req)
        assert mock_get.call_count == 1
        assert payload1 is payload2
